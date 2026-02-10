"""
Serviço de autenticação OAuth2 com Conta Azul.
Gerencia autorização, token exchange e renovação.
"""

import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import get_crypto_manager
from app.database import OAuthToken, AzulAccount
from app.logging import setup_logging

logger = setup_logging(__name__)


class ContaAzulAuthService:
    """Gerencia o fluxo OAuth2 Authorization Code com Conta Azul."""

    SCOPES = "accounts.read installments.read receipts.read"
    TOKEN_URL = "https://accounts.contaazul.com/oauth/token"
    AUTHORIZE_URL = "https://accounts.contaazul.com/oauth/authorize"
    API_URL = "https://api.contaazul.com/v1/account"

    def __init__(self, db: Session):
        """
        Inicializa o serviço.

        Args:
            db: Sessão do banco de dados
        """
        self.db = db
        self.settings = get_settings()
        self.crypto = get_crypto_manager()

    def generate_authorization_url(self) -> Tuple[str, str]:
        """
        Gera URL de autorização para o usuário.

        Returns:
            Tupla (authorization_url, state) para validação CSRF
        """
        state = secrets.token_urlsafe(32)

        auth_url = (
            f"{self.AUTHORIZE_URL}?"
            f"client_id={self.settings.CONTA_AZUL_CLIENT_ID}"
            f"&redirect_uri={self.settings.CONTA_AZUL_REDIRECT_URI}"
            f"&response_type=code"
            f"&state={state}"
            f"&scope={self.SCOPES}"
        )

        logger.info(f"URL de autorização gerada com state={state[:10]}...")
        return auth_url, state

    async def exchange_code_for_tokens(
        self,
        code: str,
    ) -> Optional[dict]:
        """
        Troca authorization code por access_token e refresh_token.

        Args:
            code: Authorization code recebido do callback

        Returns:
            Dicionário com tokens ou None se falhou
        """
        # Preparar credentials em Base64
        credentials = f"{self.settings.CONTA_AZUL_CLIENT_ID}:{self.settings.CONTA_AZUL_CLIENT_SECRET}"
        b64_credentials = base64.b64encode(credentials.encode()).decode()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.TOKEN_URL,
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

                if response.status_code == 200:
                    token_data = response.json()
                    logger.info(
                        f"Token obtido com sucesso. "
                        f"Expires in: {token_data.get('expires_in')}s"
                    )
                    return token_data
                else:
                    logger.error(
                        f"Erro ao trocar code por token: {response.status_code}"
                    )
                    logger.error(f"Response: {response.text[:100]}")
                    return None

        except Exception as e:
            logger.error(f"Erro ao fazer requisição de token: {e}")
            return None

    async def get_account_info(self, access_token: str) -> Optional[dict]:
        """
        Busca informações da conta autenticada.

        Args:
            access_token: Token de acesso (plaintext)

        Returns:
            Dicionário com informações da conta ou None
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                if response.status_code == 200:
                    account_info = response.json()
                    logger.info(
                        f"Informações da conta obtidas: "
                        f"id={account_info.get('id')[:10]}..."
                    )
                    return account_info
                else:
                    logger.error(
                        f"Erro ao buscar informações da conta: {response.status_code}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Erro ao fazer requisição de account info: {e}")
            return None

    def save_tokens(
        self,
        account_id: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        owner_email: Optional[str] = None,
        owner_name: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> bool:
        """
        Salva tokens criptografados no banco.

        Args:
            account_id: ID da conta Conta Azul
            access_token: Token de acesso (será criptografado)
            refresh_token: Refresh token (será criptografado)
            expires_in: Segundos até expiração
            owner_email: Email do proprietário (opcional)
            owner_name: Nome do proprietário (opcional)
            company_name: Nome da empresa (opcional)

        Returns:
            True se salvo com sucesso, False caso contrário
        """
        try:
            # Criptografar tokens
            encrypted_access = self.crypto.encrypt(access_token)
            encrypted_refresh = self.crypto.encrypt(refresh_token)

            # Calcular data de expiração
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            # Verificar se já existe token para esta conta
            existing_token = (
                self.db.query(OAuthToken)
                .filter(OAuthToken.account_id == account_id)
                .first()
            )

            if existing_token:
                # Atualizar token existente
                existing_token.access_token = encrypted_access
                existing_token.refresh_token = encrypted_refresh
                existing_token.expires_at = expires_at
                logger.info(f"Token atualizado para conta {account_id[:10]}...")
            else:
                # Criar novo token
                token_record = OAuthToken(
                    account_id=account_id,
                    access_token=encrypted_access,
                    refresh_token=encrypted_refresh,
                    expires_at=expires_at,
                )
                self.db.add(token_record)
                logger.info(f"Novo token criado para conta {account_id[:10]}...")

            # Registrar/atualizar conta
            account_record = (
                self.db.query(AzulAccount)
                .filter(AzulAccount.account_id == account_id)
                .first()
            )

            if account_record:
                account_record.owner_email = owner_email
                account_record.owner_name = owner_name
                account_record.company_name = company_name
                account_record.is_active = 1
                logger.info(f"Conta atualizada: {account_id[:10]}...")
            else:
                account_record = AzulAccount(
                    account_id=account_id,
                    owner_email=owner_email,
                    owner_name=owner_name,
                    company_name=company_name,
                    is_active=1,
                )
                self.db.add(account_record)
                logger.info(f"Nova conta registrada: {account_id[:10]}...")

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Erro ao salvar tokens: {e}")
            return False

    def get_token(self, account_id: str) -> Optional[OAuthToken]:
        """
        Busca token de uma conta.

        Args:
            account_id: ID da conta

        Returns:
            OAuthToken ou None
        """
        return (
            self.db.query(OAuthToken)
            .filter(OAuthToken.account_id == account_id)
            .first()
        )

    def is_token_expired(self, token: OAuthToken) -> bool:
        """
        Verifica se token está expirado.

        Args:
            token: Registro OAuthToken

        Returns:
            True se expirado, False caso contrário
        """
        return datetime.now(timezone.utc) >= token.expires_at

    async def refresh_access_token(self, account_id: str) -> Optional[str]:
        """
        Renova access_token usando refresh_token.

        IMPORTANTE: Refresh token muda a cada renovação!
        Sempre salvar o novo refresh_token retornado.

        Args:
            account_id: ID da conta

        Returns:
            Novo access_token (plaintext) ou None se falhou
        """
        token_record = self.get_token(account_id)

        if not token_record:
            logger.error(f"Token não encontrado para {account_id[:10]}...")
            return None

        try:
            # Decriptografar refresh_token
            refresh_token = self.crypto.decrypt(token_record.refresh_token)

            # Preparar credentials
            credentials = f"{self.settings.CONTA_AZUL_CLIENT_ID}:{self.settings.CONTA_AZUL_CLIENT_SECRET}"
            b64_credentials = base64.b64encode(credentials.encode()).decode()

            # Requisição para renovar
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    headers={
                        "Authorization": f"Basic {b64_credentials}",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"Erro ao renovar token para {account_id[:10]}...: "
                        f"{response.status_code}"
                    )
                    return None

                token_data = response.json()
                new_access_token = token_data.get("access_token")
                new_refresh_token = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 3600)

                if not new_access_token:
                    logger.error(f"Novo access_token não retornado")
                    return None

                # Criptografar novos tokens
                encrypted_access = self.crypto.encrypt(new_access_token)
                encrypted_refresh = self.crypto.encrypt(new_refresh_token)

                # Atualizar no banco
                token_record.access_token = encrypted_access
                token_record.refresh_token = encrypted_refresh
                token_record.expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=expires_in
                )
                self.db.commit()

                logger.info(
                    f"Token renovado com sucesso para {account_id[:10]}... "
                    f"(novo refresh_token salvo)"
                )
                return new_access_token

        except Exception as e:
            logger.error(f"Erro ao renovar token: {e}")
            return None

    def get_valid_access_token(self, account_id: str) -> Optional[str]:
        """
        Obtém um access_token válido, renovando se necessário.

        Args:
            account_id: ID da conta

        Returns:
            Access token válido (plaintext) ou None

        Note:
            Esta é uma função síncrona que chama refresh_access_token async.
            Para uso em async context, use refresh_access_token diretamente.
        """
        token_record = self.get_token(account_id)

        if not token_record:
            logger.error(f"Token não encontrado para {account_id[:10]}...")
            return None

        # Se ainda válido, retornar
        if not self.is_token_expired(token_record):
            try:
                access_token = self.crypto.decrypt(token_record.access_token)
                logger.debug(f"Token válido para {account_id[:10]}...")
                return access_token
            except Exception as e:
                logger.error(f"Erro ao decriptografar token: {e}")
                return None

        # Token expirou, precisa renovar
        logger.warning(f"Token expirado para {account_id[:10]}..., renovando...")
        logger.info("Use refresh_access_token() para renovação async")
        return None

