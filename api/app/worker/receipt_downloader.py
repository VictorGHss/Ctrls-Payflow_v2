"""
Serviço para download, validação e armazenamento de recibos.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional, Tuple

from app.logging import setup_logging
from app.worker.conta_azul_financial_client import ContaAzulFinancialClient

logger = setup_logging(__name__)


class ReceiptDownloader:
    """
    Gerencia download e validação de recibos.
    """

    def __init__(self, client: ContaAzulFinancialClient):
        """
        Inicializa downloader.

        Args:
            client: ContaAzulFinancialClient
        """
        self.client = client

    async def download_receipt(
        self,
        receipt_url: str,
    ) -> Optional[Tuple[bytes, str]]:
        """
        Baixa recibo e valida integridade.

        Args:
            receipt_url: URL do recibo

        Returns:
            Tupla (pdf_bytes, filename) ou None se falhou
        """
        if not receipt_url:
            logger.warning("URL de recibo vazia")
            return None

        logger.debug(f"Iniciando download de {receipt_url[:50]}...")

        try:
            pdf_bytes = await self.client.download_receipt(receipt_url)

            if not pdf_bytes:
                logger.warning("PDF vazio ou não baixado")
                return None

            # Validar que é um PDF válido
            if not pdf_bytes.startswith(b"%PDF"):
                logger.warning("Conteúdo baixado não é um PDF válido")
                return None

            # Gerar nome de arquivo baseado em hash
            pdf_hash = hashlib.md5(pdf_bytes).hexdigest()[:8]
            filename = f"recibo_{pdf_hash}.pdf"

            logger.debug(
                f"Recibo baixado com sucesso: {filename} ({len(pdf_bytes)} bytes)"
            )

            return pdf_bytes, filename

        except Exception as e:
            logger.error(f"Erro ao baixar recibo: {e}")
            return None

    def validate_receipt(
        self,
        pdf_bytes: Optional[bytes],
    ) -> bool:
        """
        Valida integridade do PDF.

        Args:
            pdf_bytes: Conteúdo do PDF

        Returns:
            True se válido
        """
        if not pdf_bytes:
            return False

        # Verificar magic bytes do PDF
        if not pdf_bytes.startswith(b"%PDF"):
            logger.warning("PDF com magic bytes inválidos")
            return False

        # Tamanho mínimo (1KB) e máximo (100MB)
        if len(pdf_bytes) < 1024:
            logger.warning(f"PDF muito pequeno: {len(pdf_bytes)} bytes")
            return False

        if len(pdf_bytes) > 100 * 1024 * 1024:
            logger.warning(f"PDF muito grande: {len(pdf_bytes)} bytes")
            return False

        return True

    def get_receipt_hash(self, pdf_bytes: bytes) -> str:
        """
        Calcula hash SHA256 do PDF para deduplicação.

        Args:
            pdf_bytes: Conteúdo do PDF

        Returns:
            Hash SHA256 em hex
        """
        return hashlib.sha256(pdf_bytes).hexdigest()

