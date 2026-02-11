"""
Testes para Worker - Idempotência e Checkpoint
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import AzulAccount, Base, FinancialCheckpoint, SentReceipt
from app.worker.processor import FinancialProcessor


@pytest.fixture
def test_db():
    """Cria banco de dados em memória para testes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def test_account(test_db):
    """Cria conta de teste."""
    account = AzulAccount(
        account_id="test_account_001",
        owner_name="Test Owner",
        owner_email="test@example.com",
        company_name="Test Company",
        is_active=1,
    )
    test_db.add(account)
    test_db.commit()
    return account


@pytest.fixture
def processor(test_db):
    """Cria processador."""
    from unittest.mock import patch

    class MockSettings:
        POLLING_INTERVAL_SECONDS = 300
        POLLING_SAFETY_WINDOW_MINUTES = 10
        DOCTORS_FALLBACK_JSON = "{}"

    with patch("app.worker.processor.get_settings") as mock_settings:
        mock_settings.return_value = MockSettings()
        return FinancialProcessor(test_db)


# ============================================================================
# TESTES DE CHECKPOINT
# ============================================================================


def test_get_or_create_checkpoint(processor, test_account, test_db):
    """Testa criação de novo checkpoint."""
    account_id = test_account.account_id

    checkpoint = processor._get_or_create_checkpoint(account_id)

    assert checkpoint is not None
    assert checkpoint.account_id == account_id
    assert checkpoint.last_processed_changed_at is not None

    # Verificar que foi salvo no banco
    saved = (
        test_db.query(FinancialCheckpoint)
        .filter(FinancialCheckpoint.account_id == account_id)
        .first()
    )
    assert saved is not None


def test_checkpoint_reuse(processor, test_account, test_db):
    """Testa que reusa checkpoint existente."""
    account_id = test_account.account_id

    # Criar primeiro
    cp1 = processor._get_or_create_checkpoint(account_id)
    original_date = cp1.last_processed_changed_at

    # Aguardar um pouco
    import time

    time.sleep(0.1)

    # Buscar novamente
    cp2 = processor._get_or_create_checkpoint(account_id)

    # Deve ser o mesmo registro (mesma data inicial)
    assert cp2.last_processed_changed_at == original_date

    # Contar registros (deve ser só 1)
    count = test_db.query(FinancialCheckpoint).count()
    assert count == 1


def test_update_checkpoint(processor, test_account, test_db):
    """Testa atualização de checkpoint."""
    account_id = test_account.account_id

    checkpoint = processor._get_or_create_checkpoint(account_id)
    original_date = checkpoint.last_processed_changed_at

    # Atualizar
    processor._update_checkpoint(checkpoint)

    # Deve ter alterado para agora
    assert checkpoint.last_processed_changed_at > original_date
    assert checkpoint.last_processed_changed_at <= datetime.now(timezone.utc)


def test_calculate_changed_since_with_safety_window(processor, test_account, test_db):
    """Testa cálculo de data com janela de segurança."""
    checkpoint = processor._get_or_create_checkpoint(test_account.account_id)

    # Definir data conhecida
    known_date = datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc)
    checkpoint.last_processed_changed_at = known_date

    # Calcular changed_since (com janela de segurança de 10 min)
    changed_since = processor._calculate_changed_since(checkpoint)

    # Deve ser 10 minutos antes
    expected = known_date - timedelta(minutes=10)
    assert changed_since == expected


def test_calculate_changed_since_default(processor, test_db):
    """Testa cálculo padrão (30 dias atrás)."""
    checkpoint = FinancialCheckpoint(
        account_id="test_account_default",
        last_processed_changed_at=None,
    )

    changed_since = processor._calculate_changed_since(checkpoint)

    # Deve ser ~30 dias atrás
    now = datetime.now(timezone.utc)
    delta = (now - changed_since).days

    assert delta >= 29 and delta <= 31


# ============================================================================
# TESTES DE IDEMPOTÊNCIA
# ============================================================================


def test_is_receipt_not_sent(processor, test_account):
    """Testa verificação de recibo não enviado."""
    account_id = test_account.account_id
    installment_id = "inst_001"
    attachment_url = "https://example.com/recibo.pdf"

    # Deve retornar False (não foi enviado)
    is_sent = processor._is_receipt_already_sent(
        account_id,
        installment_id,
        attachment_url,
    )

    assert is_sent is False


def test_is_receipt_already_sent(processor, test_account, test_db):
    """Testa detecção de recibo já enviado."""
    account_id = test_account.account_id
    installment_id = "inst_001"
    attachment_url = "https://example.com/recibo.pdf"

    # Registrar envio
    processor._register_sent_receipt(
        account_id,
        installment_id,
        attachment_url,
        "doctor@example.com",
        "hash123",
        {},
    )

    # Agora deve retornar True
    is_sent = processor._is_receipt_already_sent(
        account_id,
        installment_id,
        attachment_url,
    )

    assert is_sent is True


def test_idempotency_unique_constraint(processor, test_account, test_db):
    """Testa constraint de unicidade de idempotência."""
    account_id = test_account.account_id
    installment_id = "inst_002"
    attachment_url = "https://example.com/recibo2.pdf"

    # Primeiro registro
    processor._register_sent_receipt(
        account_id,
        installment_id,
        attachment_url,
        "doctor@example.com",
        "hash1",
        {"amount": 100},
    )

    # Tentar registrar novamente (deve falhar com violação de constraint)
    with pytest.raises(IntegrityError):
        processor._register_sent_receipt(
            account_id,
            installment_id,
            attachment_url,
            "other@example.com",
            "hash2",
            {"amount": 200},
        )
        test_db.commit()  # Força commit para erro aparecer


def test_idempotency_different_urls(processor, test_account):
    """Testa que URLs diferentes podem ser registradas."""
    account_id = test_account.account_id
    installment_id = "inst_003"

    # Duas URLs diferentes para mesma parcela
    url1 = "https://example.com/recibo1.pdf"
    url2 = "https://example.com/recibo2.pdf"

    # Ambas devem ser registráveis
    processor._register_sent_receipt(
        account_id,
        installment_id,
        url1,
        "doctor1@example.com",
        "hash1",
        {},
    )

    processor._register_sent_receipt(
        account_id,
        installment_id,
        url2,
        "doctor2@example.com",
        "hash2",
        {},
    )

    # Ambas devem estar registradas
    sent1 = processor._is_receipt_already_sent(account_id, installment_id, url1)
    sent2 = processor._is_receipt_already_sent(account_id, installment_id, url2)

    assert sent1 is True
    assert sent2 is True


def test_register_sent_receipt_metadata(processor, test_account, test_db):
    """Testa registro com metadata."""
    account_id = test_account.account_id
    installment_id = "inst_004"
    attachment_url = "https://example.com/recibo.pdf"
    metadata = {
        "customer_name": "João Silva",
        "amount": 500.00,
        "payment_date": "2026-02-10T10:30:00Z",
    }

    processor._register_sent_receipt(
        account_id,
        installment_id,
        attachment_url,
        "doctor@example.com",
        "hash",
        metadata,
    )

    # Verificar que foi salvo
    sent_receipt = (
        test_db.query(SentReceipt)
        .filter(
            SentReceipt.account_id == account_id,
            SentReceipt.installment_id == installment_id,
        )
        .first()
    )

    assert sent_receipt is not None
    assert sent_receipt.metadata["customer_name"] == "João Silva"
    assert sent_receipt.metadata["amount"] == 500.00


def test_register_sent_receipt_hash(processor, test_account, test_db):
    """Testa que hash é armazenado para deduplicação."""
    account_id = test_account.account_id
    installment_id = "inst_005"
    attachment_url = "https://example.com/recibo.pdf"
    receipt_hash = "sha256_hash_1234567890"

    processor._register_sent_receipt(
        account_id,
        installment_id,
        attachment_url,
        "doctor@example.com",
        receipt_hash,
        {},
    )

    sent_receipt = (
        test_db.query(SentReceipt).filter(SentReceipt.account_id == account_id).first()
    )

    assert sent_receipt.receipt_hash == receipt_hash


# ============================================================================
# TESTES DE INTEGRAÇÃO
# ============================================================================


def test_get_active_accounts(test_db):
    """Testa busca de contas ativas."""
    # Criar contas
    active1 = AzulAccount(
        account_id="active_1",
        company_name="Ativa 1",
        is_active=1,
    )
    active2 = AzulAccount(
        account_id="active_2",
        company_name="Ativa 2",
        is_active=1,
    )
    inactive = AzulAccount(
        account_id="inactive_1",
        company_name="Inativa",
        is_active=0,
    )

    test_db.add_all([active1, active2, inactive])
    test_db.commit()

    from unittest.mock import patch

    class MockSettings:
        POLLING_INTERVAL_SECONDS = 300
        POLLING_SAFETY_WINDOW_MINUTES = 10

    with patch("app.worker.processor.get_settings") as mock_settings:
        mock_settings.return_value = MockSettings()
        processor = FinancialProcessor(test_db)

        accounts = processor.get_active_accounts()

        assert len(accounts) == 2
        account_ids = {a.account_id for a in accounts}
        assert "active_1" in account_ids
        assert "active_2" in account_ids
        assert "inactive_1" not in account_ids
