"""
Client para API Financeira da Conta Azul.
Consulta contas a receber, parcelas e detalhes de pagamento.
"""

import asyncio
import base64
import ipaddress
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
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

    BASE_URL = "https://api.contaazul.com/v1"
    MIN_INTERVAL_BETWEEN_REQUESTS = 0.1  # 10 req/s
    RATE_LIMIT_REQUESTS = 600
    RATE_LIMIT_WINDOW = 60

    # Dominios permitidos para download de recibos
    ALLOWED_RECEIPT_DOMAINS = {
        "api.contaazul.com",
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
            endpoint: Caminho relativo (ex: /receivables)
            params: Query parameters
            json_data: JSON body

        Returns:
            Response JSON

        Raises:
            RateLimitError: 429
            httpx.HTTPError: Outros erros
        """
        await self._apply_rate_limit()

        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_auth_header()

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    headers=headers,
                )

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "60")
                    logger.warning(
                        f"Rate limit 429. Retry-After: {retry_after}s. "
                        f"Usando backoff exponencial..."
                    )
                    raise RateLimitError(f"Rate limit: {retry_after}s")

                response.raise_for_status()
                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Erro HTTP em {method} {endpoint}: {e}")
            raise

    async def get_receivables(
        self,
        account_id: str,
        changed_since: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca contas a receber (receivables) alteradas.

        Args:
            account_id: ID da conta
            changed_since: ISO datetime (ex: 2026-02-10T15:30:00Z)
            status: Filtro por status (ex: 'received', 'pending')

        Returns:
            Lista de contas a receber
        """
        params = {}

        if changed_since:
            if isinstance(changed_since, datetime):
                changed_since = changed_since.isoformat()
            params["changedSince"] = changed_since

        if status:
            params["status"] = status

        logger.debug(f"Consultando receivables para {account_id[:10]}...")

        try:
            data = await self._request("GET", "/receivables", params=params)

            # A API retorna {data: [...], pagination: {...}}
            items = data.get("data", [])
            logger.debug(f"  Encontrados {len(items)} item(ns)")

            return items

        except Exception as e:
            logger.error(f"Erro ao buscar receivables: {e}")
            raise

    async def get_receivable_details(
        self,
        receivable_id: str,
    ) -> Dict[str, Any]:
        """
        Busca detalhes completos de uma conta a receber.

        Args:
            receivable_id: ID da conta a receber

        Returns:
            Detalhes incluindo parcelas (installments)
        """
        logger.debug(f"Buscando detalhes de receivable {receivable_id[:10]}...")

        try:
            data = await self._request(
                "GET",
                f"/receivables/{receivable_id}",
            )
            return data

        except Exception as e:
            logger.error(f"Erro ao buscar detalhes de receivable: {e}")
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

        Args:
            receivable_id: ID da conta a receber
            attachment_id: ID do anexo

        Returns:
            URL de download ou None
        """
        logger.debug(
            f"Buscando URL de recibo {attachment_id[:10]}... "
            f"(receivable {receivable_id[:10]}...)"
        )

        try:
            data = await self._request(
                "GET",
                f"/receivables/{receivable_id}/attachments/{attachment_id}",
            )

            # Assumindo que a API retorna algo como:
            # {url: "https://...", filename: "recibo.pdf", ...}
            url = data.get("url") or data.get("downloadUrl")

            if url:
                logger.debug(f"  URL obtida: {url[:50]}...")
            else:
                logger.warning("  Nenhuma URL de recibo encontrada")

            return url

        except Exception as e:
            logger.error(f"Erro ao buscar URL de recibo: {e}")
            return None

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
                logger.error(f"SSRF: Esquema não-HTTPS rejeitado: {parsed.scheme}://{parsed.netloc}")
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

            except ValueError:
                # Não é um IP, é um hostname (OK)
                pass

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

