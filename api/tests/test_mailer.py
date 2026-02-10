"""
Testes para MailerService - Envio de email via SMTP
"""

import pytest
from unittest.mock import patch, MagicMock, call
import smtplib

from app.services.mailer import (
    MailerService,
    SMTPConfigError,
    EmailValidationError,
)


@pytest.fixture
def mock_settings():
    """Mock de settings para testes."""
    class MockSettings:
        SMTP_HOST = "smtp.example.com"
        SMTP_PORT = 587
        SMTP_USER = "test@example.com"
        SMTP_PASSWORD = "test_password"
        SMTP_FROM = "sender@example.com"
        SMTP_REPLY_TO = "reply@example.com"
        SMTP_USE_TLS = True
        SMTP_TIMEOUT = 10

    return MockSettings()


@pytest.fixture
def mailer(mock_settings):
    """Mailer com settings mockado."""
    with patch("app.services.mailer.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        return MailerService()


@pytest.fixture
def valid_pdf():
    """PDF válido mínimo."""
    return b"%PDF-1.4\n%%EOF"


@pytest.fixture
def valid_pdf_large():
    """PDF válido maior."""
    # PDF de 1MB
    return b"%PDF-1.4\n" + (b"x" * (1024 * 1024)) + b"\n%%EOF"


# ============================================================================
# TESTES DE VALIDAÇÃO DE CONFIGURAÇÃO
# ============================================================================


def test_mailer_valid_config(mock_settings):
    """Testa criação com config válida."""
    with patch("app.services.mailer.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        mailer = MailerService()

        assert mailer is not None
        assert mailer.settings.SMTP_HOST == "smtp.example.com"


def test_mailer_missing_smtp_host():
    """Testa erro quando SMTP_HOST está vazio."""
    class BadSettings:
        SMTP_HOST = ""
        SMTP_PORT = 587
        SMTP_USER = "test@example.com"
        SMTP_PASSWORD = "pass"
        SMTP_FROM = "from@example.com"
        SMTP_USE_TLS = True

    with patch("app.services.mailer.get_settings") as mock_get_settings:
        mock_get_settings.return_value = BadSettings()

        with pytest.raises(SMTPConfigError):
            MailerService()


def test_mailer_invalid_from_email():
    """Testa erro quando SMTP_FROM é inválido."""
    class BadSettings:
        SMTP_HOST = "smtp.example.com"
        SMTP_PORT = 587
        SMTP_USER = "test@example.com"
        SMTP_PASSWORD = "pass"
        SMTP_FROM = "invalid_email"
        SMTP_USE_TLS = True

    with patch("app.services.mailer.get_settings") as mock_get_settings:
        mock_get_settings.return_value = BadSettings()

        with pytest.raises(SMTPConfigError):
            MailerService()


# ============================================================================
# TESTES DE VALIDAÇÃO DE EMAIL
# ============================================================================


def test_is_valid_email_valid(mailer):
    """Testa validação de email válido."""
    assert mailer._is_valid_email("test@example.com") is True
    assert mailer._is_valid_email("user.name+tag@example.co.uk") is True
    assert mailer._is_valid_email("doctor@hospital.com.br") is True


def test_is_valid_email_invalid(mailer):
    """Testa rejeição de emails inválidos."""
    assert mailer._is_valid_email("") is False
    assert mailer._is_valid_email("invalid") is False
    assert mailer._is_valid_email("@example.com") is False
    assert mailer._is_valid_email("user@") is False
    assert mailer._is_valid_email("user@nodomain") is False


# ============================================================================
# TESTES DE SANITIZAÇÃO DE SUBJECT
# ============================================================================


def test_sanitize_subject_newline_injection(mailer):
    """Testa prevenção de newline injection em subject."""
    malicious = "Test\nBcc: attacker@example.com"
    sanitized = mailer._sanitize_subject(malicious)

    assert "\n" not in sanitized
    assert "\r" not in sanitized
    assert "Bcc" not in sanitized


def test_sanitize_subject_length(mailer):
    """Testa limitação de comprimento."""
    long_subject = "A" * 200
    sanitized = mailer._sanitize_subject(long_subject)

    assert len(sanitized) <= 100
    assert sanitized.endswith("...")


def test_sanitize_subject_normal(mailer):
    """Testa subject normal."""
    normal = "Recibo de pagamento - João Silva"
    sanitized = mailer._sanitize_subject(normal)

    assert sanitized == normal


# ============================================================================
# TESTES DE VALIDAÇÃO DE ANEXO
# ============================================================================


def test_validate_attachment_valid(mailer, valid_pdf):
    """Testa validação de PDF válido."""
    # Não deve lançar exceção
    mailer._validate_attachment(valid_pdf, "recibo.pdf")


def test_validate_attachment_empty(mailer):
    """Testa rejeição de conteúdo vazio."""
    with pytest.raises(EmailValidationError):
        mailer._validate_attachment(b"", "recibo.pdf")


def test_validate_attachment_too_large(mailer):
    """Testa rejeição de arquivo muito grande."""
    # Arquivo maior que MAX_ATTACHMENT_SIZE (25MB)
    large_content = b"%PDF-1.4\n" + (b"x" * (30 * 1024 * 1024))

    with pytest.raises(EmailValidationError):
        mailer._validate_attachment(large_content, "recibo.pdf")


def test_validate_attachment_invalid_extension(mailer, valid_pdf):
    """Testa rejeição de extensão inválida."""
    with pytest.raises(EmailValidationError):
        mailer._validate_attachment(valid_pdf, "recibo.txt")

    with pytest.raises(EmailValidationError):
        mailer._validate_attachment(valid_pdf, "recibo.doc")


def test_validate_attachment_invalid_magic_bytes(mailer):
    """Testa rejeição de arquivo sem magic bytes PDF."""
    not_pdf = b"This is not a PDF file\n%%EOF"

    with pytest.raises(EmailValidationError):
        mailer._validate_attachment(not_pdf, "recibo.pdf")


# ============================================================================
# TESTES DE CONSTRUÇÃO DE MENSAGEM
# ============================================================================


def test_build_subject(mailer):
    """Testa construção de subject."""
    subject = mailer._build_subject("João Silva")
    assert "João Silva" in subject
    assert "Recibo" in subject


def test_build_body(mailer):
    """Testa construção de corpo."""
    body = mailer._build_body(
        customer_name="João Silva",
        amount=1000.50,
        receipt_date="2026-02-10",
    )

    assert "João Silva" in body
    assert "1000.50" in body
    assert "2026-02-10" in body


def test_build_body_minimal(mailer):
    """Testa construção com dados mínimos."""
    body = mailer._build_body(
        customer_name="",
        amount=0,
        receipt_date=None,
    )

    # Deve ter cabeçalho e rodapé mesmo sem dados
    assert "Prezado(a)" in body
    assert "Atenciosamente" in body


def test_build_message(mailer, valid_pdf):
    """Testa construção completa da mensagem."""
    msg = mailer._build_message(
        doctor_email="doctor@example.com",
        customer_name="João Silva",
        amount=1000.00,
        receipt_date="2026-02-10",
        pdf_content=valid_pdf,
        pdf_filename="recibo.pdf",
        reply_to="reply@example.com",
    )

    assert msg["From"] == mailer.settings.SMTP_FROM
    assert msg["To"] == "doctor@example.com"
    assert msg["Reply-To"] == "reply@example.com"
    assert "João Silva" in msg["Subject"]


def test_build_message_without_reply_to(mailer, valid_pdf):
    """Testa construção sem reply-to."""
    msg = mailer._build_message(
        doctor_email="doctor@example.com",
        customer_name="João Silva",
        amount=1000.00,
        receipt_date="2026-02-10",
        pdf_content=valid_pdf,
        pdf_filename="recibo.pdf",
        reply_to=None,
    )

    assert "Reply-To" not in msg


# ============================================================================
# TESTES DE ENVIO VIA SMTP
# ============================================================================


def test_send_via_smtp_success(mailer, valid_pdf):
    """Testa envio bem-sucedido via SMTP."""
    with patch("smtplib.SMTP") as mock_smtp:
        # Mock do servidor SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        msg = mailer._build_message(
            doctor_email="doctor@example.com",
            customer_name="João Silva",
            amount=1000.00,
            receipt_date="2026-02-10",
            pdf_content=valid_pdf,
            pdf_filename="recibo.pdf",
            reply_to=None,
        )

        mailer._send_via_smtp(msg, "doctor@example.com")

        # Verificar que starttls foi chamado
        mock_server.starttls.assert_called()

        # Verificar que login foi chamado
        mock_server.login.assert_called_with(
            "test@example.com",
            "test_password",
        )

        # Verificar que send_message foi chamado
        mock_server.send_message.assert_called_once()


def test_send_via_smtp_auth_error(mailer, valid_pdf):
    """Testa erro de autenticação SMTP."""
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Simular erro de autenticação
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
            "Invalid credentials"
        )

        msg = mailer._build_message(
            doctor_email="doctor@example.com",
            customer_name="João Silva",
            amount=1000.00,
            receipt_date="2026-02-10",
            pdf_content=valid_pdf,
            pdf_filename="recibo.pdf",
            reply_to=None,
        )

        with pytest.raises(Exception):
            mailer._send_via_smtp(msg, "doctor@example.com")


def test_send_via_smtp_timeout(mailer, valid_pdf):
    """Testa timeout na conexão SMTP."""
    with patch("smtplib.SMTP") as mock_smtp:
        # Simular timeout
        mock_smtp.side_effect = TimeoutError("Connection timeout")

        msg = mailer._build_message(
            doctor_email="doctor@example.com",
            customer_name="João Silva",
            amount=1000.00,
            receipt_date="2026-02-10",
            pdf_content=valid_pdf,
            pdf_filename="recibo.pdf",
            reply_to=None,
        )

        with pytest.raises(Exception):
            mailer._send_via_smtp(msg, "doctor@example.com")


# ============================================================================
# TESTES DE ENVIO DE EMAIL COMPLETO
# ============================================================================


def test_send_receipt_email_success(mailer, valid_pdf):
    """Testa envio completo de email bem-sucedido."""
    with patch.object(mailer, "_send_via_smtp"):
        result = mailer.send_receipt_email(
            doctor_email="doctor@example.com",
            customer_name="João Silva",
            amount=1000.00,
            receipt_date="2026-02-10",
            pdf_content=valid_pdf,
            pdf_filename="recibo.pdf",
            reply_to="reply@example.com",
        )

        assert result is True


def test_send_receipt_email_invalid_recipient(mailer, valid_pdf):
    """Testa rejeição de email inválido."""
    result = mailer.send_receipt_email(
        doctor_email="invalid_email",
        customer_name="João Silva",
        amount=1000.00,
        receipt_date="2026-02-10",
        pdf_content=valid_pdf,
        pdf_filename="recibo.pdf",
    )

    assert result is False


def test_send_receipt_email_invalid_attachment(mailer):
    """Testa rejeição de anexo inválido."""
    result = mailer.send_receipt_email(
        doctor_email="doctor@example.com",
        customer_name="João Silva",
        amount=1000.00,
        receipt_date="2026-02-10",
        pdf_content=b"not a pdf",
        pdf_filename="recibo.pdf",
    )

    assert result is False


def test_send_receipt_email_smtp_error(mailer, valid_pdf):
    """Testa tratamento de erro SMTP."""
    with patch.object(
        mailer,
        "_send_via_smtp",
        side_effect=Exception("SMTP error"),
    ):
        result = mailer.send_receipt_email(
            doctor_email="doctor@example.com",
            customer_name="João Silva",
            amount=1000.00,
            receipt_date="2026-02-10",
            pdf_content=valid_pdf,
            pdf_filename="recibo.pdf",
        )

        assert result is False


# ============================================================================
# TESTES DE EMAIL DE TESTE
# ============================================================================


def test_send_test_email(mailer):
    """Testa envio de email de teste."""
    with patch.object(mailer, "_send_via_smtp"):
        result = mailer.send_test_email("test@example.com")

        assert result is True


def test_send_test_email_invalid_address(mailer):
    """Testa rejeição de endereço inválido."""
    result = mailer.send_test_email("invalid")

    assert result is False

