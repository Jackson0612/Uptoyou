"""The database engine, async end to end.

H1 is the reason there is no synchronous path here at all. FastAPI handlers run on one
event loop shared by every connected client; a synchronous driver blocks that loop for the
whole query, and while it is blocked nobody is served. The hazard notes that the most
likely route into it is *following a working example*, because most tutorials use the
synchronous mode — so the async engine is created here, once, and there is no sync
alternative to reach for by accident.
"""

import os

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

DATABASE_URL_VAR = "UPTO_DATABASE_URL"


def database_url() -> str:
    """Read the URL, and fail loudly when it is missing.

    H16's mitigation asks the stack to fail at startup with a clear message when a
    bootstrap variable is absent, rather than failing later inside a request where it
    reads as an application bug.
    """
    url = os.environ.get(DATABASE_URL_VAR)
    if not url:
        raise RuntimeError(
            "{} is not set. It is a bootstrap variable: see app/.env.example for the "
            "names, and app/.env for this machine's values.".format(DATABASE_URL_VAR)
        )
    if "+asyncpg" not in url:
        raise RuntimeError(
            "{} must use the asyncpg driver (postgresql+asyncpg://...). A synchronous "
            "driver blocks the event loop for every connected client — see H1.".format(DATABASE_URL_VAR)
        )
    return url


def build_engine() -> AsyncEngine:
    return create_async_engine(
        database_url(),
        # One API worker (H2), so the pool is small on purpose rather than by omission.
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        echo=False,
    )


engine: AsyncEngine = build_engine()
Session = async_sessionmaker(engine, expire_on_commit=False)
