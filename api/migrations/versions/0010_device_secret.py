"""Ticket 16 — `device_secret`: the write half's caller, made resolvable.

Revision ID: 0010
Revises: 0009
Created: 2026-08-13

**D67 executed:** every write endpoint authenticates from the first one, and this is the table
the bearer token resolves against. One device holds one secret covering every circle its
owner belongs to — D12's load-bearing sentence, which is why the row hangs off `principal`
and not `member`.

**The column is a hash, never the token (D12).** H10's threat model — a reader connected to
the database directly — gets sixty-four hex characters that impersonate nobody. SHA-256
rather than a slow KDF, and D12 argues why: the token is 256-bit random, so there is no
brute-force surface for argon2 to defend, and its cost would be paid on every authenticated
request including the SSE handshake.

**This is the first name on H19's authentication allowlist.** The identity test holds a
frozen set of tables permitted a foreign key to `principal`, empty until now; this commit
adds `device_secret` to it, which is exactly the deliberate act D12 designed the test to
demand.

**Not built here, still unruled (D67 admits it):** how a device gets its first secret — the
invite flow's leading edge. Until that is walked, secrets enter by operator hand, which is
acceptable for exactly as long as there are no users.
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_secret",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("principal_id", sa.BigInteger, nullable=False),
        # SHA-256 of the token, hex. Unique because the lookup is by this column alone.
        sa.Column("secret_sha256", sa.CHAR(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"], ["principal.id"], name="fk_device_secret_principal"
        ),
        sa.UniqueConstraint("secret_sha256", name="uq_device_secret_hash"),
    )


def downgrade() -> None:
    op.drop_table("device_secret")
