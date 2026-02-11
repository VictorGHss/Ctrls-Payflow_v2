"""
Modelos SQLAlchemy para persistência.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa com typing para SQLAlchemy."""


class OAuthToken(Base):
    """Armazena tokens OAuth (criptografados)."""

    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)  # criptografado
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)  # criptografado
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<OAuthToken account_id={self.account_id}>"


class PollingCheckpoint(Base):
    """Checkpoint para polling resiliente."""

    __tablename__ = "polling_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    last_processed_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_processed_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<PollingCheckpoint account_id={self.account_id}>"


class FinancialCheckpoint(Base):
    """Checkpoint para polling de contas a receber (receivables)."""

    __tablename__ = "financial_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Última data processada (ISO 8601) com janela de segurança
    last_processed_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Timestamp da última atualização do checkpoint
    checkpoint_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    # Metadata opcional (ex: último ID processado, etc) - renomeado para checkpoint_metadata
    checkpoint_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "account_id",
            name="uq_financial_checkpoint_account",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialCheckpoint account_id={self.account_id} "
            f"last_processed={self.last_processed_changed_at}>"
        )


class SentReceipt(Base):
    """Registra recibos enviados (idempotência forte)."""

    __tablename__ = "sent_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    installment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # URL do anexo/recibo (para deduplicação)
    attachment_url: Mapped[str] = mapped_column(Text, nullable=False)
    # ID da baixa/pagamento (se existir)
    payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Email do médico/destinatário
    doctor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    # Timestamp do envio
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # Hash SHA256 do PDF (para deduplicação extra)
    receipt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Metadata: {customer_name, amount, payment_date, etc} - renomeado para receipt_metadata
    receipt_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Constraint de idempotência: (installment_id, attachment_url) deve ser único
    __table_args__ = (
        UniqueConstraint(
            "account_id",
            "installment_id",
            "attachment_url",
            name="uq_sent_receipt_idempotency",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SentReceipt installment_id={self.installment_id} "
            f"url={self.attachment_url[:30]}...>"
        )


class EmailLog(Base):
    """Log de envios de email."""

    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    receipt_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    doctor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'sent', 'failed', 'pending'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:
        return f"<EmailLog receipt_id={self.receipt_id} status={self.status}>"


class AzulAccount(Base):
    """Informações da conta Azul conectada."""

    __tablename__ = "azul_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    owner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1)  # SQLite bool como int
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    account_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<AzulAccount account_id={self.account_id}>"


def init_db(database_url: str) -> tuple:
    """
    Inicializa banco de dados.

    Args:
        database_url: URL do banco (ex: sqlite:///./data/payflow.db)

    Returns:
        Tupla (engine, SessionLocal)
    """
    # Garantir diretório do SQLite existe
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]
        db_dir = Path(db_path).parent
        if db_dir and not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        echo=False,
    )

    # Criar todas as tabelas
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def get_db_session(SessionLocal):
    """Dependency para obter sessão do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
