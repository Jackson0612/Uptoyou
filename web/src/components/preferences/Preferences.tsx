import { useCallback, useEffect, useState } from 'react'
import {
  BANDS, BAND_LABEL, CATEGORIES, INGREDIENTS,
  device, fetchPreferences, postPreference, pct, taipeiMonth,
  type Band, type Device, type Kind, type Preferences as InForce,
} from '@/lib/preferences'

/**
 * A2 — the private preference screen. Built to `idea & img/evaluator/spec-preference-screen.md`
 * §3 A · B · B-bis · C · D · F and §4's coverage sentences.
 *
 * **What is deliberately absent, and none of it is unfinished work:**
 *
 * - **No pinned `BAR`, no back control, no screen name in a masthead.** That is the frame, and the
 *   frame is `[OPEN-2]` — with `nav.tabs` gone at `42fb6c8` the React build has no navigation at
 *   all, so where this screen is reached from is the owner's ruling, not a default to be filled in
 *   here. Adding a bar now would also spend the screen's one filled control (§4's grammar) on a
 *   control nobody has ruled the destination of.
 * - **No delete, no clear, no reset** (§3 D). Un-avoiding appends `allow`; erasure is D14's
 *   separate machinery and does not appear on a screen.
 * - **No text input in any state** (D38). Every control here is a closed list.
 * - **No link from the home screen.** Home is under A0c's fidelity gate — a pixel diff against the
 *   owner-approved page — so a nav affordance added there would fail that gate before the frame
 *   has been ruled. The route exists; nothing points at it yet.
 *
 * **The one filled control is the chosen budget band.** Everything else on this screen marks state
 * with a square marker and a rule, never with an ink ground.
 */

/** The three states a row's single control can be in. **The control's meaning is the state**, which
 *  is why there is exactly one control per row rather than a toggle plus a confirm: a second
 *  control on the row would be a second way to act on one fact, and §3 D refuses that shape for
 *  the budget for the same reason. */
type RowState = 'off' | 'on' | 'asking'

/** Which avoided ingredients this device has affirmed, and in which Taipei month.
 *
 * **This is device state on purpose and it is not a cache of the server.** The carry rule for an
 * ingredient is the strictest of the three: *never carried in silently — on a new month or a new
 * device it is shown filled and asks for the tap, every time.* A new browser context has no entry,
 * so it asks; a new month does not match, so it asks. The server holds the avoidance; this holds
 * only whether this device has been shown it this month.
 *
 * **It is not the contribute-gate and must not be read as one.** Whether an unaffirmed ingredient
 * reaches the engine is a server question, and today it reaches nothing at all because no place
 * carries ingredient data — which is exactly why the gate splits the render half from the
 * contribute half and records the second `n/a` rather than passing it.
 */
const ACK_KEY = 'upto_pref_ingredient_ack'

function readAck(): Record<string, string> {
  try {
    const raw = localStorage.getItem(ACK_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' ? (parsed as Record<string, string>) : {}
  } catch {
    // A corrupt or unreadable entry means "this device has not affirmed anything", which is the
    // safe direction: it asks again. Throwing here would take the screen down over a stored string.
    return {}
  }
}

function writeAck(value: string, month: string): void {
  const next = { ...readAck(), [value]: month }
  try {
    localStorage.setItem(ACK_KEY, JSON.stringify(next))
  } catch {
    // Storage full or blocked: the row simply asks again next time. Nothing is lost server-side.
  }
}

export default function Preferences() {
  const [dev] = useState<Device | null>(device)
  const [inForce, setInForce] = useState<InForce | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const month = taipeiMonth()

  const load = useCallback(async (d: Device) => {
    try {
      setInForce(await fetchPreferences(d))
      setError('')
    } catch (e) {
      setInForce(null)
      setError((e as Error).message || '讀取失敗')
    }
  }, [])

  useEffect(() => { if (dev) void load(dev) }, [dev, load])

  /**
   * Every act is the same act: append a row, then re-read what is in force.
   *
   * **The re-read is not laziness about local state — it is the D25 rule the client is not allowed
   * to reimplement.** "In force" is the latest row per key, resolved server-side; patching the
   * local object after a write would be this browser applying latest-wins, which is the one thing
   * the endpoint exists to keep out of the client. It also means `breadth` and the coverage figures
   * re-derive against the new set rather than drifting from it.
   */
  const write = useCallback(
    async (key: string, body: { kind: Kind; value: string; persist: boolean; stance?: 'avoid' | 'allow' }) => {
      if (!dev || busy) return
      setBusy(key)
      try {
        await postPreference(dev, body)
        await load(dev)
      } catch (e) {
        setError((e as Error).message || '寫入失敗')
      } finally {
        setBusy('')
      }
    },
    [dev, busy, load],
  )

  if (!dev) {
    return (
      <main className="prefs" data-screen="preferences">
        <h1 className="prefsTitle">我的偏好</h1>
        <p className="prefsNote" data-part="pref-nodevice">
          這台裝置還沒有鑰匙，所以沒有可以填的偏好。
        </p>
      </main>
    )
  }

  const budget = inForce?.budget ?? null
  const avoidedCategories = new Set((inForce?.avoid_categories ?? []).map((a) => a.value))
  const keptCategories = new Set(
    (inForce?.avoid_categories ?? []).filter((a) => a.persist).map((a) => a.value),
  )
  const ack = readAck()
  const ingredientState = new Map<string, RowState>(
    (inForce?.avoid_ingredients ?? []).map((a) => [
      a.value,
      ack[a.value] === month ? 'on' : 'asking',
    ]),
  )
  const keptIngredients = new Set(
    (inForce?.avoid_ingredients ?? []).filter((a) => a.persist).map((a) => a.value),
  )

  return (
    <main className="prefs" data-screen="preferences">
      {/* Provisional heading — the screen's NAME is part of `[OPEN-2]`'s frame. A page with no
          h1 is worse than one whose wording may change, so it carries the plainest description
          of what is on it and no branding. */}
      <h1 className="prefsTitle">我的偏好</h1>
      <p className="prefsNote">只有你看得到，也只有這台裝置寫得動。</p>

      {error && <p className="prefsErr" data-part="pref-error">{error}</p>}

      {/* ── A · Budget ────────────────────────────────────────────────────────────
          Three states, and G9 requires all three to be distinguishable without reading the text
          twice: UNSET is two plain ghosts; IN FORCE fills the chosen one with ink; EXPIRED drops
          the ground and dashes the border — the same vocabulary design.md gives a control that is
          present but not acting, so nothing new is invented for it.
          **The expired state carries exactly one control, and it is the chooser itself.** Tapping
          your own band again IS the re-affirmation. There is no dismiss, no clear and no second
          button, because either of those would be an edit of a table that only appends. */}
      <section className="prefsBlock" data-part="pref-budget">
        <h2 className="prefsH">這個月的預算</h2>
        <div className="bandRow">
          {BANDS.map((b: Band) => {
            const chosen = budget?.value === b
            const expired = chosen && budget.expired
            return (
              <button
                key={b}
                type="button"
                className="band"
                data-chosen={chosen ? 'yes' : 'no'}
                data-expired={expired ? 'yes' : 'no'}
                aria-pressed={chosen}
                disabled={busy !== ''}
                onClick={() => void write(`budget:${b}`, {
                  kind: 'budget', value: b, persist: budget?.persist ?? false,
                })}
              >
                {BAND_LABEL[b]}
              </button>
            )
          })}
        </div>

        {budget?.expired && (
          <p className="prefsNote" data-part="pref-budget-expired">
            這是 {budget.valid_from.slice(0, 7)} 的選擇，已經過期，這個月還沒有算進去。點一下同一個選項就沿用。
          </p>
        )}

        {/* C · the keep choice, per preference. It appears once there is a preference to keep, and
            renders NOT KEPT until an explicit act — D17's default is expressed by the payload, not
            by this markup. Keeping re-posts the same band with `persist: true`, which appends a new
            row; there is no field to edit. */}
        {budget && (
          <button
            type="button"
            className="keep"
            data-part="pref-budget-keep"
            data-kept={budget.persist ? 'yes' : 'no'}
            aria-pressed={budget.persist}
            disabled={busy !== ''}
            onClick={() => void write('budget:keep', {
              kind: 'budget', value: budget.value, persist: !budget.persist,
            })}
          >
            <span className="mark" aria-hidden="true" />
            下個月也留著這個選擇
          </button>
        )}
      </section>

      {/* ── B · Categories ─────────────────────────────────────────────────────── */}
      <section className="prefsBlock" data-part="pref-categories">
        <h2 className="prefsH">不想吃的類型</h2>
        <ul className="rows">
          {CATEGORIES.map((c) => {
            const on = avoidedCategories.has(c)
            return (
              <li key={c} className="row" data-part="pref-category" data-on={on ? 'yes' : 'no'}>
                <button
                  type="button"
                  className="rowTap"
                  aria-pressed={on}
                  disabled={busy !== ''}
                  onClick={() => void write(`cat:${c}`, {
                    kind: 'avoid_category', value: c,
                    stance: on ? 'allow' : 'avoid',
                    persist: keptCategories.has(c),
                  })}
                >
                  <span className="mark" aria-hidden="true" />
                  <span className="rowName">{c}</span>
                  {on && <span className="rowState">避開</span>}
                </button>
                {on && (
                  <button
                    type="button"
                    className="keep keepInline"
                    data-kept={keptCategories.has(c) ? 'yes' : 'no'}
                    aria-pressed={keptCategories.has(c)}
                    aria-label={`下個月也留著避開${c}`}
                    disabled={busy !== ''}
                    onClick={() => void write(`cat:keep:${c}`, {
                      kind: 'avoid_category', value: c, stance: 'avoid',
                      persist: !keptCategories.has(c),
                    })}
                  >
                    <span className="mark" aria-hidden="true" />
                    留著
                  </button>
                )}
              </li>
            )
          })}
        </ul>

        {/* §4's honesty requirement. The number is the payload's and is never written here — today's
            figure moved from about 6% to nearly 13% in one day, and a constant would have been
            false by the afternoon while still rendering. It STATES what the data covers; it does
            not tell anyone to wait, to choose differently, or that a choice is pointless (D20). */}
        {inForce && (
          <p className="prefsNote" data-part="pref-category-coverage">
            全市 {inForce.category_coverage.reference_rows.toLocaleString('en-US')} 家登記店家裡，
            目前有 {(inForce.category_coverage.with_category ?? 0).toLocaleString('en-US')} 家帶有分類
            （{pct(inForce.category_coverage.share)}）。沒有分類的店，避開讀不到。
          </p>
        )}

        {/* D22's breadth. **Stated, never called "crossed"** — the payload's `threshold` is null
            because D22 names no line, and a screen that invented one would be warning against a
            number nobody ruled. So while the threshold is null this renders as a plain statement of
            the share WITH the denominator the API named, and no warning renders at all.
            The denominator is NAMED in the sentence, not left to the reader: 「這個圈子提得出來
            的」 is the API's own `denominator` field said in the screen's language — the same set,
            not a second definition. Rendering the payload's English string here would put an
            untranslated sentence on a Chinese screen; restating it as a different set would be
            the unstated denominator the gate refuses. */}
        {inForce && inForce.breadth.removed > 0 && (
          <p className="prefsNote" data-part="pref-breadth">
            這些選擇目前排掉 {inForce.breadth.removed.toLocaleString('en-US')} 家，
            範圍是這個圈子提得出來的 {inForce.breadth.proposable.toLocaleString('en-US')} 家
            （{pct(inForce.breadth.share)}）。
          </p>
        )}
      </section>

      {/* ── B-bis · Ingredients ─────────────────────────────────────────────────
          The same closed-list control, labelled 「不吃 …」. **The copy on this block, in every
          state including this comment's neighbours, names no medical reason of any kind.** What is
          recorded is a dietary choice; the wording is what keeps that true, and it is a PDPA
          boundary rather than a matter of tone. */}
      <section className="prefsBlock" data-part="pref-ingredients">
        <h2 className="prefsH">不吃的食材</h2>
        <ul className="rows">
          {INGREDIENTS.map((g) => {
            const state: RowState = ingredientState.get(g) ?? 'off'
            const next = state === 'off' ? 'avoid' : state === 'asking' ? 'avoid' : 'allow'
            return (
              <li key={g} className="row" data-part="pref-ingredient" data-on={state}>
                <button
                  type="button"
                  className="rowTap"
                  aria-pressed={state !== 'off'}
                  disabled={busy !== ''}
                  onClick={() => {
                    // An `asking` row affirms rather than toggles: the carry rule asks for the tap
                    // every new month and on every new device, and a tap that flipped it off
                    // instead would make the asking state a trap.
                    //
                    // **The ack is written whenever the tap results in `avoid` — including the
                    // first time.** Recording it only on the affirming tap left a just-set
                    // exclusion rendering 「點一下沿用」 the instant it was set, which asks a
                    // person to re-affirm a choice they are still looking at. The carry rule is
                    // about arriving on a NEW device or in a NEW month, not about the tap that
                    // created the row.
                    if (next === 'avoid') writeAck(g, month)
                    void write(`ing:${g}`, {
                      kind: 'avoid_ingredient', value: g,
                      stance: next, persist: keptIngredients.has(g),
                    })
                  }}
                >
                  <span className="mark" aria-hidden="true" />
                  <span className="rowName">不吃 {g}</span>
                  {state === 'on' && <span className="rowState">避開</span>}
                  {state === 'asking' && <span className="rowState asking">點一下沿用</span>}
                </button>
                {state !== 'off' && (
                  <button
                    type="button"
                    className="keep keepInline"
                    data-kept={keptIngredients.has(g) ? 'yes' : 'no'}
                    aria-pressed={keptIngredients.has(g)}
                    aria-label={`下個月也留著不吃${g}`}
                    disabled={busy !== ''}
                    onClick={() => void write(`ing:keep:${g}`, {
                      kind: 'avoid_ingredient', value: g, stance: 'avoid',
                      persist: !keptIngredients.has(g),
                    })}
                  >
                    <span className="mark" aria-hidden="true" />
                    留著
                  </button>
                )}
              </li>
            )
          })}
        </ul>

        {/* §4's harder case, and the sentence carries the defence rather than hiding it: on day one
            nothing acts on these at all. The figure comes from the payload for the same reason the
            category one does — the day a source arrives, a zero in the markup keeps reading zero. */}
        {inForce && (inForce.ingredient_coverage.with_ingredient ?? 0) === 0 && (
          <p className="prefsNote" data-part="pref-ingredient-coverage">
            目前沒有任何店家帶有食材資料，所以這裡的選擇還不會影響任何一輪。
            先記下來，是為了資料到位的那天不用再問一次。
          </p>
        )}
      </section>
    </main>
  )
}
