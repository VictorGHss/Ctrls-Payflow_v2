"""
Testes para criptografia e decriptografia.
"""

import base64

import pytest

from app.crypto import CryptoManager


@pytest.fixture
def crypto_manager():
    """Cria um CryptoManager com chave de teste."""
    # Gerar 32 bytes aleatórios e codificar em base64
    import secrets

    key = base64.urlsafe_b64encode(secrets.token_bytes(32))

    # Mock do settings
    class MockSettings:
        MASTER_KEY = key.decode("utf-8")

    import app.config

    original_get_settings = app.config.get_settings
    app.config.get_settings = lambda: MockSettings()

    try:
        return CryptoManager()
    finally:
        app.config.get_settings = original_get_settings


def test_encrypt_decrypt(crypto_manager):
    """Testa criptografia e decriptografia básicas."""
    plaintext = "meu_token_secreto_123"

    # Criptografar
    encrypted = crypto_manager.encrypt(plaintext)
    assert encrypted != plaintext
    assert isinstance(encrypted, str)

    # Decriptografar
    decrypted = crypto_manager.decrypt(encrypted)
    assert decrypted == plaintext


def test_encrypt_different_outputs(crypto_manager):
    """Testa que a mesma string gera saídas diferentes (IV aleatório)."""
    plaintext = "mesmo_conteudo"

    encrypted1 = crypto_manager.encrypt(plaintext)
    encrypted2 = crypto_manager.encrypt(plaintext)

    # Outputs diferentes (Fernet usa IV aleatório)
    assert encrypted1 != encrypted2

    # Mas ambos decriptografam para o mesmo valor
    assert crypto_manager.decrypt(encrypted1) == plaintext
    assert crypto_manager.decrypt(encrypted2) == plaintext


def test_decrypt_invalid_ciphertext(crypto_manager):
    """Testa erro ao decriptografar dados inválidos."""
    with pytest.raises(RuntimeError):
        crypto_manager.decrypt("invalid_ciphertext_data")


def test_encrypt_special_characters(crypto_manager):
    """Testa criptografia com caracteres especiais."""
    plaintext = "token!@#$%^&*()_+-=[]{}|;:',.<>?/~`"

    encrypted = crypto_manager.encrypt(plaintext)
    decrypted = crypto_manager.decrypt(encrypted)

    assert decrypted == plaintext


def test_encrypt_unicode(crypto_manager):
    """Testa criptografia com Unicode."""
    plaintext = "token_com_acentuação_ñ_中文"

    encrypted = crypto_manager.encrypt(plaintext)
    decrypted = crypto_manager.decrypt(encrypted)

    assert decrypted == plaintext
