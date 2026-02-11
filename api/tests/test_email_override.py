"""
Testes para override de destinatário de email.
"""

import pytest
from unittest.mock import Mock, patch

from app.services.mailer import MailerService


class TestEmailOverride:
    """Testes para OVERRIDE_RECIPIENT_EMAIL."""

    @pytest.fixture
    def mock_smtp_config(self):
        """Mock de configuração SMTP válida."""
        return {
            "SMTP_HOST": "smtp.example.com",
            "SMTP_PORT": 587,
            "SMTP_USER": "user@example.com",
            "SMTP_PASSWORD": "password",
            "SMTP_FROM": "noreply@example.com",
            "SMTP_REPLY_TO": "",
            "SMTP_USE_TLS": True,
            "SMTP_USE_SSL": False,
            "SMTP_TIMEOUT": 10,
            "OVERRIDE_RECIPIENT_EMAIL": None,
        }

    @pytest.fixture
    def pdf_content(self):
        """PDF válido de exemplo."""
        return b"%PDF-1.4\nfake pdf content"

    @patch("app.services.mailer.get_settings")
    @patch("app.services.mailer.smtplib.SMTP")
    def test_no_override_sends_to_real_recipient(
        self, mock_smtp, mock_get_settings, mock_smtp_config, pdf_content
    ):
        """Sem override, email deve ser enviado para destinatário real."""
        # Setup
        mock_settings = Mock(**mock_smtp_config)
        mock_get_settings.return_value = mock_settings

        mailer = MailerService()

        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Send
        result = mailer.send_receipt_email(
            doctor_email="doctor@hospital.com",
            customer_name="João Silva",
            amount=150.00,
            receipt_date="2026-02-11",
            pdf_content=pdf_content,
            pdf_filename="recibo.pdf",
        )

        assert result is True

        # Verificar que enviou para doctor@hospital.com
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["To"] == "doctor@hospital.com"

    @patch("app.services.mailer.get_settings")
    @patch("app.services.mailer.smtplib.SMTP")
    def test_with_override_sends_to_override_email(
        self, mock_smtp, mock_get_settings, mock_smtp_config, pdf_content
    ):
        """Com override, email deve ser enviado para override email."""
        # Setup com override
        mock_smtp_config["OVERRIDE_RECIPIENT_EMAIL"] = "testes@example.com"
        mock_settings = Mock(**mock_smtp_config)
        mock_get_settings.return_value = mock_settings

        mailer = MailerService()

        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Send
        result = mailer.send_receipt_email(
            doctor_email="doctor@hospital.com",  # Real
            customer_name="João Silva",
            amount=150.00,
            receipt_date="2026-02-11",
            pdf_content=pdf_content,
            pdf_filename="recibo.pdf",
        )

        assert result is True

        # Verificar que enviou para testes@example.com (override)
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["To"] == "testes@example.com"

    @patch("app.services.mailer.get_settings")
    @patch("app.services.mailer.smtplib.SMTP")
    def test_invalid_override_email_uses_real_recipient(
        self, mock_smtp, mock_get_settings, mock_smtp_config, pdf_content, caplog
    ):
        """Override inválido deve usar destinatário real e logar erro."""
        # Setup com override inválido
        mock_smtp_config["OVERRIDE_RECIPIENT_EMAIL"] = "email_invalido"
        mock_settings = Mock(**mock_smtp_config)
        mock_get_settings.return_value = mock_settings

        mailer = MailerService()

        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Send
        result = mailer.send_receipt_email(
            doctor_email="doctor@hospital.com",
            customer_name="João Silva",
            amount=150.00,
            receipt_date="2026-02-11",
            pdf_content=pdf_content,
            pdf_filename="recibo.pdf",
        )

        assert result is True

        # Verificar que enviou para doctor@hospital.com (real)
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["To"] == "doctor@hospital.com"

        # Verificar que logou erro de override inválido
        assert "OVERRIDE_RECIPIENT_EMAIL inválido" in caplog.text

    @patch("app.services.mailer.get_settings")
    @patch("app.services.mailer.smtplib.SMTP")
    def test_empty_override_uses_real_recipient(
        self, mock_smtp, mock_get_settings, mock_smtp_config, pdf_content
    ):
        """Override vazio (string vazia) deve usar destinatário real."""
        # Setup com override vazio
        mock_smtp_config["OVERRIDE_RECIPIENT_EMAIL"] = ""
        mock_settings = Mock(**mock_smtp_config)
        mock_get_settings.return_value = mock_settings

        mailer = MailerService()

        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Send
        result = mailer.send_receipt_email(
            doctor_email="doctor@hospital.com",
            customer_name="João Silva",
            amount=150.00,
            receipt_date="2026-02-11",
            pdf_content=pdf_content,
            pdf_filename="recibo.pdf",
        )

        assert result is True

        # Verificar que enviou para doctor@hospital.com (real)
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["To"] == "doctor@hospital.com"

    @patch("app.services.mailer.get_settings")
    @patch("app.services.mailer.smtplib.SMTP")
    def test_override_logging(
        self, mock_smtp, mock_get_settings, mock_smtp_config, pdf_content, caplog
    ):
        """Verificar que override é logado corretamente."""
        # Setup com override
        mock_smtp_config["OVERRIDE_RECIPIENT_EMAIL"] = "testes@example.com"
        mock_settings = Mock(**mock_smtp_config)
        mock_get_settings.return_value = mock_settings

        mailer = MailerService()

        # Mock SMTP
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Send
        mailer.send_receipt_email(
            doctor_email="doctor@hospital.com",
            customer_name="João Silva",
            amount=150.00,
            receipt_date="2026-02-11",
            pdf_content=pdf_content,
            pdf_filename="recibo.pdf",
        )

        # Verificar logs
        assert "Override de destinatário ativado" in caplog.text
        assert "Real=doctor@hospital.com" in caplog.text
        assert "Override=testes@example.com" in caplog.text
        assert "Email enviado com sucesso (override)" in caplog.text

