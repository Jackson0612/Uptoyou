"""Ticket 19 — the dice are part of the stored result.

Revision ID: 0011
Revises: 0010
Created: 2026-08-13

D15 stores what the round computed; D72 makes the dice genuinely random — which means a
replay can rebuild the table and the weights but never the roll itself. So the two dice are
columns on the round, written in the same transaction as the close. The reveal panel's
「3+4=7 → 這家」 sentence reads from here.

An open round carries no dice. A closed one normally carries both; the constraint does not
demand it, because rounds closed before this revision exist and a close without a roll (a
cancel) is deliberately unruled (0008's own note).
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("round", sa.Column("die1", sa.SmallInteger, nullable=True))
    op.add_column("round", sa.Column("die2", sa.SmallInteger, nullable=True))
    op.create_check_constraint(
        "ck_round_open_has_no_dice", "round", "status <> 'open' or (die1 is null and die2 is null)"
    )
    op.create_check_constraint(
        "ck_round_dice_pair_whole", "round", "(die1 is null) = (die2 is null)"
    )
    op.create_check_constraint(
        "ck_round_dice_range",
        "round",
        "(die1 is null or (die1 between 1 and 6)) and (die2 is null or (die2 between 1 and 6))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_round_dice_range", "round")
    op.drop_constraint("ck_round_dice_pair_whole", "round")
    op.drop_constraint("ck_round_open_has_no_dice", "round")
    op.drop_column("round", "die2")
    op.drop_column("round", "die1")
