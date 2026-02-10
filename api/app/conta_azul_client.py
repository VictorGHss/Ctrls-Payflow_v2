"""
Cliente HTTP para integração com Conta Azul com suporte a rate limit e retry.
"""

import time
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings
from app.logging import setup_logging

logger = setup_logging(__name__)


class ContaAzulClient:
    """Cliente para API Conta Azul com backoff exponencial."""

    def __init__(self, access_token: Optional[str] = None):
        """
        Inicializa cliente Conta Azul.

        Args:
            access_token: Token de acesso (pode ser adicionado depois)
        """
        settings = get_settings()
        self.base_url = settings.CONTA_AZUL_API_BASE_URL
        self.access_token = access_token
        self.rate_limit_remaining = 600
        self.rate_limit_reset = None

    def set_token(self, access_token: str) -> None:
        """Define token de acesso."""
        self.access_token = access_token

    def _get_headers(self) -> Dict[str, str]:
        """Monta headers da requisição."""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _handle_rate_limit(self, response: httpx.Response) -> None:
        """Processa rate limit headers."""
        if "X-RateLimit-Remaining" in response.headers:
            self.rate_limit_remaining = int(
                response.headers["X-RateLimit-Remaining"],
            )
        if "X-RateLimit-Reset" in response.headers:
            self.rate_limit_reset = int(response.headers["X-RateLimit-Reset"])

    def _retry_with_backoff(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """
        Executa requisição com retry exponencial em 429.

        Args:
            method: HTTP method (GET, POST, etc)
            url: URL da requisição
            **kwargs: Argumentos para httpx.request

        Returns:
            Response object
        """
        max_retries = 5
        base_wait = 1  # 1 segundo

        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=30) as client:
                    response = client.request(
                        method,
                        url,
                        headers=self._get_headers(),
                        **kwargs,
                    )

                self._handle_rate_limit(response)

                # 429 = Too Many Requests
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = base_wait * (2 ** attempt)
                        logger.warning(
                            f"Rate limit atingido. Aguardando {wait_time}s "
                            f"(tentativa {attempt + 1}/{max_retries})",
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        response.raise_for_status()

                return response

            except httpx.HTTPError as e:
                logger.error(f"Erro HTTP: {e}")
                raise

        raise RuntimeError("Falha ao executar requisição após retries")

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        GET request.

        Args:
            endpoint: Caminho do endpoint (ex: /v1/customers)
            params: Query parameters

        Returns:
            JSON response
        """
        url = f"{self.base_url}{endpoint}"
        response = self._retry_with_backoff("GET", url, params=params)
        response.raise_for_status()
        return response.json()

    def post(
        self,
        endpoint: str,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        POST request.

        Args:
            endpoint: Caminho do endpoint
            json_data: Dados JSON

        Returns:
            JSON response
        """
        url = f"{self.base_url}{endpoint}"
        response = self._retry_with_backoff("POST", url, json=json_data or {})
        response.raise_for_status()
        return response.json()

    def get_installments(
        self,
        filter_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Busca parcelas/recebimentos.

        Args:
            filter_date: Data de filtro (ISO format, ex: '2025-02-01')

        Returns:
            Lista de parcelas
        """
        params = {}
        if filter_date:
            params["filter[modifiedDate]"] = f">={filter_date}"

        return self.get("/v1/installments", params=params)

    def get_receipt(self, receipt_id: str) -> Dict[str, Any]:
        """
        Busca detalhes de um recibo.

        Args:
            receipt_id: ID do recibo

        Returns:
            Detalhes do recibo
        """
        return self.get(f"/v1/receipts/{receipt_id}")

    def download_attachment(self, attachment_url: str) -> bytes:
        """
        Baixa um anexo (PDF).

        Args:
            attachment_url: URL completa do anexo

        Returns:
            Conteúdo do arquivo em bytes
        """
        with httpx.Client(timeout=30) as client:
            response = client.get(
                attachment_url,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            return response.content

