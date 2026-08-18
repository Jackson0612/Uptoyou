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

from .api_common import place_names, resolve_member, result_body, trip_for
from .db import session_factory
from .engine.fold import Contribution, fold
from .engine.load import load_contributions
from .engine.store import write_roll
from .engine.table import EmptyPoolError, allocate
from .engine.table import build as build_table
from .engine.table import place_for
from .stream import publish

# Error `detail` strings a person can reach from the surface are product copy — the front end
# prints them verbatim (D96/A10, 2026-08-17): plain 繁體中文, no spec citations. The 422 for a
# malformed target_hour stays English because only a client bug, never a person, produces it.
# No prefix: the proxy strips /api/ before forwarding (upto.conf's rewrite), so the app
# serves /circles/... and the outside world sees /api/circles/... — same convention as
# /weather. A prefix here once produced a proxy-only 404 the tests could not see.
router = APIRouter()

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
            raise HTTPException(status_code=404, detail="找不到這一輪。")
        member = await _resolve_member(session, request, round_row.circle_id)
        if round_row.status != "open":
            raise HTTPException(status_code=409, detail="這一輪已經擲過了。")
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
            raise HTTPException(status_code=404, detail="找不到這家店。")
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
                    status_code=409, detail="一輪最多提三家。"
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
    # B2: `None` until somebody signs, and the same shape wherever a trip appears — nickname and
    # time, never the signer's id (H3). Read here rather than assembled, so the reveal, the SSE
    # snapshot and the signing response cannot drift apart.
    body["trip"] = await trip_for(session, round_id)
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
            raise HTTPException(status_code=404, detail="找不到這一輪。")
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
                detail="池子是空的，或每一家的權重都是零，擲不出結果。",
            ) from None
        dice = (secrets.randbelow(6) + 1, secrets.randbelow(6) + 1)
        winner = place_for(table, dice[0], dice[1])
        await write_roll(session, round_id, pinned, weights, winner, dice)
        await session.commit()
        body = await _closed_body(session, round_id, dice, winner, weights)
        # D53: the close is pushed once, with its result, and then the channel is quiet.
        publish(round_row.circle_id, {"type": "closed", "result": body})
    return body

@router.post("/rounds/{round_id}/trip", status_code=201)
async def sign_trip(round_id: int, request: Request, response: Response) -> dict:
    """B2 / item 9 — one member says the group went. 201, or 200 on a retry, or 409 with the signer.

    **§3.0's asymmetry, as an endpoint.** A proposal is anonymous and D14's trigger has already
    erased its author by the time this can be called; a trip is *named*, because "we went" is a fact
    about an outing rather than an opinion about a restaurant. So this is the one place a member's
    identity is recorded and kept.

    **Nothing is published to the stream (D53).** A close is pushed once and then the channel is
    quiet. A trip event would tell four other people the *moment* one person tapped, and §3.0's whole
    argument is that at five people the timing of an event is one guess from a name. D53's own flip
    condition is a measurement of when people actually sign — not an intuition that a live badge
    would be nice — so there is deliberately no `publish` call in this function.

    **The three outcomes are the database's, not this code's.**

    * **201** — the insert succeeded and this member is the signer.
    * **200** — the same member tapped twice. D69's idiom: a retry is not an error, and it returns
      the same trip rather than a conflict, because the second tap usually means the first response
      was lost.
    * **409 with the fact** — somebody else signed first, and the response names *who* and *when*
      (D68). A bare 409 would leave a screen saying "already signed" with no way to show by whom,
      and the nickname is circle-visible information: everyone in the circle knows who is in it.

    **The race is settled by `trip.round_id`'s UNIQUE and not by a `SELECT` first.** Two taps in the
    same instant both pass a check-then-insert; only one passes the index. So the insert is attempted
    and the conflict is *read* afterwards — which also means the 409's facts come from the row that
    actually won rather than from whatever a prior read saw.

    **A signature outside the circle is refused by the composite foreign keys**, not here. See
    revision 0024: `(circle_id, member_id) → member(circle_id, id)` cannot be satisfied by a member
    of another circle, so even a bug in this function cannot store one.
    """
    async with session_factory()() as session:
        round_row = (
            await session.execute(
                text("select circle_id, status, winning_place_id from round where id = :r"),
                {"r": round_id},
            )
        ).one_or_none()
        if round_row is None:
            raise HTTPException(status_code=404, detail="找不到這一輪。")
        member = await _resolve_member(session, request, round_row.circle_id)
        # A trip needs somewhere to have gone. An open round has no winner, so signing one would
        # record an outing to a place nobody has chosen yet.
        if round_row.status != "closed" or round_row.winning_place_id is None:
            raise HTTPException(status_code=409, detail="這一輪還沒擲出結果。")
        try:
            await session.execute(
                text(
                    "insert into trip (round_id, circle_id, member_id) "
                    "values (:r, :c, :m)"
                ),
                {"r": round_id, "c": round_row.circle_id, "m": member},
            )
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = (
                await session.execute(
                    text("select member_id from trip where round_id = :r"), {"r": round_id}
                )
            ).one_or_none()
            if existing is None:
                # The insert failed and no trip exists: the composite keys refused it, which means
                # the member does not belong to this round's circle. Re-raised rather than turned
                # into a 409, because it is not a conflict — nothing is there to conflict with.
                raise HTTPException(status_code=403, detail="這一輪不屬於你的圈子。") from None
            trip = await trip_for(session, round_id)
            if existing.member_id == member:
                response.status_code = 200
                return {"trip": trip}
            raise HTTPException(
                status_code=409,
                detail="{}已經在 {} 記下這一趟了。".format(trip["nickname"], trip["signed_at"]),
            ) from None
        return {"trip": await trip_for(session, round_id)}
