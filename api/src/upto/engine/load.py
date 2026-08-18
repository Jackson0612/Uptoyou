"""Ticket 15 — the engine's load half: fetch what the contributors will be handed.

D43 gives this module the queries and the contributors none of them. It walks the round's
pool, resolves each place's township, finds the rain reading for the meal's hour, and calls
the contributor once per place (D44) — collecting records and pinning each with the exact
reading row it was computed from, because only this module knows which row that was.

**Two passes, and the unit differs between them (A1, 2026-08-18).** The weather pass is one
record per *place*. The preference pass is one record per *(member, place)*: five people avoiding
the same category produce five records on one place, each pinned to that member's own preference
version — because D13's channel rule is about *who may see the reason*, and one shared record
could not answer that. Each preference record pins the **version in force** (`PreferencePin`), so
a round can be re-read and a version some round used cannot be erased (D24, D25).

**How a place reaches a township.** A `reference` place carries the 登錄字號 and nothing
else (D28's 2026-08-13 ruling): the township comes from the **latest** publication's
`reference_place` row for that number — D57's latest-wins, reused. A `circle-local` place has
no township and produces nothing, which D28 rules is neutrality rather than a penalty.

**How an hour reaches a reading.** 降雨機率 is three-hourly, so the reading is the slot that
*covers* the target hour, from the latest forecast publication that has one (D57). The loader
reads the round's stored `target_hour` as it stands: re-resolving a defaulted hour at the
roll is the roll endpoint's job (D41), not this module's.

Contribution ids here are synthetic (1..n, assigned in pool order): the database assigns the
durable ids at write time. D46's display order is re-derived from the stored rows, and the
fold's product is order-independent, so the synthetic ids never leak into anything durable.
"""

from __future__ import annotations

from sqlalchemy import text

from upto.engine.preference import REASON_VISIBILITY, avoid_contribution
from upto.engine.store import ForecastPin, PinnedContribution, PreferencePin
from upto.engine.weather import rain_contribution


async def load_contributions(session, round_id: int) -> list[PinnedContribution]:
    """One round's pool, walked once; returns every pinned record the fold will see."""
    round_row = (
        await session.execute(
            text("select circle_id, target_hour, status from round where id = :r"),
            {"r": round_id},
        )
    ).one_or_none()
    if round_row is None or round_row.status != "open":
        raise ValueError(f"round {round_id} is not an open round")
    target_hour = round_row.target_hour

    pool = (
        await session.execute(
            text(
                "select p.place_id, pl.origin, pl.registry_no, pl.category "
                "from proposal p join place pl on pl.id = p.place_id "
                "where p.round_id = :r order by p.place_id"
            ),
            {"r": round_id},
        )
    ).all()

    pinned: list[PinnedContribution] = []
    next_id = 1
    for row in pool:
        if row.origin != "reference":
            continue  # D28: no township, no reading, no record — neutral.
        township_code = (
            await session.execute(
                text(
                    "select rp.township_code from reference_place rp "
                    "join place_publication pp on pp.id = rp.publication_id "
                    "where rp.registry_no = :no order by pp.detected_at desc limit 1"
                ),
                {"no": row.registry_no},
            )
        ).scalar_one_or_none()
        if township_code is None:
            continue  # An address that never parsed costs its row a nudge and nothing else.
        reading = (
            await session.execute(
                text(
                    "select fr.publication_id, fr.township_code, fr.element, fr.measure, "
                    "fr.slot_start, fr.value "
                    "from forecast_reading fr "
                    "join forecast_publication fp on fp.id = fr.publication_id "
                    "where fr.township_code = :tc "
                    "and fr.measure = 'ProbabilityOfPrecipitation' "
                    "and fr.slot_start <= :hour "
                    "and (fr.slot_end is null or fr.slot_end > :hour) "
                    "order by fp.detected_at desc limit 1"
                ),
                {"tc": township_code, "hour": target_hour},
            )
        ).one_or_none()
        if reading is None:
            continue  # No reading for the hour: not nudged is simply not nudged.
        contribution = rain_contribution(next_id, row.place_id, int(reading.value))
        if contribution is None:
            continue
        pinned.append(
            PinnedContribution(
                contribution=contribution,
                pin=ForecastPin(
                    publication_id=reading.publication_id,
                    township_code=reading.township_code,
                    element=reading.element,
                    measure=reading.measure,
                    slot_start=reading.slot_start,
                ),
                reason_visibility="none",
            )
        )
        next_id += 1

    # --- A1: the private preferences of this circle's members -------------------------------
    #
    # **A second pass rather than a second loop inside the first, because the unit differs.** The
    # weather pass is one record per *place*; this one is one record per *(member, place)* — five
    # people avoiding the same category produce five records on one place, each pinned to its own
    # member's own preference version, because D13's channel rule is about *who may see the
    # reason* and one shared record could not answer that.
    #
    # The avoided sets are fetched once for the whole circle. D44 still holds: the contributor is
    # called once per place and is handed one place's category and one member's set — it never
    # sees the pool and never queries.
    avoided_rows = (
        await session.execute(
            text(
                "select member_id, value, id from ("
                "  select distinct on (member_id, value) member_id, value, stance, id"
                "    from preference"
                "   where kind = 'avoid_category'"
                "     and member_id in (select id from member where circle_id = :c)"
                "   order by member_id, value, valid_from desc, id desc"
                ") latest where stance = 'avoid'"
            ),
            {"c": round_row.circle_id},
        )
    ).all()
    # member_id -> {category: preference_id}. The id is the *version in force*, which is what the
    # contribution pins so a round can be re-read and a used version cannot be erased (D25).
    by_member: dict[int, dict[str, int]] = {}
    for row in avoided_rows:
        by_member.setdefault(row.member_id, {})[row.value] = row.id

    for member_id, avoided in sorted(by_member.items()):
        for row in pool:
            contribution = avoid_contribution(
                next_id, row.place_id, row.category, avoided.keys()
            )
            if contribution is None:
                continue
            pinned.append(
                PinnedContribution(
                    contribution=contribution,
                    pin=PreferencePin(preference_id=avoided[row.category]),
                    reason_visibility=REASON_VISIBILITY,
                    member_id=member_id,
                )
            )
            next_id += 1

    return pinned
