"""
Worker de polling para processar recibos periodicamente.
"""

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import init_db
from app.logging import setup_logging
from app.payment_processor import PaymentProcessor

logger = setup_logging(__name__, level="INFO")


async def worker_loop():
    """
    Loop principal do worker.
    Executa polling periódico.
    """
    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)

    logger.info("Worker iniciado")
    logger.info(f"Intervalo de polling: {settings.POLLING_INTERVAL_SECONDS}s")

    while True:
        try:
            db: Session = SessionLocal()
            processor = PaymentProcessor(db, settings.DOCTORS_FALLBACK_JSON)

            # Buscar e processar contas ativas
            accounts = processor.get_active_accounts()

            if not accounts:
                logger.info("Nenhuma conta ativa encontrada")
            else:
                total_processed = 0
                total_errors = 0

                for account in accounts:
                    try:
                        processed, errors = processor.process_account(account)
                        total_processed += processed
                        total_errors += errors
                    except Exception as e:
                        logger.error(f"Erro ao processar {account.account_id}: {e}")
                        total_errors += 1

                logger.info(
                    f"Ciclo completo: {total_processed} recibos, {total_errors} erros",
                )

        except Exception as e:
            logger.error(f"Erro no loop de polling: {e}")

        finally:
            try:
                db.close()
            except:
                pass

            # Aguardar próximo ciclo
            logger.info(
                f"Próximo polling em {settings.POLLING_INTERVAL_SECONDS}s",
            )
            await asyncio.sleep(settings.POLLING_INTERVAL_SECONDS)


def main():
    """Ponto de entrada do worker."""
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker encerrado por usuário")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

