"""Ticket 17 — D72's table: two dice, 36 outcomes, apportioned by the folded weights.

**The table is the truth of the draw.** It derives deterministically from the stored weights
— largest remainder, ties by place id, slots ordered by (sum, die1, die2) — so a replay of a
closed round rebuilds the exact table it rolled against, from nothing but `proposal.weight`.

**Two rules bend the arithmetic, both on purpose:**

- **A zero weight gets exactly zero outcomes.** D45's veto survives the apportionment: no
  rounding rule may hand a vetoed place a slot.
- **A positive weight gets at least one outcome.** §3.0 says nothing is ever removed, and a
  place with real odds rounded down to 0/36 would be removed in the only sense that matters.
  The cost is a small distortion of the heaviest places' shares, admitted here; the pool is
  capped far below 36 by §3.0's three-proposals-per-member, so the floor always fits.

**A fully vetoed pool refuses loudly** — D22's shape: a constraint broad enough to sweep the
pool cannot be hidden behind an arbitrary winner.
"""

from __future__ import annotations

from decimal import Decimal

# Every (die1, die2) pair, ordered by (sum, die1, die2). Position in this tuple is the slot
# index, so the mapping from a physical roll to a slot is fixed for all time.
OUTCOMES: tuple[tuple[int, int], ...] = tuple(
    sorted(((d1, d2) for d1 in range(1, 7) for d2 in range(1, 7)), key=lambda p: (p[0] + p[1], p))
)


class EmptyPoolError(Exception):
    """Every place in the pool is at weight zero — there is nothing honest to draw."""


def allocate(weights: dict[int, Decimal]) -> dict[int, int]:
    """Outcome counts per place: sum 36, veto kept, positive weight never erased."""
    total = sum(weights.values())
    if not weights or total == 0:
        raise EmptyPoolError(
            "every place is at weight zero — the pool is swept, and that is said out loud "
            "rather than resolved by an arbitrary winner (D22)"
        )
    positive = {place: w for place, w in weights.items() if w > 0}
    if len(positive) > 36:
        raise ValueError("more than 36 places with positive weight cannot share two dice")

    # One guaranteed slot per positive place (§3.0), the rest by largest remainder (D72).
    counts = {place: 1 for place in positive}
    remaining = 36 - len(positive)
    shares = {place: w / total * remaining for place, w in positive.items()}
    for place in positive:
        counts[place] += int(shares[place])
    leftover = remaining - sum(int(shares[place]) for place in positive)
    by_remainder = sorted(
        positive, key=lambda place: (shares[place] - int(shares[place]), -place), reverse=True
    )
    for place in by_remainder[:leftover]:
        counts[place] += 1

    for place, w in weights.items():
        if w == 0:
            counts[place] = 0
    return counts


def build(weights: dict[int, Decimal]) -> tuple[int, ...]:
    """The 36-slot table: places laid contiguously in id order over the ordered outcomes."""
    counts = allocate(weights)
    table: list[int] = []
    for place in sorted(counts):
        table.extend([place] * counts[place])
    return tuple(table)


def place_for(table: tuple[int, ...], die1: int, die2: int) -> int:
    """The draw: a physical roll lands on its slot, the slot names the place."""
    if not (1 <= die1 <= 6 and 1 <= die2 <= 6):
        raise ValueError(f"({die1}, {die2}) is not a roll of two dice")
    return table[OUTCOMES.index((die1, die2))]
