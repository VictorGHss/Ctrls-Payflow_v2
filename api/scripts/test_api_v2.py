#!/usr/bin/env python
"""
Script para testar a correção do endpoint da API v2 da Conta Azul.
Verifica se as URLs corretas estão configuradas e testa o endpoint /company.
"""

import asyncio
import sys
from pathlib import Path

# Adicionar o diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


def test_configuration():
    """Testa se as configurações estão corretas."""
    settings = get_settings()

    logger.info("=" * 80)
    logger.info("🔍 VERIFICANDO CONFIGURAÇÃO DA API v2")
    logger.info("=" * 80)

    # URLs esperadas
    expected_api_base = "https://api-v2.contaazul.com"
    expected_auth_base = "https://auth.contaazul.com"
    expected_auth_url = "https://auth.contaazul.com/login"
    expected_token_url = "https://auth.contaazul.com/oauth2/token"

    issues = []

    # Verificar API Base URL
    logger.info(f"\n📍 API Base URL:")
    logger.info(f"   Esperado: {expected_api_base}")
    logger.info(f"   Atual:    {settings.CONTA_AZUL_API_BASE_URL}")

    if settings.CONTA_AZUL_API_BASE_URL == expected_api_base:
        logger.info("   ✅ CORRETO")
    else:
        logger.error("   ❌ INCORRETO!")
        issues.append("API Base URL incorreta")

    # Verificar Auth Base URL
    if hasattr(settings, 'CONTA_AZUL_AUTH_BASE_URL'):
        logger.info(f"\n📍 Auth Base URL:")
        logger.info(f"   Esperado: {expected_auth_base}")
        logger.info(f"   Atual:    {settings.CONTA_AZUL_AUTH_BASE_URL}")

        if settings.CONTA_AZUL_AUTH_BASE_URL == expected_auth_base:
            logger.info("   ✅ CORRETO")
        else:
            logger.error("   ❌ INCORRETO!")
            issues.append("Auth Base URL incorreta")

    # Verificar Auth URL
    logger.info(f"\n📍 Auth URL:")
    logger.info(f"   Esperado: {expected_auth_url}")
    logger.info(f"   Atual:    {settings.CONTA_AZUL_AUTH_URL}")

    if settings.CONTA_AZUL_AUTH_URL == expected_auth_url:
        logger.info("   ✅ CORRETO")
    else:
        logger.error("   ❌ INCORRETO!")
        issues.append("Auth URL incorreta")

    # Verificar Token URL
    logger.info(f"\n📍 Token URL:")
    logger.info(f"   Esperado: {expected_token_url}")
    logger.info(f"   Atual:    {settings.CONTA_AZUL_TOKEN_URL}")

    if settings.CONTA_AZUL_TOKEN_URL == expected_token_url:
        logger.info("   ✅ CORRETO")
    else:
        logger.error("   ❌ INCORRETO!")
        issues.append("Token URL incorreta")

    logger.info("\n" + "=" * 80)

    if issues:
        logger.error(f"❌ {len(issues)} problema(s) encontrado(s):")
        for issue in issues:
            logger.error(f"   - {issue}")
        return False
    else:
        logger.info("✅ Todas as configurações estão corretas!")
        return True


def test_service_urls():
    """Testa se os serviços estão usando as URLs corretas."""
    logger.info("\n" + "=" * 80)
    logger.info("🔍 VERIFICANDO URLs NOS SERVIÇOS")
    logger.info("=" * 80)

    from app.services_auth import ContaAzulAuthService
    from app.worker.conta_azul_financial_client import ContaAzulFinancialClient

    issues = []

    # Verificar ContaAzulAuthService
    logger.info(f"\n📍 ContaAzulAuthService.API_URL:")
    logger.info(f"   {ContaAzulAuthService.API_URL}")

    if "api-v2.contaazul.com" in ContaAzulAuthService.API_URL:
        logger.info("   ✅ Usando API v2")
    else:
        logger.error("   ❌ Não está usando API v2!")
        issues.append("ContaAzulAuthService usando API antiga")

    if "/company" in ContaAzulAuthService.API_URL:
        logger.info("   ✅ Usando endpoint /company")
    elif "/v1/me" in ContaAzulAuthService.API_URL:
        logger.error("   ❌ Ainda usando endpoint legado /v1/me!")
        issues.append("ContaAzulAuthService usando endpoint legado")

    # Verificar ContaAzulFinancialClient
    logger.info(f"\n📍 ContaAzulFinancialClient.BASE_URL:")
    logger.info(f"   {ContaAzulFinancialClient.BASE_URL}")

    if "api-v2.contaazul.com" in ContaAzulFinancialClient.BASE_URL:
        logger.info("   ✅ Usando API v2")
    else:
        logger.error("   ❌ Não está usando API v2!")
        issues.append("ContaAzulFinancialClient usando API antiga")

    # Verificar domínios permitidos
    logger.info(f"\n📍 Domínios permitidos para recibos:")
    for domain in sorted(ContaAzulFinancialClient.ALLOWED_RECEIPT_DOMAINS):
        logger.info(f"   - {domain}")

    if "api-v2.contaazul.com" in ContaAzulFinancialClient.ALLOWED_RECEIPT_DOMAINS:
        logger.info("   ✅ api-v2.contaazul.com está permitido")
    else:
        logger.error("   ❌ api-v2.contaazul.com não está na lista!")
        issues.append("api-v2.contaazul.com não permitido")

    logger.info("\n" + "=" * 80)

    if issues:
        logger.error(f"❌ {len(issues)} problema(s) encontrado(s):")
        for issue in issues:
            logger.error(f"   - {issue}")
        return False
    else:
        logger.info("✅ Todos os serviços estão configurados corretamente!")
        return True


async def test_api_endpoint_with_fake_token():
    """Testa o endpoint /company com um token falso (espera-se 401)."""
    logger.info("\n" + "=" * 80)
    logger.info("🧪 TESTANDO ENDPOINT /company (com token fake)")
    logger.info("=" * 80)

    import httpx

    settings = get_settings()
    fake_token = "fake_token_for_testing_purposes"
    api_url = f"{settings.CONTA_AZUL_API_BASE_URL}/company"

    logger.info(f"\n📍 URL: {api_url}")
    logger.info(f"🔑 Authorization: Bearer {fake_token[:10]}...")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                api_url,
                headers={"Authorization": f"Bearer {fake_token}"},
            )

            logger.info(f"\n📊 Status Code: {response.status_code}")

            if response.status_code == 401:
                logger.info("✅ 401 recebido (esperado para token inválido)")
                logger.info("✅ Endpoint /company existe e responde corretamente")

                try:
                    error_body = response.json()
                    logger.info(f"\n📋 Response Body:")
                    logger.info(f"   {error_body}")
                except Exception:
                    logger.info(f"\n📋 Response: {response.text[:200]}")

                return True

            elif response.status_code == 404:
                logger.error("❌ 404 Not Found - Endpoint /company não existe!")
                logger.error("   Verifique se a API v2 está correta")
                return False

            else:
                logger.warning(f"⚠️  Status inesperado: {response.status_code}")
                logger.info(f"   Response: {response.text[:200]}")
                return False

    except httpx.ConnectError as e:
        logger.error(f"❌ Erro de conexão: {e}")
        logger.error("   Verifique a conectividade com a API da Conta Azul")
        return False

    except Exception as e:
        logger.error(f"❌ Erro: {e}")
        return False


def main():
    """Função principal."""
    logger.info("🚀 INICIANDO TESTE DE CORREÇÃO API v2")
    logger.info("")

    # Teste 1: Configuração
    config_ok = test_configuration()

    # Teste 2: URLs nos serviços
    services_ok = test_service_urls()

    # Teste 3: Endpoint real
    endpoint_ok = asyncio.run(test_api_endpoint_with_fake_token())

    # Resumo
    logger.info("\n" + "=" * 80)
    logger.info("📊 RESUMO DOS TESTES")
    logger.info("=" * 80)
    logger.info(f"Configuração:         {'✅ OK' if config_ok else '❌ FALHOU'}")
    logger.info(f"Serviços:             {'✅ OK' if services_ok else '❌ FALHOU'}")
    logger.info(f"Endpoint /company:    {'✅ OK' if endpoint_ok else '❌ FALHOU'}")
    logger.info("=" * 80)

    if config_ok and services_ok and endpoint_ok:
        logger.info("\n🎉 TODAS AS CORREÇÕES FORAM APLICADAS CORRETAMENTE!")
        logger.info("")
        logger.info("Próximos passos:")
        logger.info("1. Rebuild do container: docker-compose up -d --build")
        logger.info("2. Testar o fluxo OAuth completo")
        logger.info("3. Verificar logs que agora devem mostrar api-v2.contaazul.com")
        return 0
    else:
        logger.error("\n❌ ALGUNS TESTES FALHARAM!")
        logger.error("Revise as correções acima antes de fazer deploy.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

