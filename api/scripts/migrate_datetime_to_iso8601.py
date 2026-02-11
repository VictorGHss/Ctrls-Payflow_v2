"""
Migração de dados: Converte expires_at de naive para timezone-aware (ISO 8601).

Esta migração atualiza tokens existentes no banco para usar o novo formato TZDateTime.

Executar:
    python scripts/migrate_datetime_to_iso8601.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Adicionar diretório app ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.config import get_settings
from app.database import init_db, OAuthToken
from app.logging import setup_logging

logger = setup_logging(__name__)


def migrate_datetime_to_iso8601():
    """
    Migra expires_at de datetime naive para string ISO 8601 com timezone.

    Lógica:
    1. Lê todos os tokens
    2. Para cada expires_at:
       - Se já é string ISO 8601 → Skip
       - Se é datetime naive → Assume UTC e converte para ISO 8601
       - Se é datetime aware → Converte para UTC e ISO 8601
    3. Atualiza no banco
    """
    logger.info("=" * 80)
    logger.info("MIGRAÇÃO DE DATETIME PARA ISO 8601")
    logger.info("=" * 80)

    settings = get_settings()
    engine, SessionLocal = init_db(settings.DATABASE_URL)
    db = SessionLocal()

    try:
        # Buscar todos os tokens
        tokens = db.query(OAuthToken).all()

        if not tokens:
            logger.info("✅ Nenhum token encontrado. Migração não necessária.")
            return

        logger.info(f"📊 Encontrados {len(tokens)} token(s) para verificar")

        migrated_count = 0
        already_migrated_count = 0

        for token in tokens:
            account_id = token.account_id
            expires_at = token.expires_at

            logger.info(f"\n📍 Token: {account_id[:20]}...")
            logger.info(f"   expires_at atual: {expires_at}")
            logger.info(f"   Tipo: {type(expires_at)}")

            # Se já é uma string, verificar se é ISO 8601 válida
            if isinstance(expires_at, str):
                try:
                    dt = datetime.fromisoformat(expires_at)
                    if dt.tzinfo is not None:
                        logger.info(f"   ✅ Já é ISO 8601 com timezone - Skip")
                        already_migrated_count += 1
                        continue
                    else:
                        logger.info(f"   ⚠️  É ISO 8601 mas sem timezone - Migrando")
                        # Assumir UTC
                        dt = dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(f"   ⚠️  String inválida, tentando converter...")
                    continue

            # Se é datetime, converter para ISO 8601 com timezone
            elif isinstance(expires_at, datetime):
                # Se naive, assumir UTC
                if expires_at.tzinfo is None:
                    logger.info(f"   🔄 Datetime naive detectado - Assumindo UTC")
                    dt = expires_at.replace(tzinfo=timezone.utc)
                else:
                    logger.info(f"   🔄 Datetime aware detectado - Convertendo para UTC")
                    dt = expires_at.astimezone(timezone.utc)
            else:
                logger.error(f"   ❌ Tipo não reconhecido: {type(expires_at)}")
                continue

            # Converter para ISO 8601 e atualizar
            iso_string = dt.isoformat()

            # Atualizar diretamente no banco via SQL raw
            # (para evitar conversão automática do ORM)
            db.execute(
                text("UPDATE oauth_tokens SET expires_at = :expires_at WHERE id = :id"),
                {"expires_at": iso_string, "id": token.id}
            )

            logger.info(f"   ✅ Migrado para: {iso_string}")
            migrated_count += 1

        # Commit todas as mudanças
        db.commit()

        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMO DA MIGRAÇÃO")
        logger.info("=" * 80)
        logger.info(f"Total de tokens: {len(tokens)}")
        logger.info(f"✅ Migrados: {migrated_count}")
        logger.info(f"⏭️  Já migrados: {already_migrated_count}")
        logger.info(f"❌ Erros: {len(tokens) - migrated_count - already_migrated_count}")

        if migrated_count > 0:
            logger.info("\n✅ Migração concluída com sucesso!")
            logger.info("   expires_at agora está em formato ISO 8601 com timezone")
        else:
            logger.info("\n✅ Todos os tokens já estavam no formato correto")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erro durante migração: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate_datetime_to_iso8601()

