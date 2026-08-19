/**
 * A1 / item 4's two endpoints, as the API actually answers them (`upto/preferences.py`).
 *
 * **The client never resolves "in force".** The `GET` returns the latest row per key already
 * resolved server-side, and D25 and D5 both refuse the alternative: a browser applying
 * latest-wins would put the convention in the one place that cannot be tested from the database.
 * So there is no reducer here and no history — what arrives is what is true.
 *
 * **Nothing is edited and nothing is deleted.** Every write appends: a different band, an `allow`
 * that un-avoids, a re-post of the same value carrying `persist: true`. There is no DELETE in this
 * file because there is none in the product (§3 D).
 */

/** The two bands. Not a number — a typed budget would need a currency, a period and a model. */
export const BANDS = ['tight', 'easy'] as const
export type Band = (typeof BANDS)[number]

/** The label a person reads. `tight`/`easy` are the wire's words and appear on no screen. */
export const BAND_LABEL: Record<Band, string> = { tight: '省一點', easy: '鬆一點' }

/** D38's ten, in the order the API's closed list carries them. Mirrored, not fetched: the list is
 *  closed and versioned by a migration, and a screen that discovered its own controls at runtime
 *  would render an empty settings page on a failed request. The integration test asserts the two
 *  agree; a value outside the list is refused by the database whatever this file believes. */
export const CATEGORIES = [
  '麵食', '飯食', '小吃', '火鍋', '燒烤', '日式', '西式', '早餐', '咖啡飲料', '其他',
] as const

/** 衛福部's eleven food-label groups, mirrored from revision 0023's CHECK for the same reason.
 *
 *  **The word for why a person avoids one of these appears nowhere in this file, on this screen,
 *  or in any string it renders.** What is recorded is a dietary choice. The moment the copy names
 *  a medical reason, the row stops being a preference and becomes health information about an
 *  identified person, which this product does not hold. That is a PDPA boundary and it is kept by
 *  the wording — there is no flag to set. */
export const INGREDIENTS = [
  '甲殼類', '芒果', '花生', '牛奶／羊奶', '蛋', '堅果類',
  '芝麻', '含麩質之穀物', '大豆', '魚類', '亞硫酸鹽類',
] as const

export type Kind = 'budget' | 'avoid_category' | 'avoid_ingredient'
export type Stance = 'avoid' | 'allow'

export type Avoidance = { value: string; persist: boolean; valid_from: string }

export type Coverage = {
  reference_rows: number
  share: number
  with_category?: number
  with_ingredient?: number
}

export type Preferences = {
  breadth: {
    /** **`zeroed`, not `removed`, and the rename is a correction rather than a preference.** An
     *  avoidance sets a place's weight to ZERO (D103/D45); it never takes the place out of
     *  anything. The place stays proposable, can still be proposed and still appears in the pool —
     *  it simply holds no cells on the dice table, so no roll can land on it. The old name was the
     *  only thing in the system saying otherwise, and it was enough to put a wrong mechanism into a
     *  spec another session wrote from reading the payload. */
    zeroed: number
    proposable: number
    share: number
    /** Stated by the API, never composed here. A share whose denominator the screen invents is
     *  the warning the evaluator refuses at the gate. */
    denominator: string
    /** **`null` today, and that is a ruling rather than a gap.** D22 says "when that crosses the
     *  line" and names no number, so the payload will not invent one — and neither may this
     *  screen. While it is null nothing may render as *crossed*. */
    threshold: number | null
  }
  category_coverage: Coverage
  ingredient_coverage: Coverage
  budget: {
    value: Band
    persist: boolean
    expires_on: string
    valid_from: string
    /** Still returned, deliberately. Expiry stops the band *contributing*; the flag exists so the
     *  screen can show D25's re-affirmation prompt rather than present a stale band as current. */
    expired: boolean
  } | null
  avoid_categories: Avoidance[]
  avoid_ingredients: Avoidance[]
}

/** The device's own credential, D74's operator-issued secret pasted on the device screen. Both
 *  halves or neither — a token with no circle addresses no endpoint. */
export type Device = { token: string; circle: string }

export function device(): Device | null {
  const token = localStorage.getItem('upto_token')
  const circle = localStorage.getItem('upto_circle')
  return token && circle ? { token, circle } : null
}

function auth(d: Device): HeadersInit {
  return { authorization: `Bearer ${d.token}` }
}

/**
 * **The API's `detail` is written for whoever is holding a terminal, and 401's is written in
 * English.** Driven on 2026-08-19 against a circle this credential does not hold: the preferences
 * screen rendered 「the token does not resolve to a member of this circle」 — a developer's sentence,
 * in the wrong language, on a screen whose whole promise is 「只有你看得到」.
 *
 * The same rule `round.ts` already follows, and it is a rule rather than a habit: **401 and 404 are
 * about the credential and are answered in the surface's own words; every other status keeps the
 * API's sentence**, because those are written for a person already and second-guessing them is how
 * a screen comes to state something the server did not.
 */
async function said(r: Response, fallback: string): Promise<Error> {
  if (r.status === 401) return new Error('這把鑰匙開不了這個圈子。回到裝置畫面重新貼一次。')
  if (r.status === 404) return new Error('找不到這個圈子。')
  const body = await r.json().catch(() => ({}))
  return new Error((body as { detail?: string }).detail || `${fallback}（${r.status}）`)
}

export async function fetchPreferences(d: Device): Promise<Preferences> {
  const r = await fetch(`/api/circles/${encodeURIComponent(d.circle)}/preferences`, {
    headers: auth(d),
    // `no-store` is not politeness. G3 drives a NEW browser context and asserts the value came
    // from the GET; a cached read would pass that gate while proving nothing about the server.
    cache: 'no-store',
  })
  if (!r.ok) throw await said(r, '讀取失敗')
  return r.json()
}

/**
 * Append one preference row. **204 and an empty body — there is nothing to parse and nothing to
 * echo**, and the caller re-reads rather than patching local state: the server owns "in force".
 *
 * `persist` is passed explicitly on every call. The endpoint defaults it to `false` (D17), and a
 * caller that relies on the default is one refactor away from sending `undefined` where it meant
 * `false` — same value, no record of a choice having been made.
 */
export async function postPreference(
  d: Device,
  body: { kind: Kind; value: string; persist: boolean; stance?: Stance },
): Promise<void> {
  const r = await fetch(`/api/circles/${encodeURIComponent(d.circle)}/preferences`, {
    method: 'POST',
    headers: { ...auth(d), 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (r.status === 204) return
  throw await said(r, '寫入失敗')
}

/** `YYYY-MM` in Taipei, which is the boundary the database computed `expires_on` against. Reading
 *  the browser's own month would put two clocks on one question. */
export function taipeiMonth(now = new Date()): string {
  const taipei = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000)
  return `${taipei.getFullYear()}-${String(taipei.getMonth() + 1).padStart(2, '0')}`
}

/** A whole-number percentage for a share the API already rounded. Rendered from the payload on
 *  every screen that states one — never written into the markup, because today's figure becomes
 *  false the moment a backfill runs and says nothing when it does. */
export function pct(share: number): string {
  return `${(share * 100).toFixed(1)}%`
}
