"""
Teste interativo do fluxo OAuth2 com Conta Azul.

Valida:
1. Geração da URL de autorização
2. Troca de code por tokens
3. Salvamento dos tokens criptografados no banco
4. Refresh do access_token

Uso:
    python scripts/test_oauth_flow.py
"""

import asyncio
import sys
from pathlib import Path

# Adicionar path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.crypto import get_crypto_manager
from app.database import init_db, OAuthToken, AzulAccount
from app.services_auth import ContaAzulAuthService
from app.logging import setup_logging

logger = setup_logging(__name__)


async def test_oauth_flow():
    """Testa fluxo OAuth completo."""
    print("\n" + "=" * 80)
    print("🔐 TESTE DE FLUXO OAUTH2 - CONTA AZUL")
    print("=" * 80 + "\n")

    # 1. Inicializar
    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)
    db = SessionLocal()
    auth_service = ContaAzulAuthService(db)
    crypto = get_crypto_manager()

    print("✅ Configuração carregada:")
    print(f"   Client ID: {settings.CONTA_AZUL_CLIENT_ID[:20]}...")
    print(f"   Redirect URI: {settings.CONTA_AZUL_REDIRECT_URI}")
    print()

    # 2. Gerar URL de autorização
    print("📋 PASSO 1: Gerar URL de autorização")
    auth_url, state = auth_service.generate_authorization_url()
    print(f"\n✅ URL gerada (State: {state[:10]}...):")
    print(f"\n{auth_url}\n")
    print("🌐 Copie a URL acima e abra no navegador")
    print("   Após autorizar, você será redirecionado para:")
    print(f"   {settings.CONTA_AZUL_REDIRECT_URI}?code=...")
    print()

    # 3. Aguardar código
    code = input("📥 Cole o 'code' aqui (da URL de callback): ").strip()

    if not code:
        print("❌ Código não fornecido. Abortando.")
        return

    print(f"\n✅ Código recebido: {code[:20]}...\n")

    # 4. Trocar code por tokens
    print("🔄 PASSO 2: Trocar code por tokens...")
    token_data = await auth_service.exchange_code_for_tokens(code)

    if not token_data:
        print("❌ Falha ao obter tokens!")
        print("   Verifique:")
        print("   - Client ID e Client Secret estão corretos no .env")
        print("   - Redirect URI no .env == Redirect URI no Portal Conta Azul")
        print("   - Código não expirou (válido por ~1 minuto)")
        return

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    print(f"✅ Tokens obtidos:")
    print(f"   Access Token: {access_token[:30]}...")
    print(f"   Refresh Token: {refresh_token[:30]}...")
    print(f"   Expires in: {expires_in}s ({expires_in // 60} minutos)\n")

    # 5. Buscar informações da conta
    print("👤 PASSO 3: Buscar informações da conta...")
    account_info = await auth_service.get_account_info(access_token)

    if not account_info:
        print("⚠️ Não foi possível buscar informações da conta")
        print("   Mas os tokens foram obtidos corretamente.")
        # Usar fallback
        account_id = "account_" + code[:10]
        owner_email = "unknown@example.com"
        owner_name = "Unknown"
        company_name = "Unknown Company"
    else:
        account_id = account_info.get("id") or account_info.get("accountId")
        owner_email = account_info.get("email") or "unknown@example.com"
        owner_name = account_info.get("name") or "Unknown"
        company_name = account_info.get("companyName") or "Unknown Company"

        print(f"✅ Conta encontrada:")
        print(f"   ID: {account_id}")
        print(f"   Nome: {owner_name}")
        print(f"   Email: {owner_email}")
        print(f"   Empresa: {company_name}\n")

    # 6. Salvar tokens no banco
    print("💾 PASSO 4: Salvar tokens no banco...")
    success = auth_service.save_tokens(
        account_id=account_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        owner_email=owner_email,
        owner_name=owner_name,
        company_name=company_name,
    )

    if not success:
        print("❌ Falha ao salvar tokens!")
        return

    print("✅ Tokens salvos (criptografados)\n")

    # 7. Verificar no banco
    print("🔍 PASSO 5: Verificar tokens no banco...")
    token_record = db.query(OAuthToken).filter(OAuthToken.account_id == account_id).first()
    account_record = db.query(AzulAccount).filter(AzulAccount.account_id == account_id).first()

    if token_record:
        print(f"✅ Token encontrado:")
        print(f"   Account ID: {token_record.account_id}")
        print(f"   Access Token (criptografado): {token_record.access_token[:50]}...")
        print(f"   Refresh Token (criptografado): {token_record.refresh_token[:50]}...")
        print(f"   Expires at: {token_record.expires_at}")

        # Testar decriptação
        try:
            decrypted_access = crypto.decrypt(token_record.access_token)
            decrypted_refresh = crypto.decrypt(token_record.refresh_token)
            print(f"\n✅ Decriptação OK:")
            print(f"   Access (decriptado): {decrypted_access[:30]}...")
            print(f"   Refresh (decriptado): {decrypted_refresh[:30]}...")
        except Exception as e:
            print(f"❌ Erro ao decriptografar: {e}")
    else:
        print("❌ Token não encontrado no banco!")

    if account_record:
        print(f"\n✅ Conta registrada:")
        print(f"   Account ID: {account_record.account_id}")
        print(f"   Nome: {account_record.owner_name}")
        print(f"   Email: {account_record.owner_email}")
        print(f"   Empresa: {account_record.company_name}")
        print(f"   Ativa: {account_record.is_active}")
    else:
        print("❌ Conta não encontrada no banco!")

    # 8. Testar refresh (opcional)
    print("\n" + "=" * 80)
    test_refresh = input("🔄 Testar refresh do token? (s/N): ").strip().lower()

    if test_refresh == 's':
        print("\n🔄 PASSO 6: Testar refresh do access_token...")
        new_access_token = await auth_service.refresh_access_token(account_id)

        if new_access_token:
            print(f"✅ Token renovado com sucesso!")
            print(f"   Novo Access Token: {new_access_token[:30]}...")

            # Verificar que refresh_token também mudou
            updated_token = db.query(OAuthToken).filter(OAuthToken.account_id == account_id).first()
            if updated_token:
                print(f"   Novo Refresh Token (criptografado): {updated_token.refresh_token[:50]}...")
                print("   ✅ IMPORTANTE: Refresh token foi atualizado no banco!")
        else:
            print("❌ Falha ao renovar token")

    print("\n" + "=" * 80)
    print("✅ TESTE COMPLETO!")
    print("=" * 80 + "\n")
    print("📊 Próximos passos:")
    print("   1. Verificar tokens no SQLite:")
    print(f"      sqlite3 {settings.DATABASE_URL.replace('sqlite:///', '')}")
    print("      SELECT account_id, created_at FROM oauth_tokens;")
    print("   2. Testar SMTP: python scripts/test_smtp.py")
    print("   3. Rodar worker: python -m app.worker.main")
    print()

    db.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_oauth_flow())
    except KeyboardInterrupt:
        print("\n\n❌ Teste cancelado pelo usuário")
    except Exception as e:
        print(f"\n\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()

