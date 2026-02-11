"""
Testes para correção do bug de datetime naive/aware.

Testa is_token_expired com diferentes cenários:
- Token com expires_at naive (sem timezone)
- Token com expires_at aware (com timezone UTC)
- Token expirado vs não expirado
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.database import OAuthToken
from app.services_auth import ContaAzulAuthService, normalize_datetime_utc


class TestNormalizeDatetimeUtc:
    """Testes para função normalize_datetime_utc."""

    def test_normalize_naive_datetime(self):
        """Datetime naive deve ser tratado como UTC."""
        # Datetime naive (sem timezone)
        naive_dt = datetime(2026, 2, 11, 18, 0, 0)

        result = normalize_datetime_utc(naive_dt)

        assert result.tzinfo == timezone.utc
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 11
        assert result.hour == 18

    def test_normalize_utc_aware_datetime(self):
        """Datetime já em UTC deve permanecer inalterado."""
        aware_dt = datetime(2026, 2, 11, 18, 0, 0, tzinfo=timezone.utc)

        result = normalize_datetime_utc(aware_dt)

        assert result.tzinfo == timezone.utc
        assert result == aware_dt

    def test_normalize_non_utc_aware_datetime(self):
        """Datetime aware em outro timezone deve ser convertido para UTC."""
        # GMT-3 (3 horas atrás do UTC)
        from datetime import timezone as tz
        gmt_minus_3 = tz(timedelta(hours=-3))
        aware_dt = datetime(2026, 2, 11, 15, 0, 0, tzinfo=gmt_minus_3)

        result = normalize_datetime_utc(aware_dt)

        assert result.tzinfo == timezone.utc
        # 15:00 GMT-3 = 18:00 UTC
        assert result.hour == 18


class TestIsTokenExpired:
    """Testes para is_token_expired com naive/aware datetimes."""

    @pytest.fixture
    def auth_service(self, test_db):
        """Fixture de auth service para testes."""
        return ContaAzulAuthService(test_db)

    def test_token_not_expired_naive_datetime(self, auth_service):
        """Token com expires_at naive (futuro) não deve estar expirado."""
        # Cria token com expires_at naive (1 hora no futuro)
        token = OAuthToken(
            account_id="test_account",
            access_token="encrypted_access",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now() + timedelta(hours=1)  # Naive datetime
        )

        result = auth_service.is_token_expired(token)

        assert result is False

    def test_token_expired_naive_datetime(self, auth_service):
        """Token com expires_at naive (passado) deve estar expirado."""
        # Cria token com expires_at naive (1 hora no passado)
        token = OAuthToken(
            account_id="test_account",
            access_token="encrypted_access",
            refresh_token="encrypted_refresh",
            expires_at=datetime.now() - timedelta(hours=1)  # Naive datetime
        )

        result = auth_service.is_token_expired(token)

        assert result is True

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
            expires_at=datetime.now() - timedelta(seconds=1)  # Naive
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
            expires_at=datetime.now() + timedelta(seconds=10)  # Naive
        )

        result = auth_service.is_token_expired(token)

        assert result is False

    def test_no_crash_with_naive_and_aware_comparison(self, auth_service):
        """
        Teste principal: garantir que não ocorre TypeError ao comparar
        naive e aware datetimes.

        Este era o bug original:
        TypeError: can't compare offset-naive and offset-aware datetimes
        """
        # Simula token vindo do SQLite (naive)
        naive_token = OAuthToken(
            account_id="test_naive",
            access_token="encrypted",
            refresh_token="encrypted",
            expires_at=datetime(2026, 12, 31, 23, 59, 59)  # Naive datetime
        )

        # Deve funcionar sem erro
        try:
            result = auth_service.is_token_expired(naive_token)
            # Token expira no futuro, não deve estar expirado
            assert result is False
        except TypeError as e:
            pytest.fail(f"TypeError não deveria ocorrer: {e}")

