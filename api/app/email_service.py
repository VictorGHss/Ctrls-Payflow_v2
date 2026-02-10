"""
Serviço de email com suporte a anexos e TLS.
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


class EmailService:
    """Serviço de envio de emails com SMTP TLS."""

    def __init__(self):
        """Inicializa configurações SMTP."""
        settings = get_settings()
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM
        self.reply_to = settings.SMTP_REPLY_TO
        self.use_tls = settings.SMTP_USE_TLS

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        pdf_content: Optional[bytes] = None,
        pdf_filename: str = "recibo.pdf",
    ) -> bool:
        """
        Envia email com anexo PDF opcional.

        Args:
            to_email: Email destinatário
            subject: Assunto do email
            body: Corpo do email (HTML ou plain text)
            pdf_content: Conteúdo do PDF em bytes
            pdf_filename: Nome do arquivo PDF

        Returns:
            True se enviado com sucesso, False caso contrário
        """
        try:
            # Criar mensagem MIME
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email
            msg["Reply-To"] = self.reply_to

            # Adicionar corpo (plain text)
            msg.attach(MIMEText(body, "plain"))

            # Adicionar PDF se fornecido
            if pdf_content:
                attachment = MIMEApplication(pdf_content, Name=pdf_filename)
                attachment["Content-Disposition"] = f"attachment; filename={pdf_filename}"
                msg.attach(attachment)
                logger.info(f"Anexo {pdf_filename} adicionado ao email")

            # Conectar e enviar
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()

                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email enviado com sucesso para {to_email}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"Erro de autenticação SMTP: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"Erro ao enviar email: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar email: {e}")
            return False

    def send_receipt_email(
        self,
        doctor_email: str,
        customer_name: str,
        amount: float,
        receipt_date: str,
        pdf_content: bytes,
    ) -> bool:
        """
        Envia email de recibo formatado.

        Args:
            doctor_email: Email do médico
            customer_name: Nome do cliente/paciente
            amount: Valor da parcela
            receipt_date: Data do recebimento
            pdf_content: Conteúdo do PDF

        Returns:
            True se enviado com sucesso
        """
        subject = f"Recibo de Pagamento - {customer_name}"

        body = f"""
Prezado(a),

Segue anexado o recibo de pagamento para o cliente/paciente:

Cliente: {customer_name}
Valor: R$ {amount:,.2f}
Data: {receipt_date}

Qualquer dúvida, favor entrar em contato.

Atenciosamente,
Sistema PayFlow
"""

        return self.send_email(
            to_email=doctor_email,
            subject=subject,
            body=body,
            pdf_content=pdf_content,
            pdf_filename=f"recibo_{customer_name.replace(' ', '_')}.pdf",
        )

