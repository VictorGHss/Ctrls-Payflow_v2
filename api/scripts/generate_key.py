#!/usr/bin/env python
"""
Script para gerar MASTER_KEY segura.
"""

import base64
import secrets


def generate_master_key() -> str:
    """Gera MASTER_KEY de 32 bytes (256 bits)."""
    key_bytes = secrets.token_bytes(32)
    key_b64 = base64.urlsafe_b64encode(key_bytes).decode("utf-8")
    return key_b64


if __name__ == "__main__":
    key = generate_master_key()
    print("=" * 60)
    print("MASTER_KEY Gerada com Sucesso")
    print("=" * 60)
    print(f"\nMASTER_KEY={key}\n")
    print("Adicionar ao arquivo .env")
    print("=" * 60)

