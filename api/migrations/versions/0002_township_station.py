"""Ticket 06 — every 臺北市 township resolves to exactly one station.

Revision ID: 0002
Revises: 0001
Created: 2026-08-11

**The mapping is a lookup, never arithmetic** (D26). A station is found by township *code*
before anything else, and the tie among several stations in one township is broken by the
lowest `StationAltitude` — a field the payload states, not a computation over coordinates
whose datum is doubtful (H23).

**Three townships hold no station at all** — 中山, 大同, 萬華 — and their nearest was resolved
**once, offline**, against a boundary file that declares its datum (D32). Those three ship as
rows like any other, distinguished only by how they were resolved, because the read path must
not care.

`observation_reading` gains `town_code` in the same revision. D26 rules the match on the code
rather than the name, and item 10 was storing only the name — so the rule could not actually
be applied against the ingested rows, and the seed could not be checked against reality.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # D26's identifier, missing from item 10's first cut. Nullable because rows written
    # before this revision have no code; the loader's check tolerates them rather than
    # rewriting history.
    op.add_column("observation_reading", sa.Column("town_code", sa.Text, nullable=True))
    op.create_index(
        "ix_observation_reading_town_code", "observation_reading", ["town_code", "observed_at"]
    )

    op.create_table(
        "township_station",
        # 內政部 鄉鎮市區代碼. The primary key, because a code is the identifier and a name
        # is not — H24's blast radius stops here for the same reason.
        sa.Column("township_code", sa.Text, primary_key=True),
        sa.Column("township_name", sa.Text, nullable=False),
        sa.Column("station_id", sa.Text, nullable=False),
        sa.Column("station_name", sa.Text, nullable=False),
        # How this row was decided, so item 14 can answer for it and so the two paths stay
        # distinguishable without a second table.
        #   town_code        — the station sits in the township; the ordinary case
        #   lowest_altitude  — several did, and the lowest one won (D26)
        #   offline_centroid — none did, resolved once against a boundary file (D32)
        sa.Column("resolution", sa.Text, nullable=False),
        # Only the offline rows carry these, and they are evidence rather than inputs:
        # nothing at run time reads them.
        sa.Column("distance_km", sa.Numeric(6, 2), nullable=True),
        sa.Column("margin_km", sa.Numeric(6, 2), nullable=True),
        sa.Column("source_note", sa.Text, nullable=True),
        sa.CheckConstraint(
            "resolution in ('town_code', 'lowest_altitude', 'offline_centroid')",
            name="ck_township_station_resolution",
        ),
        # An offline row without its measured distance would be a claim with no evidence,
        # and the reverse would be evidence attached to a row that did not need it.
        sa.CheckConstraint(
            "(resolution = 'offline_centroid') = (distance_km is not null)",
            name="ck_township_station_offline_carries_distance",
        ),
    )


def downgrade() -> None:
    op.drop_table("township_station")
    op.drop_index("ix_observation_reading_town_code", table_name="observation_reading")
    op.drop_column("observation_reading", "town_code")
