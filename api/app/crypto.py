"""
Criptografia de segredos em repouso.
"""

import base64
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from app.config import get_settings


class CryptoManager:
    """Gerencia criptografia de tokens e segredos."""

    def __init__(self):
        """Inicializa com MASTER_KEY."""
        settings = get_settings()
        try:
            self._key = base64.urlsafe_b64decode(settings.MASTER_KEY)
            if len(self._key) != 32:
                raise ValueError("MASTER_KEY deve ser 32 bytes (base64 encoded)")
        except Exception as e:
            raise RuntimeError(f"Erro ao decodificar MASTER_KEY: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Criptografa plaintext.

        Args:
            plaintext: Texto a criptografar

        Returns:
            Token criptografado em base64
        """
        if not isinstance(plaintext, str):
            plaintext = str(plaintext)

        # Usar Fernet (AES 128 + HMAC)
        f = Fernet(base64.urlsafe_b64encode(self._key))
        encrypted = f.encrypt(plaintext.encode("utf-8"))
        return encrypted.decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """
        Decriptografa ciphertext.

        Args:
            ciphertext: Token criptografado em base64

        Returns:
            Plaintext decriptografado
        """
        try:
            f = Fernet(base64.urlsafe_b64encode(self._key))
            plaintext = f.decrypt(ciphertext.encode("utf-8"))
            return plaintext.decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Erro ao decriptografar: {e}")


def get_crypto_manager() -> CryptoManager:
    """Retorna instância do gerenciador de criptografia."""
    return CryptoManager()

