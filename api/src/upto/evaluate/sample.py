"""Draw the fixed test set — stratified, deterministic, labeled by a person afterwards.

    docker compose exec -T api python -m upto.evaluate.sample > testset-draft.json

Ruled 2026-08-14: ~200 names from 松山區 — **15 per category** (the ten of D38), **30
decided legal entities**, and a hand-picked hard stratum added to the draft afterwards.
Stratification is the point: 日式 holds ~52 of the township's 3,324 places, so a uniform
draw would put two or three in the set and the per-class cell on the evaluation page would
be a guess wearing a denominator.

**The current classification is the sampling frame and never the answer.** Using it to
decide *who is drawn* is a recorded circularity (the frame under-represents what the
current model gets catastrophically wrong); using it to decide *what the answer is* would
make the evaluation grade the model against itself. The draft carries the current answer in
`frame_answer` so the labeler sees it — and the label field starts empty on purpose.

**Deterministic:** the draw is ordered by a fixed seed's hash over the registry number, so
re-running against the same data yields the same set. No randomness API is touched.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys

from sqlalchemy import text

from upto.api_common import SINGLE_BRAND, STOREFRONT
from upto.classify.categories import CATEGORIES
from upto.db import dispose_all, session_factory

TOWNSHIP = "63000010"
PER_CATEGORY = 15
LEGAL_ENTITIES = 30
SEED = "upto-eval-v1"


def _rank(registry_no: str) -> str:
    return hashlib.sha256((SEED + registry_no).encode()).hexdigest()


BASE = (
    "select p.registry_no, "
    "coalesce(storefront.name, brand.brand_name, rp.name) as asked_name, "
    "rp.name as registered_name, p.category as frame_answer "
    "from place p "
    "join reference_place rp on rp.registry_no = p.registry_no "
    "left join lateral (" + STOREFRONT.format(registry="p.registry_no") + ") storefront on true "
    "left join lateral (" + SINGLE_BRAND.format(company="rp.name") + ") brand on true "
    "where p.origin = 'reference' and rp.township_code = :tc "
    "and rp.publication_id = ("
    "  select id from place_publication order by detected_at desc limit 1) "
)


async def main() -> int:
    Session = session_factory()
    rows: list[dict] = []
    try:
        async with Session() as session:
            for category in CATEGORIES:
                drawn = (
                    await session.execute(
                        text(BASE + "and p.category = :cat"),
                        {"tc": TOWNSHIP, "cat": category},
                    )
                ).all()
                drawn = sorted(drawn, key=lambda r: _rank(r.registry_no))[:PER_CATEGORY]
                for row in drawn:
                    rows.append(_entry(row, stratum="category:" + category))
            # D79's decided absences — provenance present, category NULL.
            sentinels = (
                await session.execute(
                    text(
                        BASE + "and p.category is null and p.category_generated_at is not null"
                    ),
                    {"tc": TOWNSHIP},
                )
            ).all()
            sentinels = sorted(sentinels, key=lambda r: _rank(r.registry_no))[:LEGAL_ENTITIES]
            for row in sentinels:
                rows.append(_entry(row, stratum="legal-entity"))
    finally:
        await dispose_all()

    for entry in rows:
        print(json.dumps(entry, ensure_ascii=False))
    print(
        "drew {} rows ({} strata); the hard stratum is hand-picked and appended by the "
        "labeler".format(len(rows), len(CATEGORIES) + 1),
        file=sys.stderr,
    )
    return 0


def _entry(row, stratum: str) -> dict:
    return {
        "registry_no": row.registry_no,
        "asked_name": row.asked_name,
        "registered_name": row.registered_name,
        "stratum": stratum,
        # What the frame said, shown to the labeler, never copied into `label` unexamined.
        "frame_answer": row.frame_answer,
        # Ruled by a person. 法人 is a valid label here even though it is not a category —
        # the evaluation must grade the sentinel decision too.
        "label": None,
        "disputed": False,
        "note": None,
    }


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
