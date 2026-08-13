"""Ticket 10 — the fold: contributions become one weight, exactly and in one order.

**Contributions multiply (D45).** Each place starts at 1 and every contribution carries a
factor. Multiplication has an absorbing zero, so a private veto cannot be bought back by a
later factor — the worked example in D45 is a test here. Each channel's factors are folded
first, the channel product is clamped back into the channel's own range, and the clamped
channel products multiply into the final weight.

**The clamp exists because a CHECK sees one row (D45).** Three contextual factors of 0.8 each
sit inside [0.5, 2] and multiply to 0.512, which nearly kills a place the channel is forbidden
to kill. The clamp is the engine-side half of the bound, and every clamp is returned as its own
record because the panel must show arithmetic that works out: 0.8 × 0.8 × 0.8 displayed beside
0.5 is an error to any reader unless the clamp is its own line (D45).

**One total order (D46):** channel (private → contextual → commercial) → contributor name →
contribution id. The fold multiplies in that order and the panel displays the same tuple, so
the evidence never shuffles between two loads of the same round.

**Exact decimals, deliberately (D46).** ``effect`` mirrors the column type numeric(4,3): at
most three decimal places. Products are taken under a context whose precision is set here
rather than inherited, with the Inexact trap armed — a fold that would round raises instead.
Python's default context holds 28 significant digits and ten three-place factors reach thirty,
so the day a fifth contributor lands the default becomes a silent rounding; the trap turns
that day into a loud one.

**What is not here on purpose:** loading sources, calling contributors, writing rows. D43
gives those to the engine's other half, which cannot exist before the round tables do. A
contributor's purity is a property of that half's calling convention, not of this module.
"""

from __future__ import annotations

import decimal
from dataclasses import dataclass
from decimal import Decimal

# Channel order is D13's organising idea — who may see the reason — from most restricted to
# least, and it reads as: what was ruled out, then what was nudged, then who paid (D46).
CHANNELS = ("private", "contextual", "commercial")

# D45's CHECK constraints, mirrored exactly. The database enforces these per row; this module
# enforces them at construction so a bad record fails where it was written, and enforces the
# same range again on the per-channel product, which no row constraint can see.
CHANNEL_BOUNDS: dict[str, tuple[Decimal, Decimal]] = {
    "private": (Decimal("0"), Decimal("1")),  # may zero, may never lift
    "contextual": (Decimal("0.5"), Decimal("2")),  # may nudge, can never reach 0
    "commercial": (Decimal("1"), Decimal("1.5")),  # may help, may never suppress
}

# numeric(4,3): three decimal places, one digit before the point covers every bound above.
_EFFECT_QUANTUM = Decimal("0.001")

# D46's debt paid: the context precision is chosen, not inherited. Three decimal places per
# factor means the product's digits grow by three per contribution; 80 significant digits
# hold more than twenty-five contributions on one place, several times v1's four contributors.
# The Inexact trap makes the boundary loud: past it the fold raises rather than rounds.
FOLD_PRECISION = 80


def _fold_context() -> decimal.Context:
    return decimal.Context(prec=FOLD_PRECISION, traps=[decimal.Inexact, decimal.InvalidOperation])


@dataclass(frozen=True)
class Contribution:
    """One contributor's effect on one place, and the sentence behind it (H8).

    ``contributor`` is the stable name D46 requires on the record — renaming a contributor
    rewrites how historical rounds sort, so the name is data, not a class attribute.
    """

    id: int
    place_id: int
    channel: str
    contributor: str
    effect: Decimal
    reason: str

    def __post_init__(self) -> None:
        if self.channel not in CHANNEL_BOUNDS:
            raise ValueError(f"unknown channel {self.channel!r}")
        if not isinstance(self.effect, Decimal):
            raise TypeError("effect must be a Decimal — a float here is D46 undone")
        if self.effect != self.effect.quantize(_EFFECT_QUANTUM):
            raise ValueError(f"effect {self.effect} has more than 3 decimal places (numeric(4,3))")
        low, high = CHANNEL_BOUNDS[self.channel]
        if not low <= self.effect <= high:
            raise ValueError(
                f"effect {self.effect} outside {self.channel} range [{low}, {high}] (D45)"
            )
        if not self.reason.strip():
            raise ValueError("a contribution carries one human sentence, or it does not exist (H8)")
        if not self.contributor.strip():
            raise ValueError("a contribution carries its contributor's stable name (D46)")

    @property
    def sort_key(self) -> tuple[int, str, int]:
        return (CHANNELS.index(self.channel), self.contributor, self.id)


@dataclass(frozen=True)
class Clamp:
    """A per-channel product pulled back into range — the panel line D45 requires."""

    channel: str
    raw: Decimal
    clamped: Decimal


@dataclass(frozen=True)
class FoldResult:
    """The fold's whole answer: the display order, the products, the clamps, the weight.

    ``contributions`` is already in D46's total order and is the panel's display order —
    there is no second sort anywhere for the two to disagree.
    """

    place_id: int
    contributions: tuple[Contribution, ...]
    channel_products: dict[str, Decimal]
    clamps: tuple[Clamp, ...]
    weight: Decimal


def fold(place_id: int, contributions: list[Contribution]) -> FoldResult:
    """Fold one place's contributions into its weight. Pure, exact, one order."""
    for c in contributions:
        if c.place_id != place_id:
            raise ValueError(
                f"contribution {c.id} is for place {c.place_id}, not {place_id} — "
                "the fold is per place (D44)"
            )
    ordered = tuple(sorted(contributions, key=lambda c: c.sort_key))

    ctx = _fold_context()
    channel_products: dict[str, Decimal] = {}
    clamps: list[Clamp] = []
    weight = Decimal("1")
    for channel in CHANNELS:
        factors = [c.effect for c in ordered if c.channel == channel]
        if not factors:
            continue
        product = Decimal("1")
        for factor in factors:
            product = ctx.multiply(product, factor)
        channel_products[channel] = product
        low, high = CHANNEL_BOUNDS[channel]
        clamped = min(max(product, low), high)
        if clamped != product:
            clamps.append(Clamp(channel=channel, raw=product, clamped=clamped))
        weight = ctx.multiply(weight, clamped)

    return FoldResult(
        place_id=place_id,
        contributions=ordered,
        channel_products=channel_products,
        clamps=tuple(clamps),
        weight=weight,
    )
