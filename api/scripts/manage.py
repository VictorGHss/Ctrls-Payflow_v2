#!/usr/bin/env python
"""
Script para criar conta de teste ou fazer reset do banco.
"""

import sys
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import AzulAccount, PollingCheckpoint, init_db
from app.logging import setup_logging

logger = setup_logging(__name__)


def create_test_account(db: Session) -> None:
    """Cria conta de teste."""
    existing = (
        db.query(AzulAccount)
        .filter(AzulAccount.account_id == "test_account_001")
        .first()
    )

    if existing:
        logger.info("Conta de teste já existe")
        return

    account = AzulAccount(
        account_id="test_account_001",
        owner_name="Test Owner",
        owner_email="test@example.com",
        company_name="Test Company",
        is_active=1,
    )
    db.add(account)

    checkpoint = PollingCheckpoint(
        account_id="test_account_001",
        last_processed_date=datetime.now(timezone.utc),
    )
    db.add(checkpoint)

    db.commit()
    logger.info("Conta de teste criada com sucesso")


def reset_database() -> None:
    """Reseta o banco de dados (apaga tudo)."""
    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)

    from app.database import Base

    logger.warning("Deletando todas as tabelas...")
    Base.metadata.drop_all(bind=engine)

    logger.info("Recriando tabelas...")
    Base.metadata.create_all(bind=engine)

    logger.info("Banco resetado com sucesso")


def main() -> None:
    """Main function."""
    if len(sys.argv) < 2:
        print("Uso: python manage.py [create-test | reset]")
        sys.exit(1)

    command = sys.argv[1]
    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)

    if command == "create-test":
        db = SessionLocal()
        try:
            create_test_account(db)
        finally:
            db.close()

    elif command == "reset":
        confirm = input("Tem certeza? (sim/nao): ")
        if confirm.lower() == "sim":
            reset_database()
        else:
            logger.info("Operação cancelada")

    else:
        print(f"Comando desconhecido: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
