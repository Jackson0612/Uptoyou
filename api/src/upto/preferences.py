"""A1 / item 4 — the private preference surface: write silently, read what is in force.

*Written 2026-08-18, owner-ruled (A1). Table: revision 0022. Contributor: `upto.engine.preference`.*

**Two endpoints, and the asymmetry between them is the design.** The write says nothing back and
appears nowhere; the read is a deliberate act by the member on their own device, and D25 requires
it — *「Re-confirmation shows the value, it does not ask the question again… the screen arrives with
it filled in.」* Asking afresh every round would be the exact pressure the product exists to remove.

**The write is silent, and "silent" is stronger than "anonymous" (§3.0).** `204`, empty body, and —
the part that matters most — **nothing is published to the circle's stream.** Not a count, not an
anonymous "someone updated a preference", nothing. At five people the *timing* of an event is one
guess from a name, and once guessed the person must either own it or publicly correct it, which is
the exposure their silence was buying. D55 already refuses authorship in the snapshot for the same
reason; this refuses the event itself. **The response also does not echo the value**, so a device
left on a table after the fact tells a passer-by nothing.

**Nothing is edited (D25).** Every write appends a row. Changing a budget appends a new band;
un-avoiding a category appends `stance='allow'`. "The value in force" is therefore a *query* — the
latest row per key — and resolving it **server-side** is not a convenience: a client applying
latest-wins would put the convention in the browser, which is what D5 and D13 exist to refuse.

**`persist` defaults to `false`.** D17: persistence is opt-in per preference and *the default is not
to keep*. A `persist=false` row is still written and still used for the round in force, then erased
by the scheduled job — so "do not remember this" is a fact with provenance rather than an absence,
and the screen's choice is not a no-op.

**No aggregate, and no other member, ever (H3, §3.0).** Both endpoints read `member_id` from the
device secret and touch nothing else. There is no circle-wide summary here and there is no column
to build one from — `preference` has no circle column at all.

**Error copy follows the rounds router's convention.** A person can reach nothing here but their own
screen, and both 400s are produced only by a client sending outside the closed list — a client bug,
never a person — so they stay English and name the list. The 401 is D67's one answer for both halves.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import text

from .api_common import resolve_member
from .db import session_factory

# D38's ten and §4C-2's two bands, mirrored from revision 0022's CHECKs. **Two copies on purpose,
# and the duplication is the cheaper half:** the database refuses a bad value whatever the API
# believes (D39's condition 2), and this list exists only so the refusal is a 400 naming the list
# rather than a 500 carrying a constraint name. The integration test asserts they agree.
CATEGORIES = ("麵食", "飯食", "小吃", "火鍋", "燒烤", "日式", "西式", "早餐", "咖啡飲料", "其他")
BUDGET_BANDS = ("tight", "easy")
STANCES = ("avoid", "allow")

KIND_BUDGET = "budget"
KIND_AVOID = "avoid_category"

# No prefix: the proxy strips /api/ before forwarding, so the app serves /circles/… — the same
# convention the rounds and live routers keep, and a prefix here once produced a proxy-only 404.
router = APIRouter()

_resolve_member = resolve_member

# `valid_from` and `expires_on` both come from the database's clock in one statement, so a month
# boundary cannot fall between two readings of two clocks. D25: salary is monthly, so a budget
# statement expires at the end of its own month — computed at write time and stored, because a
# boundary four readers each re-derive is how two of them disagree.
INSERT = """
insert into preference (member_id, kind, value, stance, persist, expires_on)
values (
    :member_id, :kind, :value, :stance, :persist,
    case when :kind = 'budget'
         then (date_trunc('month', now()) + interval '1 month' - interval '1 day')::date
         else null end
)
returning id
"""

# The latest row per key, which is what "in force" means once nothing is edited. `distinct on` is
# the shape the index `ix_preference_in_force` was built for: (member_id, kind, valid_from desc).
IN_FORCE_BUDGET = """
select distinct on (kind) value, persist, expires_on, valid_from,
       (expires_on < current_date) as expired
  from preference
 where member_id = :member_id and kind = 'budget'
 order by kind, valid_from desc, id desc
"""

# One row per avoided category — the latest stance for each value, then only the ones still
# `avoid`. An `allow` row is a real fact with a real history and is deliberately *not* returned:
# the screen asks "what am I avoiding", not "what have I ever said".
IN_FORCE_AVOID = """
select value, persist, valid_from from (
    select distinct on (value) value, stance, persist, valid_from
      from preference
     where member_id = :member_id and kind = 'avoid_category'
     order by value, valid_from desc, id desc
) latest
 where stance = 'avoid'
 order by value
"""


# The evaluator's ask (2026-08-18), and the reason it is a payload field rather than a sentence in
# the markup: hardcoding today's proportion makes the screen's statement **false the moment the
# backfill runs**, silently. Same refusal M2 makes when it prints *insufficient history* instead of
# copying a cadence off a webpage. The denominator is the current reference publication — the set a
# member could actually propose from — and the numerator is the places that have a category, which
# is what decides whether an avoid can fire at all.
CATEGORY_COVERAGE = """
select (select count(*) from place where category is not null) as with_category,
       (select count(*) from reference_place
         where publication_id = (
             select id from place_publication order by detected_at desc, id desc limit 1
         )) as reference_rows
"""


# **The proposable set, defined once (owner-ruled 2026-08-18, D22's amendment).** D22's breadth
# number needs a denominator, and "the feasible pool" is only defined inside a round — while the
# preference screen is by definition opened with none running (D17's decisive reason: payday lands
# with nothing open). The ruled denominator is **the circle's proposable set: every place any member
# could propose** — every `reference` place in the current publication, plus this circle's own
# `circle-local` places. Rejected: the last round's pool (answers a question about the past, so a
# member setting a preference after a quiet fortnight is warned against a pool nobody is choosing
# from) and the latest publication unscoped (counts thousands nobody in the circle would propose, so
# the proportion reads reassuringly small and means nothing).
#
# **The numerator can only count places that have a category**, because only a categorised place can
# be avoided — which is why the coverage figure below sits beside it rather than in the markup.
BREADTH = """
with latest as (
    select id from place_publication order by detected_at desc, id desc limit 1
),
proposable as (
    select p.category
      from reference_place rp
      join latest on true
      left join place p
        on p.registry_no = rp.registry_no and p.origin = 'reference'
     where rp.publication_id = latest.id
    union all
    select p.category
      from place p
     where p.origin = 'circle-local' and p.circle_id = :circle_id
)
select count(*) as proposable,
       count(*) filter (where category = any(:avoided)) as removed
  from proposable
"""


class PreferenceBody(BaseModel):
    kind: str
    value: str
    # D17's default, expressed where the default belongs: absent means not kept.
    persist: bool = False
    stance: str | None = None


def _validate(body: PreferenceBody) -> None:
    """Refuse anything outside the closed lists, naming the list. Never coerce (D39).

    Coercing a near-miss — 「拉麵」 to 麵食, or a missing stance to `avoid` — would turn a client
    bug into a plausible stored fact, which is the H23 shape this schema keeps meeting. A default
    stance is the one that would hurt: it would let a malformed request *start* an avoidance.
    """
    if body.kind not in (KIND_BUDGET, KIND_AVOID):
        raise HTTPException(
            status_code=400,
            detail="kind must be one of {} — {!r} is not".format(
                ", ".join((KIND_BUDGET, KIND_AVOID)), body.kind
            ),
        )
    if body.kind == KIND_BUDGET:
        if body.value not in BUDGET_BANDS:
            raise HTTPException(
                status_code=400,
                detail="a budget value must be one of {} — {!r} is not".format(
                    ", ".join(BUDGET_BANDS), body.value
                ),
            )
        if body.stance is not None:
            raise HTTPException(
                status_code=400,
                detail="a budget carries no stance; stance belongs to a category alone",
            )
        return
    if body.value not in CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="a category must be one of D38's ten ({}) — {!r} is not".format(
                "、".join(CATEGORIES), body.value
            ),
        )
    if body.stance not in STANCES:
        raise HTTPException(
            status_code=400,
            detail="a category needs a stance, one of {} — {!r} is not. It is not defaulted: a "
            "malformed request must not be able to start an avoidance.".format(
                ", ".join(STANCES), body.stance
            ),
        )


@router.post("/circles/{circle_id}/preferences", status_code=204, response_class=Response)
async def record_preference(circle_id: int, body: PreferenceBody, request: Request) -> Response:
    """Append one preference row. Answers 204 with nothing, and publishes nothing.

    **The absence of a `publish(...)` call in this function is load-bearing.** Every other write
    in this application announces itself on the circle's stream; this one must not, and a future
    reader adding one "for consistency" would undo §3.0. The integration test asserts the stream
    stays quiet across a write.

    No 409: a second write is not a conflict, it is the next version. That is D70's quiet-success
    shape applied to a table that appends.
    """
    _validate(body)
    async with session_factory()() as session:
        member_id = await _resolve_member(session, request, circle_id)
        await session.execute(
            text(INSERT),
            {
                "member_id": member_id,
                "kind": body.kind,
                "value": body.value,
                "stance": body.stance,
                "persist": body.persist,
            },
        )
        await session.commit()
    # 204 and no body. Not the row's id, not the value back — see the module docstring.
    return Response(status_code=204)


@router.get("/circles/{circle_id}/preferences")
async def preferences_in_force(circle_id: int, request: Request) -> dict:
    """What this member has in force — resolved here, never in the client (D5, D13).

    D25 requires this: the screen arrives with the value filled in rather than asking again — and
    that includes a band whose month has ended, flagged `expired` so the screen can prompt the
    re-affirmation D25 asks for rather than presenting a stale number as current. The history is
    not returned; a member does not need last month's band to change this month's, and
    a payload carrying twelve months of a person's states is a larger thing to hand out than the
    one fact the screen needs.

    **Shaped so D22's breadth number can be added without moving anything** — it will arrive as a
    sibling key when the owner has ruled what "the feasible pool" means outside a round, which is
    the one thing D22 defines only inside one.
    """
    async with session_factory()() as session:
        member_id = await _resolve_member(session, request, circle_id)
        budget_row = (
            await session.execute(text(IN_FORCE_BUDGET), {"member_id": member_id})
        ).one_or_none()
        avoided = (
            await session.execute(text(IN_FORCE_AVOID), {"member_id": member_id})
        ).all()
        coverage = (await session.execute(text(CATEGORY_COVERAGE))).one()
        breadth = (
            await session.execute(
                text(BREADTH),
                {"circle_id": circle_id, "avoided": [row.value for row in avoided]},
            )
        ).one()
    return {
        # **D22's breadth, with its denominator stated in the payload rather than assumed.** The
        # evaluator refuses an unstated denominator at the gate and is right to: the same share
        # means three different things over three candidate pools, and a warning nobody can check
        # is not a warning. `threshold` is `null` on purpose — **D22 says "when that crosses the
        # line" and names no number**, so the line is unruled and this payload will not invent
        # one. A screen may state the share; it may not say "crossed" until there is a line.
        "breadth": {
            "removed": breadth.removed,
            "proposable": breadth.proposable,
            "share": 0.0
            if not breadth.proposable
            else round(breadth.removed / breadth.proposable, 4),
            "denominator": "the circle's proposable set — every reference place in the current "
                           "publication, plus this circle's own places",
            "threshold": None,
        },
        # **What an avoid can currently reach.** Not decoration: only a place with a category can
        # be avoided, so this is the honest bound on the whole feature, and it is 6.2% today
        # because one township has been classified. The screen states it and never advises on it.
        "category_coverage": {
            "with_category": coverage.with_category,
            "reference_rows": coverage.reference_rows,
            "share": 0.0
            if not coverage.reference_rows
            else round(coverage.with_category / coverage.reference_rows, 4),
        },
        "budget": None
        if budget_row is None
        else {
            "value": budget_row.value,
            "persist": budget_row.persist,
            # The month D25 gives it. A screen may say "until the end of August" without
            # re-deriving a boundary the database already decided.
            "expires_on": budget_row.expires_on.isoformat(),
            "valid_from": budget_row.valid_from.isoformat(),
            # **An expired budget is still returned, and that is D25's own rule rather than
            # laxity:** *「Re-confirmation shows the value, it does not ask the question again.」*
            # The screen arrives with last month's band filled in and the member accepts or
            # changes it. What expiry stops is the *contributing* — the contributor ignores an
            # expired band — so the flag is here for the prompt, not as a deletion signal.
            "expired": bool(budget_row.expired),
        },
        "avoid_categories": [
            {
                "value": row.value,
                "persist": row.persist,
                "valid_from": row.valid_from.isoformat(),
            }
            for row in avoided
        ],
    }
