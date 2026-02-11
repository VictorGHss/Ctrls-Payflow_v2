"""
Testes para OAuth2 - Criptografia e Persistência de Tokens
"""

import base64
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crypto import get_crypto_manager
from app.database import AzulAccount, Base, OAuthToken
from app.services_auth import ContaAzulAuthService


@pytest.fixture
def test_db():
    """Cria banco de dados em memória para testes."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@pytest.fixture
def crypto_manager():
    """Retorna CryptoManager com chave de teste."""
    import secrets
    from unittest.mock import patch

    # Gerar chave de teste
    key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()

    class MockSettings:
        MASTER_KEY = key

    with patch("app.crypto.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MockSettings()
        return get_crypto_manager()


@pytest.fixture
def auth_service(test_db, crypto_manager):
    """Retorna ContaAzulAuthService configurado para testes."""
    from unittest.mock import patch

    # Mock dos settings
    class MockSettings:
        CONTA_AZUL_CLIENT_ID = "test_client_id"
        CONTA_AZUL_CLIENT_SECRET = "test_client_secret"
        CONTA_AZUL_REDIRECT_URI = "http://localhost:8000/oauth/callback"

    with patch("app.services_auth.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MockSettings()
        return ContaAzulAuthService(test_db)


# ============================================================================
# TESTES DE CRIPTOGRAFIA
# ============================================================================


def test_crypto_encrypt_decrypt(crypto_manager):
    """Testa criptografia e decriptografia básicas."""
    plaintext = "meu_token_secreto_123"

    # Criptografar
    encrypted = crypto_manager.encrypt(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)

    # Decriptografar
    decrypted = crypto_manager.decrypt(encrypted)
    assert decrypted == plaintext


def test_crypto_encrypt_produces_different_outputs(crypto_manager):
    """Testa que a mesma string produz outputs diferentes (IV aleatório)."""
    plaintext = "mesmo_conteudo"

    encrypted1 = crypto_manager.encrypt(plaintext)
    encrypted2 = crypto_manager.encrypt(plaintext)

    # Outputs diferentes
    assert encrypted1 != encrypted2

    # Mas ambos decriptografam para o mesmo valor
    assert crypto_manager.decrypt(encrypted1) == plaintext
    assert crypto_manager.decrypt(encrypted2) == plaintext


def test_crypto_encrypt_special_characters(crypto_manager):
    """Testa criptografia com caracteres especiais."""
    plaintext = "token!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

    encrypted = crypto_manager.encrypt(plaintext)
    decrypted = crypto_manager.decrypt(encrypted)

    assert decrypted == plaintext


def test_crypto_encrypt_unicode(crypto_manager):
    """Testa criptografia com Unicode."""
    plaintext = "token_com_acentuação_ñ_中文"

    encrypted = crypto_manager.encrypt(plaintext)
    decrypted = crypto_manager.decrypt(encrypted)

    assert decrypted == plaintext


def test_crypto_decrypt_invalid_fails(crypto_manager):
    """Testa erro ao decriptografar dados inválidos."""
    with pytest.raises(RuntimeError):
        crypto_manager.decrypt("invalid_ciphertext_data")


# ============================================================================
# TESTES DE PERSISTÊNCIA DE TOKENS
# ============================================================================


def test_save_tokens_new_account(test_db, auth_service, crypto_manager):
    """Testa salvamento de tokens para nova conta."""
    account_id = "account_123"
    access_token = "access_token_xyz"
    refresh_token = "refresh_token_abc"
    expires_in = 3600

    # Salvar tokens
    result = auth_service.save_tokens(
        account_id=account_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        owner_email="owner@example.com",
        owner_name="Test Owner",
        company_name="Test Company",
    )

    assert result is True

    # Verificar que foi salvo
    token_record = test_db.query(OAuthToken).filter_by(account_id=account_id).first()
    assert token_record is not None
    assert token_record.account_id == account_id

    # Verificar que tokens foram criptografados
    assert token_record.access_token != access_token
    assert token_record.refresh_token != refresh_token

    # Verificar que podem ser decriptografados
    decrypted_access = crypto_manager.decrypt(token_record.access_token)
    decrypted_refresh = crypto_manager.decrypt(token_record.refresh_token)

    assert decrypted_access == access_token
    assert decrypted_refresh == refresh_token

    # Verificar data de expiração
    assert token_record.expires_at > datetime.now(timezone.utc)


def test_save_tokens_update_existing(test_db, auth_service, crypto_manager):
    """Testa atualização de tokens para conta existente."""
    account_id = "account_456"

    # Primeiro save
    auth_service.save_tokens(
        account_id=account_id,
        access_token="old_access",
        refresh_token="old_refresh",
        expires_in=3600,
    )

    # Segundo save (update)
    new_access = "new_access_token"
    new_refresh = "new_refresh_token"

    result = auth_service.save_tokens(
        account_id=account_id,
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=7200,
    )

    assert result is True

    # Verificar que há apenas um registro
    records = test_db.query(OAuthToken).filter_by(account_id=account_id).all()
    assert len(records) == 1

    # Verificar que foi atualizado
    token_record = records[0]
    decrypted_access = crypto_manager.decrypt(token_record.access_token)
    decrypted_refresh = crypto_manager.decrypt(token_record.refresh_token)

    assert decrypted_access == new_access
    assert decrypted_refresh == new_refresh


def test_get_token(test_db, auth_service):
    """Testa busca de token."""
    account_id = "account_789"

    # Sem token
    result = auth_service.get_token(account_id)
    assert result is None

    # Adicionar token
    auth_service.save_tokens(
        account_id=account_id,
        access_token="test_access",
        refresh_token="test_refresh",
        expires_in=3600,
    )

    # Buscar token
    token_record = auth_service.get_token(account_id)
    assert token_record is not None
    assert token_record.account_id == account_id


def test_is_token_expired(test_db, auth_service):
    """Testa verificação de expiração de token."""
    account_id = "account_exp"

    # Salvar token com expiração no futuro
    auth_service.save_tokens(
        account_id=account_id,
        access_token="test",
        refresh_token="test",
        expires_in=3600,
    )

    token_record = auth_service.get_token(account_id)

    # Não deve estar expirado
    assert not auth_service.is_token_expired(token_record)

    # Simular expiração alterando expires_at
    token_record.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_db.commit()

    # Agora deve estar expirado
    assert auth_service.is_token_expired(token_record)


def test_save_creates_azul_account(test_db, auth_service):
    """Testa que save_tokens também cria registro em AzulAccount."""
    account_id = "account_new"
    owner_email = "owner@test.com"
    owner_name = "Test User"
    company_name = "Test Corp"

    auth_service.save_tokens(
        account_id=account_id,
        access_token="access",
        refresh_token="refresh",
        expires_in=3600,
        owner_email=owner_email,
        owner_name=owner_name,
        company_name=company_name,
    )

    # Verificar que AzulAccount foi criado
    account = test_db.query(AzulAccount).filter_by(account_id=account_id).first()
    assert account is not None
    assert account.owner_email == owner_email
    assert account.owner_name == owner_name
    assert account.company_name == company_name
    assert account.is_active == 1


def test_save_updates_azul_account(test_db, auth_service):
    """Testa atualização de AzulAccount quando tokens são atualizados."""
    account_id = "account_update"

    # Primeiro save
    auth_service.save_tokens(
        account_id=account_id,
        access_token="access1",
        refresh_token="refresh1",
        expires_in=3600,
        owner_name="Old Name",
        company_name="Old Company",
    )

    # Segundo save com novo nome
    auth_service.save_tokens(
        account_id=account_id,
        access_token="access2",
        refresh_token="refresh2",
        expires_in=3600,
        owner_name="New Name",
        company_name="New Company",
    )

    # Verificar que há apenas um account
    accounts = test_db.query(AzulAccount).filter_by(account_id=account_id).all()
    assert len(accounts) == 1

    # Verificar que foi atualizado
    account = accounts[0]
    assert account.owner_name == "New Name"
    assert account.company_name == "New Company"


def test_tokens_are_encrypted_at_rest(test_db, auth_service, crypto_manager):
    """
    Testa que tokens são armazenados criptografados no banco (at rest).
    Simula leitura direta do banco sem passar por crypto.decrypt().
    """
    account_id = "account_secret"
    access_token_plaintext = "super_secret_access_token_123"
    refresh_token_plaintext = "super_secret_refresh_token_456"

    auth_service.save_tokens(
        account_id=account_id,
        access_token=access_token_plaintext,
        refresh_token=refresh_token_plaintext,
        expires_in=3600,
    )

    # Buscar direto do banco (como um atacante faria)
    token_record = test_db.query(OAuthToken).filter_by(account_id=account_id).first()

    # Dados no banco não devem ser plaintexts
    assert token_record.access_token != access_token_plaintext
    assert token_record.refresh_token != refresh_token_plaintext

    # Dados no banco devem ser criptografados
    assert token_record.access_token.startswith("gAAAAAA")  # Fernet header
    assert token_record.refresh_token.startswith("gAAAAAA")  # Fernet header

    # Apenas com crypto.decrypt() conseguir ler
    decrypted_access = crypto_manager.decrypt(token_record.access_token)
    decrypted_refresh = crypto_manager.decrypt(token_record.refresh_token)

    assert decrypted_access == access_token_plaintext
    assert decrypted_refresh == refresh_token_plaintext
