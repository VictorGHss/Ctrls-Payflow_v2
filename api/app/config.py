"""
Configurações da aplicação usando Pydantic Settings.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações centralizadas."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ===== Conta Azul =====
    CONTA_AZUL_CLIENT_ID: str
    CONTA_AZUL_CLIENT_SECRET: str
    CONTA_AZUL_REDIRECT_URI: str
    CONTA_AZUL_API_BASE_URL: str = "https://api-v2.contaazul.com"
    CONTA_AZUL_AUTH_BASE_URL: str = "https://auth.contaazul.com"
    CONTA_AZUL_AUTH_URL: str = "https://auth.contaazul.com/login"
    CONTA_AZUL_TOKEN_URL: str = "https://auth.contaazul.com/oauth2/token"

    # ===== Segurança =====
    MASTER_KEY: str  # Base64 encoded 32 bytes
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440

    # ===== SMTP =====
    SMTP_HOST: str
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM: str
    SMTP_REPLY_TO: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False  # Para porta 465
    SMTP_TIMEOUT: int = 10  # Timeout em segundos

    # ===== Polling =====
    POLLING_INTERVAL_SECONDS: int = 300  # 5 minutos
    POLLING_INITIAL_LOOKBACK_DAYS: int = 30
    # Janela de segurança: voltar N minutos para não perder eventos
    POLLING_SAFETY_WINDOW_MINUTES: int = 10

    # ===== API =====
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_LOG_LEVEL: str = "info"

    # ===== Cloudflare Tunnel =====
    CLOUDFLARE_TUNNEL_TOKEN: Optional[str] = None

    # ===== Database =====
    DATABASE_URL: str = "sqlite:///./data/payflow.db"
    DATABASE_ECHO: bool = False

    # ===== Fallback Médicos =====
    DOCTORS_FALLBACK_JSON: str = "{}"

    # ===== Projeto =====
    PROJECT_NAME: str = "PayFlow Automation"
    PROJECT_VERSION: str = "1.0.0"
    APP_ROOT: Path = Path(__file__).parent.parent


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância única das configurações."""
    return Settings()  # pyright: ignore[reportCallIssue]
