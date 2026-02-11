"""
Configuração do pytest.
"""

import sys
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def mock_env(monkeypatch):
    """Fixture para mockar variáveis de ambiente."""
    import base64
    import secrets

    # Gerar MASTER_KEY válida
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")

    monkeypatch.setenv("CONTA_AZUL_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("CONTA_AZUL_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("CONTA_AZUL_REDIRECT_URI", "http://localhost:8000/callback")
    monkeypatch.setenv("MASTER_KEY", key)
    monkeypatch.setenv("JWT_SECRET", "test_jwt_secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "test@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test_password")
    monkeypatch.setenv("SMTP_FROM", "test@test.com")
    monkeypatch.setenv("SMTP_REPLY_TO", "reply@test.com")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
