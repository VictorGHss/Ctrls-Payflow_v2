"""
Testes para correção do bug de datetime naive/aware.

Com TZDateTime, expires_at é sempre timezone-aware (UTC).
Testes verificam compatibilidade retroativa e comportamento correto.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.database import OAuthToken
from app.services_auth import ContaAzulAuthService


class TestIsTokenExpired:
    """
    Testes para is_token_expired com TZDateTime.

    TZDateTime garante que expires_at seja sempre timezone-aware (UTC).
    Estes testes verificam o comportamento correto.
    """

    @pytest.fixture
    def auth_service(self, test_db):
        """Fixture de auth service para testes."""
        return ContaAzulAuthService(test_db)

    def test_token_not_expired_aware_datetime(self, auth_service):
        """Token com expires_at aware UTC (futuro) não deve estar expirado."""
        # Cria token com expires_at aware (1 hora no futuro)
        token = OAuthToken(
            account_id="test_account",
            access_token="encrypted_access",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        result = auth_service.is_token_expired(token)

        assert result is False

    def test_token_expired_aware_datetime(self, auth_service):
        """Token com expires_at aware UTC (passado) deve estar expirado."""
        # Cria token com expires_at aware (1 hora no passado)
        token = OAuthToken(
            account_id="test_account",
            access_token="encrypted_access",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1)
        )

        result = auth_service.is_token_expired(token)

        assert result is True

    def test_token_just_expired(self, auth_service):
        """Token que acabou de expirar deve estar expirado."""
        # Token expira exatamente agora (ou 1 segundo no passado)
        token = OAuthToken(
            account_id="test_account",
            access_token="encrypted_access",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        result = auth_service.is_token_expired(token)

        assert result is True

    def test_token_about_to_expire(self, auth_service):
        """Token que está prestes a expirar ainda não deve estar expirado."""
        # Token expira em 10 segundos
        token = OAuthToken(
            account_id="test_account",
            access_token="encrypted_access",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=10)
        )

        result = auth_service.is_token_expired(token)

        assert result is False

    def test_backwards_compatibility_naive_datetime(self, auth_service):
        """
        Teste de compatibilidade retroativa: token naive (de migração antiga).

        TZDateTime converte automaticamente, mas se vier naive de alguma forma,
        is_token_expired() deve lidar com isso gracefully.
        """
        # Simula token naive que pode ter vindo de banco antigo
        naive_token = OAuthToken(
            account_id="test_naive",
            access_token="encrypted",
            refresh_token="encrypted",
            expires_at=datetime(2026, 12, 31, 23, 59, 59)  # Naive datetime
        )

        # Deve funcionar sem erro (log de warning esperado)
        try:
            result = auth_service.is_token_expired(naive_token)
            # Token expira no futuro, não deve estar expirado
            assert result is False
        except TypeError as e:
            pytest.fail(f"TypeError não deveria ocorrer com naive datetime: {e}")

    def test_no_crash_with_timezone_aware_comparison(self, auth_service):
        """
        Teste principal: garantir que não ocorre TypeError.

        Com TZDateTime, expires_at é sempre aware, então comparação
        com datetime.now(timezone.utc) sempre funciona.
        """
        # Token aware UTC (padrão com TZDateTime)
        aware_token = OAuthToken(
            account_id="test_aware",
            access_token="encrypted",
            refresh_token="encrypted",
            expires_at=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        )

        # Deve funcionar perfeitamente
        try:
            result = auth_service.is_token_expired(aware_token)
            assert result is False
        except TypeError as e:
            pytest.fail(f"TypeError não deveria ocorrer: {e}")

    def test_token_expires_at_has_timezone_info(self, auth_service):
        """Verifica que expires_at sempre tem timezone info."""
        token = OAuthToken(
            account_id="test_tz",
            access_token="encrypted",
            refresh_token="encrypted",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        # Com TZDateTime, expires_at deve sempre ter timezone
        assert token.expires_at.tzinfo is not None
        assert token.expires_at.tzinfo == timezone.utc

