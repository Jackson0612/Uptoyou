"""Ticket 05's open gap — the forecast is keyed by township geocode, not by name.

Revision ID: 0003
Revises: 0002
Created: 2026-08-11

D26 rules the match **by identifier wherever an identifier exists**, and item 10 stored only
CWA's `LocationName`. The payload carries `Geocode` beside it — `63000010` for 松山區, the same
內政部 鄉鎮市區代碼 space the seeded `township_station` uses — so the identifier was there the
whole time and the read path was joining on a string.

**What that string join cost, before it cost anything:** the read path had to carry a guard
that raised when the seed's name matched no forecast row, because an absence and a
misspelling are indistinguishable — 台 on one side and 臺 on the other is H24 exactly. A code
cannot be misspelled, so the primary path stops needing the guard.

**The name stays as a column.** It is what CWA calls the township and it is what a lineage
answer should quote back; it simply is not the key.

**The content hash is deliberately untouched.** `content_digest` still reduces the forecast
over the township *name*, so no stored hash moves and no publication is re-inserted. Changing
what the digest reads is a schema change with a migration and a plan behind it — the docstring
on that function says so, after adding `measure` to it invalidated every forecast hash once.
The digest's job is change detection, and the name is stable within a payload.

The existing rows are backfilled through the seed's name column — the same join this revision
exists to retire, used once, at migration time, where its failure is visible.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("forecast_reading", sa.Column("township_code", sa.Text, nullable=True))

    # One name join, at migration time. Any row it cannot resolve is left null and the
    # not-null constraint below refuses the migration, which is the loud failure D32's loader
    # asks for rather than a null discovered at read time.
    op.execute(
        """
        update forecast_reading r
           set township_code = s.township_code
          from township_station s
         where s.township_name = r.township
           and r.township_code is null
        """
    )

    op.alter_column("forecast_reading", "township_code", nullable=False)

    op.drop_index("ix_forecast_reading_lookup", table_name="forecast_reading")
    op.drop_constraint("forecast_reading_pkey", "forecast_reading", type_="primary")
    op.create_primary_key(
        "forecast_reading_pkey",
        "forecast_reading",
        ["publication_id", "township_code", "element", "measure", "slot_start"],
    )
    # The read path asks for one township code, one hour (D36), so that is the index.
    op.create_index(
        "ix_forecast_reading_lookup",
        "forecast_reading",
        ["township_code", "element", "measure", "slot_start"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_reading_lookup", table_name="forecast_reading")
    op.drop_constraint("forecast_reading_pkey", "forecast_reading", type_="primary")
    op.create_primary_key(
        "forecast_reading_pkey",
        "forecast_reading",
        ["publication_id", "township", "element", "measure", "slot_start"],
    )
    op.create_index(
        "ix_forecast_reading_lookup",
        "forecast_reading",
        ["township", "element", "measure", "slot_start"],
    )
    op.drop_column("forecast_reading", "township_code")
