"""Alembic, driven by the same async engine the application uses.

There is no synchronous driver anywhere in this project (H1), so migrations run through
`connection.run_sync` rather than by adding psycopg alongside asyncpg. One driver is one
fewer thing that can behave differently from the code under test.
"""

import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from upto.db import database_url

config = context.config
config.set_main_option("sqlalchemy.url", database_url())

# No model metadata: the migrations are hand-written, so there is nothing to compare
# against and `--autogenerate` is deliberately unusable here.
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
