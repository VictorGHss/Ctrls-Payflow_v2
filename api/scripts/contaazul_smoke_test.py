#!/usr/bin/env python
"""
Script de smoke test para validar token da Conta Azul.
Testa se um access_token consegue fazer chamadas à API v2.

Uso:
    python scripts/contaazul_smoke_test.py <access_token>

ou com token do ambiente:
    export CONTA_AZUL_ACCESS_TOKEN=<token>
    python scripts/contaazul_smoke_test.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Adicionar diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from app.logging import setup_logging

logger = setup_logging(__name__)

# Endpoint para smoke test (deve existir e estar documentado)
SMOKE_TEST_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=1"


async def smoke_test_token(access_token: str) -> bool:
    """
    Testa se o access_token funciona na API da Conta Azul.

    Args:
        access_token: Token de acesso a ser testado

    Returns:
        True se o token é válido, False caso contrário
    """
    # Mascarar token para log seguro
    token_preview = f"{access_token[:8]}...{access_token[-4:]}" if len(access_token) > 12 else "***"

    logger.info("=" * 80)
    logger.info("🧪 SMOKE TEST - Conta Azul API v2")
    logger.info("=" * 80)
    logger.info(f"🔑 Token: {token_preview}")
    logger.info(f"📍 Endpoint: {SMOKE_TEST_URL}")
    logger.info("")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                SMOKE_TEST_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            logger.info(f"📊 Status Code: {response.status_code}")
            logger.info(f"📋 Content-Type: {response.headers.get('content-type', 'N/A')}")

            if "x-ratelimit-remaining" in response.headers:
                logger.info(f"🚦 Rate Limit Remaining: {response.headers['x-ratelimit-remaining']}")

            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ SUCESSO - Token válido!")
                logger.info(f"📦 Response preview: {str(data)[:200]}...")
                logger.info("")
                logger.info("=" * 80)
                logger.info("✅ SMOKE TEST PASSOU")
                logger.info("=" * 80)
                return True

            elif response.status_code == 401:
                logger.error(f"❌ FALHA - Token inválido ou expirado")
                try:
                    error_data = response.json()
                    logger.error(f"📋 Error: {error_data}")
                except Exception:
                    logger.error(f"📋 Response: {response.text[:200]}")
                logger.info("")
                logger.info("=" * 80)
                logger.info("❌ SMOKE TEST FALHOU")
                logger.info("=" * 80)
                return False

            elif response.status_code == 404:
                logger.error(f"❌ FALHA - Endpoint não encontrado")
                logger.error(f"📋 Response: {response.text[:200]}")
                logger.error(f"⚠️  Verifique se a URL está correta: {SMOKE_TEST_URL}")
                logger.info("")
                logger.info("=" * 80)
                logger.info("❌ SMOKE TEST FALHOU")
                logger.info("=" * 80)
                return False

            else:
                logger.error(f"❌ FALHA - Status inesperado: {response.status_code}")
                logger.error(f"📋 Response: {response.text[:200]}")
                logger.info("")
                logger.info("=" * 80)
                logger.info("❌ SMOKE TEST FALHOU")
                logger.info("=" * 80)
                return False

    except httpx.TimeoutException:
        logger.error("❌ TIMEOUT - A API não respondeu em 30 segundos")
        logger.info("=" * 80)
        logger.info("❌ SMOKE TEST FALHOU")
        logger.info("=" * 80)
        return False

    except Exception as e:
        logger.error(f"❌ ERRO - Exceção ao fazer requisição: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.info("=" * 80)
        logger.info("❌ SMOKE TEST FALHOU")
        logger.info("=" * 80)
        return False


def main():
    """Função principal."""
    # Obter token da linha de comando ou variável de ambiente
    if len(sys.argv) > 1:
        access_token = sys.argv[1]
    else:
        access_token = os.getenv("CONTA_AZUL_ACCESS_TOKEN")

    if not access_token:
        print("❌ ERRO: Access token não fornecido!")
        print("")
        print("Uso:")
        print("  python scripts/contaazul_smoke_test.py <access_token>")
        print("")
        print("ou:")
        print("  export CONTA_AZUL_ACCESS_TOKEN=<token>")
        print("  python scripts/contaazul_smoke_test.py")
        sys.exit(1)

    # Executar smoke test
    success = asyncio.run(smoke_test_token(access_token))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

