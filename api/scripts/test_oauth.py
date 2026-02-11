#!/usr/bin/env python
"""
Script para simular o fluxo OAuth (útil para testes).
"""

import json

import httpx

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


def test_oauth_flow() -> None:
    """Testa o fluxo OAuth completo."""
    settings = get_settings()

    print("=" * 60)
    print("Teste de Fluxo OAuth Conta Azul")
    print("=" * 60)

    # 1. Gerar URL de autorização
    print("\n1. Gerando URL de autorização...")
    auth_url = (
        f"{settings.CONTA_AZUL_AUTH_URL}?"
        f"client_id={settings.CONTA_AZUL_CLIENT_ID}"
        f"&redirect_uri={settings.CONTA_AZUL_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=accounts.read+installments.read+receipts.read"
    )
    print(f"URL: {auth_url}")

    print("\n2. Abra a URL no navegador e autorize")
    print("3. Você será redirecionado para:")
    print(f"   {settings.CONTA_AZUL_REDIRECT_URI}?code=<code>&state=<state>")

    # 4. Simular callback (manual)
    code = input("\n4. Cole o código aqui: ").strip()

    if not code:
        print("Código não fornecido")
        return

    print("\n5. Trocando código por token...")

    try:
        response = httpx.post(
            settings.CONTA_AZUL_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.CONTA_AZUL_CLIENT_ID,
                "client_secret": settings.CONTA_AZUL_CLIENT_SECRET,
                "redirect_uri": settings.CONTA_AZUL_REDIRECT_URI,
            },
            timeout=30,
        )
        response.raise_for_status()

        token_data = response.json()

        print("\n6. Tokens recebidos:")
        print(
            json.dumps(
                {
                    "access_token": token_data.get("access_token")[:20] + "...",
                    "refresh_token": token_data.get("refresh_token")[:20] + "...",
                    "expires_in": token_data.get("expires_in"),
                },
                indent=2,
            )
        )

        # 7. Testar acesso à API
        print("\n7. Testando acesso à API...")
        access_token = token_data.get("access_token")

        api_response = httpx.get(
            f"{settings.CONTA_AZUL_API_BASE_URL}/v1/account",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        if api_response.status_code == 200:
            account_info = api_response.json()
            print("✅ Acesso bem-sucedido!")
            print(json.dumps(account_info, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Erro: {api_response.status_code}")
            print(api_response.text)

    except httpx.HTTPError as e:
        print(f"❌ Erro HTTP: {e}")


if __name__ == "__main__":
    test_oauth_flow()
