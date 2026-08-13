"""Ticket 19 — the write half's three endpoints: open, propose, roll.

Every endpoint resolves the caller to a member of the round's circle before anything else
(D67), and the two halves of a failed resolution — an unknown token, a circle without a seat
— read identically, so the error is not a probe.

The response shapes the entries already ruled:

- a losing simultaneous open answers **409 carrying the round that won** (D68), so a typed
  hour is never silently dropped;
- a repeat proposal is a **quiet 200** (D70) — a proposal carries no input beyond which
  place, so two requests for the same place cannot disagree;
- rolling a closed round answers **200 with the stored result** (D69) — the retry gets
  exactly the answer it missed, in the same shape a first roll returns it;
- a swept or empty pool answers 409 out loud (D22's shape) rather than resolving to an
  arbitrary winner.

The roll is the whole chain in one transaction: re-resolve a defaulted hour to the hour the
roll stands in (D73, D41), load and pin (D43), fold (D45/D46), apportion 36 outcomes (D72),
two cryptographically random dice, and `write_roll` — which re-folds the records it stores
and refuses the whole write on any mismatch (D15).
"""

from __future__ import annotations

import secrets
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from .api_common import place_names, resolve_member, result_body
from .db import session_factory
from .engine.fold import Contribution, fold
from .engine.load import load_contributions
from .engine.store import write_roll
from .engine.table import EmptyPoolError, allocate
from .engine.table import build as build_table
from .engine.table import place_for
from .stream import publish

router = APIRouter(prefix="/api")

_resolve_member = resolve_member


class OpenRoundBody(BaseModel):
    target_hour: datetime | None = None


@router.post("/circles/{circle_id}/rounds", status_code=201)
async def open_round(circle_id: int, body: OpenRoundBody, request: Request) -> dict:
    typed = body.target_hour is not None
    if typed and body.target_hour.tzinfo is None:
        raise HTTPException(status_code=422, detail="target_hour must carry a UTC offset (H17)")
    async with session_factory()() as session:
        await _resolve_member(session, request, circle_id)
        try:
            row = (
                await session.execute(
                    text(
                        "insert into round (circle_id, target_hour, target_hour_typed) "
                        "values (:c, coalesce(:h, date_trunc('hour', now())), :typed) "
                        "returning id, target_hour, target_hour_typed, opened_at"
                    ),
                    {"c": circle_id, "h": body.target_hour, "typed": typed},
                )
            ).one()
            await session.commit()
            # After the commit, never before: an event for a rolled-back write is a lie.
            publish(
                circle_id,
                {
                    "type": "round_opened",
                    "round": {
                        "round_id": row.id,
                        "target_hour": row.target_hour.isoformat(),
                        "target_hour_typed": row.target_hour_typed,
                        "opened_at": row.opened_at.isoformat(),
                        "pool": [],
                    },
                },
            )
        except IntegrityError:
            # D52's partial unique index fired: someone else's open won. D68: say so, and
            # hand over the winner so the client enters it without a second fetch.
            await session.rollback()
            winner = (
                await session.execute(
                    text(
                        "select id, target_hour, target_hour_typed, opened_at from round "
                        "where circle_id = :c and status = 'open'"
                    ),
                    {"c": circle_id},
                )
            ).one_or_none()
            detail: dict = {"error": "a round is already open in this circle (D68)"}
            if winner is not None:
                detail["open_round"] = {
                    "round_id": winner.id,
                    "target_hour": winner.target_hour.isoformat(),
                    "target_hour_typed": winner.target_hour_typed,
                    "opened_at": winner.opened_at.isoformat(),
                }
            raise HTTPException(status_code=409, detail=detail) from None
    return {
        "round_id": row.id,
        "status": "open",
        "target_hour": row.target_hour.isoformat(),
        "target_hour_typed": row.target_hour_typed,
    }


class ProposeBody(BaseModel):
    place_id: int


@router.post("/rounds/{round_id}/proposals", status_code=201)
async def propose(round_id: int, body: ProposeBody, request: Request, response: Response) -> dict:
    async with session_factory()() as session:
        round_row = (
            await session.execute(
                text("select circle_id, status from round where id = :r"), {"r": round_id}
            )
        ).one_or_none()
        if round_row is None:
            raise HTTPException(status_code=404, detail="no such round")
        member = await _resolve_member(session, request, round_row.circle_id)
        if round_row.status != "open":
            raise HTTPException(status_code=409, detail="the round is closed")
        place = (
            await session.execute(
                text("select origin, circle_id from place where id = :p"),
                {"p": body.place_id},
            )
        ).one_or_none()
        # A circle-local place of another circle answers exactly like no place at all:
        # what other circles typed is not this circle's to discover (D28's scoping).
        if place is None or (
            place.origin == "circle-local" and place.circle_id != round_row.circle_id
        ):
            raise HTTPException(status_code=404, detail="no such place")
        try:
            await session.execute(
                text(
                    "insert into proposal (round_id, place_id, member_id) "
                    "values (:r, :p, :m)"
                ),
                {"r": round_id, "p": body.place_id, "m": member},
            )
            await session.commit()
            names = await place_names(session, [body.place_id])
            publish(
                round_row.circle_id,
                {
                    "type": "pooled",
                    "round_id": round_id,
                    "place": {
                        "place_id": body.place_id,
                        "name": names.get(body.place_id),
                    },
                },
            )
        except (IntegrityError, DBAPIError) as failure:
            await session.rollback()
            message = str(getattr(failure, "orig", failure))
            if "uq_proposal_place_per_round" in message:
                # D70: the place is in the pool, which is what the request wanted.
                response.status_code = 200
                return {"round_id": round_id, "place_id": body.place_id, "pooled": True}
            if "3 proposals" in message:
                raise HTTPException(
                    status_code=409, detail="three proposals per member per round (§3.0)"
                ) from None
            raise
    return {"round_id": round_id, "place_id": body.place_id, "pooled": True}


async def _closed_body(
    session,
    round_id: int,
    dice: tuple[int, int] | None,
    winning_place_id: int,
    weights: dict[int, object],
) -> dict:
    body = result_body(
        round_id,
        dice,
        winning_place_id,
        weights,
        await place_names(session, weights.keys()),
        allocate({p: w for p, w in weights.items()}),
    )
    # The reveal panel's evidence: the stored records, re-folded so the clamp lines D45
    # requires are derived from the same rows the audit reads — never a second bookkeeping.
    # A reason travels only at 'table' visibility (D13): this payload is circle-wide, so a
    # represented member's sentence and a 'none' sentence alike stay behind; the factor and
    # its contributor still show, because the *odds* were never the secret.
    rows = (
        await session.execute(
            text(
                "select id, place_id, channel, contributor, effect, reason, "
                "reason_visibility from weight_contribution "
                "where round_id = :r"
            ),
            {"r": round_id},
        )
    ).all()
    panel: dict[str, dict] = {}
    for place_id in weights:
        contributions = [
            Contribution(
                id=row.id,
                place_id=place_id,
                channel=row.channel,
                contributor=row.contributor,
                effect=row.effect,
                reason=row.reason,
            )
            for row in rows
            if row.place_id == place_id
        ]
        folded = fold(place_id, contributions)
        visibility = {row.id: row.reason_visibility for row in rows}
        panel[str(place_id)] = {
            # D46's total order, straight from the fold — the panel must never re-sort.
            "factors": [
                {
                    "channel": c.channel,
                    "contributor": c.contributor,
                    # normalize(): numeric(4,3) reads back as 0.800, and the panel says ×0.8.
                    # Display only — the fold and D15's reconciliation compare values.
                    "effect": str(c.effect.normalize()),
                    "reason": c.reason if visibility[c.id] == "table" else None,
                }
                for c in folded.contributions
            ],
            # D45: a clamped channel is its own line, or the arithmetic visibly fails.
            "clamps": [
                {
                    "channel": cl.channel,
                    "raw": str(cl.raw.normalize()),
                    "clamped": str(cl.clamped.normalize()),
                }
                for cl in folded.clamps
            ],
        }
    body["panel"] = panel
    return body


@router.post("/rounds/{round_id}/roll")
async def roll(round_id: int, request: Request) -> dict:
    async with session_factory()() as session:
        round_row = (
            await session.execute(
                text(
                    "select circle_id, status, target_hour_typed, die1, die2, "
                    "winning_place_id from round where id = :r"
                ),
                {"r": round_id},
            )
        ).one_or_none()
        if round_row is None:
            raise HTTPException(status_code=404, detail="no such round")
        await _resolve_member(session, request, round_row.circle_id)

        if round_row.status == "closed":
            # D69: the retry gets the answer it missed, in the shape a first roll returns.
            stored = (
                await session.execute(
                    text("select place_id, weight from proposal where round_id = :r"),
                    {"r": round_id},
                )
            ).all()
            dice = (
                (round_row.die1, round_row.die2) if round_row.die1 is not None else None
            )
            return await _closed_body(
                session, round_id, dice, round_row.winning_place_id,
                {row.place_id: row.weight for row in stored},
            )

        if not round_row.target_hour_typed:
            # D73 through D41: a defaulted hour is re-resolved to the hour the roll stands in.
            await session.execute(
                text("update round set target_hour = date_trunc('hour', now()) where id = :r"),
                {"r": round_id},
            )

        pinned = await load_contributions(session, round_id)
        pool = (
            (
                await session.execute(
                    text("select place_id from proposal where round_id = :r"), {"r": round_id}
                )
            )
            .scalars()
            .all()
        )
        weights = {
            place: fold(
                place, [p.contribution for p in pinned if p.contribution.place_id == place]
            ).weight
            for place in pool
        }
        try:
            table = build_table(weights)
        except EmptyPoolError:
            raise HTTPException(
                status_code=409,
                detail="nothing can be drawn — the pool is empty or fully at weight zero (D22)",
            ) from None
        dice = (secrets.randbelow(6) + 1, secrets.randbelow(6) + 1)
        winner = place_for(table, dice[0], dice[1])
        await write_roll(session, round_id, pinned, weights, winner, dice)
        await session.commit()
        body = await _closed_body(session, round_id, dice, winner, weights)
        # D53: the close is pushed once, with its result, and then the channel is quiet.
        publish(round_row.circle_id, {"type": "closed", "result": body})
    return body
