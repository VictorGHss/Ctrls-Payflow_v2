"""
Rotas OAuth2 Authorization Code para Conta Azul.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db_session, init_db
from app.logging import setup_logging
from app.services_auth import ContaAzulAuthService

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


@router.get("/authorize")
def authorize_request(db: Session):
    """
    Inicia fluxo OAuth.
    Redireciona para página de login da Conta Azul.
    """
    settings = get_settings()

    # Gerar state para CSRF protection
    state = secrets.token_urlsafe(32)

    # Montar URL de autorização
    auth_url = (
        f"{settings.CONTA_AZUL_AUTH_URL}?"
        f"client_id={settings.CONTA_AZUL_CLIENT_ID}"
        f"&redirect_uri={settings.CONTA_AZUL_REDIRECT_URI}"
        f"&response_type=code"
        f"&state={state}"
        f"&scope=accounts.read+installments.read+receipts.read"
    )

    logger.info(f"Iniciando fluxo OAuth, state={state}")

    return {"auth_url": auth_url, "state": state}


@router.get("/callback")
def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = None,
):
    """
    Callback da Conta Azul após usuário autorizar.
    Troca código por token.

    Args:
        code: Authorization code
        state: State para validação CSRF
        db: Sessão do banco
    """
    settings = get_settings()
    crypto = get_crypto_manager()

    if not code:
        logger.error("Callback sem código de autorização")
        raise HTTPException(status_code=400, detail="Código de autorização ausente")

    try:
        # Trocar código por token
        token_response = httpx.post(
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
        token_response.raise_for_status()

    except httpx.HTTPError as e:
        logger.error(f"Erro ao trocar código por token: {e}")
        raise HTTPException(status_code=500, detail="Erro na autenticação")

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)

    if not access_token or not refresh_token:
        logger.error("Token response sem access_token ou refresh_token")
        raise HTTPException(status_code=500, detail="Tokens inválidos")

    # Buscar informações da conta (account_id)
    try:
        account_info = _get_account_info(access_token, settings)
        account_id = account_info.get("id")
        owner_email = account_info.get("email")
        owner_name = account_info.get("name")
        company_name = account_info.get("companyName")

    except Exception as e:
        logger.error(f"Erro ao buscar informações da conta: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar dados da conta",
        )

    # Salvar tokens criptografados
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    try:
        encrypted_access = crypto.encrypt(access_token)
        encrypted_refresh = crypto.encrypt(refresh_token)

        # Verificar se já existe token para esta conta
        existing = (
            db.query(OAuthToken)
            .filter(OAuthToken.account_id == account_id)
            .first()
        )

        if existing:
            existing.access_token = encrypted_access
            existing.refresh_token = encrypted_refresh
            existing.expires_at = expires_at
        else:
            oauth_record = OAuthToken(
                account_id=account_id,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                expires_at=expires_at,
            )
            db.add(oauth_record)

        # Registrar/atualizar dados da conta
        account_record = (
            db.query(AzulAccount)
            .filter(AzulAccount.account_id == account_id)
            .first()
        )

        if account_record:
            account_record.owner_email = owner_email
            account_record.owner_name = owner_name
            account_record.company_name = company_name
            account_record.is_active = 1
        else:
            account_record = AzulAccount(
                account_id=account_id,
                owner_email=owner_email,
                owner_name=owner_name,
                company_name=company_name,
                is_active=1,
            )
            db.add(account_record)

        db.commit()
        logger.info(f"Tokens salvos para conta {account_id}")

        return {
            "status": "success",
            "message": f"Conta {company_name} conectada com sucesso!",
            "account_id": account_id,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar tokens: {e}")
        raise HTTPException(status_code=500, detail="Erro ao salvar autenticação")


def _get_account_info(access_token: str, settings) -> dict:
    """
    Busca informações da conta autenticada.

    Args:
        access_token: Token de acesso
        settings: Configurações

    Returns:
        Dicionário com informações da conta
    """
    # Adaptar para endpoint real da Conta Azul (ex: /v1/account ou /me)
    response = httpx.get(
        f"{settings.CONTA_AZUL_API_BASE_URL}/v1/account",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(db: Session, account_id: str) -> Optional[str]:
    """
    Renova access_token usando refresh_token.

    Args:
        db: Sessão do banco
        account_id: ID da conta

    Returns:
        Novo access_token ou None
    """
    settings = get_settings()
    crypto = get_crypto_manager()

    token_record = (
        db.query(OAuthToken)
        .filter(OAuthToken.account_id == account_id)
        .first()
    )

    if not token_record:
        logger.error(f"Token não encontrado para {account_id}")
        return None

    try:
        refresh_token = crypto.decrypt(token_record.refresh_token)
    except Exception as e:
        logger.error(f"Erro ao decriptografar refresh_token: {e}")
        return None

    try:
        # Requisição para renovar token
        response = httpx.post(
            settings.CONTA_AZUL_TOKEN_URL,
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.CONTA_AZUL_CLIENT_ID,
                "client_secret": settings.CONTA_AZUL_CLIENT_SECRET,
            },
            timeout=30,
        )
        response.raise_for_status()

    except httpx.HTTPError as e:
        logger.error(f"Erro ao renovar token: {e}")
        return None

    token_data = response.json()
    new_access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token", refresh_token)
    expires_in = token_data.get("expires_in", 3600)

    if not new_access_token:
        logger.error("Novo access_token não retornado")
        return None

    try:
        # Salvar novos tokens (refresh_token muda a cada renovação)
        encrypted_access = crypto.encrypt(new_access_token)
        encrypted_refresh = crypto.encrypt(new_refresh_token)

        token_record.access_token = encrypted_access
        token_record.refresh_token = encrypted_refresh
        token_record.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=expires_in,
        )
        db.commit()

        logger.info(f"Token renovado para {account_id}")
        return new_access_token

    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao salvar novo token: {e}")
        return None

