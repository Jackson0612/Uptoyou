"""D71 — the weather contributor, pure.

One rule: at RAIN_THRESHOLD percent or above, the place's odds fold by RAIN_EFFECT, and the
sentence says the number. Below it, nothing is returned — D43's no-record-no-effect, so the
panel shows nothing for a place the weather left alone.

The constants are named because they are unmeasured (D71 admits this): they wait on real
rounds to tune against, and a name is where the re-tuning will land.

The function never queries anything (D43) and never sees another candidate (D44): the loader
hands it one place's probability, and which reading that number came from is the loader's pin,
not this function's concern.
"""

from __future__ import annotations

from decimal import Decimal

from upto.engine.fold import Contribution

CONTRIBUTOR_NAME = "weather"
RAIN_THRESHOLD = 70
RAIN_EFFECT = Decimal("0.8")


def rain_contribution(
    contribution_id: int, place_id: int, probability: int
) -> Contribution | None:
    """One place, one probability, one record or nothing (D71)."""
    if probability < RAIN_THRESHOLD:
        return None
    return Contribution(
        id=contribution_id,
        place_id=place_id,
        channel="contextual",
        contributor=CONTRIBUTOR_NAME,
        effect=RAIN_EFFECT,
        reason=f"降雨機率{probability}%",
    )
