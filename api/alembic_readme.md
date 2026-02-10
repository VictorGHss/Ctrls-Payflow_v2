"""
Alembic initialization and migration management.

Para criar uma nova migration após mudança em models:
    alembic revision --autogenerate -m "descrição da mudança"

Para aplicar migrations:
    alembic upgrade head

Para reverter:
    alembic downgrade -1
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base

# ...existing code...

