"""The seat set is part of the commitment, and nothing was pinning it.

Revision 0027, written 2026-08-19 after `explain_round` reported a closed round whose recomputed
decider did not match its stored dice.

**The bug, exactly.** The decider is drawn from the circle's member set. That set was read at roll
time from `member`, which is *live* — so the answer moved whenever the circle's membership changed.
Round 358 opened at 09:48:54 and closed at 09:49:12 with dice `(4,3)`; a third member joined at
09:54:13, five minutes after it closed, and the round's decider recomputed to that member with pair
`(1,6)`. Nothing about the round had changed and its arithmetic stopped checking out.

**Two consequences, the second worse than the first.**

1. A closed round's verification breaks retroactively when anybody joins or leaves. The commitment is
   fine; the recomputation reads a different question.
2. **An open round's decider changes when somebody joins mid-round** — which breaks RP-4 (*the chosen
   member does not change on reload or reconnect*) and D91 (*fixed before the dice*) outright. That
   was live from the moment D108 shipped and no test caught it, because every test opens a round in a
   circle whose membership then sits still.

**So the seats are pinned at open, beside the seed.** «Fixed at open» has to mean the whole draw, and
the member set is an input to it. A round now carries the seat list it was drawn against.

**Why a plain `bigint[]` with no foreign key, against this schema's habit.** Every other cross-entity
reference here is a composite FK precisely so a row cannot point at something from another circle.
This one must be the exception, and the reason is the whole point of the column: **a snapshot that
follows the `member` table is not a snapshot.** A FK with `ON DELETE CASCADE` would erase the seat
when the member goes, and the round's arithmetic would change again — reintroducing the bug through
the door the constraint was supposed to protect. `ON DELETE RESTRICT` would be worse still: it would
make a closed round block a member's erasure, and D14 does not negotiate with history.

So the ids are stored as values, not as references, and the honest statement is that **this column
records who the seats were, not who exists.** A member erased later stays in the list as a number,
which is what a verifiable past requires. **`explain_round` returns ids and never nicknames**, so what
survives is an integer with no person attached to it — that was the trade the owner took when H20 was
narrowed, and it happens to be exactly what makes this column tolerable.

**Nullable, and NULL means the round predates this revision** — the same rule 0021 and 0026 use.
Nothing is backfilled: the seat set a past round was drawn against is not recoverable, because the
membership it read no longer exists anywhere. A round with a seed and no seats can still be verified
for its commitment and not for its decider, and `explain_round` says which.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "round",
        sa.Column("seat_ids", postgresql.ARRAY(sa.BigInteger()), nullable=True),
    )
    # The seats and the seed arrive together or not at all. A round holding one without the other is a
    # round whose draw is half-committed, and half a commitment is not a weaker promise — it is a
    # promise about something else.
    op.create_check_constraint(
        "ck_round_seats_with_seed",
        "round",
        "seat_ids is null or outcome_seed is not null",
    )


def downgrade() -> None:
    op.drop_constraint("ck_round_seats_with_seed", "round", type_="check")
    op.drop_column("round", "seat_ids")
