"""D75's backfill: one township, materialised then classified, with provenance on every row.

Run inside the stack, with the model service up (it is behind a compose profile):

    docker compose --profile model up -d ollama
    docker compose exec api python -m upto.classify.run 63000010

Two passes, in this order and for a reason:

1. **Materialise (D76).** Every `reference_place` in the township that has no `place` row
   gets one — origin `reference`, the 登錄字號 and nothing else, which is D28's shape. The
   category then has one home, 0007's own columns.
2. **Classify.** Every place in that township still carrying no category is sent to the
   model one at a time, validated against D38's ten values, and written **with the prompt
   version and the model name** (D39's condition 3). An answer outside the list is not
   written and not coerced — it is counted and reported as pending, which is D63's rule.

**The model's absence is ordinary, not an error.** The service is off unless a backfill is
running, so this exits 3 and says so, having written nothing. Exit 0 means the pass ran —
including the pass that had nothing left to do.

**Committed in batches rather than at the end**, because 3,324 places is roughly seven hours
and a crash at hour six must not throw away hour one. Each batch is a transaction; a
re-run resumes at the first unclassified row, which is what makes this safe to interrupt.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import text

from upto.classify.classify import Classified, classify_name
from upto.classify.model import MODEL, available, ask
from upto.db import dispose_all, session_factory

BATCH = 25


async def materialise(session, township_code: str) -> int:
    """D76: give the township's reference places their rows. Idempotent by 0007's index."""
    created = (
        await session.execute(
            text(
                "insert into place (origin, registry_no) "
                "select 'reference', rp.registry_no from reference_place rp "
                "where rp.publication_id = ("
                "  select id from place_publication order by detected_at desc limit 1"
                ") and rp.township_code = :tc "
                "and not exists ("
                "  select 1 from place p where p.origin = 'reference' "
                "  and p.registry_no = rp.registry_no"
                ") returning id"
            ),
            {"tc": township_code},
        )
    ).scalars().all()
    await session.commit()
    return len(created)


async def pending(session, township_code: str) -> list[tuple[int, str]]:
    """Places in this township with no category yet, named from the latest publication."""
    rows = (
        await session.execute(
            text(
                "select p.id, rp.name from place p "
                "join reference_place rp on rp.registry_no = p.registry_no "
                "where p.origin = 'reference' and p.category is null "
                "and rp.township_code = :tc "
                "and rp.publication_id = ("
                "  select id from place_publication order by detected_at desc limit 1"
                ") order by p.id"
            ),
            {"tc": township_code},
        )
    ).all()
    return [(row.id, row.name) for row in rows]


async def main(township_code: str) -> int:
    Session = session_factory()
    try:
        if not available():
            print(
                f"model {MODEL} is not reachable — the service is behind a compose profile "
                "and is off unless a backfill is running. Nothing was written.",
                file=sys.stderr,
            )
            return 3

        async with Session() as session:
            created = await materialise(session, township_code)
            todo = await pending(session, township_code)
        print(f"township {township_code}: {created} rows created, {len(todo)} to classify")

        done = refused = 0
        for start in range(0, len(todo), BATCH):
            batch = todo[start : start + BATCH]
            results = []
            for place_id, name in batch:
                outcome = classify_name(name, ask)
                if isinstance(outcome, Classified):
                    results.append((place_id, outcome))
                else:
                    refused += 1
            async with Session() as session:
                for place_id, outcome in results:
                    await session.execute(
                        text(
                            "update place set category = :c, category_model = :m, "
                            "category_prompt_version = :v, category_generated_at = :t "
                            "where id = :id"
                        ),
                        {
                            "c": outcome.category,
                            "m": MODEL,
                            "v": outcome.prompt_version,
                            "t": datetime.now(timezone.utc),
                            "id": place_id,
                        },
                    )
                await session.commit()
            done += len(results)
            print(f"  {done + refused}/{len(todo)}  written {done}  pending {refused}", flush=True)

        print(f"done: {done} classified, {refused} left pending (answer outside D38's list)")
        return 0
    finally:
        await dispose_all()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m upto.classify.run <township_code>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
