"""
Lógica de negócio principal - processamento de recibos e envio de emails.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.conta_azul_client import ContaAzulClient
from app.crypto import get_crypto_manager
from app.database import (
    AzulAccount,
    EmailLog,
    OAuthToken,
    PollingCheckpoint,
    SentReceipt,
)
from app.logging import setup_logging
from app.services.mailer import MailerService

logger = setup_logging(__name__)


class DoctorFallbackResolver:
    """Resolve email do médico via fallback configurável."""

    def __init__(self, fallback_json: str):
        """
        Inicializa com mapeamento de fallback.

        Args:
            fallback_json: JSON com mapping {nome_cliente -> email}
        """
        try:
            self.mapping = json.loads(fallback_json) if fallback_json else {}
        except json.JSONDecodeError:
            logger.warning("Fallback JSON inválido, usando mapping vazio")
            self.mapping = {}

    def resolve(
        self,
        customer_name: Optional[str],
        fallback_email: Optional[str],
    ) -> Optional[str]:
        """
        Resolve email do médico.

        Args:
            customer_name: Nome do cliente
            fallback_email: Email de fallback padrão

        Returns:
            Email do médico ou None
        """
        # 1. Tentar buscar via nome do cliente
        if customer_name and customer_name in self.mapping:
            email = self.mapping[customer_name]
            logger.info(f"Email do médico resolvido via mapping: {customer_name}")
            return email

        # 2. Usar fallback fornecido
        if fallback_email:
            logger.info(f"Usando email de fallback: {fallback_email}")
            return fallback_email

        logger.warning(f"Não foi possível resolver email para {customer_name}")
        return None


class PaymentProcessor:
    """Processa pagamentos recebidos da Conta Azul."""

    def __init__(self, db: Session, fallback_json: str):
        """
        Inicializa processador.

        Args:
            db: Sessão do banco de dados
            fallback_json: JSON com fallback de emails
        """
        self.db = db
        self.mailer = MailerService()
        self.crypto = get_crypto_manager()
        self.doctor_resolver = DoctorFallbackResolver(fallback_json)

    def get_active_accounts(self) -> List[AzulAccount]:
        """Busca contas ativas no banco."""
        return self.db.query(AzulAccount).filter(AzulAccount.is_active == 1).all()

    def get_oauth_token(self, account_id: str) -> Optional[OAuthToken]:
        """Busca token OAuth criptografado."""
        return (
            self.db.query(OAuthToken)
            .filter(OAuthToken.account_id == account_id)
            .first()
        )

    def get_polling_checkpoint(self, account_id: str) -> Optional[PollingCheckpoint]:
        """Busca último checkpoint de polling."""
        return (
            self.db.query(PollingCheckpoint)
            .filter(PollingCheckpoint.account_id == account_id)
            .first()
        )

    def update_checkpoint(
        self,
        account_id: str,
        last_date: datetime,
        last_id: Optional[str] = None,
    ) -> None:
        """Atualiza checkpoint de polling."""
        checkpoint = self.get_polling_checkpoint(account_id)

        if checkpoint:
            checkpoint.last_processed_date = last_date
            if last_id:
                checkpoint.last_processed_id = last_id
        else:
            checkpoint = PollingCheckpoint(
                account_id=account_id,
                last_processed_date=last_date,
                last_processed_id=last_id,
            )
            self.db.add(checkpoint)

        self.db.commit()
        logger.info(f"Checkpoint atualizado para {account_id}")

    def is_receipt_already_sent(
        self,
        account_id: str,
        installment_id: str,
        attachment_url: str,
    ) -> bool:
        """Verifica idempotência (recibo já enviado?)."""
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

    def log_email_attempt(
        self,
        account_id: str,
        receipt_ref: str,
        doctor_email: str,
        status: str,
        error_msg: Optional[str] = None,
    ) -> None:
        """Log de tentativa de envio."""
        log = EmailLog(
            account_id=account_id,
            receipt_id=receipt_ref,
            doctor_email=doctor_email,
            status=status,
            error_message=error_msg,
        )
        self.db.add(log)
        self.db.commit()

    def process_account(self, account: AzulAccount) -> Tuple[int, int]:
        """
        Processa uma conta: busca recibos novos e envia emails.

        Args:
            account: Conta Azul para processar

        Returns:
            Tupla (recibos_processados, erros)
        """
        logger.info(f"Processando conta: {account.account_id}")

        # 1. Buscar token
        token_record = self.get_oauth_token(account.account_id)
        if not token_record:
            logger.error(f"Sem token OAuth para {account.account_id}")
            return 0, 1

        try:
            access_token = self.crypto.decrypt(token_record.access_token)
        except Exception as e:
            logger.error(f"Erro ao decriptografar token: {e}")
            return 0, 1

        # 2. Buscar checkpoint
        checkpoint = self.get_polling_checkpoint(account.account_id)
        if checkpoint:
            filter_date = checkpoint.last_processed_date.isoformat()
        else:
            # Fallback: últimos 30 dias
            filter_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

        logger.info(f"Filtrando parcelas a partir de: {filter_date}")

        # 3. Buscar parcelas/recibos
        try:
            client = ContaAzulClient(access_token)
            # Nota: adaptar para endpoint real da Conta Azul
            # Este é um exemplo genérico
            installments_response = client.get_installments(filter_date=filter_date)
        except Exception as e:
            logger.error(f"Erro ao buscar parcelas: {e}")
            return 0, 1

        # 4. Processar cada parcela
        processed = 0
        errors = 0

        # Adaptação para resposta real da Conta Azul
        installments = installments_response.get("data", [])

        for installment in installments:
            try:
                result = self._process_installment(
                    account,
                    client,
                    installment,
                )
                if result:
                    processed += 1
                else:
                    errors += 1
            except Exception as e:
                logger.error(f"Erro ao processar parcela: {e}")
                errors += 1

        # 5. Atualizar checkpoint
        if processed > 0:
            latest_date = max(
                [
                    datetime.fromisoformat(inst.get("modifiedDate", filter_date))
                    for inst in installments
                ],
                default=datetime.now(timezone.utc),
            )
            self.update_checkpoint(
                account.account_id,
                latest_date,
                last_id=installments[-1].get("id") if installments else None,
            )

        logger.info(
            f"Conta {account.account_id}: " f"{processed} processados, {errors} erros",
        )
        return processed, errors

    def _process_installment(
        self,
        account: AzulAccount,
        client: ContaAzulClient,
        installment: Dict[str, Any],
    ) -> bool:
        """
        Processa uma parcela individual.

        Args:
            account: Conta Azul
            client: Cliente HTTP
            installment: Dados da parcela

        Returns:
            True se processado com sucesso
        """
        installment_id = installment.get("id")
        status = installment.get("status")

        if not installment_id:
            logger.warning("Parcela sem ID; ignorando")
            return False

        # Filtrar apenas parcelas recebidas/baixadas
        if status not in ["received", "settled", "paid"]:
            logger.debug(f"Ignorando parcela {installment_id} com status {status}")
            return False

        # Buscar recibos/anexos
        try:
            receipt_url = installment.get("receiptUrl")
            if not receipt_url:
                logger.warning(f"Parcela {installment_id} sem URL de recibo")
                return False

            attachment_url = receipt_url
            receipt_id = receipt_url.split("/")[-1]  # Extrair ID da URL

            # Verificar idempotência
            if self.is_receipt_already_sent(
                account.account_id,
                installment_id,
                attachment_url,
            ):
                logger.info(f"Recibo {receipt_id} já enviado, ignorando")
                return False

            # Baixar PDF
            try:
                pdf_content = client.download_attachment(receipt_url)
            except Exception as e:
                logger.error(f"Erro ao baixar PDF: {e}")
                self.log_email_attempt(
                    account.account_id,
                    attachment_url,
                    "unknown",
                    "failed",
                    str(e),
                )
                return False

            # Resolver email do médico
            customer_name = installment.get("customerName")
            doctor_email = self.doctor_resolver.resolve(
                customer_name,
                installment.get("doctorEmail"),
            )

            if not doctor_email:
                logger.warning(
                    f"Não foi possível resolver email para {customer_name}",
                )
                return False

            # Enviar email
            success = self.mailer.send_receipt_email(
                doctor_email=doctor_email,
                customer_name=customer_name or "Cliente",
                amount=float(installment.get("amount", 0)),
                receipt_date=installment.get("receivedDate", ""),
                pdf_content=pdf_content,
                pdf_filename="recibo.pdf",
            )

            if success:
                # Registrar envio (idempotência)
                sent = SentReceipt(
                    account_id=account.account_id,
                    installment_id=installment_id,
                    attachment_url=attachment_url,
                    doctor_email=doctor_email,
                    sent_at=datetime.now(timezone.utc),
                    receipt_hash=None,
                    receipt_metadata={
                        "customer_name": customer_name,
                        "amount": installment.get("amount"),
                        "receipt_id": receipt_id,
                    },
                )
                self.db.add(sent)
                self.db.commit()
                self.log_email_attempt(
                    account.account_id,
                    attachment_url,
                    doctor_email,
                    "sent",
                )
                return True
            else:
                self.log_email_attempt(
                    account.account_id,
                    attachment_url,
                    doctor_email,
                    "failed",
                    "Email service error",
                )
                return False

        except Exception as e:
            logger.error(f"Erro ao processar parcela {installment_id}: {e}")
            return False
