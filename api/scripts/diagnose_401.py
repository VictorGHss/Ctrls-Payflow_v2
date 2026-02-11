"""
Script de diagnóstico para erro 401 ao buscar informações da conta.

Execução:
    python scripts/diagnose_401.py

Verifica:
- URLs de autorização e token (oficiais vs. incorretos)
- Formato do Authorization header
- Validade do access_token
- Resposta da API /company
- Scopes e permissões
"""

import asyncio
import base64
import sys
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


class OAuth401Diagnostics:
    """Diagnóstico completo do erro 401."""

    def __init__(self):
        self.settings = get_settings()
        self.issues = []
        self.warnings = []

    def check_urls(self):
        """Verifica se as URLs estão corretas."""
        logger.info("=" * 80)
        logger.info("🔍 VERIFICANDO URLs DO OAUTH2")
        logger.info("=" * 80)

        # URLs corretas oficiais
        correct_authorize = "https://auth.contaazul.com/login"
        correct_token = "https://auth.contaazul.com/oauth2/token"
        correct_api = "https://api-v2.contaazul.com"

        # URLs INCORRETAS comuns
        wrong_authorize = "https://auth.contaazul.com/login?"  # com ? no final
        wrong_api_v1 = "https://api.contaazul.com"  # API v1 antiga
        wrong_api_hyphen = "https://api.conta-azul.com"  # com hífen

        logger.info(f"📍 Authorize URL configurada:")
        logger.info(f"   {self.settings.CONTA_AZUL_AUTH_URL}")

        if self.settings.CONTA_AZUL_AUTH_URL != correct_authorize:
            self.issues.append(
                f"❌ CONTA_AZUL_AUTH_URL incorreta! "
                f"Use: {correct_authorize}"
            )
        else:
            logger.info("   ✅ Correto")

        logger.info(f"\n📍 Token URL configurada:")
        logger.info(f"   {self.settings.CONTA_AZUL_TOKEN_URL}")

        if self.settings.CONTA_AZUL_TOKEN_URL != correct_token:
            self.issues.append(
                f"❌ CONTA_AZUL_TOKEN_URL incorreta! "
                f"Use: {correct_token}"
            )
        else:
            logger.info("   ✅ Correto")

        logger.info(f"\n📍 API Base URL configurada:")
        logger.info(f"   {self.settings.CONTA_AZUL_API_BASE_URL}")

        if self.settings.CONTA_AZUL_API_BASE_URL != correct_api:
            self.issues.append(
                f"❌ CONTA_AZUL_API_BASE_URL incorreta! "
                f"Use: {correct_api}"
            )
        else:
            logger.info("   ✅ Correto")

    def check_credentials_format(self):
        """Verifica formato das credenciais."""
        logger.info("\n" + "=" * 80)
        logger.info("🔐 VERIFICANDO CREDENCIAIS")
        logger.info("=" * 80)

        client_id = self.settings.CONTA_AZUL_CLIENT_ID
        client_secret = self.settings.CONTA_AZUL_CLIENT_SECRET

        logger.info(f"📋 Client ID: {client_id[:10]}...{client_id[-4:]}")
        logger.info(f"📋 Client Secret: {client_secret[:4]}...{client_secret[-4:]}")

        # Verificar formato básico
        if len(client_id) < 20:
            self.warnings.append("⚠️  Client ID parece curto demais")

        if len(client_secret) < 20:
            self.warnings.append("⚠️  Client Secret parece curto demais")

        # Testar Base64 encoding
        credentials = f"{client_id}:{client_secret}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        logger.info(f"\n📝 Authorization Basic Header:")
        logger.info(f"   Basic {b64_credentials[:20]}...{b64_credentials[-10:]}")

    async def test_token_endpoint(self, code: str = "test_code"):
        """Testa endpoint de token (vai falhar, mas mostra o erro)."""
        logger.info("\n" + "=" * 80)
        logger.info("🧪 TESTANDO TOKEN ENDPOINT (com code fake)")
        logger.info("=" * 80)

        credentials = f"{self.settings.CONTA_AZUL_CLIENT_ID}:{self.settings.CONTA_AZUL_CLIENT_SECRET}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.settings.CONTA_AZUL_TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.settings.CONTA_AZUL_REDIRECT_URI,
                    },
                    headers={
                        "Authorization": f"Basic {b64_credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                logger.info(f"📊 Status Code: {response.status_code}")
                logger.info(f"📊 Response Headers:")
                for key, value in response.headers.items():
                    if key.lower() not in ["set-cookie", "authorization"]:
                        logger.info(f"   {key}: {value}")

                logger.info(f"\n📊 Response Body:")
                try:
                    body = response.json()
                    logger.info(f"   {body}")

                    if response.status_code == 401:
                        self.issues.append(
                            "❌ Token endpoint retornou 401 - "
                            "Credenciais inválidas!"
                        )
                    elif response.status_code == 400:
                        error = body.get("error", "")
                        if error == "invalid_grant":
                            logger.info("   ℹ️  Esperado: code fake usado para teste")
                        else:
                            self.warnings.append(
                                f"⚠️  Erro inesperado: {error}"
                            )
                except Exception:
                    logger.info(f"   {response.text}")

        except Exception as e:
            logger.error(f"❌ Erro na requisição: {e}")
            self.issues.append(f"Erro ao testar token endpoint: {e}")

    async def test_api_me_with_fake_token(self):
        """Testa endpoint /company com token fake (para ver erro)."""
        logger.info("\n" + "=" * 80)
        logger.info("🧪 TESTANDO API /company (com token fake)")
        logger.info("=" * 80)

        fake_token = "fake_token_for_testing"
        api_url = f"{self.settings.CONTA_AZUL_API_BASE_URL}/company"

        logger.info(f"📍 URL: {api_url}")
        logger.info(f"🔑 Authorization: Bearer {fake_token}")

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    api_url,
                    headers={"Authorization": f"Bearer {fake_token}"},
                )

                logger.info(f"\n📊 Status Code: {response.status_code}")
                logger.info(f"📊 Response Headers:")
                for key, value in response.headers.items():
                    if key.lower() not in ["set-cookie", "authorization"]:
                        logger.info(f"   {key}: {value}")

                logger.info(f"\n📊 Response Body:")
                try:
                    body = response.json()
                    logger.info(f"   {body}")

                    if response.status_code == 401:
                        error = body.get("error", "")
                        error_desc = body.get("error_description", "")
                        message = body.get("message", "")

                        logger.info("\n📋 Análise do erro 401:")
                        logger.info(f"   Error: {error}")
                        logger.info(f"   Description: {error_desc}")
                        logger.info(f"   Message: {message}")

                        if "invalid_token" in str(error).lower():
                            logger.info("   ℹ️  Esperado: token fake usado")
                        elif "insufficient" in str(error_desc).lower():
                            self.issues.append(
                                "❌ Scope insuficiente! "
                                "Verificar permissões do app no Portal Conta Azul"
                            )
                        elif "audience" in str(error_desc).lower():
                            self.issues.append(
                                "❌ Audience incorreta! "
                                "Token pode ser para ambiente errado"
                            )

                except Exception:
                    logger.info(f"   {response.text}")

        except Exception as e:
            logger.error(f"❌ Erro na requisição: {e}")
            self.issues.append(f"Erro ao testar API /company: {e}")

    def check_scopes(self):
        """Verifica scopes configurados."""
        logger.info("\n" + "=" * 80)
        logger.info("🎯 VERIFICANDO SCOPES")
        logger.info("=" * 80)

        # Scopes esperados (conforme serviço auth)
        from app.services_auth import ContaAzulAuthService
        expected_scopes = ContaAzulAuthService.SCOPES

        logger.info(f"📋 Scopes configurados no código:")
        logger.info(f"   {expected_scopes}")

        logger.info(f"\n📋 Scopes esperados pela Conta Azul:")
        logger.info(f"   openid profile aws.cognito.signin.user.admin")

        if expected_scopes != "openid profile aws.cognito.signin.user.admin":
            self.warnings.append(
                "⚠️  Scopes podem estar incorretos. "
                "Verificar documentação da Conta Azul"
            )

        logger.info(f"\n💡 IMPORTANTE:")
        logger.info(f"   No Portal Conta Azul (portal.contaazul.com):")
        logger.info(f"   - Verificar se o app tem permissões de LEITURA")
        logger.info(f"   - Verificar se o app está em PRODUÇÃO (não sandbox)")
        logger.info(f"   - Verificar se a conta autorizada tem acesso aos dados")

    def print_summary(self):
        """Imprime resumo dos problemas encontrados."""
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMO DO DIAGNÓSTICO")
        logger.info("=" * 80)

        if not self.issues and not self.warnings:
            logger.info("✅ Nenhum problema detectado!")
            logger.info("\n💡 Se ainda há erro 401, verifique:")
            logger.info("   1. Permissões do app no Portal Conta Azul")
            logger.info("   2. Se o app está em PRODUÇÃO (não sandbox)")
            logger.info("   3. Se a conta tem dados disponíveis")
            logger.info("   4. Logs detalhados durante fluxo real")
            return

        if self.issues:
            logger.info(f"\n🚨 PROBLEMAS CRÍTICOS ({len(self.issues)}):")
            for issue in self.issues:
                logger.info(f"   {issue}")

        if self.warnings:
            logger.info(f"\n⚠️  AVISOS ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.info(f"   {warning}")

        logger.info("\n" + "=" * 80)

    async def run(self):
        """Executa todos os diagnósticos."""
        logger.info("\n" + "=" * 80)
        logger.info("🏥 DIAGNÓSTICO DE ERRO 401 - OAUTH2 CONTA AZUL")
        logger.info("=" * 80)

        self.check_urls()
        self.check_credentials_format()
        await self.test_token_endpoint()
        await self.test_api_me_with_fake_token()
        self.check_scopes()
        self.print_summary()


async def main():
    """Função principal."""
    diagnostics = OAuth401Diagnostics()
    await diagnostics.run()


if __name__ == "__main__":
    asyncio.run(main())

