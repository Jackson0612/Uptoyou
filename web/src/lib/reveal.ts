/**
 * The reveal's wire shapes — D105's two of them.
 *
 * **There is one type here for the member and one for the operator, and the member's is not the
 * operator's with fields marked optional.** That is the whole ruling expressed in the type system:
 * the member's *response* does not contain the accounting, so there is nothing in the browser to
 * hide, toggle or forget to hide. A single type with `weights?: …` would compile the leak.
 *
 * `for_credential` in `api_common.py` builds the member shape by whitelist — `round_id · status ·
 * dice · sum · winning_place_id · places · trip` — so a field added to the payload is operator-only
 * until someone names it there. These types mirror that whitelist and nothing else.
 */

/** `place_id` → the name the API composed (D92's three layers). Keys are strings on the wire. */
export type Places = Record<string, string>

/** D106: the trip is named. One per round, and the proposal it beat is still anonymous. */
export type Trip = { nickname: string; signed_at: string } | null

export type MemberReveal = {
  round_id: number
  status: string
  dice: [number, number]
  sum: number
  winning_place_id: number | null
  places: Places
  trip: Trip
}

/** Operator only. Kept in a separate type so that nothing which renders a member screen can even
 *  name these fields — §8's build order made concrete: member state complete first, because
 *  building the operator state and subtracting is how a field survives in the member payload. */
export type OperatorReveal = MemberReveal & {
  weights: Record<string, string>
  allocation: Record<string, number>
  panel: Record<string, { factors: unknown[]; clamps: unknown[] }>
}

/** design.md §1: the four face colours, cycled by **pool seat**. Identity, never quantity — the
 *  colour says which place, never how much of the 36 it holds. */
export const FACES = ['hot', 'cobalt', 'jade', 'sun'] as const
export type Face = (typeof FACES)[number]

/** The seat a place holds in the pool, and therefore its face. Key order is the payload's, which
 *  is the pool's, so the same place keeps the same colour between the round screen and the reveal.
 *  Returns `null` for a place not in the pool rather than defaulting to seat 0 — a wrong colour is
 *  a wrong identity claim, and silence is better than a confident one. */
export function faceOf(places: Places, placeId: number | null): Face | null {
  if (placeId === null) return null
  const seat = Object.keys(places).indexOf(String(placeId))
  return seat < 0 ? null : FACES[seat % FACES.length]
}

export type Device = { token: string; circle: string }

export function device(): Device | null {
  const token = localStorage.getItem('upto_token')
  const circle = localStorage.getItem('upto_circle')
  return token && circle ? { token, circle } : null
}

/**
 * Roll, or re-read a round already rolled.
 *
 * **D69: rolling a closed round answers 200 with the stored result**, so this one call is both
 * "roll it" and "show me what it landed on" — the retry gets what it lost. That is why the reveal
 * needs no second endpoint to read a result, and why a reload after the roll is not a special case.
 */
export async function fetchReveal(d: Device, roundId: number): Promise<MemberReveal> {
  const r = await fetch(`/api/rounds/${roundId}/roll`, {
    method: 'POST',
    headers: { authorization: `Bearer ${d.token}` },
    cache: 'no-store',
  })
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error(body.detail || `讀取失敗（${r.status}）`)
  }
  return r.json()
}

/**
 * D106 — sign the trip. **No body**: who signed comes from the credential, and where they went is
 * the round's own stored winner. There is nothing for a client to assert and therefore nothing for
 * it to get wrong.
 *
 * Three outcomes and none of them is an error the screen should shout about: **201** this member
 * signed, **200** the same member tapped twice (D69's idiom — a retry is not a conflict), **409**
 * somebody else already signed, and the body carries who and when. The 409 is the one that changes
 * the screen, and it changes it to *the same thing a success would have*: the trip, named.
 */
export async function signTrip(
  d: Device,
  roundId: number,
): Promise<{ trip: Trip; alreadySigned: boolean }> {
  const r = await fetch(`/api/rounds/${roundId}/trip`, {
    method: 'POST',
    headers: { authorization: `Bearer ${d.token}` },
  })
  const body = await r.json().catch(() => ({}))
  if (r.status === 201 || r.status === 200) {
    return { trip: { nickname: body.nickname, signed_at: body.signed_at }, alreadySigned: false }
  }
  if (r.status === 409) {
    return {
      trip: { nickname: body.nickname ?? body.detail?.nickname, signed_at: body.signed_at ?? body.detail?.signed_at },
      alreadySigned: true,
    }
  }
  throw new Error(body.detail || `簽不上（${r.status}）`)
}
