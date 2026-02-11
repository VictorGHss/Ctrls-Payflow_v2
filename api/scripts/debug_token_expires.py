"""
Script de debug para verificar expires_at e timezone info dos tokens.

Execução:
    python scripts/debug_token_expires.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Adicionar diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.database import init_db, OAuthToken
from app.logging import setup_logging

logger = setup_logging(__name__)


def debug_token_expires():
    """
    Debug de todos os tokens no banco.

    Mostra:
    - account_id
    - expires_at (valor raw)
    - expires_at.tzinfo
    - Tipo de expires_at
    - Se está expirado
    - Tempo restante/passado
    """
    logger.info("=" * 80)
    logger.info("🔍 DEBUG DE TOKENS - EXPIRES_AT E TIMEZONE INFO")
    logger.info("=" * 80)

    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)
    db = SessionLocal()

    try:
        tokens = db.query(OAuthToken).all()

        if not tokens:
            logger.info("📭 Nenhum token encontrado no banco")
            return

        logger.info(f"📊 Total de tokens: {len(tokens)}\n")

        now = datetime.now(timezone.utc)
        logger.info(f"⏰ Hora atual (UTC): {now.isoformat()}\n")

        for idx, token in enumerate(tokens, 1):
            logger.info("─" * 80)
            logger.info(f"Token #{idx}")
            logger.info("─" * 80)

            # Account ID
            logger.info(f"📝 account_id: {token.account_id}")

            # expires_at raw
            expires_at = token.expires_at
            logger.info(f"📅 expires_at: {expires_at}")
            logger.info(f"   Tipo: {type(expires_at).__name__}")

            # Timezone info
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    logger.warning(f"   ⚠️  tzinfo: None (NAIVE - problema!)")
                else:
                    logger.info(f"   ✅ tzinfo: {expires_at.tzinfo}")

                # ISO format
                logger.info(f"   ISO 8601: {expires_at.isoformat()}")

                # Verificar se expirado
                try:
                    # Se naive, assumir UTC para comparação
                    expires_at_aware = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
                    is_expired = now >= expires_at_aware

                    if is_expired:
                        time_diff = now - expires_at_aware
                        logger.error(f"   ❌ Status: EXPIRADO há {time_diff.total_seconds():.0f}s")
                    else:
                        time_diff = expires_at_aware - now
                        logger.info(f"   ✅ Status: VÁLIDO por mais {time_diff.total_seconds():.0f}s")
                except TypeError as e:
                    logger.error(f"   ❌ Erro ao comparar: {e}")

            elif isinstance(expires_at, str):
                logger.info(f"   📝 String value: {expires_at}")
                try:
                    dt = datetime.fromisoformat(expires_at)
                    if dt.tzinfo is None:
                        logger.warning(f"   ⚠️  String sem timezone info")
                    else:
                        logger.info(f"   ✅ String com timezone: {dt.tzinfo}")
                except ValueError as e:
                    logger.error(f"   ❌ String não é ISO 8601 válida: {e}")

            else:
                logger.error(f"   ❌ Tipo não reconhecido: {type(expires_at)}")

            # Timestamps
            logger.info(f"🕒 created_at: {token.created_at}")
            logger.info(f"🕒 updated_at: {token.updated_at}")
            logger.info("")

        logger.info("=" * 80)
        logger.info("✅ DEBUG COMPLETO")
        logger.info("=" * 80)

        # Resumo
        naive_count = sum(
            1 for t in tokens
            if isinstance(t.expires_at, datetime) and t.expires_at.tzinfo is None
        )
        aware_count = sum(
            1 for t in tokens
            if isinstance(t.expires_at, datetime) and t.expires_at.tzinfo is not None
        )
        string_count = sum(
            1 for t in tokens
            if isinstance(t.expires_at, str)
        )

        logger.info(f"\n📊 Resumo:")
        logger.info(f"   Naive datetimes: {naive_count}")
        logger.info(f"   Aware datetimes: {aware_count}")
        logger.info(f"   Strings: {string_count}")

        if naive_count > 0:
            logger.warning(f"\n⚠️  {naive_count} token(s) com datetime naive detectado(s)!")
            logger.warning(f"   Execute: python scripts/migrate_datetime_to_iso8601.py")
        else:
            logger.info(f"\n✅ Todos os tokens estão no formato correto!")

    except Exception as e:
        logger.error(f"❌ Erro durante debug: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        db.close()


if __name__ == "__main__":
    debug_token_expires()

