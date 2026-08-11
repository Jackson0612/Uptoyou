"""The database engine, async end to end, and built on first use rather than on import.

H1 is the reason there is no synchronous path here at all. FastAPI handlers run on one
event loop shared by every connected client; a synchronous driver blocks that loop for the
whole query, and while it is blocked nobody is served. The hazard notes that the most likely
route into it is *following a working example*, because most tutorials use the synchronous
mode — so the async engine is the only one available, and there is no sync alternative to
reach for by accident.

**Why the engine is lazy.** It used to be created at import time from an environment
variable. D33 rules that operational credentials reach a task as an **Airflow Connection**,
which a DAG can only read once it is running — after the module would already have been
imported. Binding at import forced the URL into the environment, which is the arrangement
D33 exists to reject. Now a caller may pass a URL it just read from a Connection, and the
environment variable is only the fallback the API uses.
"""

import os
from typing import Dict

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

DATABASE_URL_VAR = "UPTO_DATABASE_URL"

_engines: Dict[str, AsyncEngine] = {}


def database_url() -> str:
    """The fallback URL, and it fails loudly when absent.

    H16's mitigation asks the stack to fail at startup with a clear message when a bootstrap
    variable is missing, rather than failing later inside a request where it reads as an
    application bug.
    """
    url = os.environ.get(DATABASE_URL_VAR)
    if not url:
        raise RuntimeError(
            "{} is not set, and no URL was passed. The API reads it from the environment; a "
            "DAG passes one built from its Airflow Connection (D33).".format(DATABASE_URL_VAR)
        )
    return _checked(url)


def _checked(url: str) -> str:
    if "+asyncpg" not in url:
        raise RuntimeError(
            "the database URL must use the asyncpg driver (postgresql+asyncpg://...). A "
            "synchronous driver blocks the event loop for every connected client — see H1."
        )
    return url


def engine_for(url: str | None = None) -> AsyncEngine:
    resolved = _checked(url) if url else database_url()
    if resolved not in _engines:
        _engines[resolved] = create_async_engine(
            resolved,
            # One API worker (H2), so the pool is small on purpose rather than by omission.
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            echo=False,
        )
    return _engines[resolved]


def session_factory(url: str | None = None) -> async_sessionmaker:
    return async_sessionmaker(engine_for(url), expire_on_commit=False)


async def dispose_all() -> None:
    for engine in list(_engines.values()):
        await engine.dispose()
    _engines.clear()
