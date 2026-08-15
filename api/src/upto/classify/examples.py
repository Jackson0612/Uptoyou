"""D88's example store: loading the frozen set into vectors, and retrieving cribs from it.

Load it once, inside the stack, with the model service up (it is behind a compose profile):

    docker compose --profile model up -d ollama
    docker compose exec ollama ollama pull bge-m3
    docker compose exec api python -m upto.classify.examples load

Exit **0** the table holds the set · **3** the embedding service is not up and **nothing was
written** — ordinary rather than a failure, the same code `upto.classify.run` uses for the
same situation.

**The load is one transaction that empties the table and refills it.** Not an upsert: the
table is a derived cache of `testset_v1.json` (0018), and a partial refresh would leave rows
from two digests side by side while `testset_sha256` claimed one of them. Delete-then-insert
means the table is either wholly the old set or wholly the new one, and the digest column is
then a true statement about every row rather than about most of them.

**Retrieval is leave-one-out and that is not a detail.** During an evaluation round the
asked name is itself in the store — the store *is* the frozen set — so a neighbour search
that did not exclude it would hand the model the exam answer as a worked example, and the
round would measure the lookup rather than the classifier. `nearest(exclude_name=...)` is
what keeps the experiment honest, and D82's rule that an example drawn from the exam teaches
the exam is why it is refused at the query rather than filtered afterwards.

**Ordering is exact cosine distance over a sequential scan.** 179 rows (0018 explains the
number) is microseconds, and the ANN indexes pgvector offers are approximate — they would
buy a speed nobody needs by sometimes dropping the true nearest neighbour, which is a
different experiment.

Nothing here is imported by `upto.evaluate.run_round` at module level: this module pulls
SQLAlchemy, the host Python that runs the score tests has none, and the round runner is
importable there today. The import happens inside `--rag` alone.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from upto.classify.embed import EMBED_MODEL, EmbedUnavailable, as_literal, available, embed
from upto.db import database_url
from upto.evaluate.score import load_testset

# One request per 32 names. The service embeds a batch in one pass, and a batch this size
# keeps the request body small enough to read in a log if it ever has to be.
EMBED_BATCH = 32

# How many cribs a prompt carries. Five is the starting value of the variable under test —
# the round file records it, so a later k is a different round rather than a silent change.
K = 5

# Who wrote the labels this loader stores. **Not the owner** — disclosed 2026-08-15: the
# frozen set was drafted by Fable 5 and cross-checked against Gemini, and never
# hand-adjudicated. It is stamped rather than left implicit because an example teaches, and a
# crib that turns out to have taught the wrong thing has to name its teacher. A later case
# book written by a different model arrives under its own value and is distinguishable here.
TESTSET_LABELED_BY = "fable5+gemini"


# --- the store ---------------------------------------------------------------------------


async def stored_sha(target) -> str | None:
    """The digest the stored rows were built from, or None if the table is empty.

    Singular on purpose: the load writes one digest across every row, so more than one value
    here means something wrote outside the load, and the caller should be told that rather
    than shown whichever one sorted first.
    """
    rows = (await _execute(target, "select distinct testset_sha256 from example_embedding")).all()
    if not rows:
        return None
    if len(rows) > 1:
        raise RuntimeError(
            "example_embedding holds rows from "
            f"{len(rows)} different test-set digests — it is written whole by "
            "`python -m upto.classify.examples load` and by nothing else. Re-run the load."
        )
    return rows[0][0]


async def nearest(target, query_vector: list[float], k: int = K,
                  exclude_name: str = "") -> list[dict]:
    """The k labelled names closest to a vector, nearest first, excluding one name.

    **`exclude_name` is the leave-one-out rule and it is required in practice.** In an
    evaluation round the asked name is a row in this table; retrieving its own gold row would
    hand the model the exam answer, and the score would be a score of the lookup. Excluded
    by name rather than by id because 0018's UNIQUE collapses the frozen set's repeated
    names — one exclusion therefore removes every copy of the asked string.
    """
    rows = (
        await _execute(
            target,
            "select name, label, subtype from example_embedding where name <> :exclude "
            # Cast through text, not straight to vector: the driver would otherwise be asked
            # to send a `vector`-typed parameter and has no codec for one.
            "order by embedding <=> (:vec)::text::vector limit :k",
            {"exclude": exclude_name, "vec": as_literal(query_vector), "k": k},
        )
    ).all()
    # `subtype` travels with the label because the prompt renders it when it is there
    # (0018: finer granularity lives in the case book, never in D38's ten). It is NULL for
    # everything loaded from the frozen set, so today this is the shape and not yet the value.
    return [{"name": row.name, "label": row.label, "subtype": row.subtype} for row in rows]


async def replace_all(connection, rows: list[dict], vectors: list[list[float]],
                      digest: str, embed_model: str,
                      labeled_by: str = TESTSET_LABELED_BY) -> int:
    """Empty the table and refill it, in the caller's transaction. Returns rows written.

    The frozen set repeats 7 names across 21 rows and never contradicts itself about their
    labels (measured 2026-08-15), so the collapse onto 0018's UNIQUE name is lossless — but
    it is asserted rather than assumed, because a future amendment that *did* contradict
    itself would otherwise be resolved silently by whichever row was inserted last.
    """
    seen: dict[str, dict] = {}
    for row, vector in zip(rows, vectors):
        name = row["name"]
        previous = seen.get(name)
        if previous is not None:
            if previous["label"] != row["label"]:
                raise ValueError(
                    f"the frozen set gives {name!r} two labels — {previous['label']} and "
                    f"{row['label']}. One name is one crib (0018's UNIQUE); resolve the set."
                )
            continue
        seen[name] = {
            "label": row["label"],
            "layer": row.get("layer"),
            # The frozen set carries no finer tag, so this is NULL — the column is 0018's
            # room for a case book, not something to invent a value for here.
            "subtype": row.get("subtype"),
            "vector": vector,
        }

    await connection.execute(text("delete from example_embedding"))
    for name, row in seen.items():
        await connection.execute(
            text(
                "insert into example_embedding "
                "(name, label, subtype, layer, embedding, embed_model, testset_sha256, "
                " labeled_by) "
                "values (:name, :label, :subtype, :layer, (:vec)::text::vector, :model, "
                " :sha, :by)"
            ),
            {
                "name": name,
                "label": row["label"],
                "subtype": row["subtype"],
                "layer": row["layer"],
                "vec": as_literal(row["vector"]),
                "model": embed_model,
                "sha": digest,
                "by": labeled_by,
            },
        )
    return len(seen)


# --- plumbing ----------------------------------------------------------------------------


async def _execute(target, statement: str, parameters: dict | None = None):
    """Run one statement against an engine, a connection or a session, whichever was passed.

    An engine gets its own connection for the call; anything else is already one and is used
    as it is, so a caller inside a transaction stays inside it.
    """
    if hasattr(target, "connect"):
        async with target.connect() as connection:
            return await connection.execute(text(statement), parameters or {})
    return await target.execute(text(statement), parameters or {})


async def _with_connection(work):
    engine = create_async_engine(database_url(), poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            return await work(connection)
    finally:
        await engine.dispose()


def stored_sha_sync() -> str | None:
    """`stored_sha` for a synchronous caller — the round runner, which has no loop of its own.

    A fresh engine per call, disposed per call: an asyncpg connection belongs to the loop
    that opened it, and `asyncio.run` closes that loop on the way out. The cost is one
    connect per call, and against a 7-second model call per row it does not register.
    """
    return asyncio.run(_with_connection(stored_sha))


def nearest_sync(query_vector: list[float], k: int = K, exclude_name: str = "") -> list[dict]:
    """`nearest` for a synchronous caller. Same per-call engine, same reason as above."""

    async def work(connection):
        return await nearest(connection, query_vector, k=k, exclude_name=exclude_name)

    return asyncio.run(_with_connection(work))


# --- the load ----------------------------------------------------------------------------


async def main() -> int:
    rows, digest = load_testset()
    if not available():
        print(
            f"the embedding model {EMBED_MODEL} is not reachable — the service is behind a "
            "compose profile and is off unless a backfill or a round is running: "
            "`docker compose --profile model up -d ollama`. Nothing was written.",
            file=sys.stderr,
        )
        return 3

    vectors: list[list[float]] = []
    try:
        for start in range(0, len(rows), EMBED_BATCH):
            batch = rows[start : start + EMBED_BATCH]
            vectors.extend(embed([row["name"] for row in batch]))
            print(f"  embedded {len(vectors)}/{len(rows)}", flush=True)
    except EmbedUnavailable as error:
        print(f"{error}. Nothing was written.", file=sys.stderr)
        return 3

    engine = create_async_engine(database_url(), poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            written = await replace_all(connection, rows, vectors, digest, EMBED_MODEL)
    finally:
        await engine.dispose()

    print(
        f"example_embedding: {written} distinct names from {len(rows)} frozen rows, "
        f"embedded by {EMBED_MODEL}, labels by {TESTSET_LABELED_BY}, "
        f"test set sha256 {digest}"
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] != "load":
        print("usage: python -m upto.classify.examples load", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main()))
