"""Ticket 20 — the read half: the circle's stream, and the places a proposal needs.

**The snapshot is the stream's first event (D56), and there is no endpoint beside it** — a
reconnecting client and a fresh one run the same code path, which is the whole reason D56
ruled it this way. The subscription opens *before* the snapshot is built: an event landing in
that window is delivered twice — once inside the snapshot, once as itself — and a duplicate
is the safe direction, because the client applies events idempotently (a pooled place it
already shows, a close it already drew) while a gap would be a fact it never learns.

**Nothing on this stream carries a member (D55).** The pool is places; the close is a result;
authorship exists only inside an open round's table rows and dies at the close (D14). A trip
is never on the stream (D53) — it is signed hours later, when nobody is watching a channel.

**The propose flow is D28's:** the typeahead searches this circle's own rows and the latest
publication's reference rows; a name nothing matches is submitted as it stands and becomes a
circle-local row. Creating a place that exists is a quiet success — the name (or the 登錄字號)
is the only input, so two requests cannot disagree, which is D70's argument one table over.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .api_common import place_names, resolve_member, result_body
from .db import session_factory
from .engine.table import allocate
from .stream import subscribe

# No prefix — the proxy strips /api/ before forwarding, same as rounds.py explains.
router = APIRouter()


async def _snapshot(session, circle_id: int) -> dict:
    """The circle's current state: an open round with its pool, else the last result (D54)."""
    open_row = (
        await session.execute(
            text(
                "select id, target_hour, target_hour_typed, opened_at from round "
                "where circle_id = :c and status = 'open'"
            ),
            {"c": circle_id},
        )
    ).one_or_none()
    if open_row is not None:
        pool_ids = (
            (
                await session.execute(
                    text("select place_id from proposal where round_id = :r order by place_id"),
                    {"r": open_row.id},
                )
            )
            .scalars()
            .all()
        )
        names = await place_names(session, pool_ids)
        return {
            "type": "snapshot",
            "open_round": {
                "round_id": open_row.id,
                "target_hour": open_row.target_hour.isoformat(),
                "target_hour_typed": open_row.target_hour_typed,
                "opened_at": open_row.opened_at.isoformat(),
                "pool": [{"place_id": p, "name": names.get(p)} for p in pool_ids],
            },
            "last_result": None,
        }
    last = (
        await session.execute(
            text(
                "select id, die1, die2, winning_place_id from round "
                "where circle_id = :c and status = 'closed' "
                "order by closed_at desc limit 1"
            ),
            {"c": circle_id},
        )
    ).one_or_none()
    last_result = None
    if last is not None:
        stored = (
            await session.execute(
                text("select place_id, weight from proposal where round_id = :r"),
                {"r": last.id},
            )
        ).all()
        weights = {row.place_id: row.weight for row in stored}
        dice = (last.die1, last.die2) if last.die1 is not None else None
        last_result = result_body(
            last.id,
            dice,
            last.winning_place_id,
            weights,
            await place_names(session, weights.keys()),
            allocate(weights) if weights else {},
        )
    return {"type": "snapshot", "open_round": None, "last_result": last_result}


@router.get("/circles/{circle_id}/stream")
async def stream(circle_id: int, request: Request) -> StreamingResponse:
    async with session_factory()() as session:
        await resolve_member(session, request, circle_id)

    async def events():
        async with subscribe(circle_id) as queue:
            # Subscribe first, snapshot second: the overlap duplicates, never drops.
            async with session_factory()() as session:
                snapshot = await _snapshot(session, circle_id)
            yield "data: " + json.dumps(snapshot, ensure_ascii=False) + "\n\n"
            while True:
                event = await queue.get()
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/circles/{circle_id}/places")
async def search_places(
    circle_id: int,
    request: Request,
    q: str = Query(..., min_length=1, description="a fragment of the place's name"),
) -> dict:
    async with session_factory()() as session:
        await resolve_member(session, request, circle_id)
        local = (
            await session.execute(
                text(
                    "select id, name from place "
                    "where origin = 'circle-local' and circle_id = :c "
                    "and name ilike '%' || :q || '%' order by name limit 10"
                ),
                {"c": circle_id, "q": q},
            )
        ).all()
        latest_pub = (
            await session.execute(
                text("select id from place_publication order by detected_at desc limit 1")
            )
        ).scalar_one_or_none()
        reference = []
        if latest_pub is not None:
            reference = (
                await session.execute(
                    text(
                        "select rp.registry_no, rp.name, p.id as place_id "
                        "from reference_place rp "
                        "left join place p on p.registry_no = rp.registry_no "
                        "  and p.origin = 'reference' "
                        "where rp.publication_id = :pub "
                        "and rp.name ilike '%' || :q || '%' order by rp.name limit 10"
                    ),
                    {"pub": latest_pub, "q": q},
                )
            ).all()
    return {
        "candidates": [
            {"kind": "circle-local", "place_id": row.id, "name": row.name} for row in local
        ]
        + [
            {
                "kind": "reference",
                "place_id": row.place_id,
                "registry_no": row.registry_no,
                "name": row.name,
            }
            for row in reference
        ]
    }


class CreatePlace(BaseModel):
    name: str | None = None
    registry_no: str | None = None


@router.post("/circles/{circle_id}/places", status_code=201)
async def create_place(
    circle_id: int, body: CreatePlace, request: Request, response: Response
) -> dict:
    if (body.name is None) == (body.registry_no is None):
        raise HTTPException(
            status_code=422, detail="exactly one of name or registry_no (D28's two doors)"
        )
    async with session_factory()() as session:
        await resolve_member(session, request, circle_id)
        if body.name is not None:
            name = body.name.strip()
            if not name:
                raise HTTPException(status_code=422, detail="a place needs a name")
            try:
                place_id = (
                    await session.execute(
                        text(
                            "insert into place (origin, circle_id, name) "
                            "values ('circle-local', :c, :n) returning id"
                        ),
                        {"c": circle_id, "n": name},
                    )
                ).scalar_one()
                await session.commit()
            except IntegrityError:
                # The circle already typed this name: same row, quiet success (D28's moat —
                # credit accumulates against one row, so a second typing must not split it).
                await session.rollback()
                place_id = (
                    await session.execute(
                        text(
                            "select id from place where origin = 'circle-local' "
                            "and circle_id = :c and name = :n"
                        ),
                        {"c": circle_id, "n": name},
                    )
                ).scalar_one()
                response.status_code = 200
            return {"place_id": place_id, "name": name}
        known = (
            await session.execute(
                text("select 1 from reference_place where registry_no = :no limit 1"),
                {"no": body.registry_no},
            )
        ).scalar_one_or_none()
        if known is None:
            raise HTTPException(status_code=404, detail="no reference place with that 登錄字號")
        try:
            place_id = (
                await session.execute(
                    text(
                        "insert into place (origin, registry_no) "
                        "values ('reference', :no) returning id"
                    ),
                    {"no": body.registry_no},
                )
            ).scalar_one()
            await session.commit()
        except IntegrityError:
            await session.rollback()
            place_id = (
                await session.execute(
                    text(
                        "select id from place where origin = 'reference' "
                        "and registry_no = :no"
                    ),
                    {"no": body.registry_no},
                )
            ).scalar_one()
            response.status_code = 200
        names = await place_names(session, [place_id])
        return {"place_id": place_id, "name": names.get(place_id)}
