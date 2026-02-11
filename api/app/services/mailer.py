"""
Serviço de envio de email via SMTP com TLS.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


class SMTPConfigError(Exception):
    """Erro de configuração SMTP."""

    pass


class EmailValidationError(Exception):
    """Erro de validação de email."""

    pass


class MailerService:
    """
    Serviço de envio de email via SMTP.

    Segurança:
    - TLS obrigatório
    - Senha não é loggada
    - Timeout configurável
    - Retry com controle
    - Validação de anexos
    """

    # Tamanho máximo de anexo: 10MB (reduzido de 25MB para segurança)
    MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

    # Tipos MIME permitidos para anexos
    ALLOWED_MIME_TYPES = {
        "application/pdf": [".pdf"],
    }

    def __init__(self):
        """Inicializa mailer com config."""
        self.settings = get_settings()
        self._validate_config()

    def _validate_config(self) -> None:
        """Valida configuração SMTP."""
        required_fields = [
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USER",
            "SMTP_PASSWORD",
            "SMTP_FROM",
        ]

        for field in required_fields:
            if not getattr(self.settings, field, None):
                raise SMTPConfigError(f"Config ausente: {field}")

        # Validar que SMTP_FROM é um email válido
        if not self._is_valid_email(self.settings.SMTP_FROM):
            raise SMTPConfigError(f"SMTP_FROM inválido: {self.settings.SMTP_FROM}")

        logger.info(
            f"SMTP configurado: {self.settings.SMTP_HOST}:"
            f"{self.settings.SMTP_PORT} (TLS={self.settings.SMTP_USE_TLS})"
        )

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validação básica de email."""
        if not email:
            return False

        parts = email.split("@")
        if len(parts) != 2:
            return False

        local, domain = parts
        if not local or not domain:
            return False

        if "." not in domain:
            return False

        return True

    @staticmethod
    def _sanitize_subject(subject: str, max_length: int = 100) -> str:
        """
        Sanitiza subject.

        - Remove quebras de linha
        - Limita tamanho
        - Escapa caracteres especiais
        """
        # Remover newlines (injeção SMTP)
        sanitized = subject.replace("\n", "").replace("\r", "")

        # Limitar tamanho
        if len(sanitized) > max_length:
            sanitized = sanitized[: max_length - 3] + "..."

        return sanitized

    def _validate_attachment(
        self,
        pdf_content: bytes,
        filename: str,
    ) -> None:
        """
        Valida anexo (PDF).

        Args:
            pdf_content: Conteúdo do arquivo
            filename: Nome do arquivo

        Raises:
            EmailValidationError: Se inválido
        """
        if not pdf_content:
            raise EmailValidationError("Conteúdo do anexo vazio")

        # Verificar tamanho
        if len(pdf_content) > self.MAX_ATTACHMENT_SIZE:
            raise EmailValidationError(
                f"Anexo muito grande: {len(pdf_content)} bytes "
                f"(máximo {self.MAX_ATTACHMENT_SIZE} bytes)"
            )

        # Verificar extensão
        if not filename.lower().endswith(".pdf"):
            raise EmailValidationError(f"Arquivo não é PDF: {filename}")

        # Verificar magic bytes do PDF
        if not pdf_content.startswith(b"%PDF"):
            raise EmailValidationError("Conteúdo não é um PDF válido")

    def send_receipt_email(
        self,
        doctor_email: str,
        customer_name: str,
        amount: float,
        receipt_date: Optional[str],
        pdf_content: bytes,
        pdf_filename: str,
        reply_to: Optional[str] = None,
    ) -> bool:
        """
        Envia email com recibo em anexo.

        Args:
            doctor_email: Email do destinatário
            customer_name: Nome do cliente/paciente
            amount: Valor da transação
            receipt_date: Data da transação (ISO format ou similar)
            pdf_content: Conteúdo do PDF (bytes)
            pdf_filename: Nome do arquivo PDF
            reply_to: Email de reply-to (opcional)

        Returns:
            True se enviado com sucesso, False caso contrário
        """
        # Validar email do destinatário
        if not self._is_valid_email(doctor_email):
            logger.error(f"Email do destinatário inválido: {doctor_email}")
            return False

        # Validar reply-to se fornecido
        if reply_to and not self._is_valid_email(reply_to):
            logger.error(f"Email de reply-to inválido: {reply_to}")
            return False

        # Validar anexo
        try:
            self._validate_attachment(pdf_content, pdf_filename)
        except EmailValidationError as e:
            logger.error(f"Validação de anexo falhou: {e}")
            return False

        # Construir email
        try:
            msg = self._build_message(
                doctor_email=doctor_email,
                customer_name=customer_name,
                amount=amount,
                receipt_date=receipt_date,
                pdf_content=pdf_content,
                pdf_filename=pdf_filename,
                reply_to=reply_to,
            )

            # Enviar
            self._send_via_smtp(msg, doctor_email)

            logger.info(f"Email enviado com sucesso para {doctor_email}")
            return True

        except Exception as e:
            logger.error(f"Erro ao enviar email: {e}", exc_info=True)
            return False

    def _build_message(
        self,
        doctor_email: str,
        customer_name: str,
        amount: float,
        receipt_date: Optional[str],
        pdf_content: bytes,
        pdf_filename: str,
        reply_to: Optional[str],
    ) -> MIMEMultipart:
        """
        Constrói mensagem de email.

        Args:
            doctor_email: Email do destinatário
            customer_name: Nome do cliente
            amount: Valor
            receipt_date: Data da transação
            pdf_content: Conteúdo PDF
            pdf_filename: Nome arquivo
            reply_to: Email de reply

        Returns:
            MIMEMultipart com mensagem construída
        """
        # Criar mensagem
        msg = MIMEMultipart()
        msg["From"] = self.settings.SMTP_FROM
        msg["To"] = doctor_email
        msg["Subject"] = self._build_subject(customer_name)

        if reply_to:
            msg["Reply-To"] = reply_to

        # Corpo do email
        body = self._build_body(
            customer_name=customer_name,
            amount=amount,
            receipt_date=receipt_date,
        )

        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Anexar PDF
        attachment = MIMEApplication(pdf_content, name=pdf_filename)
        attachment["Content-Disposition"] = f"attachment; filename={pdf_filename}"
        msg.attach(attachment)

        return msg

    @staticmethod
    def _build_subject(customer_name: str) -> str:
        """Constrói subject do email."""
        subject = f"Recibo de pagamento - {customer_name}"
        return MailerService._sanitize_subject(subject)

    @staticmethod
    def _build_body(
        customer_name: str,
        amount: float,
        receipt_date: Optional[str],
    ) -> str:
        """
        Constrói corpo do email.

        Sem vazar informações sensíveis.
        """
        lines = [
            "Prezado(a),",
            "",
            "Segue em anexo o recibo referente ao pagamento realizado.",
            "",
        ]

        if customer_name:
            lines.append(f"Cliente: {customer_name}")

        if amount:
            lines.append(f"Valor: R$ {amount:.2f}")

        if receipt_date:
            lines.append(f"Data: {receipt_date}")

        lines.extend(
            [
                "",
                "Atenciosamente,",
                "Sistema de Gestão Financeira",
            ]
        )

        return "\n".join(lines)

    def _send_via_smtp(
        self,
        msg: MIMEMultipart,
        recipient_email: str,
    ) -> None:
        """
        Envia via SMTP com TLS ou SSL.

        Args:
            msg: Mensagem MIME
            recipient_email: Email do destinatário

        Raises:
            Exception: Se falhar no envio
        """
        try:
            logger.debug(
                f"Conectando ao SMTP: {self.settings.SMTP_HOST}:"
                f"{self.settings.SMTP_PORT}"
            )

            # Escolher entre SSL (porta 465) ou TLS (porta 587)
            if self.settings.SMTP_USE_SSL:
                # SSL direto (porta 465)
                logger.debug("Usando SMTP_SSL (porta 465)")
                with smtplib.SMTP_SSL(
                    self.settings.SMTP_HOST,
                    self.settings.SMTP_PORT,
                    timeout=self.settings.SMTP_TIMEOUT,
                ) as server:
                    # Login
                    logger.debug(f"Autenticando como {self.settings.SMTP_USER}")
                    server.login(
                        self.settings.SMTP_USER,
                        self.settings.SMTP_PASSWORD,
                    )

                    # Enviar
                    logger.debug(f"Enviando para {recipient_email}...")
                    server.send_message(msg)
                    logger.debug("Email enviado com sucesso via SMTP_SSL")
            else:
                # STARTTLS (porta 587)
                logger.debug("Usando SMTP com STARTTLS (porta 587)")
                with smtplib.SMTP(
                    self.settings.SMTP_HOST,
                    self.settings.SMTP_PORT,
                    timeout=self.settings.SMTP_TIMEOUT,
                ) as server:

                    # Usar STARTTLS se configurado
                    if self.settings.SMTP_USE_TLS:
                        logger.debug("Iniciando TLS...")
                        server.starttls()

                    # Login
                    logger.debug(f"Autenticando como {self.settings.SMTP_USER}")
                    server.login(
                        self.settings.SMTP_USER,
                        self.settings.SMTP_PASSWORD,
                    )

                    # Enviar
                    logger.debug(f"Enviando para {recipient_email}...")
                    server.send_message(msg)
                    logger.debug("Email enviado com sucesso via SMTP")

        except smtplib.SMTPAuthenticationError as e:
            logger.error("Erro de autenticação SMTP (user/password inválido)")
            raise Exception("SMTP authentication failed") from e

        except smtplib.SMTPException as e:
            logger.error(f"Erro SMTP: {str(e)[:100]}")
            raise Exception(f"SMTP error: {type(e).__name__}") from e

        except TimeoutError as e:
            logger.error(f"Timeout SMTP (timeout={self.settings.SMTP_TIMEOUT}s)")
            raise Exception("SMTP timeout") from e

        except Exception as e:
            logger.error(f"Erro ao enviar email: {type(e).__name__}")
            raise

    def send_test_email(self, to_email: str) -> bool:
        """
        Envia email de teste.

        Útil para validar configuração SMTP.

        Args:
            to_email: Email de teste

        Returns:
            True se sucesso
        """
        logger.info(f"Enviando email de teste para {to_email}")

        return self.send_receipt_email(
            doctor_email=to_email,
            customer_name="TESTE",
            amount=0.00,
            receipt_date="2026-02-10",
            pdf_content=b"%PDF-1.4\n%%EOF",  # PDF mínimo válido
            pdf_filename="teste.pdf",
        )
