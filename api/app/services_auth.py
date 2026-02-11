"""
Serviço de autenticação OAuth2 com Conta Azul.
Gerencia autorização, token exchange e renovação.
"""

import base64
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import get_crypto_manager
from app.database import AzulAccount, OAuthToken
from app.logging import setup_logging

logger = setup_logging(__name__)


class ContaAzulAuthService:
    """Gerencia o fluxo OAuth2 Authorization Code com Conta Azul."""

    # URLs e scope conforme painel oficial da Conta Azul (auth.contaazul.com)
    # Scope: openid profile aws.cognito.signin.user.admin
    SCOPES = "openid profile aws.cognito.signin.user.admin"
    AUTHORIZE_URL = "https://auth.contaazul.com/login"
    TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
    # API v2 endpoint - /v1/pessoas é um endpoint real para smoke test do token
    # Retorna lista de pessoas cadastradas (mesmo vazio, confirma que token funciona)
    API_URL = "https://api-v2.contaazul.com/v1/pessoas?pagina=1&tamanho_pagina=1"

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

    def _decode_id_token(self, id_token: str) -> Optional[dict]:
        """
        Decodifica id_token JWT para extrair informações do usuário.

        ATENÇÃO: Este método faz decodificação SEM validação de assinatura.
        Usar apenas para extrair claims não-críticos do token já validado.

        Args:
            id_token: JWT id_token recebido na resposta OAuth

        Returns:
            Dicionário com claims do token ou None se falhou
        """
        try:
            # JWT tem 3 partes separadas por ponto: header.payload.signature
            parts = id_token.split('.')
            if len(parts) != 3:
                logger.error("❌ id_token inválido: não possui 3 partes")
                return None

            # Decodificar payload (segunda parte)
            payload_b64 = parts[1]
            # Adicionar padding se necessário
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding

            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes.decode('utf-8'))

            logger.info(f"✅ id_token decodificado com sucesso")
            logger.debug(f"📋 Claims: sub={payload.get('sub', 'N/A')}, email={payload.get('email', 'N/A')}")

            return payload

        except Exception as e:
            logger.error(f"❌ Erro ao decodificar id_token: {e}")
            return None

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

        # Log seguro
        code_preview = f"{code[:8]}...{code[-4:]}" if len(code) > 12 else "***"
        logger.info(f"🔄 Trocando authorization code por tokens")
        logger.debug(f"📍 Token URL: {self.TOKEN_URL}")
        logger.debug(f"📋 Code: {code_preview}")
        logger.debug(f"🔑 Redirect URI: {self.settings.CONTA_AZUL_REDIRECT_URI}")

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

                logger.info(f"📊 Token exchange response: {response.status_code}")

                if response.status_code == 200:
                    token_data = response.json()
                    logger.info(
                        f"✅ Token obtido com sucesso. "
                        f"Expires in: {token_data.get('expires_in')}s"
                    )

                    # Verificar se todos os campos esperados estão presentes
                    if "access_token" not in token_data:
                        logger.error("⚠️  access_token ausente na resposta!")
                    if "refresh_token" not in token_data:
                        logger.error("⚠️  refresh_token ausente na resposta!")

                    # Verificar se há id_token (contém informações do usuário)
                    if "id_token" in token_data:
                        logger.info("📋 id_token presente na resposta")
                        # Armazenar id_token para uso posterior
                        token_data["_has_id_token"] = True
                    else:
                        logger.warning("⚠️  id_token ausente na resposta")

                    return token_data

                elif response.status_code == 401:
                    # Diagnóstico detalhado do 401
                    logger.error("=" * 80)
                    logger.error("🚨 ERRO 401 UNAUTHORIZED na troca code → tokens")
                    logger.error("=" * 80)
                    logger.error(f"📍 URL chamada: {self.TOKEN_URL}")
                    logger.error(f"📋 Grant type: authorization_code")
                    logger.error(f"📋 Code: {code_preview}")
                    logger.error(f"📊 Status Code: {response.status_code}")

                    try:
                        error_body = response.json()
                        logger.error(f"📋 Response Body: {error_body}")

                        error_type = error_body.get("error", "")
                        error_desc = error_body.get("error_description", "")

                        logger.error(f"\n💡 Possíveis causas do 401:")
                        logger.error(f"   1. CLIENT_ID ou CLIENT_SECRET incorretos")
                        logger.error(f"   2. Credenciais de ambiente errado (sandbox vs prod)")
                        logger.error(f"   3. Authorization header mal formatado")
                        logger.error(f"   4. App desativado no Portal Conta Azul")

                        logger.error(f"\n🔧 Verificar:")
                        logger.error(f"   - Portal Conta Azul → Integrações → APIs")
                        logger.error(f"   - CLIENT_ID: {self.settings.CONTA_AZUL_CLIENT_ID[:10]}...{self.settings.CONTA_AZUL_CLIENT_ID[-4:]}")
                        logger.error(f"   - CLIENT_SECRET: {self.settings.CONTA_AZUL_CLIENT_SECRET[:4]}...{self.settings.CONTA_AZUL_CLIENT_SECRET[-4:]}")
                        logger.error(f"   - Base64 Authorization: Basic {b64_credentials[:20]}...{b64_credentials[-10:]}")

                        if error_type == "invalid_client":
                            logger.error(f"\n❌ ERRO: invalid_client")
                            logger.error(f"   → Credenciais CLIENT_ID/SECRET estão incorretas!")
                            logger.error(f"   → Copiar novamente do Portal Conta Azul")

                    except Exception:
                        logger.error(f"📋 Response Body (text): {response.text[:500]}")

                    logger.error("=" * 80)
                    return None

                else:
                    logger.error(
                        f"❌ Erro ao trocar code por token: {response.status_code}"
                    )
                    try:
                        error_body = response.json()
                        logger.error(f"📋 Response: {error_body}")
                    except Exception:
                        logger.error(f"📋 Response (text): {response.text[:500]}")
                    return None

        except Exception as e:
            logger.error(f"❌ Exceção ao fazer requisição de token: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    async def get_account_info(self, access_token: str, id_token: Optional[str] = None) -> Optional[dict]:
        """
        Busca informações da conta autenticada.

        Faz smoke test do access_token chamando a API e extrai informações
        do id_token se disponível.

        Args:
            access_token: Token de acesso (plaintext)
            id_token: ID token JWT (opcional, contém informações do usuário)

        Returns:
            Dicionário com informações da conta ou None
        """
        try:
            # Log seguro - apenas primeiros e últimos caracteres do token
            token_preview = f"{access_token[:8]}...{access_token[-4:]}" if len(access_token) > 12 else "***"
            logger.info(f"🔍 Validando token com smoke test na API")
            logger.debug(f"📍 URL: {self.API_URL}")

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    self.API_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                # Log detalhado da resposta
                logger.info(f"📊 Smoke Test Status Code: {response.status_code}")

                # Log headers relevantes (sem secrets)
                relevant_headers = ["content-type", "x-ratelimit-remaining", "x-ratelimit-reset", "www-authenticate"]
                for header in relevant_headers:
                    if header in response.headers:
                        logger.debug(f"📋 Header {header}: {response.headers[header]}")

                if response.status_code == 200:
                    api_response = response.json()
                    logger.info(f"✅ Token validado com sucesso - API respondeu 200")
                    logger.debug(f"📋 API Response: {str(api_response)[:200]}...")

                    # Extrair informações do id_token se disponível
                    account_info = {}

                    if id_token:
                        logger.info("🔓 Extraindo informações do id_token...")
                        id_claims = self._decode_id_token(id_token)

                        if id_claims:
                            # Extrair campos do JWT (Cognito/Conta Azul)
                            account_info = {
                                "id": id_claims.get("sub", f"user_{secrets.token_hex(16)}"),
                                "email": id_claims.get("email", "user@contaazul.com"),
                                "name": id_claims.get("name", id_claims.get("cognito:username", "Usuário Conta Azul")),
                                "companyName": id_claims.get("custom:company_name", "Empresa Conta Azul"),
                                "_from_id_token": True,
                                "_smoke_test_passed": True,
                            }
                            logger.info(f"✅ Informações extraídas do id_token: sub={id_claims.get('sub', 'N/A')}")
                        else:
                            logger.warning("⚠️  Falha ao decodificar id_token, usando fallback")
                            account_info = self._create_fallback_account_info()
                    else:
                        logger.warning("⚠️  id_token não fornecido, usando dados fallback")
                        account_info = self._create_fallback_account_info()

                    logger.info(
                        f"✅ Account info preparado. ID: "
                        f"{account_info.get('id')[:20]}..."
                    )
                    return account_info

                elif response.status_code == 401:
                    # Diagnóstico detalhado do 401
                    logger.error("=" * 80)
                    logger.error("🚨 ERRO 401 UNAUTHORIZED ao buscar company info")
                    logger.error("=" * 80)
                    logger.error(f"📍 URL chamada: {self.API_URL}")
                    logger.error(f"🔑 Token usado: {token_preview}")
                    logger.error(f"📊 Status Code: {response.status_code}")

                    # Tentar extrair corpo da resposta
                    try:
                        error_body = response.json()
                        logger.error(f"📋 Response Body:")

                        # Redigir tokens se presentes
                        safe_body = str(error_body)
                        if len(access_token) > 10:
                            safe_body = safe_body.replace(access_token, f"{token_preview}")

                        logger.error(f"   {safe_body}")

                        # Análise do erro
                        error_type = error_body.get("error", "")
                        error_desc = error_body.get("error_description", "")
                        message = error_body.get("message", "")

                        logger.error(f"\n📋 Análise do erro:")
                        if error_type:
                            logger.error(f"   Error Type: {error_type}")
                        if error_desc:
                            logger.error(f"   Description: {error_desc}")
                        if message:
                            logger.error(f"   Message: {message}")

                        # Sugestões baseadas no tipo de erro
                        logger.error(f"\n💡 Possíveis causas:")

                        if "invalid_token" in error_type.lower() or "invalid" in error_desc.lower():
                            logger.error("   1. Token expirado (verifique expires_in do token)")
                            logger.error("   2. Token malformado ou corrompido")
                            logger.error("   3. Token de ambiente errado (sandbox vs prod)")

                        elif "insufficient" in error_desc.lower() or "scope" in error_desc.lower():
                            logger.error("   1. Scope insuficiente no token")
                            logger.error("   2. App sem permissão de leitura no Portal Conta Azul")
                            logger.error("   3. Verificar scopes em services_auth.py: SCOPES")

                        elif "audience" in error_desc.lower():
                            logger.error("   1. Audience incorreta (token para API errada)")
                            logger.error("   2. Verificar CONTA_AZUL_API_BASE_URL no .env")

                        else:
                            logger.error("   1. App não autorizado no Portal Conta Azul")
                            logger.error("   2. App em sandbox mas usando API de produção")
                            logger.error("   3. Credenciais CLIENT_ID/SECRET incorretas")
                            logger.error("   4. Conta sem dados ou acesso restrito")

                        logger.error(f"\n🔧 Verificar:")
                        logger.error(f"   - Portal Conta Azul → Integrações → APIs")
                        logger.error(f"   - App em PRODUÇÃO (não sandbox)")
                        logger.error(f"   - Permissões de LEITURA habilitadas")
                        logger.error(f"   - URLs corretas no .env (auth.contaazul.com, api-v2.contaazul.com)")
                        logger.error("=" * 80)

                    except Exception:
                        # Se não for JSON, mostrar texto
                        logger.error(f"📋 Response Body (text): {response.text[:500]}")

                    # Log WWW-Authenticate header se presente
                    if "www-authenticate" in response.headers:
                        logger.error(f"🔐 WWW-Authenticate: {response.headers['www-authenticate']}")

                    return None

                else:
                    logger.error(
                        f"❌ Erro ao buscar informações da conta: {response.status_code}"
                    )
                    logger.error(f"📋 Response: {response.text[:500]}")
                    return None

        except Exception as e:
            logger.error(f"❌ Exceção ao fazer requisição de account info: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _create_fallback_account_info(self) -> dict:
        """
        Cria informações de conta fallback quando id_token não está disponível.

        Returns:
            Dicionário com informações básicas geradas
        """
        return {
            "id": f"conta_azul_user_{secrets.token_hex(16)}",
            "email": "user@contaazul.com",
            "name": "Usuário Conta Azul",
            "companyName": "Empresa Conta Azul",
            "_from_id_token": False,
            "_smoke_test_passed": True,
            "_warning": "Dados gerados - id_token não disponível",
        }

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
                    logger.error("Novo access_token não retornado")
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
