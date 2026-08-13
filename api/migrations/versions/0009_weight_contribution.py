"""Ticket 13 — `weight_contribution`, and the weight the roll was drawn against.

Revision ID: 0009
Revises: 0008
Created: 2026-08-13

**One row per factor that moved the odds (D15), landing only on a pooled place:** the
(round_id, place_id) pair references the proposal pair, so a contribution for a place nobody
proposed cannot exist. D13's four CHECKs and D45's three ranges are here verbatim — the entries
wrote the SQL and this file copies it, because a paraphrased constraint is a second claim.

**The source pin is a composite foreign key, and the width is the cost of D24's own argument.**
D24 sketched `forecast_id REFERENCES ...(id)`, but the reading tables' primary keys are
composite (H14's idempotency lives in them), and D24's whole reason is that only a real key is
protected by the database — a table-name-and-row-number pair lets a deletion pass silently. So
the forecast pin is five columns and the observation pin is four, each group all-or-nothing,
exactly one group set. Sideways growth was admitted by D24 the day it was ruled.

**The preference pin is absent the way partner's origin is absent in 0007:** D17/D25's table
does not exist, so its FK cannot be written, and the exactly-one CHECK spans the two sources
that do. Widening it is the preference migration's deliberate act. Until then a `private`
contribution is uninsertable — by the source CHECK, not by the channel CHECK — which matches
D62: preference recording sits past October, so v1's roll folds weather alone. The channel
CHECKs still name all three, D13's pattern of proving the guarantee before the feature.

**`proposal.weight` is D15's materialised result**, written by the engine in the roll's
transaction after the write-time reconciliation passes. Unconstrained numeric on purpose: D46
stores the folded weight at whatever scale the exact product reached.
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weight_contribution",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("round_id", sa.BigInteger, nullable=False),
        sa.Column("place_id", sa.BigInteger, nullable=False),
        sa.Column("channel", sa.Text, nullable=False),
        # D46: the stable name historical rounds sort by. Data, not a class attribute.
        sa.Column("contributor", sa.Text, nullable=False),
        # numeric(4,3): D45's ranges all fit one digit and three decimals; D46 rules the type.
        sa.Column("effect", sa.Numeric(4, 3), nullable=False),
        # H8 as a database fact: every factor carries one human sentence.
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("reason_visibility", sa.Text, nullable=False),
        # Private is tied to a person and kept — the previous round's preference carries
        # forward (MVP item 5), which is why D14 erases proposal authorship but not this.
        sa.Column("member_id", sa.BigInteger, nullable=True),
        # D24's forecast pin: forecast_reading's whole primary key — which 0003 re-keyed on
        # the township *code*, and 0009 first shipped referencing the 0001 name-keyed shape.
        sa.Column("forecast_publication_id", sa.BigInteger, nullable=True),
        sa.Column("forecast_township_code", sa.Text, nullable=True),
        sa.Column("forecast_element", sa.Text, nullable=True),
        sa.Column("forecast_measure", sa.Text, nullable=True),
        sa.Column("forecast_slot_start", sa.DateTime(timezone=True), nullable=True),
        # D24's observation pin: observation_reading's whole primary key.
        sa.Column("observation_publication_id", sa.BigInteger, nullable=True),
        sa.Column("observation_station_id", sa.Text, nullable=True),
        sa.Column("observation_element", sa.Text, nullable=True),
        sa.Column("observation_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["round_id", "place_id"],
            ["proposal.round_id", "proposal.place_id"],
            name="fk_contribution_pooled_place",
        ),
        sa.ForeignKeyConstraint(["member_id"], ["member.id"], name="fk_contribution_member"),
        sa.ForeignKeyConstraint(
            [
                "forecast_publication_id",
                "forecast_township_code",
                "forecast_element",
                "forecast_measure",
                "forecast_slot_start",
            ],
            [
                "forecast_reading.publication_id",
                "forecast_reading.township_code",
                "forecast_reading.element",
                "forecast_reading.measure",
                "forecast_reading.slot_start",
            ],
            name="fk_contribution_forecast_reading",
        ),
        sa.ForeignKeyConstraint(
            [
                "observation_publication_id",
                "observation_station_id",
                "observation_element",
                "observation_observed_at",
            ],
            [
                "observation_reading.publication_id",
                "observation_reading.station_id",
                "observation_reading.element",
                "observation_reading.observed_at",
            ],
            name="fk_contribution_observation_reading",
        ),
        sa.CheckConstraint(
            "channel in ('private', 'contextual', 'commercial')",
            name="ck_contribution_channel",
        ),
        # D45's three ranges, verbatim.
        sa.CheckConstraint(
            "channel <> 'private' or (effect >= 0 and effect <= 1)",
            name="ck_contribution_private_range",
        ),
        sa.CheckConstraint(
            "channel <> 'contextual' or (effect >= 0.5 and effect <= 2)",
            name="ck_contribution_contextual_range",
        ),
        sa.CheckConstraint(
            "channel <> 'commercial' or (effect >= 1 and effect <= 1.5)",
            name="ck_contribution_commercial_range",
        ),
        # D13's four CHECKs, verbatim.
        sa.CheckConstraint(
            "reason_visibility in ('table', 'represented_member', 'none')",
            name="ck_contribution_visibility",
        ),
        sa.CheckConstraint(
            "channel <> 'commercial' or reason_visibility = 'table'",
            name="ck_contribution_commercial_public",
        ),
        sa.CheckConstraint(
            "channel <> 'private' or reason_visibility <> 'table'",
            name="ck_contribution_private_never_table",
        ),
        sa.CheckConstraint(
            "channel <> 'private' or member_id is not null",
            name="ck_contribution_private_has_member",
        ),
        sa.CheckConstraint(
            "channel = 'private' or member_id is null",
            name="ck_contribution_only_private_has_member",
        ),
        # D24: exactly one source, each pin all-or-nothing. The preference source widens
        # this CHECK when its table exists.
        sa.CheckConstraint(
            "num_nonnulls(forecast_publication_id, forecast_township_code, forecast_element, "
            "forecast_measure, forecast_slot_start) in (0, 5)",
            name="ck_contribution_forecast_pin_whole",
        ),
        sa.CheckConstraint(
            "num_nonnulls(observation_publication_id, observation_station_id, "
            "observation_element, observation_observed_at) in (0, 4)",
            name="ck_contribution_observation_pin_whole",
        ),
        sa.CheckConstraint(
            "num_nonnulls(forecast_publication_id, observation_publication_id) = 1",
            name="ck_contribution_exactly_one_source",
        ),
    )
    # The panel and the replay both read a round's contributions; D46's order is applied in
    # code over this set, so the index is the fetch, not the order.
    op.create_index(
        "ix_contribution_round", "weight_contribution", ["round_id", "place_id"]
    )

    # D15's materialised result: the weight the roll was drawn against, per pooled place.
    op.add_column("proposal", sa.Column("weight", sa.Numeric, nullable=True))


def downgrade() -> None:
    op.drop_column("proposal", "weight")
    op.drop_table("weight_contribution")
