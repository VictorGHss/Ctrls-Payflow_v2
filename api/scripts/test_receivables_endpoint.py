#!/usr/bin/env python3
"""
Script de teste rápido para endpoint de contas a receber.

Faz 1 chamada real ao endpoint correto e exibe status + preview do JSON.

Uso:
    python scripts/test_receivables_endpoint.py <access_token>

Exemplo:
    python scripts/test_receivables_endpoint.py eyJhbGc...
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

import httpx


async def test_receivables_endpoint(access_token: str):
    """
    Testa endpoint de contas a receber com 1 chamada real.

    Args:
        access_token: Token JWT (plaintext, não criptografado)
    """
    from zoneinfo import ZoneInfo

    # Timezone São Paulo
    sp_tz = ZoneInfo("America/Sao_Paulo")

    # Preparar parâmetros
    now_utc = datetime.now(timezone.utc)
    now_sp = now_utc.astimezone(sp_tz)
    changed_since = now_utc - timedelta(days=30)
    changed_since_sp = changed_since.astimezone(sp_tz)

    params = {
        "data_alteracao_de": changed_since_sp.strftime("%Y-%m-%dT%H:%M:%S"),
        "data_alteracao_ate": now_sp.strftime("%Y-%m-%dT%H:%M:%S"),
        "data_vencimento_de": (changed_since - timedelta(days=365)).date().strftime("%Y-%m-%d"),
        "data_vencimento_ate": (now_utc + timedelta(days=1)).date().strftime("%Y-%m-%d"),
        "status": ["RECEBIDO", "RECEBIDO_PARCIAL"],
        "pagina": 1,
        "tamanho_pagina": 10,  # Apenas 10 para teste rápido
    }

    base_url = "https://api-v2.contaazul.com"
    endpoint = "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"
    url = f"{base_url}{endpoint}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    print("=" * 80)
    print("🧪 TESTE - ENDPOINT DE CONTAS A RECEBER")
    print("=" * 80)
    print(f"\n📍 URL: {url}")
    print(f"\n📋 Parâmetros:")
    for key, value in params.items():
        print(f"   {key}: {value}")
    print(f"\n🔑 Token: {access_token[:20]}...{access_token[-10:]}")
    print("\n" + "=" * 80)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                params=params,
                headers=headers,
            )

            status_code = response.status_code
            print(f"\n✅ Status Code: {status_code}")

            if status_code == 200:
                data = response.json()
                print(f"\n📊 Response JSON (preview):")
                print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
                print("\n...")

                # Extrair info útil
                itens = data.get("itens", []) or data.get("contas", []) or []
                total = data.get("total", len(itens))

                print(f"\n📈 Resumo:")
                print(f"   Total de itens nesta página: {len(itens)}")
                print(f"   Total geral: {total}")

                if itens:
                    print(f"\n📋 Primeira conta:")
                    first = itens[0]
                    print(f"   ID: {first.get('id', 'N/A')}")
                    print(f"   Valor: {first.get('valor', 'N/A')}")
                    print(f"   Status: {first.get('status_traduzido', first.get('situacao', 'N/A'))}")
                    print(f"   Vencimento: {first.get('data_vencimento', 'N/A')}")

                print("\n✅ TESTE BEM-SUCEDIDO!")

            else:
                print(f"\n❌ Erro HTTP {status_code}")
                print(f"\n📋 Response Body:")
                print(response.text[:1000])

            print("\n" + "=" * 80)

    except httpx.HTTPError as e:
        print(f"\n❌ Erro de HTTP: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)


def main():
    """Função principal."""
    if len(sys.argv) < 2:
        print("❌ ERRO: Access token não fornecido!")
        print("")
        print("Uso:")
        print("  python scripts/test_receivables_endpoint.py <access_token>")
        print("")
        print("O token deve ser JWT (plaintext), começando com 'eyJ'")
        print("")
        print("Para obter um token:")
        print("  1. Faça login via /connect")
        print("  2. Extraia o token do banco (descriptografado)")
        sys.exit(1)

    access_token = sys.argv[1]

    if not access_token.startswith("eyJ"):
        print("⚠️  Aviso: Token não parece ser JWT!")
        print("Esperado: token começando com 'eyJ'")
        print("Recebido: ", access_token[:20], "...")
        print("")
        response = input("Continuar mesmo assim? (s/N): ")
        if response.lower() != "s":
            sys.exit(1)

    asyncio.run(test_receivables_endpoint(access_token))


if __name__ == "__main__":
    main()

