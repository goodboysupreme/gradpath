import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import CATALOG_SCHEMA
from app.db.models import catalog as catalog_models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = catalog_models.Base.metadata

DATABASE_URL_ENV = "GRADPATH_API_DATABASE_URL"
OFFLINE_DATABASE_URL = "postgresql://offline@localhost/gradpath_offline"


def database_url(*, offline: bool) -> URL:
    raw_url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not raw_url:
        if offline:
            return make_url(OFFLINE_DATABASE_URL)
        raise RuntimeError(f"{DATABASE_URL_ENV} is required for online migrations")

    try:
        url = make_url(raw_url)
    except ArgumentError as error:
        raise RuntimeError(f"{DATABASE_URL_ENV} is not a valid database URL") from error

    if url.drivername not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError(f"{DATABASE_URL_ENV} must use postgresql:// or postgresql+asyncpg://")
    drivername = "postgresql" if offline else "postgresql+asyncpg"
    return url.set(drivername=drivername)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(offline=True),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema=CATALOG_SCHEMA,
    )
    with context.begin_transaction():
        context.execute(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_SCHEMA}")
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_SCHEMA}"))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table="alembic_version",
        version_table_schema=CATALOG_SCHEMA,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        database_url(offline=False),
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.begin() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
