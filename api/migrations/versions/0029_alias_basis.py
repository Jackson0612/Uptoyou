"""D113's amendment — which authority a row stands on, as a column rather than as prose.

Revision ID: 0029
Revises: 0028
Created: 2026-08-20

Hand-written (H10). D113 was amended 2026-08-20 with a **per-row owner-exception path**: the default
bound is that an alias must be checkable against a published pairing, and the owner may rule a
specific row in without one, its note then citing the ruling.

**Two paths means the row has to say which it is, and `note` cannot be that answer.** The first
version of this shipped with the basis in prose and `test_search_alias.py` asserting that every note
names `brand_registration`. The two owner-ruled rows passed it — because their notes mention
`brand_registration` **to say it does not support them**. A true assertion about the wrong subject,
which is this week's recurring defect and the sixth instance of it; caught before the rows landed.

So the basis is a column with a `CHECK`, and the test reads the column:

  `pairing`     — the default. A published `brand_registration` row connects this registered name to
                  the brand the alias is the everyday rendering of. Withdrawable by checking a source.
  `owner-ruled` — D113's amendment. Nothing published supports it; the owner accepted that the row's
                  correctness is his assertion. **Withdrawable only by asking him.**

**The distinction is not bookkeeping.** It is the difference between a row somebody can falsify and a
row somebody must be asked about, and `--list` is the audit surface where that has to be visible
without reading paragraphs.

**Backfilled to `pairing`, and that is safe rather than convenient**: 星巴克 is the only row that
predates this revision and it is a pairing row by construction (D113's ruled example, verified
against `悠旅生活事業股份有限公司 → STARBUCKS COFFEE`). Every future row states its own basis because
the column is NOT NULL with no default.
"""

from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

BASES = ("pairing", "owner-ruled")


def upgrade() -> None:
    # Added nullable, backfilled, then made NOT NULL — the shape that works on a table with rows.
    op.add_column("search_alias", sa.Column("basis", sa.Text, nullable=True))
    op.execute("update search_alias set basis = 'pairing' where basis is null")
    op.alter_column("search_alias", "basis", nullable=False)
    op.create_check_constraint(
        "ck_search_alias_basis_known",
        "search_alias",
        "basis in ('pairing', 'owner-ruled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_search_alias_basis_known", "search_alias", type_="check")
    op.drop_column("search_alias", "basis")
