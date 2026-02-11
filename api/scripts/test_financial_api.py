"""
Script de teste para validar endpoint de contas a receber.

Testa o novo endpoint /v1/financeiro/eventos-financeiros/contas-a-receber/buscar

Uso:
    python scripts/test_financial_api.py <access_token>
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Adicionar diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging import setup_logging
from app.worker.conta_azul_financial_client import ContaAzulFinancialClient

logger = setup_logging(__name__)


async def test_financial_api(access_token: str):
    """
    Testa API de contas a receber.

    Args:
        access_token: Token de acesso OAuth2
    """
    logger.info("=" * 80)
    logger.info("🧪 TESTE - API FINANCEIRO CONTA AZUL")
    logger.info("=" * 80)

    # Criar client
    client = ContaAzulFinancialClient(access_token)

    # Testar busca de contas a receber
    logger.info("\n1️⃣ Testando busca de contas a receber...")
    logger.info("-" * 80)

    try:
        # Buscar contas dos últimos 30 dias
        changed_since = datetime.now(timezone.utc) - timedelta(days=30)

        logger.info(f"📅 Buscando desde: {changed_since.isoformat()}")
        logger.info(f"🔍 Status: RECEBIDO")

        receivables = await client.get_receivables(
            account_id="test_account",
            changed_since=changed_since,
            status="received"  # Será convertido para RECEBIDO
        )

        logger.info(f"\n✅ Sucesso! Encontradas {len(receivables)} conta(s) a receber")

        if receivables:
            logger.info("\n📋 Primeira conta encontrada:")
            first = receivables[0]
            logger.info(f"   ID: {first.get('id', 'N/A')}")
            logger.info(f"   Valor: {first.get('valor', 'N/A')}")
            logger.info(f"   Status: {first.get('situacao', 'N/A')}")
            logger.info(f"   Data: {first.get('dataVencimento', 'N/A')}")

            # Testar busca de detalhes
            if first.get('id'):
                logger.info("\n2️⃣ Testando busca de detalhes...")
                logger.info("-" * 80)

                try:
                    details = await client.get_receivable_details(first['id'])
                    logger.info(f"✅ Detalhes obtidos com sucesso")
                    logger.info(f"   Campos: {list(details.keys())}")
                except Exception as e:
                    logger.error(f"❌ Erro ao buscar detalhes: {e}")
        else:
            logger.info("ℹ️  Nenhuma conta a receber encontrada no período")
            logger.info("   Isso pode ser normal se não houver movimentação")

        logger.info("\n" + "=" * 80)
        logger.info("✅ TESTE CONCLUÍDO COM SUCESSO")
        logger.info("=" * 80)
        return True

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error(f"❌ TESTE FALHOU: {type(e).__name__}")
        logger.error("=" * 80)
        logger.error(f"Erro: {e}")

        import traceback
        logger.error("\nStack trace:")
        logger.error(traceback.format_exc())

        return False


def main():
    """Função principal."""
    if len(sys.argv) < 2:
        print("❌ ERRO: Access token não fornecido!")
        print("")
        print("Uso:")
        print("  python scripts/test_financial_api.py <access_token>")
        print("")
        print("Ou obter token do banco:")
        print("  cd api")
        print("  sqlite3 data/payflow.db")
        print("  SELECT access_token FROM oauth_tokens;")
        sys.exit(1)

    access_token = sys.argv[1]

    # Se o token estiver criptografado, avisar
    if not access_token.startswith("eyJ"):
        print("⚠️  Token parece estar criptografado!")
        print("Este script espera o token em plaintext (JWT).")
        print("")
        print("Para descriptografar:")
        print("  1. Use o crypto manager do app")
        print("  2. Ou obtenha um token novo via OAuth flow")
        sys.exit(1)

    # Executar teste
    success = asyncio.run(test_financial_api(access_token))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

