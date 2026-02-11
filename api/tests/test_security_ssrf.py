"""
Testes de Segurança - Validação de SSRF
"""

from unittest.mock import patch

import pytest

from app.worker.conta_azul_financial_client import ContaAzulFinancialClient


@pytest.fixture
def client():
    """Client para testes."""
    with patch("app.worker.conta_azul_financial_client.get_settings") as mock_settings:

        class MockSettings:
            SMTP_TIMEOUT = 10

        mock_settings.return_value = MockSettings()
        return ContaAzulFinancialClient("test_token")


# ============================================================================
# TESTES DE SSRF - URLs MALICIOSAS
# ============================================================================


def test_ssrf_localhost(client):
    """❌ Rejeitar localhost."""
    assert not client._validate_receipt_url("https://localhost:8000/admin")
    assert not client._validate_receipt_url("https://127.0.0.1/admin")
    assert not client._validate_receipt_url("https://0.0.0.0/admin")


def test_ssrf_private_ip(client):
    """❌ Rejeitar IP privado (RFC 1918)."""
    assert not client._validate_receipt_url("https://192.168.1.1/config")
    assert not client._validate_receipt_url("https://10.0.0.1/admin")
    assert not client._validate_receipt_url("https://172.16.0.1/data")


def test_ssrf_metadata(client):
    """❌ Rejeitar AWS/GCP metadata endpoints."""
    assert not client._validate_receipt_url("https://169.254.169.254/")
    assert not client._validate_receipt_url("http://169.254.169.254/latest/meta-data/")


def test_ssrf_reserved_ip(client):
    """❌ Rejeitar IPs reservados."""
    assert not client._validate_receipt_url("https://0.0.0.0/")
    assert not client._validate_receipt_url("https://255.255.255.255/")


def test_ssrf_multicast_ip(client):
    """❌ Rejeitar IP multicast."""
    assert not client._validate_receipt_url("https://224.0.0.1/")


def test_ssrf_http_not_https(client):
    """❌ Rejeitar HTTP (não HTTPS)."""
    assert not client._validate_receipt_url("http://api.contaazul.com/")


def test_ssrf_ftp_scheme(client):
    """❌ Rejeitar FTP."""
    assert not client._validate_receipt_url("ftp://api.contaazul.com/")


def test_ssrf_invalid_domain(client):
    """❌ Rejeitar domínios não-autorizados."""
    assert not client._validate_receipt_url("https://google.com/attachment")
    assert not client._validate_receipt_url("https://attacker.com/")
    assert not client._validate_receipt_url(
        "https://example.contaazul.com.attacker.com/"
    )


def test_ssrf_empty_url(client):
    """❌ Rejeitar URL vazia."""
    assert not client._validate_receipt_url("")
    assert not client._validate_receipt_url(None)


def test_ssrf_no_hostname(client):
    """❌ Rejeitar URL sem hostname."""
    assert not client._validate_receipt_url("https:///")


# ============================================================================
# TESTES DE SSRF - URLs VÁLIDAS
# ============================================================================


def test_ssrf_valid_domain_api(client):
    """✅ Aceitar api.contaazul.com."""
    assert client._validate_receipt_url("https://api.contaazul.com/attachments/123")


def test_ssrf_valid_domain_cdn(client):
    """✅ Aceitar cdn.contaazul.com."""
    assert client._validate_receipt_url("https://cdn.contaazul.com/recibos/456")


def test_ssrf_valid_domain_attachments(client):
    """✅ Aceitar attachments.contaazul.com."""
    assert client._validate_receipt_url("https://attachments.contaazul.com/pdf/789")


def test_ssrf_valid_domain_static(client):
    """✅ Aceitar static.contaazul.com."""
    assert client._validate_receipt_url("https://static.contaazul.com/documents/000")


def test_ssrf_valid_subdomain(client):
    """✅ Aceitar subdomínios."""
    assert client._validate_receipt_url("https://api.contaazul.com/attachment.pdf")


def test_ssrf_valid_with_port(client):
    """✅ Aceitar com porta (HTTPS)."""
    assert client._validate_receipt_url("https://api.contaazul.com:443/file")


def test_ssrf_valid_with_query(client):
    """✅ Aceitar com query params."""
    assert client._validate_receipt_url(
        "https://api.contaazul.com/file?id=123&token=abc"
    )


def test_ssrf_valid_long_url(client):
    """✅ Aceitar URL longa válida."""
    url = "https://api.contaazul.com/v1/receivables/123/attachments/456/download?format=pdf&sign=true"
    assert client._validate_receipt_url(url)


# ============================================================================
# TESTES DE SSRF - CASOS EXTREMOS
# ============================================================================


def test_ssrf_hostname_case_insensitive(client):
    """✅ Aceitar independente de maiúsculas."""
    assert client._validate_receipt_url("https://API.CONTAAZUL.COM/file")
    assert client._validate_receipt_url("https://Api.ContaAzul.Com/file")


def test_ssrf_ipv6_loopback(client):
    """❌ Rejeitar IPv6 loopback."""
    assert not client._validate_receipt_url("https://[::1]/admin")


def test_ssrf_ipv6_private(client):
    """❌ Rejeitar IPv6 privado."""
    assert not client._validate_receipt_url("https://[fc00::1]/config")


def test_ssrf_unicode_bypass(client):
    """❌ Rejeitar unicode/punycode bypass attempts."""
    # Punycode encoding de "localhost"
    assert not client._validate_receipt_url("https://[::ffff:127.0.0.1]/")


def test_ssrf_newline_injection(client):
    """❌ Rejeitar newlines (injection)."""
    assert not client._validate_receipt_url("https://api.contaazul.com/\nAdministrator")


# ============================================================================
# TESTES DE TAMANHO DE RESPONSE
# ============================================================================


def test_max_response_size_configured(client):
    """✅ Verificar que MAX_RESPONSE_SIZE está configurado."""
    assert client.MAX_RESPONSE_SIZE == 100 * 1024 * 1024  # 100MB
    assert client.MAX_RESPONSE_SIZE > 0


def test_allowed_domains_configured(client):
    """✅ Verificar que ALLOWED_RECEIPT_DOMAINS está configurado."""
    assert len(client.ALLOWED_RECEIPT_DOMAINS) > 0
    assert "api.contaazul.com" in client.ALLOWED_RECEIPT_DOMAINS
    assert "cdn.contaazul.com" in client.ALLOWED_RECEIPT_DOMAINS
