"""The API. One endpoint so far, and it is the one the stack's health depends on.

Nothing about the product is here yet. The build order puts the pipeline first, so the
first real endpoints arrive after the ingest tables exist.
"""

from fastapi import FastAPI, Response, status
from sqlalchemy import text

from .db import dispose_all, session_factory

app = FastAPI(
    title="Up to you",
    summary="Decide one meal, without anybody having to give something up first.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/health")
async def health(response: Response) -> dict:
    """Answer only after the database has answered.

    A health check that reports the process is alive tells the orchestrator nothing worth
    acting on. compose gates the proxy on this endpoint, so it has to mean *the stack can
    serve a request*, which includes reaching the database.
    """
    try:
        async with session_factory()() as session:
            await session.execute(text("select 1"))
    except Exception as failure:  # noqa: BLE001 — the reason belongs in the body
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "database": "unreachable", "detail": str(failure)[:200]}
    return {"status": "ok", "database": "reachable"}


@app.on_event("shutdown")
async def dispose_engines() -> None:
    await dispose_all()
