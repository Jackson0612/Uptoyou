"""D67 — a bearer token resolves to a member, or the write does not happen.

The rule this module carries: **authentication references only `principal`, the product
domain references only `member`, and they meet at `member.principal_id`** (D12). So the
resolution is one join — hash the token, find the principal that owns the secret, find that
principal's seat in the circle the request names. A token the table does not know and a
principal with no seat in that circle produce the same `None`, because the caller learns
nothing about which half failed (H3's instinct: the error must not be a probe).

The token is hashed with SHA-256 before it touches a query, so the plaintext exists only in
the request. D12 rules the fast hash and why.
"""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import text


async def member_for(session, token: str, circle_id: int) -> int | None:
    """The caller's member id in this circle, or None. The only crossing is the D12 join."""
    digest = sha256(token.encode("utf-8")).hexdigest()
    return (
        await session.execute(
            text(
                "select m.id from device_secret ds "
                "join member m on m.principal_id = ds.principal_id "
                "where ds.secret_sha256 = :digest and m.circle_id = :circle"
            ),
            {"digest": digest, "circle": circle_id},
        )
    ).scalar_one_or_none()
