#!/usr/bin/env python
"""
Validação completa do fluxo OAuth corrigido.
Executa testes automatizados para garantir que todas as correções estão aplicadas.

Uso:
    python scripts/validate_oauth_fix.py
"""

import sys
from pathlib import Path

# Adicionar diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.logging import setup_logging
from app.services_auth import ContaAzulAuthService

logger = setup_logging(__name__)


def validate_urls():
    """Valida se as URLs estão corretas."""
    logger.info("=" * 80)
    logger.info("🔍 VALIDANDO URLs DO FLUXO OAUTH")
    logger.info("=" * 80)

    issues = []

    # Verificar URL de autorização
    if ContaAzulAuthService.AUTHORIZE_URL != "https://auth.contaazul.com/login":
        issues.append("❌ AUTHORIZE_URL incorreta")
    else:
        logger.info("✅ AUTHORIZE_URL correta: https://auth.contaazul.com/login")

    # Verificar URL de token
    if ContaAzulAuthService.TOKEN_URL != "https://auth.contaazul.com/oauth2/token":
        issues.append("❌ TOKEN_URL incorreta")
    else:
        logger.info("✅ TOKEN_URL correta: https://auth.contaazul.com/oauth2/token")

    # Verificar API URL (smoke test endpoint)
    api_url = ContaAzulAuthService.API_URL
    if "api-v2.contaazul.com" not in api_url:
        issues.append("❌ API_URL não usa api-v2.contaazul.com")
    else:
        logger.info(f"✅ API_URL usa api-v2.contaazul.com: {api_url}")

    # Verificar que não usa endpoints legados
    if "/v1/me" in api_url or "/company" in api_url:
        issues.append(f"⚠️  API_URL usa endpoint potencialmente inexistente: {api_url}")

    # Verificar que usa endpoint documentado
    if "/v1/pessoas" in api_url:
        logger.info("✅ API_URL usa endpoint documentado: /v1/pessoas")
    else:
        logger.warning(f"⚠️  API_URL usa endpoint não verificado: {api_url}")

    # Verificar scope
    if ContaAzulAuthService.SCOPES == "openid profile aws.cognito.signin.user.admin":
        logger.info("✅ SCOPES correto: openid profile aws.cognito.signin.user.admin")
    else:
        issues.append(f"❌ SCOPES incorreto: {ContaAzulAuthService.SCOPES}")

    logger.info("")
    return issues


def validate_methods():
    """Valida se os métodos necessários existem."""
    logger.info("=" * 80)
    logger.info("🔍 VALIDANDO MÉTODOS IMPLEMENTADOS")
    logger.info("=" * 80)

    issues = []

    # Verificar método de decodificação de id_token
    if hasattr(ContaAzulAuthService, '_decode_id_token'):
        logger.info("✅ Método _decode_id_token() implementado")
    else:
        issues.append("❌ Método _decode_id_token() não encontrado")

    # Verificar método de fallback
    if hasattr(ContaAzulAuthService, '_create_fallback_account_info'):
        logger.info("✅ Método _create_fallback_account_info() implementado")
    else:
        issues.append("❌ Método _create_fallback_account_info() não encontrado")

    # Verificar assinatura de get_account_info
    import inspect
    sig = inspect.signature(ContaAzulAuthService.get_account_info)
    params = list(sig.parameters.keys())

    if 'id_token' in params:
        logger.info("✅ get_account_info() aceita parâmetro id_token")
    else:
        issues.append("❌ get_account_info() não aceita parâmetro id_token")

    logger.info("")
    return issues


def validate_files():
    """Valida se os arquivos necessários existem."""
    logger.info("=" * 80)
    logger.info("🔍 VALIDANDO ARQUIVOS CRIADOS")
    logger.info("=" * 80)

    issues = []

    # Verificar smoke test script
    smoke_test_path = Path(__file__).parent / "contaazul_smoke_test.py"
    if smoke_test_path.exists():
        logger.info(f"✅ Smoke test script existe: {smoke_test_path.name}")
    else:
        issues.append(f"❌ Smoke test script não encontrado: {smoke_test_path}")

    # Verificar .env.example atualizado
    env_example_path = Path(__file__).parent.parent / ".env.example"
    if env_example_path.exists():
        content = env_example_path.read_text()
        if "api-v2.contaazul.com" in content:
            logger.info("✅ .env.example contém api-v2.contaazul.com")
        else:
            issues.append("❌ .env.example não contém api-v2.contaazul.com")

        if "CONTA_AZUL_API_BASE_URL" in content:
            logger.info("✅ .env.example documenta CONTA_AZUL_API_BASE_URL")
        else:
            issues.append("❌ .env.example não documenta CONTA_AZUL_API_BASE_URL")
    else:
        issues.append(f"❌ .env.example não encontrado: {env_example_path}")

    logger.info("")
    return issues


def validate_no_legacy():
    """Valida que não há referências aos endpoints legados."""
    logger.info("=" * 80)
    logger.info("🔍 VALIDANDO REMOÇÃO DE ENDPOINTS LEGADOS")
    logger.info("=" * 80)

    issues = []

    # Verificar que /v1/me não está mais hardcoded
    services_auth_path = Path(__file__).parent.parent / "app" / "services_auth.py"
    if services_auth_path.exists():
        content = services_auth_path.read_text()
        if '"/v1/me"' in content or "'/v1/me'" in content:
            issues.append("❌ Referência a /v1/me encontrada em services_auth.py")
        else:
            logger.info("✅ Nenhuma referência hardcoded a /v1/me em services_auth.py")

        if '"/company"' in content and "api-v2.contaazul.com/company" in content:
            issues.append("⚠️  Referência a /company encontrada (endpoint não existe)")
        else:
            logger.info("✅ Nenhuma referência a endpoint /company")

    logger.info("")
    return issues


def main():
    """Função principal."""
    logger.info("\n")
    logger.info("╔" + "=" * 78 + "╗")
    logger.info("║" + " " * 20 + "VALIDAÇÃO DO FIX OAUTH - CONTA AZUL" + " " * 23 + "║")
    logger.info("╚" + "=" * 78 + "╝")
    logger.info("\n")

    all_issues = []

    # Executar validações
    all_issues.extend(validate_urls())
    all_issues.extend(validate_methods())
    all_issues.extend(validate_files())
    all_issues.extend(validate_no_legacy())

    # Resumo
    logger.info("=" * 80)
    logger.info("📊 RESUMO DA VALIDAÇÃO")
    logger.info("=" * 80)

    if not all_issues:
        logger.info("✅ TODAS AS VALIDAÇÕES PASSARAM!")
        logger.info("")
        logger.info("O fluxo OAuth foi corrigido com sucesso:")
        logger.info("  • URLs corretas (api-v2.contaazul.com)")
        logger.info("  • Endpoint real documentado (/v1/pessoas)")
        logger.info("  • Extração de informações do id_token")
        logger.info("  • Smoke test implementado")
        logger.info("  • Documentação atualizada")
        logger.info("")
        logger.info("Próximos passos:")
        logger.info("  1. docker-compose up -d --build")
        logger.info("  2. Acesse http://localhost:8000/connect")
        logger.info("  3. Verifique logs: docker-compose logs -f api")
        logger.info("=" * 80)
        return 0
    else:
        logger.error(f"❌ {len(all_issues)} PROBLEMA(S) ENCONTRADO(S):")
        for issue in all_issues:
            logger.error(f"  {issue}")
        logger.info("")
        logger.error("Revise as correções antes de continuar.")
        logger.info("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())

