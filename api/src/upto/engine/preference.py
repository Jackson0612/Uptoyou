"""A1 / item 4 — the private preference contributor, pure.

*Written 2026-08-18, owner-ruled (A1). D17 gives the preference a home, D25 makes it append-only,
D45 gives this channel its range, D43/D44 give this function its shape.*

One rule: if the place's category is one this member avoids, the place's odds fold by **zero**.
Below that — no category, or a category the member said nothing about — **nothing is returned**,
which is D43's no-record-no-effect, so the panel shows nothing for a place the member's
preferences left alone.

**Why zero and not a large reduction.** D45's worked example is the whole argument: contributions
multiply, and multiplication has an absorbing zero, so once a factor is `0` no later factor
recovers it. Under addition a paying restaurant could cancel an avoidance — *a veto that can be
bought back is not a veto*. An avoid is the one thing in this product that is meant to be
absolute, and `private`'s range `[0, 1]` exists precisely so this channel may zero and may never
lift.

**A place with no category produces nothing, and that is neutrality rather than a penalty.** Only
6.2% of the reference list carries a category today — 2,267 rows of 36,499, because one township
has been classified (measured 2026-08-18) — so this contributor is correct and nearly inert until
the backfill covers more. Treating "unknown category" as "not avoided" is the same choice the
loader already makes for a `circle-local` place with no township (D28's ruling, read through
`upto.engine.load`): the absence of a fact is not evidence against the place.

**The function never queries anything (D43) and never sees another candidate (D44).** The loader
hands it one place's category and the set this member avoids; which preference row that set came
from is the loader's pin, not this function's concern.

**The reason names the category, deliberately.** `reason` exists to explain a number to whoever
may see it (D13), and for a `private` row that is the represented member alone —
`reason_visibility = 'represented_member'`, and the reveal panel shows channel-only labels for
this channel, so the text never reaches another person's screen. Withholding the category from its
owner would make the column useless to the only reader it has; and it would buy nothing against a
database leak, because the `preference` row itself already states the same fact more plainly.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Collection, Optional

from upto.engine.fold import Contribution

CONTRIBUTOR_NAME = "preference"

# D45's absorbing zero, and the reason `private` is the only channel allowed to reach it.
AVOID_EFFECT = Decimal("0")

# D13's third column: who may see the reason. `table` is refused for this channel by a CHECK on
# `weight_contribution`, so the value is named here rather than left to a caller's default.
REASON_VISIBILITY = "represented_member"


def avoid_contribution(
    contribution_id: int,
    place_id: int,
    category: Optional[str],
    avoided: Collection[str],
) -> Contribution | None:
    """One place, one member's avoided set, one record or nothing (D43, D44).

    `category` is the place's generated category (D39) or `None` when it has not been classified
    and when the place is `circle-local`. `avoided` is the categories this member has a preference
    row in force for — a set, because a member may avoid more than one.
    """
    if category is None:
        return None
    if category not in set(avoided):
        return None
    return Contribution(
        id=contribution_id,
        place_id=place_id,
        channel="private",
        contributor=CONTRIBUTOR_NAME,
        effect=AVOID_EFFECT,
        reason="避開的類型：{}".format(category),
    )
