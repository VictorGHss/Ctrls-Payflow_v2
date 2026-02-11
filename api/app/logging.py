"""
Logging com redação de informações sensíveis.
"""

import logging
import re
from typing import Dict, Optional

# Regex para redação de dados sensíveis
SENSITIVE_PATTERNS: Dict[str, str] = {
    "token": r"(authorization|access_token|refresh_token|bearer|token)[:\s]*([a-zA-Z0-9._\-]+)",
    "password": r"(password|passwd|pwd|secret)[:\s]*([a-zA-Z0-9._\-]+)",
    "api_key": r"(api[_-]?key|apikey)[:\s]*([a-zA-Z0-9._\-]+)",
}


class SensitiveDataFilter(logging.Filter):
    """Filtra e redige dados sensíveis em logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Redige dados sensíveis na mensagem de log.

        Args:
            record: LogRecord

        Returns:
            True (sempre deixa passar)
        """
        # Redação na mensagem
        record.msg = self._redact(str(record.msg))

        # Redação nos args
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact(str(arg)) for arg in record.args)

        return True

    @staticmethod
    def _redact(text: str) -> str:
        """
        Redige dados sensíveis em um texto.

        Args:
            text: Texto a rediegir

        Returns:
            Texto com dados rediegidos
        """
        for _key, pattern in SENSITIVE_PATTERNS.items():
            text = re.sub(
                pattern,
                r"\1: ***REDACTED***",
                text,
                flags=re.IGNORECASE,
            )
        return text


def setup_logging(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    Configura logging com redação de dados sensíveis.

    Args:
        name: Nome do logger
        level: Nível de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Caminho do arquivo de log (opcional)

    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Remover handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Formato do log
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)

    # Handler arquivo (opcional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SensitiveDataFilter())
        logger.addHandler(file_handler)

    return logger
