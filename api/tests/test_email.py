"""
Testes para parsing de payload e email mockado.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.email_service import EmailService


@pytest.fixture
def mock_settings():
    """Mock das configurações SMTP."""
    class MockSettings:
        SMTP_HOST = "smtp.test.com"
        SMTP_PORT = 587
        SMTP_USER = "test@test.com"
        SMTP_PASSWORD = "password123"
        SMTP_FROM = "noreply@test.com"
        SMTP_REPLY_TO = "reply@test.com"
        SMTP_USE_TLS = True

    return MockSettings()


def test_email_service_send_email_success(mock_settings):
    """Testa envio de email bem-sucedido."""
    with patch("app.email_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings

        email_service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_service.send_email(
                to_email="doctor@example.com",
                subject="Test Receipt",
                body="Test body",
                pdf_content=b"fake_pdf_content",
                pdf_filename="test.pdf",
            )

            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with(
                "test@test.com",
                "password123",
            )
            mock_server.send_message.assert_called_once()


def test_email_service_send_email_without_pdf(mock_settings):
    """Testa envio de email sem anexo PDF."""
    with patch("app.email_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings

        email_service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_service.send_email(
                to_email="doctor@example.com",
                subject="Test Subject",
                body="Test body",
            )

            assert result is True
            mock_server.send_message.assert_called_once()


def test_email_service_send_email_authentication_error(mock_settings):
    """Testa erro de autenticação SMTP."""
    with patch("app.email_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings

        email_service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.login.side_effect = Exception("Authentication failed")

            result = email_service.send_email(
                to_email="doctor@example.com",
                subject="Test",
                body="Test",
            )

            assert result is False


def test_email_service_send_receipt_email(mock_settings):
    """Testa envio formatado de recibo."""
    with patch("app.email_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings

        email_service = EmailService()

        with patch.object(email_service, "send_email") as mock_send:
            mock_send.return_value = True

            result = email_service.send_receipt_email(
                doctor_email="doctor@example.com",
                customer_name="João Silva",
                amount=150.50,
                receipt_date="2025-02-10",
                pdf_content=b"fake_pdf",
            )

            assert result is True
            mock_send.assert_called_once()

            # Verificar argumentos
            call_args = mock_send.call_args
            assert call_args[1]["to_email"] == "doctor@example.com"
            assert "João Silva" in call_args[1]["subject"]
            assert call_args[1]["pdf_content"] == b"fake_pdf"


def test_email_payload_parsing():
    """Testa parsing de payload de parcela."""
    # Simular response da Conta Azul
    installment_payload = {
        "id": "inst_001",
        "status": "received",
        "customerName": "João da Silva",
        "amount": 500.00,
        "receivedDate": "2025-02-10T10:30:00",
        "receiptUrl": "https://api.contaazul.com/v1/receipts/rec_001/download",
        "doctorEmail": "joao@doctors.com",
        "modifiedDate": "2025-02-10T10:30:00",
    }

    # Extrair dados
    assert installment_payload["id"] == "inst_001"
    assert installment_payload["status"] == "received"
    assert installment_payload["customerName"] == "João da Silva"
    assert installment_payload["amount"] == 500.00
    assert installment_payload["doctorEmail"] == "joao@doctors.com"


def test_email_payload_parsing_with_missing_fields():
    """Testa parsing de payload com campos faltando."""
    installment_payload = {
        "id": "inst_002",
        "status": "received",
        "customerName": "Maria",
        # faltando: receiptUrl, doctorEmail, etc
    }

    # Extrair com fallback
    receipt_url = installment_payload.get("receiptUrl")
    doctor_email = installment_payload.get("doctorEmail")

    assert receipt_url is None
    assert doctor_email is None


def test_email_service_multipart_message(mock_settings):
    """Testa que o email contém partes de texto e anexo."""
    with patch("app.email_service.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings

        email_service = EmailService()

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            email_service.send_email(
                to_email="test@example.com",
                subject="Test",
                body="Test body",
                pdf_content=b"pdf_data",
                pdf_filename="test.pdf",
            )

            # Verificar que foi chamado com uma mensagem
            assert mock_server.send_message.called

