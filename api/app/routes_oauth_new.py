"""
Rotas OAuth2 Authorization Code para Conta Azul.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db_session, init_db
from app.logging import setup_logging
from app.services_auth import ContaAzulAuthService
from app.config import get_settings

logger = setup_logging(__name__)

# Inicializar database
settings = get_settings()
engine, SessionLocal = init_db(settings.DATABASE_URL)


def get_db() -> Session:
    """Dependency para obter sessão do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(tags=["oauth"])


@router.get("/connect")
async def connect(db: Session = Depends(get_db)):
    """
    GET /connect → Inicia fluxo OAuth2 Authorization Code.
    Redireciona para página de login e consent da Conta Azul.

    Returns:
        Redireciona para Conta Azul login
    """
    auth_service = ContaAzulAuthService(db)
    auth_url, state = auth_service.generate_authorization_url()

    logger.info(f"Iniciando fluxo OAuth - redirecionando para Conta Azul")
    return RedirectResponse(url=auth_url)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(None),
    error: str = Query(None),
    error_description: str = Query(None),
    db: Session = Depends(get_db),
):
    """
    GET /oauth/callback → Callback do fluxo OAuth2.
    Recebe authorization code e troca por access_token + refresh_token.

    Args:
        code: Authorization code da Conta Azul
        state: State para validação CSRF (opcional)
        error: Código de erro se ocorreu (ex: access_denied)
        error_description: Descrição do erro
        db: Sessão do banco

    Returns:
        Status da autenticação (sucesso/erro)
    """
    # Verificar se houve erro
    if error:
        logger.warning(
            f"Erro no callback OAuth: {error} - {error_description}"
        )
        raise HTTPException(
            status_code=400,
            detail=f"Erro de autenticação: {error_description or error}",
        )

    if not code:
        logger.error("Callback recebido sem authorization code")
        raise HTTPException(
            status_code=400,
            detail="Authorization code ausente"
        )

    auth_service = ContaAzulAuthService(db)

    # 1. Trocar code por tokens (access + refresh)
    logger.info("Etapa 1: Trocando authorization code por tokens...")
    token_data = await auth_service.exchange_code_for_tokens(code)

    if not token_data:
        logger.error("Falha na etapa 1: exchange_code_for_tokens")
        raise HTTPException(
            status_code=500,
            detail="Erro ao obter tokens"
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        logger.error("Tokens inválidos recebidos")
        raise HTTPException(
            status_code=500,
            detail="Tokens inválidos"
        )

    logger.debug(f"Tokens recebidos (expires_in={expires_in}s)")

    # 2. Buscar informações da conta usando o access_token
    logger.info("Etapa 2: Buscando informações da conta...")
    account_info = await auth_service.get_account_info(access_token)

    if not account_info:
        logger.error("Falha na etapa 2: get_account_info")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar dados da conta"
        )

    account_id = account_info.get("id")
    owner_email = account_info.get("email")
    owner_name = account_info.get("name")
    company_name = account_info.get("companyName")

    if not account_id:
        logger.error("Conta sem ID")
        raise HTTPException(
            status_code=500,
            detail="Dados da conta inválidos"
        )

    logger.debug(f"Conta encontrada: {account_id[:10]}... ({company_name})")

    # 3. Salvar tokens criptografados no banco
    logger.info("Etapa 3: Salvando tokens criptografados no banco...")
    if not auth_service.save_tokens(
        account_id=account_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        owner_email=owner_email,
        owner_name=owner_name,
        company_name=company_name,
    ):
        logger.error("Falha na etapa 3: save_tokens")
        raise HTTPException(
            status_code=500,
            detail="Erro ao salvar autenticação"
        )

    logger.info(
        f"✅ Autenticação concluída com sucesso! "
        f"Conta: {company_name} (account_id={account_id[:10]}...)"
    )

    return {
        "status": "success",
        "message": f"Conta {company_name} conectada com sucesso!",
        "account_id": account_id,
        "owner_name": owner_name,
        "owner_email": owner_email,
        "expires_in": expires_in,
    }

