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


# The single-brand join, D77's read rule: a company mapped to **exactly one** brand shows the
# brand; a multi-brand company keeps its registered name, because nothing in either source
# says which of its brands this site is (measured 2026-08-14: the rule patches 334 松山區
# rows and forgoes 17). `having count(distinct brand_name) = 1` is the whole rule.
SINGLE_BRAND = (
    "select min(br.brand_name) as brand_name from brand_registration br"
    "  where br.company_name = {company}"
    "  and br.publication_id = ("
    "    select id from brand_publication order by detected_at desc, id desc limit 1)"
    "  having count(distinct br.brand_name) = 1"
)

# The storefront join, D78's read rule: site-level, keyed by the registry number itself, and
# it **outranks the brand join** — the brand says what the company calls its shops, this row
# says what this shop's sign says, which is the only thing that can split a multi-brand
# company's sites. No `having`: the source is one row per site (0014's key enforces it).
STOREFRONT = (
    "select sn.name from storefront_name sn"
    "  where sn.registry_no = {registry}"
    "  and sn.publication_id = ("
    "    select id from storefront_publication order by detected_at desc, id desc limit 1)"
)


LATEST_PLACE_PUBLICATION = (
    "select id from place_publication order by detected_at desc, id desc limit 1"
)


async def compose_names(session, rows) -> dict[str, dict]:
    """D92, executed once for every screen. `rows` is an iterable of mappings carrying
    `key` (whatever the caller indexes by), `own` (a circle-local row's own words, or None),
    `sign`, `brand`, `registered`, `company` (the registered company name — the collision
    key), `address`. Returns, per key: `name` (what a person reads), `name_source`
    (`circle-local` · `sign` · `brand` · `registered`), `district` (B6's second line, or None).

    The collision is judged against the whole latest publication, not against the rows on
    screen — so a name is the same in the search, the pool and the reveal (the frontend
    session's "stable per brand"), and a branch does not gain a bracket because a sibling
    happened to be searched for. The key is the registered company name among sign-less
    sites: a signed site never collides (its sign is its name), and the brand is a function
    of the company (D77's single-brand rule), so two sign-less sites of one company always
    share their base name.
    """
    from . import naming  # noqa: PLC0415  (pure module; imported here to keep the header lean)

    rows = list(rows)
    out: dict[str, dict] = {}
    pending: dict[str, list] = {}  # company -> rows that may need a bracket
    for row in rows:
        loc = naming.location(row.get("address"))
        # R-6 (owner-ruled 2026-08-18): a registry footnote at the head of the registered
        # name is read out before anything is composed; the stored row is untouched.
        row = dict(row, registered=naming.strip_registry_footnote(row.get("registered")))
        if row.get("own") is not None:
            out[row["key"]] = {"name": row["own"], "name_source": "circle-local", "district": None}
        elif row.get("sign"):
            out[row["key"]] = {"name": row["sign"], "name_source": "sign", "district": loc.where_line}
        else:
            base = row.get("brand") or row.get("registered")
            source = "brand" if row.get("brand") else "registered"
            out[row["key"]] = {"name": base, "name_source": source, "district": loc.where_line}
            if row.get("company") and base:
                pending.setdefault(row["company"], []).append(row)
    if not pending:
        return out
    # One query for every sign-less sibling of every company on screen, in the latest
    # publication — the set that decides whether the base name collides.
    siblings = (
        await session.execute(
            text(
                "select rp.name as company, rp.registry_no, rp.address "
                "from reference_place rp "
                "where rp.publication_id = (" + LATEST_PLACE_PUBLICATION + ") "
                "and rp.name in :companies "
                "and not exists (" + STOREFRONT.format(registry="rp.registry_no") + ")"
            ).bindparams(bindparam("companies", expanding=True)),
            {"companies": list(pending)},
        )
    ).all()
    by_company: dict[str, dict[str, str]] = {}
    for sib in siblings:
        by_company.setdefault(sib.company, {})[sib.registry_no] = sib.address
    for company, company_rows in pending.items():
        addresses = by_company.get(company, {})
        if len(addresses) < 2:
            continue
        base = company_rows[0].get("brand") or company_rows[0].get("registered")
        derived = naming.derive_names(base, addresses)
        for row in company_rows:
            derived_name = derived.get(row.get("registry_no"))
            if derived_name:
                out[row["key"]]["name"] = derived_name
    return out


async def place_names(session, place_ids) -> dict[int, str]:
    """Display names, most specific source first: a circle-local row's own words; the
    storefront sign for the site (D78); the brand when the company names exactly one (D77);
    the registered name from the latest publication — then D92's bracket when that base name
    is shared by other sign-less sites of the same company (`compose_names`)."""
    ids = list(place_ids)
    if not ids:
        return {}
    rows = (
        await session.execute(
            text(
                "select p.id, p.name as own, p.registry_no, "
                "storefront.name as sign, brand.brand_name as brand, "
                "ref.name as registered, ref.name as company, ref.address "
                "from place p "
                "left join lateral ("
                "  select rp.name, rp.address from reference_place rp"
                "  join place_publication pp on pp.id = rp.publication_id"
                "  where rp.registry_no = p.registry_no"
                "  order by pp.detected_at desc limit 1"
                ") ref on true "
                "left join lateral ("
                + STOREFRONT.format(registry="p.registry_no")
                + ") storefront on true "
                "left join lateral (" + SINGLE_BRAND.format(company="ref.name") + ") brand on true "
                "where p.id in :ids"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": ids},
        )
    ).all()
    composed = await compose_names(
        session,
        (
            {
                "key": row.id,
                "own": row.own,
                "registry_no": row.registry_no,
                "sign": row.sign,
                "brand": row.brand,
                "registered": row.registered,
                "company": row.company,
                "address": row.address,
            }
            for row in rows
        ),
    )
    return {key: value["name"] for key, value in composed.items()}


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

# --- B2 / item 9: the trip, read the same way everywhere it appears ------------------------
#
# **One helper for three readers, because three copies of this query is three chances to leak a
# column.** The reveal payload, the SSE snapshot and the signing endpoint's own response must all
# describe a trip identically, and what they must never carry is the signer's `member_id` — H3's
# response-shape rule, and §3.0's reason: at five people an id is a name.
#
# `nickname` and `signed_at` only. Not `member_id`, not `place_id` (the winner is read from
# `round.winning_place_id` — D28/D57, derived and never copied), and not a note, because D38 admits
# no free text.
#
# **Nobody is a hole.** An unsigned round returns `None` rather than an empty object, so a screen
# distinguishes "no trip yet" from "a trip with nothing in it" without inspecting fields.
TRIP = """
select m.nickname as nickname, t.signed_at as signed_at
  from trip t join member m on m.id = t.member_id
 where t.round_id = :round_id
"""


async def trip_for(session, round_id: int):
    """`{"nickname", "signed_at"}` for a signed round, or `None`."""
    row = (await session.execute(text(TRIP), {"round_id": round_id})).one_or_none()
    if row is None:
        return None
    return {"nickname": row.nickname, "signed_at": row.signed_at.isoformat()}
