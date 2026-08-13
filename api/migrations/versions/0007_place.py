"""Ticket 11 — the `place` table: a place is always a row of ours (D28), two origins live.

Revision ID: 0007
Revises: 0006
Created: 2026-08-13

**Two origins, not three, and the third is missing on purpose.** D28 names `reference`,
`circle-local` and `partner`; D30 rules partner rows guaranteed to carry a per-head price and a
category, and the table those live in does not exist yet. Ruled 2026-08-13: the origin CHECK
here admits only the two origins whose guarantees this schema can hold, and the partner
migration widens the CHECK as a deliberate act — the same pattern as the identity test's
authentication allowlist. A row type whose guaranteed fields have nowhere to live is not
deferred; it is absent.

**A `reference` place carries `registry_no` and deliberately not a foreign key** — ruled
2026-08-13, recorded in D28. `place_reference` holds one row per place per publication, so a
real FK welds the place to one month's file; the stable 登錄字號 lets the read path resolve the
latest publication's row, which is D57's rule reused. The cost is stated in D28: the database
cannot enforce the number, so a mistyped one points at nothing silently — the integration test
and read-time validation carry what the FK would have.

**A `reference` place also carries no name.** Name, township and opening hours live in the
publication rows and resolve at read time; a copy here would drift the day FDA amends theirs.
`circle-local` is the opposite: a member typed it, so the name is the row's whole content (D28:
"a name, and nothing else"), and it is scoped to its circle because typed text must never enter
the global pool (D28).

**One row to accumulate against, in both origins.** Credit, preferences and provenance attach
to a place id, so the same place must not exist twice: one `reference` row per `registry_no`,
one `circle-local` name per circle — partial unique indexes, because the two rules cover
different column sets.

**Category is D39's column and its provenance is all-or-nothing.** Generated at build time by a
tool, disclosed as generated, so a category with no model, no prompt version or no date is a
claim with no origin — the CHECK refuses it. No coordinate column exists anywhere here (H23,
D27): a township is read out of an address by the ingest, never computed from a point.

**H19 holds:** nothing here references `principal`. The FK to `circle` is the product domain
referencing the product domain.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "place",
        sa.Column("id", sa.BigInteger, primary_key=True),
        # Which of D28's origins this row is. `partner` is refused here until its table
        # exists — widening this CHECK is the partner migration's deliberate act.
        sa.Column("origin", sa.Text, nullable=False),
        # circle-local only: typed text is scoped to the circle that typed it (D28).
        sa.Column("circle_id", sa.BigInteger, nullable=True),
        # circle-local only: the member's own words, the row's whole content.
        sa.Column("name", sa.Text, nullable=True),
        # reference only: the FDA 登錄字號, site-level unique in the source (D31). The stable
        # pin — the latest publication's row answers for everything else at read time.
        sa.Column("registry_no", sa.Text, nullable=True),
        # D39: generated at build time, validated against D38's closed list before insert.
        # The list itself is application data; what the schema can hold is the provenance rule.
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("category_model", sa.Text, nullable=True),
        sa.Column("category_prompt_version", sa.Text, nullable=True),
        sa.Column("category_generated_at", sa.DateTime(timezone=True), nullable=True),
        # server_default rather than an application default: H10's threat model is a writer
        # that is not the application. timestamptz — H17 forbids a guessed zone.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["circle_id"], ["circle.id"], name="fk_place_circle"),
        sa.CheckConstraint(
            "origin in ('reference', 'circle-local')",
            name="ck_place_origin",
        ),
        sa.CheckConstraint(
            "origin <> 'circle-local' or "
            "(circle_id is not null and name is not null and registry_no is null)",
            name="ck_place_circle_local_shape",
        ),
        sa.CheckConstraint(
            "origin <> 'reference' or "
            "(circle_id is null and name is null and registry_no is not null)",
            name="ck_place_reference_shape",
        ),
        # D39's provenance travels with the value or the value does not exist.
        sa.CheckConstraint(
            "(category is null and category_model is null and "
            " category_prompt_version is null and category_generated_at is null) or "
            "(category is not null and category_model is not null and "
            " category_prompt_version is not null and category_generated_at is not null)",
            name="ck_place_category_provenance",
        ),
    )
    # Accumulation needs one row (D28's moat): the same source place may not enter twice,
    # and the same typed name may not split a circle's credit across two rows.
    op.create_index(
        "uq_place_reference_registry",
        "place",
        ["registry_no"],
        unique=True,
        postgresql_where=sa.text("origin = 'reference'"),
    )
    op.create_index(
        "uq_place_circle_local_name",
        "place",
        ["circle_id", "name"],
        unique=True,
        postgresql_where=sa.text("origin = 'circle-local'"),
    )


def downgrade() -> None:
    op.drop_table("place")
