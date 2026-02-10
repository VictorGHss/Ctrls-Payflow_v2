"""
Testes para idempotência e processamento de recibos.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import AzulAccount, Base, OAuthToken, SentReceipt
from app.payment_processor import PaymentProcessor


@pytest.fixture
def test_db():
    """Cria banco de dados em memória para testes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def test_account(test_db):
    """Cria uma conta de teste."""
    account = AzulAccount(
        account_id="test_account_123",
        owner_name="Test Owner",
        owner_email="owner@test.com",
        company_name="Test Company",
        is_active=1,
    )
    test_db.add(account)
    test_db.commit()
    return account


@pytest.fixture
def test_token(test_db, test_account):
    """Cria um token OAuth criptografado para testes."""
    from app.crypto import CryptoManager
    import base64
    import secrets

    # Chave de teste
    key = base64.urlsafe_b64encode(secrets.token_bytes(32))

    class MockSettings:
        MASTER_KEY = key.decode("utf-8")

    with patch("app.payment_processor.get_crypto_manager") as mock_crypto:
        crypto = CryptoManager()
        mock_crypto.return_value = crypto

        token = OAuthToken(
            account_id=test_account.account_id,
            access_token=crypto.encrypt("test_access_token_123"),
            refresh_token=crypto.encrypt("test_refresh_token_456"),
            expires_at=datetime.now(timezone.utc),
        )
        test_db.add(token)
        test_db.commit()
        return token


def test_is_receipt_already_sent_when_exists(test_db, test_account):
    """Testa detecção de recibo já enviado."""
    with patch("app.payment_processor.get_crypto_manager"):
        processor = PaymentProcessor(test_db, "{}")

        # Adicionar recibo já enviado
        sent = SentReceipt(
            account_id=test_account.account_id,
            installment_id="inst_001",
            receipt_id="rec_001",
            receipt_url="https://example.com/rec_001",
            doctor_email="doctor@example.com",
            sent_at=datetime.now(timezone.utc),
        )
        test_db.add(sent)
        test_db.commit()

        # Verificar que é detectado como já enviado
        is_sent = processor.is_receipt_already_sent(
            test_account.account_id,
            "inst_001",
            "rec_001",
        )
        assert is_sent is True


def test_is_receipt_already_sent_when_not_exists(test_db, test_account):
    """Testa detecção quando recibo não foi enviado."""
    with patch("app.payment_processor.get_crypto_manager"):
        processor = PaymentProcessor(test_db, "{}")

        is_sent = processor.is_receipt_already_sent(
            test_account.account_id,
            "inst_new",
            "rec_new",
        )
        assert is_sent is False


def test_idempotency_duplicate_receipt_not_resent(test_db, test_account):
    """
    Testa que um recibo não é reenviado se já foi enviado.
    (Idempotência)
    """
    with patch("app.payment_processor.get_crypto_manager"):
        processor = PaymentProcessor(test_db, "{}")

        # Adicionar primeiro envio
        sent1 = SentReceipt(
            account_id=test_account.account_id,
            installment_id="inst_001",
            receipt_id="rec_001",
            receipt_url="https://example.com/rec_001",
            doctor_email="doctor@example.com",
            sent_at=datetime.now(timezone.utc),
        )
        test_db.add(sent1)
        test_db.commit()

        # Tentar enviar novamente (verificação de idempotência)
        is_already_sent = processor.is_receipt_already_sent(
            test_account.account_id,
            "inst_001",
            "rec_001",
        )
        assert is_already_sent is True

        # Verificar que há apenas 1 registro
        count = (
            test_db.query(SentReceipt)
            .filter(
                SentReceipt.account_id == test_account.account_id,
                SentReceipt.receipt_id == "rec_001",
            )
            .count()
        )
        assert count == 1


def test_log_email_attempt(test_db, test_account):
    """Testa logging de tentativa de envio."""
    from app.database import EmailLog

    with patch("app.payment_processor.get_crypto_manager"):
        processor = PaymentProcessor(test_db, "{}")

        processor.log_email_attempt(
            test_account.account_id,
            "rec_001",
            "doctor@example.com",
            "sent",
            None,
        )

        # Verificar que log foi criado
        log = (
            test_db.query(EmailLog)
            .filter(EmailLog.receipt_id == "rec_001")
            .first()
        )
        assert log is not None
        assert log.status == "sent"
        assert log.doctor_email == "doctor@example.com"


def test_doctor_fallback_resolver_by_name(test_db, test_account):
    """Testa resolução de email do médico por nome."""
    from app.payment_processor import DoctorFallbackResolver

    fallback_json = '{"João Silva": "joao@doctors.com"}'
    resolver = DoctorFallbackResolver(fallback_json)

    email = resolver.resolve("João Silva", None)
    assert email == "joao@doctors.com"


def test_doctor_fallback_resolver_by_fallback(test_db, test_account):
    """Testa resolução de email do médico por fallback."""
    from app.payment_processor import DoctorFallbackResolver

    resolver = DoctorFallbackResolver("{}")

    email = resolver.resolve("Cliente Novo", "fallback@doctors.com")
    assert email == "fallback@doctors.com"


def test_doctor_fallback_resolver_no_email_found(test_db, test_account):
    """Testa quando nenhum email é encontrado."""
    from app.payment_processor import DoctorFallbackResolver

    resolver = DoctorFallbackResolver("{}")

    email = resolver.resolve("Cliente Desconhecido", None)
    assert email is None

