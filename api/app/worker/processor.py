"""
Processador principal de contas a receber.
Orquestra o fluxo: checkpoint → consulta → validação → download → email.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import get_crypto_manager
from app.database import (
    AzulAccount,
    EmailLog,
    FinancialCheckpoint,
    SentReceipt,
)
from app.logging import setup_logging
from app.services.mailer import MailerService
from app.services_auth import ContaAzulAuthService
from app.worker.conta_azul_financial_client import ContaAzulFinancialClient
from app.worker.receipt_downloader import ReceiptDownloader

logger = setup_logging(__name__)


class FinancialProcessor:
    """Processa contas a receber e envia recibos."""

    def __init__(self, db: Session):
        """
        Inicializa processador.

        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.settings = get_settings()
        self.crypto = get_crypto_manager()
        self.mailer = MailerService()

    def get_active_accounts(self) -> List[AzulAccount]:
        """
        Busca contas Azul ativas.

        Returns:
            Lista de contas ativas
        """
        try:
            accounts = (
                self.db.query(AzulAccount).filter(AzulAccount.is_active == 1).all()
            )
            return accounts
        except Exception as e:
            logger.error(f"Erro ao buscar contas ativas: {e}")
            return []

    async def process_account(
        self,
        account: AzulAccount,
    ) -> Tuple[int, int]:
        """
        Processa uma conta: consulta, valida, baixa e envia recibos.

        Args:
            account: Conta Azul

        Returns:
            Tupla (recibos_processados, erros)
        """
        account_id = account.account_id

        # 1. Obter token de acesso
        auth_service = ContaAzulAuthService(self.db)
        token_record = auth_service.get_token(account_id)

        if not token_record:
            logger.error(f"Token não encontrado para {account_id[:10]}...")
            return 0, 1

        try:
            access_token = self.crypto.decrypt(token_record.access_token)
        except Exception as e:
            logger.error(f"Erro ao decriptografar token: {e}")
            return 0, 1

        # 2. Verificar se token expirou
        if auth_service.is_token_expired(token_record):
            logger.warning(f"Token expirado para {account_id[:10]}..., renovando...")
            access_token = await auth_service.refresh_access_token(account_id)
            if not access_token:
                logger.error(f"Falha ao renovar token para {account_id[:10]}...")
                return 0, 1

        # 3. Criar client financeiro
        client = ContaAzulFinancialClient(access_token)
        downloader = ReceiptDownloader(client)

        # 4. Obter checkpoint
        checkpoint = self._get_or_create_checkpoint(account_id)
        changed_since = self._calculate_changed_since(checkpoint)

        logger.info(
            f"Consultando receivables desde {changed_since.isoformat()} "
            f"para {account_id[:10]}..."
        )

        # 5. Buscar receivables alteradas
        try:
            receivables = await client.get_receivables(
                account_id=account_id,
                changed_since=changed_since,
                status="received",  # Apenas recebidas
            )
        except Exception as e:
            logger.error(f"Erro ao buscar receivables: {e}")
            return 0, 1

        if not receivables:
            logger.debug(f"Nenhuma receivable encontrada para {account_id[:10]}...")
            self._update_checkpoint(checkpoint)
            return 0, 0

        # 6. Processar cada receivable
        processed = 0
        errors = 0

        for receivable in receivables:
            try:
                success = await self._process_receivable(
                    account,
                    receivable,
                    client,
                    downloader,
                )

                if success:
                    processed += 1
                else:
                    errors += 1

            except Exception as e:
                logger.error(
                    f"Erro crítico ao processar receivable "
                    f"{receivable.get('id', 'unknown')[:10]}...: {e}",
                    exc_info=True,
                )
                errors += 1

        # 7. Atualizar checkpoint
        self._update_checkpoint(checkpoint)

        return processed, errors

    async def _process_receivable(
        self,
        account: AzulAccount,
        receivable: dict,
        client: ContaAzulFinancialClient,
        downloader: ReceiptDownloader,
    ) -> bool:
        """
        Processa uma receivable individual.

        Args:
            account: Conta Azul
            receivable: Dados da receivable
            client: Cliente HTTP
            downloader: Download manager

        Returns:
            True se sucesso, False se erro
        """
        receivable_id = receivable.get("id")
        if not receivable_id:
            logger.warning("Receivable sem ID; ignorando")
            return False
        receivable_id_short = receivable_id[:10]
        customer_name = receivable.get("customerName", "Cliente")
        amount = receivable.get("totalAmount", 0)
        _payment_date = receivable.get("receivedDate")  # Não usado

        logger.debug(
            f"Processando receivable {receivable_id_short}... "
            f"({customer_name}, R${amount})"
        )

        # Buscar detalhes completos
        try:
            details = await client.get_receivable_details(receivable_id)
        except Exception as e:
            logger.error(f"Erro ao buscar detalhes: {e}")
            return False

        # Extrair installments (parcelas)
        installments = details.get("installments", [])

        if not installments:
            logger.warning(f"Nenhuma parcela encontrada para {receivable_id_short}...")
            return False

        # Processar cada parcela
        for installment in installments:
            try:
                await self._process_installment(
                    account,
                    receivable,
                    installment,
                    customer_name,
                    client,
                    downloader,
                )
            except Exception as e:
                logger.error(f"Erro ao processar parcela: {e}")
                continue

        return True

    async def _process_installment(
        self,
        account: AzulAccount,
        receivable: dict,
        installment: dict,
        customer_name: str,
        client: ContaAzulFinancialClient,
        downloader: ReceiptDownloader,
    ) -> None:
        """
        Processa uma parcela: validação → download → email.

        Args:
            account: Conta Azul
            receivable: Dados da receivable
            installment: Dados da parcela
            customer_name: Nome do cliente
            client: Cliente HTTP
            downloader: Download manager
        """
        installment_id = installment.get("id")
        if not installment_id:
            logger.warning("Parcela sem ID; ignorando")
            return
        installment_id_short = installment_id[:10]
        status = installment.get("status")
        payment_id = installment.get("paymentId")
        _amount = installment.get("amount", 0)  # Não usado
        _payment_date = installment.get("paidDate") or datetime.now(
            timezone.utc
        )  # Não usado

        logger.debug(
            f"Processando parcela {installment_id_short}... "
            f"(status={status}, payment_id={payment_id})"
        )

        # Validar que é pagamento/baixa
        if status not in ("received", "paid", "settled"):
            logger.debug(f"Parcela {installment_id_short}... não está recebida")
            return

        # Buscar detalhes da parcela
        try:
            inst_details = await client.get_installment_details(installment_id)
        except Exception as e:
            logger.error(f"Erro ao buscar detalhes da parcela: {e}")
            return

        # Extrair anexos/recibos
        attachments = inst_details.get("attachments", [])

        if not attachments:
            logger.debug(
                f"Nenhum anexo encontrado para parcela {installment_id_short}..."
            )
            return

        # Processar cada anexo
        for attachment in attachments:
            try:
                await self._process_attachment(
                    account,
                    receivable,
                    installment,
                    attachment,
                    customer_name,
                    client,
                    downloader,
                )
            except Exception as e:
                logger.error(f"Erro ao processar anexo: {e}")
                continue

    async def _process_attachment(
        self,
        account: AzulAccount,
        receivable: dict,
        installment: dict,
        attachment: dict,
        customer_name: str,
        client: ContaAzulFinancialClient,
        downloader: ReceiptDownloader,
    ) -> None:
        """
        Processa um anexo: validação → idempotência → download → email.

        Args:
            account: Conta Azul
            receivable: Dados da receivable
            installment: Dados da parcela
            attachment: Dados do anexo
            customer_name: Nome do cliente
            client: Cliente HTTP
            downloader: Download manager
        """
        installment_id = installment.get("id")
        attachment_id = attachment.get("id")
        attachment_url = attachment.get("url")

        if not installment_id or not attachment_id:
            logger.warning("Anexo ou parcela sem ID; ignorando")
            return

        attachment_id_short = attachment_id[:10]
        installment_id_short = installment_id[:10]

        logger.debug(
            f"Processando anexo {attachment_id_short}... "
            f"(installment={installment_id_short}...)"
        )

        if not attachment_url:
            logger.warning(f"Nenhuma URL de anexo para {attachment_id_short}...")
            return

        # Verificar idempotência
        if self._is_receipt_already_sent(
            account.account_id,
            installment_id,
            attachment_url,
        ):
            logger.debug(
                f"Recibo já enviado anteriormente para "
                f"{installment_id_short}... (idempotência)"
            )
            return

        # Baixar recibo
        result = await downloader.download_receipt(attachment_url)

        if not result:
            logger.error(f"Falha ao baixar recibo de {attachment_url[:50]}...")
            return

        pdf_bytes, filename = result

        # Validar PDF
        if not downloader.validate_receipt(pdf_bytes):
            logger.error(f"PDF inválido para {attachment_id_short}...")
            return

        # Obter hash para deduplicação
        receipt_hash = downloader.get_receipt_hash(pdf_bytes)

        # Resolver email do médico
        doctor_email = self._resolve_doctor_email(
            account.account_id,
            customer_name,
            installment,
        )

        if not doctor_email:
            logger.warning(
                f"Não conseguiu resolver email do médico para {customer_name}"
            )
            return

        # Enviar email
        success = self.mailer.send_receipt_email(
            doctor_email=doctor_email,
            customer_name=customer_name,
            amount=installment.get("amount", 0),
            receipt_date=installment.get("paidDate"),
            pdf_content=pdf_bytes,
            pdf_filename=filename,
            reply_to=self.settings.SMTP_REPLY_TO or None,
        )

        if success:
            # Registrar envio (idempotência)
            self._register_sent_receipt(
                account.account_id,
                installment_id,
                attachment_url,
                doctor_email,
                receipt_hash,
                {
                    "customer_name": customer_name,
                    "amount": installment.get("amount"),
                    "payment_date": installment.get("paidDate"),
                },
            )

            # Log de sucesso
            self._log_email_sent(
                account.account_id,
                attachment_id,
                doctor_email,
            )

            logger.info(
                f"✓ Recibo enviado com sucesso para {doctor_email} "
                f"(parcela {installment_id_short}...)"
            )
        else:
            logger.error(f"Falha ao enviar email para {doctor_email}")
            self._log_email_failed(
                account.account_id,
                attachment_id,
                doctor_email,
                "Falha ao enviar email",
            )

    def _get_or_create_checkpoint(
        self,
        account_id: str,
    ) -> FinancialCheckpoint:
        """Obter ou criar checkpoint."""
        checkpoint = (
            self.db.query(FinancialCheckpoint)
            .filter(FinancialCheckpoint.account_id == account_id)
            .first()
        )

        if not checkpoint:
            # Criar novo com janela de segurança
            default_date = datetime.now(timezone.utc) - timedelta(days=30)

            checkpoint = FinancialCheckpoint(
                account_id=account_id,
                last_processed_changed_at=default_date,
            )
            self.db.add(checkpoint)
            self.db.commit()

        return checkpoint

    def _calculate_changed_since(
        self,
        checkpoint: FinancialCheckpoint,
    ) -> datetime:
        """Calcular data desde com janela de segurança."""
        if not checkpoint.last_processed_changed_at:
            return datetime.now(timezone.utc) - timedelta(days=30)

        # Aplicar janela de segurança (voltar N minutos)
        safety_window = timedelta(minutes=self.settings.POLLING_SAFETY_WINDOW_MINUTES)
        return checkpoint.last_processed_changed_at - safety_window

    def _update_checkpoint(self, checkpoint: FinancialCheckpoint) -> None:
        """Atualizar checkpoint com data atual."""
        checkpoint.last_processed_changed_at = datetime.now(timezone.utc)
        self.db.commit()

    def _is_receipt_already_sent(
        self,
        account_id: str,
        installment_id: str,
        attachment_url: str,
    ) -> bool:
        """Verificar idempotência: já foi enviado?"""
        try:
            existing = (
                self.db.query(SentReceipt)
                .filter(
                    SentReceipt.account_id == account_id,
                    SentReceipt.installment_id == installment_id,
                    SentReceipt.attachment_url == attachment_url,
                )
                .first()
            )

            return existing is not None

        except Exception as e:
            logger.error(f"Erro ao verificar idempotência: {e}")
            return False

    def _register_sent_receipt(
        self,
        account_id: str,
        installment_id: str,
        attachment_url: str,
        doctor_email: str,
        receipt_hash: str,
        metadata: dict,
    ) -> None:
        """Registrar envio bem-sucedido."""
        try:
            sent_receipt = SentReceipt(
                account_id=account_id,
                installment_id=installment_id,
                attachment_url=attachment_url,
                doctor_email=doctor_email,
                sent_at=datetime.now(timezone.utc),
                receipt_hash=receipt_hash,
                receipt_metadata=metadata,
            )

            self.db.add(sent_receipt)
            self.db.commit()

            logger.debug(f"Registro de envio criado para {installment_id[:10]}...")

        except Exception as e:
            logger.error(f"Erro ao registrar envio: {e}")
            self.db.rollback()

    def _log_email_sent(
        self,
        account_id: str,
        attachment_id: str,
        doctor_email: str,
    ) -> None:
        """Logar envio bem-sucedido."""
        try:
            log = EmailLog(
                account_id=account_id,
                receipt_id=attachment_id,
                doctor_email=doctor_email,
                status="sent",
                created_at=datetime.now(timezone.utc),
            )

            self.db.add(log)
            self.db.commit()

        except Exception as e:
            logger.error(f"Erro ao logar envio: {e}")
            self.db.rollback()

    def _log_email_failed(
        self,
        account_id: str,
        attachment_id: str,
        doctor_email: str,
        error_message: str,
    ) -> None:
        """Logar falha."""
        try:
            log = EmailLog(
                account_id=account_id,
                receipt_id=attachment_id,
                doctor_email=doctor_email,
                status="failed",
                error_message=error_message,
                created_at=datetime.now(timezone.utc),
            )

            self.db.add(log)
            self.db.commit()

        except Exception as e:
            logger.error(f"Erro ao logar falha: {e}")
            self.db.rollback()

    def _resolve_doctor_email(
        self,
        account_id: str,
        customer_name: str,
        installment: dict,
    ) -> Optional[str]:
        """
        Resolver email do médico.

        Precedência:
        1. Campo doctorEmail do installment
        2. Fallback mapping local
        3. None
        """
        # Tentar field do installment
        doctor_email = installment.get("doctorEmail")
        if doctor_email:
            logger.debug(f"Email do installment: {doctor_email}")
            return doctor_email

        # Tentar fallback mapping
        if hasattr(self.settings, "DOCTORS_FALLBACK_JSON"):
            try:
                import json

                fallback_map = json.loads(self.settings.DOCTORS_FALLBACK_JSON or "{}")
                doctor_email = fallback_map.get(customer_name)
                if doctor_email:
                    logger.debug(f"Email do fallback: {doctor_email}")
                    return doctor_email
            except Exception as e:
                logger.debug(f"Erro ao carregar fallback: {e}")

        logger.warning(f"Não conseguiu resolver email para {customer_name}")
        return None
