"""The weight engine — the fold half.

D43 rules that a contributor is a pure function returning contribution records, and that the
engine alone loads sources, writes records and folds effects into weights. This package holds
the fold; the load and write halves arrive with the round and place tables.
"""

from upto.engine.fold import (
    CHANNELS,
    CHANNEL_BOUNDS,
    Clamp,
    Contribution,
    FoldResult,
    fold,
)

__all__ = [
    "CHANNELS",
    "CHANNEL_BOUNDS",
    "Clamp",
    "Contribution",
    "FoldResult",
    "fold",
]
