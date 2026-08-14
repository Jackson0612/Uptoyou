"""D82's draw: the evaluation set's 200 names, deterministic and stratified.

Run inside the stack, once — the output is labeled by hand and frozen; re-running with the
same seed against the same publication reproduces the same draw, which is the property the
seed exists for:

    docker compose exec api python -m upto.evaluate.draw

Prints one JSON document to stdout: the seed, the publication drawn against, and 200 rows
each carrying the registry number, the asked name (D80's ladder, same query the classifier
uses), which layer supplied that name, and an empty label slot. **The draw is not the set** —
the set is this output labeled, reviewed and committed as `testset_v1.json`.

Stratification is D82's: proportional to each layer's population with a floor of 30, so the
sign and brand layers — small but exactly the populations D77/D78 were built to fix — stay
scorable on their own.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import datetime, timezone

# sqlalchemy and the app's DB glue are imported inside main() on purpose: the pure half —
# allocate() and pick() — is what the no-database test imports, and the host Python that
# runs those tests has no sqlalchemy.

SEED = 82  # D82's number, so the choice is legible rather than magic
SIZE = 200
FLOOR = 30
TOWNSHIP = "63000010"  # 松山區 — D39 condition 4's bounded scope
LAYERS = ("sign", "brand", "registered")


def allocate(populations: dict[str, int], size: int = SIZE, floor: int = FLOOR) -> dict[str, int]:
    """Per-layer draw counts: proportional with a floor, never more than the layer holds.

    A layer smaller than the floor contributes everything it has. The remainder after floors
    is split proportionally over the un-floored population, largest remainder deciding the
    last few — so the counts are a function of the populations alone and two runs agree.
    """
    counts = {layer: min(floor, populations[layer]) for layer in populations}
    remaining = size - sum(counts.values())
    if remaining <= 0:
        return counts
    headroom = {layer: populations[layer] - counts[layer] for layer in populations}
    total_headroom = sum(headroom.values())
    if total_headroom <= remaining:
        return {layer: counts[layer] + headroom[layer] for layer in counts}
    shares = {layer: remaining * headroom[layer] / total_headroom for layer in populations}
    for layer in shares:
        counts[layer] += int(shares[layer])
    left = size - sum(counts.values())
    by_remainder = sorted(
        populations, key=lambda layer: (shares[layer] - int(shares[layer]), layer), reverse=True
    )
    for layer in by_remainder[:left]:
        counts[layer] += 1
    return counts


def pick(rows: list[dict], seed: int = SEED, size: int = SIZE, floor: int = FLOOR) -> list[dict]:
    """The deterministic draw over rows already carrying `layer`, sorted before sampling."""
    by_layer: dict[str, list[dict]] = {layer: [] for layer in LAYERS}
    for row in rows:
        by_layer[row["layer"]].append(row)
    for layer in by_layer:
        by_layer[layer].sort(key=lambda row: row["registry_no"])
    counts = allocate({layer: len(by_layer[layer]) for layer in LAYERS}, size, floor)
    rng = random.Random(seed)
    drawn: list[dict] = []
    for layer in LAYERS:  # fixed layer order, one shared rng — order is part of determinism
        drawn.extend(rng.sample(by_layer[layer], counts[layer]))
    drawn.sort(key=lambda row: row["registry_no"])
    return drawn


async def main() -> int:
    from sqlalchemy import text

    from upto.api_common import SINGLE_BRAND, STOREFRONT
    from upto.db import dispose_all, session_factory

    Session = session_factory()
    try:
        async with Session() as session:
            publication_id = (
                await session.execute(
                    text("select id from place_publication order by detected_at desc limit 1")
                )
            ).scalar_one_or_none()
            if publication_id is None:
                print("no place publication ingested — nothing to draw from", file=sys.stderr)
                return 1
            rows = (
                await session.execute(
                    text(
                        "select rp.registry_no, "
                        "coalesce(storefront.name, brand.brand_name, rp.name) as name, "
                        "case when storefront.name is not null then 'sign' "
                        "     when brand.brand_name is not null then 'brand' "
                        "     else 'registered' end as layer "
                        "from reference_place rp "
                        "left join lateral ("
                        + STOREFRONT.format(registry="rp.registry_no")
                        + ") storefront on true "
                        "left join lateral ("
                        + SINGLE_BRAND.format(company="rp.name")
                        + ") brand on true "
                        "where rp.publication_id = :pub and rp.township_code = :tc "
                        "order by rp.registry_no"
                    ),
                    {"pub": publication_id, "tc": TOWNSHIP},
                )
            ).all()
        pool = [
            {"registry_no": row.registry_no, "name": row.name, "layer": row.layer}
            for row in rows
        ]
        populations = {layer: sum(1 for r in pool if r["layer"] == layer) for layer in LAYERS}
        drawn = pick(pool)
        print(
            json.dumps(
                {
                    "seed": SEED,
                    "township_code": TOWNSHIP,
                    "publication_id": publication_id,
                    "drawn_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "layer_populations": populations,
                    "rows": [dict(row, label=None) for row in drawn],
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 0
    finally:
        await dispose_all()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
