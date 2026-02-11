"""
Worker de polling para Conta Azul.
Serviço independente que consulta periodicamente por contas a receber alteradas.
"""

import asyncio
import sys

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import init_db
from app.logging import setup_logging
from app.worker.processor import FinancialProcessor

logger = setup_logging(__name__)


async def worker_loop():
    """
    Loop principal do worker.
    Executa polling periódico de contas a receber.
    """
    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)

    logger.info("=" * 80)
    logger.info("Worker iniciado")
    logger.info(f"Intervalo de polling: {settings.POLLING_INTERVAL_SECONDS}s")
    logger.info(f"Janela de segurança: {settings.POLLING_SAFETY_WINDOW_MINUTES}min")
    logger.info("=" * 80)

    while True:
        db: Session | None = None
        try:
            db = SessionLocal()
            assert db is not None, "Failed to create database session"
            processor = FinancialProcessor(db)

            # Buscar e processar contas ativas
            accounts = processor.get_active_accounts()

            if not accounts:
                logger.debug("Nenhuma conta ativa encontrada")
            else:
                logger.info(f"Processando {len(accounts)} conta(s) ativa(s)")

                total_processed = 0
                total_errors = 0

                for account in accounts:
                    try:
                        logger.info(
                            f"Processando conta: {account.account_id[:10]}... "
                            f"({account.company_name})"
                        )
                        processed, errors = await processor.process_account(account)
                        total_processed += processed
                        total_errors += errors

                        if processed > 0:
                            logger.info(
                                f"  ✓ {processed} recibos processados para "
                                f"{account.company_name}"
                            )
                        if errors > 0:
                            logger.warning(
                                f"  ✗ {errors} erro(s) para {account.company_name}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Erro crítico ao processar {account.account_id[:10]}...: {e}",
                            exc_info=True,
                        )
                        total_errors += 1

                logger.info(
                    f"Ciclo completo: {total_processed} recibos, {total_errors} erro(s)"
                )

        except Exception as e:
            logger.error(f"Erro no loop de polling: {e}", exc_info=True)

        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

            # Aguardar próximo ciclo
            sleep_time = settings.POLLING_INTERVAL_SECONDS
            logger.debug(f"Próximo polling em {sleep_time}s")
            await asyncio.sleep(sleep_time)


def main():
    """Ponto de entrada do worker."""
    logger.info("Iniciando PayFlow Worker")

    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker encerrado por usuário")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erro fatal no worker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
