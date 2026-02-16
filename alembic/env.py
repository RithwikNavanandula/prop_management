"""Alembic env.py – configured for Property Management V2."""
import sys, os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Add project root to sys.path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
from app.config import get_settings

# Import ALL models so Base.metadata sees them
from app.modules.properties import models as _pm
from app.modules.leasing import models as _lm
from app.modules.billing import models as _bm
from app.modules.accounting import models as _am
from app.modules.maintenance import models as _mm
from app.modules.crm import models as _cm
from app.modules.marketing import models as _mkm
from app.modules.compliance import models as _cpm
from app.modules.workflow import models as _wm
from app.auth import models as _auth

config = context.config

# Override sqlalchemy.url from app settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          render_as_batch=True)  # batch mode for SQLite ALTER
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
