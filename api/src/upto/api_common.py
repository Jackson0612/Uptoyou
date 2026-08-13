"""Shared by the write half (rounds) and the read half (live): the three helpers both need.

`resolve_member` is D67's gate. `place_names` is D28's 2026-08-13 ruling executed at read
time — a reference place carries only its 登錄字號, so its display name comes from the latest
publication's row, never from a copy that would drift. `result_body` is the one shape a close
has, whether it answers a roll, a retry (D69), or arrives on the stream (D53) — one builder,
so the shapes cannot disagree.
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import bindparam, text

from .auth import member_for


async def resolve_member(session, request: Request, circle_id: int) -> int:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="a bearer token is required (D67)")
    member = await member_for(session, header[7:].strip(), circle_id)
    if member is None:
        # One answer for both halves: which half failed is not the caller's to learn.
        raise HTTPException(
            status_code=401, detail="the token does not resolve to a member of this circle"
        )
    return member


async def place_names(session, place_ids) -> dict[int, str]:
    """Display names: a circle-local row's own words, a reference row's latest publication."""
    ids = list(place_ids)
    if not ids:
        return {}
    rows = (
        await session.execute(
            text(
                "select p.id, coalesce(p.name, ("
                "  select rp.name from reference_place rp"
                "  join place_publication pp on pp.id = rp.publication_id"
                "  where rp.registry_no = p.registry_no"
                "  order by pp.detected_at desc limit 1"
                ")) as display_name "
                "from place p where p.id in :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": ids},
        )
    ).all()
    return {row.id: row.display_name for row in rows}


def result_body(
    round_id: int,
    dice: tuple[int, int] | None,
    winning_place_id: int,
    weights: dict[int, object],
    names: dict[int, str],
    allocation: dict[int, int],
) -> dict:
    return {
        "round_id": round_id,
        "status": "closed",
        "dice": list(dice) if dice is not None else None,
        "sum": dice[0] + dice[1] if dice is not None else None,
        "winning_place_id": winning_place_id,
        # Strings, not floats: the weights are exact decimals and stay that way (D46).
        "weights": {str(p): str(w) for p, w in weights.items()},
        # The table is the truth of the draw (D72): each place's share of the 36 outcomes.
        "allocation": {str(p): n for p, n in allocation.items()},
        "places": {str(p): n for p, n in names.items()},
    }
