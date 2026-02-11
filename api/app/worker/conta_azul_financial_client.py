"""
Client para API Financeira da Conta Azul.
Consulta contas a receber, parcelas e detalhes de pagamento.
"""

import asyncio
import ipaddress
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


class RateLimitError(Exception):
    """Erro de rate limit (429)."""

    pass


class ContaAzulFinancialClient:
    """
    Client para API Financeira da Conta Azul.

    Implementa:
    - Rate limiting (10 req/s, 600 req/min)
    - Backoff exponencial em 429
    - Consulta de contas a receber alteradas
    - Busca de detalhes de parcelas
    """

    BASE_URL = "https://api-v2.contaazul.com"
    MIN_INTERVAL_BETWEEN_REQUESTS = 0.1  # 10 req/s
    RATE_LIMIT_REQUESTS = 600
    RATE_LIMIT_WINDOW = 60

    # Dominios permitidos para download de recibos
    ALLOWED_RECEIPT_DOMAINS = {
        "api.contaazul.com",  # Legacy support
        "api-v2.contaazul.com",  # Current API
        "attachments.contaazul.com",
        "cdn.contaazul.com",
        "static.contaazul.com",
    }

    # Tamanho máximo de resposta
    MAX_RESPONSE_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(self, access_token: str):
        """
        Inicializa client.

        Args:
            access_token: Token de acesso OAuth2 da Conta Azul (plaintext)
        """
        self.access_token = access_token
        self.settings = get_settings()
        self._last_request_time: Optional[datetime] = None
        self._request_count = 0
        self._window_start: Optional[datetime] = None

    async def _apply_rate_limit(self) -> None:
        """Aplicar rate limiting local (10 req/s)."""
        now = datetime.now(timezone.utc)

        if self._last_request_time is None:
            self._last_request_time = now
            return

        elapsed = (now - self._last_request_time).total_seconds()
        if elapsed < self.MIN_INTERVAL_BETWEEN_REQUESTS:
            wait_time = self.MIN_INTERVAL_BETWEEN_REQUESTS - elapsed
            logger.debug(f"Rate limit: aguardando {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self._last_request_time = datetime.now(timezone.utc)

    def _get_auth_header(self) -> Dict[str, str]:
        """Retorna header de autorização."""
        return {"Authorization": f"Bearer {self.access_token}"}

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=16),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Faz requisição com retry em rate limit.

        Args:
            method: GET, POST, etc
            endpoint: Caminho relativo (ex: /v1/financeiro/...)
            params: Query parameters
            json_data: JSON body

        Returns:
            Response JSON

        Raises:
            RateLimitError: 429
            httpx.HTTPStatusError: Erros HTTP (4xx, 5xx)
            httpx.HTTPError: Outros erros
        """
        await self._apply_rate_limit()

        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_auth_header()

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=headers,
            )

            # Rate limit: retry com backoff exponencial
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                logger.warning(
                    f"⚠️  Rate limit 429. Retry-After: {retry_after}s. "
                    f"Usando backoff exponencial..."
                )
                raise RateLimitError(f"Rate limit: {retry_after}s")

            # Outros erros HTTP: propagar para tratamento específico
            response.raise_for_status()

            return response.json()

    async def get_receivables(
        self,
        account_id: str,
        changed_since: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca contas a receber usando API Financeiro v1 com paginação completa.

        Endpoint: GET /v1/financeiro/eventos-financeiros/contas-a-receber/buscar

        Args:
            account_id: ID da conta (para logs)
            changed_since: Data/hora (UTC) desde quando buscar alterações
            status: Filtro por status - aceita 'received', 'pending', etc (convertido para PT-BR)

        Returns:
            Lista consolidada de contas a receber de todas as páginas
        """
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        # Timezone São Paulo (GMT-3)
        sp_tz = ZoneInfo("America/Sao_Paulo")

        # Preparar parâmetros obrigatórios e opcionais
        now_utc = datetime.now(timezone.utc)
        now_sp = now_utc.astimezone(sp_tz)

        params = {}

        # data_alteracao_de e data_alteracao_ate (formato ISO sem 'Z')
        if changed_since:
            if isinstance(changed_since, datetime):
                changed_since_sp = changed_since.astimezone(sp_tz)
                # Formato: 2026-01-12T18:38:19 (sem timezone offset)
                params["data_alteracao_de"] = changed_since_sp.strftime("%Y-%m-%dT%H:%M:%S")
            else:
                # Se vier string, tentar converter
                changed_since_dt = datetime.fromisoformat(str(changed_since).replace('Z', '+00:00'))
                changed_since_sp = changed_since_dt.astimezone(sp_tz)
                params["data_alteracao_de"] = changed_since_sp.strftime("%Y-%m-%dT%H:%M:%S")

            params["data_alteracao_ate"] = now_sp.strftime("%Y-%m-%dT%H:%M:%S")

            logger.info(
                f"📅 Consultando contas a receber alteradas entre: "
                f"{params['data_alteracao_de']} e {params['data_alteracao_ate']} (SP) "
                f"(conta: {account_id[:10]}...)"
            )
        else:
            logger.info(f"📅 Consultando contas a receber (sem filtro de alteração) (conta: {account_id[:10]}...)")

        # data_vencimento_de e data_vencimento_ate (OBRIGATÓRIOS, formato YYYY-MM-DD)
        # Janela segura: 365 dias antes de changed_since até hoje + 1 dia
        if changed_since:
            venc_de = (changed_since - timedelta(days=365)).date()
        else:
            venc_de = (now_utc - timedelta(days=365)).date()

        venc_ate = (now_utc + timedelta(days=1)).date()

        params["data_vencimento_de"] = venc_de.strftime("%Y-%m-%d")
        params["data_vencimento_ate"] = venc_ate.strftime("%Y-%m-%d")

        logger.debug(f"   Janela de vencimento: {params['data_vencimento_de']} a {params['data_vencimento_ate']}")

        # Status: converter inglês para português
        if status:
            status_map = {
                "received": "RECEBIDO",
                "pending": "PENDENTE",
                "overdue": "VENCIDO",
                "cancelled": "CANCELADO",
            }
            api_status = status_map.get(status.lower(), status.upper())
            # Status pode ser array: ["RECEBIDO", "RECEBIDO_PARCIAL"]
            if api_status == "RECEBIDO":
                params["status"] = ["RECEBIDO", "RECEBIDO_PARCIAL"]
            else:
                params["status"] = [api_status]
            logger.debug(f"   Filtro de status: {params['status']}")

        # Paginação
        page_size = getattr(self.settings, 'RECEIVABLES_PAGE_SIZE', 100)
        params["tamanho_pagina"] = page_size

        endpoint = "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar"

        # Buscar todas as páginas
        all_items = []
        current_page = 1
        total_pages_estimate = "?"

        while True:
            params["pagina"] = current_page

            logger.debug(
                f"🔍 Request página {current_page}/{total_pages_estimate}: "
                f"GET {self.BASE_URL}{endpoint}"
            )
            logger.debug(f"   Parâmetros: {params}")

            try:
                data = await self._request("GET", endpoint, params=params)

                # Extrair itens (estrutura pode variar)
                items = data.get("itens", []) or data.get("contas", []) or data.get("data", []) or []

                if not items:
                    logger.debug(f"   Página {current_page} vazia, encerrando paginação")
                    break

                all_items.extend(items)
                logger.info(f"   ✅ Página {current_page}: +{len(items)} item(ns) (total acumulado: {len(all_items)})")

                # Atualizar estimativa de páginas totais
                if "total" in data and data["total"] > 0:
                    total_pages_estimate = (data["total"] + page_size - 1) // page_size

                # Condição de parada: menos itens que page_size = última página
                if len(items) < page_size:
                    logger.debug(f"   Última página atingida (itens < {page_size})")
                    break

                current_page += 1

                # Segurança: máximo 100 páginas (evitar loop infinito)
                if current_page > 100:
                    logger.warning(f"⚠️  Limite de 100 páginas atingido, encerrando busca")
                    break

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code

                # Log detalhado de erros HTTP
                if status_code == 400:
                    logger.error(
                        f"❌ Erro 400 Bad Request ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Parâmetros: {params}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Resposta: {e.response.text[:500]}\n"
                        f"   Possível causa: Parâmetros inválidos, formato incorreto ou campos obrigatórios faltando"
                    )
                elif status_code == 401:
                    logger.error(
                        f"❌ Erro 401 Unauthorized ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Possível causa: Token expirado ou inválido"
                    )
                elif status_code == 403:
                    logger.error(
                        f"❌ Erro 403 Forbidden ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Possível causa: Sem permissão para acessar contas a receber"
                    )
                elif status_code == 404:
                    logger.error(
                        f"❌ Erro 404 Not Found ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Resposta: {e.response.text[:500]}\n"
                        f"   ⚠️  ENDPOINT/PATH INVÁLIDO! Verifique:\n"
                        f"      - Prefixo /v1 está presente?\n"
                        f"      - Recurso correto: /financeiro/eventos-financeiros/contas-a-receber/buscar\n"
                        f"      - Base URL: {self.BASE_URL}"
                    )
                elif status_code == 429:
                    logger.error(
                        f"❌ Erro 429 Rate Limit ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Retry-After: {e.response.headers.get('Retry-After', 'N/A')}s"
                    )
                elif status_code >= 500:
                    logger.error(
                        f"❌ Erro {status_code} Server Error ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Resposta: {e.response.text[:500]}\n"
                        f"   Possível causa: Instabilidade na API da Conta Azul"
                    )
                else:
                    logger.error(
                        f"❌ Erro HTTP {status_code} ao buscar contas a receber\n"
                        f"   Método: GET\n"
                        f"   URL: {self.BASE_URL}{endpoint}\n"
                        f"   Status Code: {status_code}\n"
                        f"   Resposta: {e.response.text[:500]}"
                    )

                raise

            except Exception as e:
                logger.error(
                    f"❌ Erro inesperado ao buscar contas a receber: {type(e).__name__}: {e}\n"
                    f"   Endpoint: {endpoint}\n"
                    f"   Conta: {account_id[:10]}..."
                )
                raise

        # Retornar lista consolidada de todas as páginas
        logger.info(f"✅ Total consolidado: {len(all_items)} conta(s) a receber de {current_page - 1} página(s)")

        if all_items:
            logger.debug(f"   Primeira conta: ID={all_items[0].get('id', 'N/A')}")

        return all_items

    async def get_receivable_details(
        self,
        receivable_id: str,
    ) -> Dict[str, Any]:
        """
        Busca detalhes completos de uma conta a receber.

        Endpoint: GET /v1/financeiro/eventos-financeiros/contas-a-receber/{id}

        Args:
            receivable_id: ID da conta a receber

        Returns:
            Detalhes incluindo parcelas (installments)
        """
        endpoint = f"/v1/financeiro/eventos-financeiros/contas-a-receber/{receivable_id}"

        logger.debug(f"🔍 Buscando detalhes de conta a receber {receivable_id[:10]}...")
        logger.debug(f"   Endpoint: GET {self.BASE_URL}{endpoint}")

        try:
            data = await self._request("GET", endpoint)

            logger.debug(f"✅ Detalhes obtidos para {receivable_id[:10]}...")

            return data

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            if status_code == 404:
                logger.error(
                    f"❌ Erro 404: Conta a receber não encontrada\n"
                    f"   ID: {receivable_id}\n"
                    f"   Endpoint: {endpoint}"
                )
            elif status_code == 401:
                logger.error(f"❌ Erro 401: Token expirado ou inválido")
            else:
                logger.error(
                    f"❌ Erro HTTP {status_code} ao buscar detalhes\n"
                    f"   ID: {receivable_id}\n"
                    f"   Resposta: {e.response.text[:300]}"
                )
            raise

        except Exception as e:
            logger.error(f"❌ Erro ao buscar detalhes: {type(e).__name__}: {e}")
            raise

    async def get_installment_details(
        self,
        installment_id: str,
    ) -> Dict[str, Any]:
        """
        Busca detalhes de uma parcela específica.

        Args:
            installment_id: ID da parcela

        Returns:
            Detalhes da parcela incluindo status de pagamento
        """
        logger.debug(f"Buscando detalhes de installment {installment_id[:10]}...")

        try:
            data = await self._request(
                "GET",
                f"/installments/{installment_id}",
            )
            return data

        except Exception as e:
            logger.error(f"Erro ao buscar detalhes de installment: {e}")
            raise

    async def get_receipt_url(
        self,
        receivable_id: str,
        attachment_id: str,
    ) -> Optional[str]:
        """
        Busca URL de download do recibo/anexo.

        Endpoint: GET /v1/financeiro/eventos-financeiros/contas-a-receber/{id}/anexos/{anexoId}

        Args:
            receivable_id: ID da conta a receber
            attachment_id: ID do anexo

        Returns:
            URL de download ou None
        """
        endpoint = f"/v1/financeiro/eventos-financeiros/contas-a-receber/{receivable_id}/anexos/{attachment_id}"

        logger.debug(
            f"📎 Buscando URL de anexo {attachment_id[:10]}... "
            f"(conta: {receivable_id[:10]}...)"
        )
        logger.debug(f"   Endpoint: GET {self.BASE_URL}{endpoint}")

        try:
            data = await self._request("GET", endpoint)

            # API pode retornar url, downloadUrl, link, etc
            url = (
                data.get("url")
                or data.get("downloadUrl")
                or data.get("link")
                or data.get("urlDownload")
            )

            if url:
                logger.debug(f"✅ URL obtida: {url[:60]}...")
            else:
                logger.warning(
                    f"⚠️  Nenhuma URL de anexo encontrada na resposta\n"
                    f"   Campos disponíveis: {list(data.keys())}"
                )

            return url

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code

            if status_code == 404:
                logger.error(
                    f"❌ Erro 404: Anexo não encontrado\n"
                    f"   Conta: {receivable_id}\n"
                    f"   Anexo: {attachment_id}\n"
                    f"   Endpoint: {endpoint}"
                )
            else:
                logger.error(
                    f"❌ Erro HTTP {status_code} ao buscar URL de anexo\n"
                    f"   Resposta: {e.response.text[:300]}"
                )
            return None

        except Exception as e:
            logger.error(
                f"❌ Erro ao buscar URL de anexo: {type(e).__name__}: {e}\n"
                f"   Conta: {receivable_id}\n"
                f"   Anexo: {attachment_id}"
            )
            return None

    def _is_ip_address_safe(self, hostname: str) -> bool:
        """
        Verifica se um endereço IP é seguro (não é privado/loopback/etc).

        Args:
            hostname: hostname para verificar

        Returns:
            True se seguro (ou não é IP), False se IP perigoso
        """
        try:
            ip = ipaddress.ip_address(hostname)

            if ip.is_loopback:
                logger.error(f"SSRF: IP loopback rejeitado: {ip}")
                return False

            if ip.is_private:
                logger.error(f"SSRF: IP privado rejeitado: {ip}")
                return False

            if ip.is_multicast:
                logger.error(f"SSRF: IP multicast rejeitado: {ip}")
                return False

            if ip.is_reserved:
                logger.error(f"SSRF: IP reservado rejeitado: {ip}")
                return False

            return True
        except ValueError:
            # Não é um IP, é um hostname (OK)
            return True

    def _validate_receipt_url(self, url: str) -> bool:
        """
        Valida URL de recibo contra SSRF (Server-Side Request Forgery).

        Segurança:
        - Apenas HTTPS
        - Apenas domínios permitidos (Conta Azul)
        - Sem IPs privados/loopback
        - Sem redirects

        Args:
            url: URL do recibo

        Returns:
            True se válida, False caso contrário
        """
        if not url:
            logger.warning("URL vazia rejeitada")
            return False

        try:
            parsed = urlparse(url)

            # 1. Apenas HTTPS (não HTTP, ftp, etc)
            if parsed.scheme != "https":
                logger.error(
                    f"SSRF: Esquema não-HTTPS rejeitado: {parsed.scheme}://{parsed.netloc}"
                )
                return False

            # 2. Validar hostname (permitir apenas domínios Conta Azul)
            hostname = parsed.hostname

            if not hostname:
                logger.error("SSRF: URL sem hostname")
                return False

            # Verificar domínio permitido
            domain_allowed = any(
                hostname == domain or hostname.endswith(f".{domain}")
                for domain in self.ALLOWED_RECEIPT_DOMAINS
            )

            if not domain_allowed:
                logger.error(f"SSRF: Domínio não permitido: {hostname}")
                return False

            # 3. Rejeitar IPs privados/loopback/multicast
            if not self._is_ip_address_safe(hostname):
                return False

            logger.debug(f"URL validada: {url[:60]}...")
            return True

        except Exception as e:
            logger.error(f"SSRF: Erro ao validar URL: {e}")
            return False

    async def download_receipt(
        self,
        receipt_url: str,
    ) -> Optional[bytes]:
        """
        Baixa PDF do recibo com validação de SSRF.

        Args:
            receipt_url: URL do recibo

        Returns:
            Conteúdo do PDF em bytes ou None
        """
        # ✅ Validar URL contra SSRF
        if not self._validate_receipt_url(receipt_url):
            logger.error(f"Falha na validação SSRF: {receipt_url}")
            return None

        logger.debug(f"Baixando recibo de {receipt_url[:50]}...")

        try:
            async with httpx.AsyncClient(
                timeout=10,  # ✅ Reduzido de 30s para 10s
                limits=httpx.Limits(
                    max_connections=1,
                    max_keepalive_connections=0,
                ),
                follow_redirects=False,  # ✅ Não seguir redirects (SSRF prevention)
            ) as client:
                response = await client.get(receipt_url)
                response.raise_for_status()

                pdf_bytes = response.content

                # ✅ Validar tamanho da resposta
                if len(pdf_bytes) > self.MAX_RESPONSE_SIZE:
                    logger.error(
                        f"Resposta muito grande: {len(pdf_bytes)} bytes "
                        f"(máximo {self.MAX_RESPONSE_SIZE})"
                    )
                    return None

                logger.debug(f"PDF baixado: {len(pdf_bytes)} bytes")

                return pdf_bytes

        except Exception as e:
            logger.error(f"Erro ao baixar recibo: {e}")
            return None
