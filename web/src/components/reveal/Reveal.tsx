import { useCallback, useEffect, useRef, useState } from 'react'
import Die from './Die'
import Evidence from './Evidence'
import {
  device, evidenceIn, faceOf, fetchRaw, signTrip,
  type Device, type Evidence as EvidenceData, type MemberReveal, type Trip,
} from '@/lib/reveal'

/**
 * A3 — the reveal, **member state**, built to `spec-reveal-two-states.md` §1–§4 and `design.md` §4b.
 *
 * **This component cannot render the accounting, and that is structural rather than careful.** It is
 * typed on `MemberReveal`, whose fields are the API's own whitelist — `round_id · status · dice ·
 * sum · winning_place_id · places · trip`. There is no `weights`, no `allocation` and no `panel` in
 * the type, so there is nothing here to hide, gate or forget to gate. §8's order says member first
 * for exactly this reason: **build the operator state and subtract, and a field survives in the
 * member payload.** The operator state will be an addition in its own component.
 *
 * **What is deliberately absent from member state (§1a), each an assertion to test for rather than a
 * feature to omit:** no per-place share, count, percentage or fraction — in any element, attribute,
 * `title` or `aria-label`; no reason and no channel label; no count of contributors; **no operator
 * affordance of any kind — no disabled control, no mode hint, because a disabled door is a door**;
 * and no promise of a member-verifiable audit, including any paraphrase of the removed line
 * 「每一個數字都查得到出處。」
 *
 * **`D91` is honoured by construction:** the result is decided by the server before a frame animates,
 * the answer is genuinely absent from the screen mid-tumble via `opacity` while its box is held, and
 * nothing here changes a layout box at any point in the sequence.
 */

/** The tumble's length. The result is already known when it starts — this is a moment given to the
 *  reader, not a computation being waited on, and `D91` is the rule that keeps those two apart. */
const TUMBLE_MS = 1400

export default function Reveal({ roundId }: { roundId: number }) {
  const [dev] = useState<Device | null>(device)
  const [data, setData] = useState<MemberReveal | null>(null)
  const [landed, setLanded] = useState(false)
  const [error, setError] = useState('')
  const [trip, setTrip] = useState<Trip>(null)
  /** `null` for a member, and for a member it is null because **nothing arrived** — not because
   *  this component declined to read something that did. D105's whole point. */
  const [evidence, setEvidence] = useState<EvidenceData | null>(null)
  const [signing, setSigning] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (!dev) return
    let live = true
    fetchRaw(dev, roundId)
      .then((raw) => {
        if (!live) return
        const d = raw as MemberReveal
        setData(d)
        setTrip(d.trip)
        setEvidence(evidenceIn(raw))
        // Demo scaffolding: the switcher's 開獎 stop needs a round to point at and there is no
        // endpoint for "this circle's latest". Recording the one actually looked at is the
        // cheapest honest answer, and it disappears with the switcher.
        localStorage.setItem('upto_last_round', String(roundId))
        // **Reduced motion lands instantly and still lands** (§5 rule 3: the end states apply, the
        // transitions do not). Not "no animation and no reveal" — the person still gets the answer.
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) setLanded(true)
        else timer.current = window.setTimeout(() => setLanded(true), TUMBLE_MS)
      })
      .catch((e: Error) => { if (live) setError(e.message || '讀取失敗') })
    return () => { live = false; window.clearTimeout(timer.current) }
  }, [dev, roundId])

  const sign = useCallback(async () => {
    if (!dev || signing) return
    setSigning(true)
    try {
      setTrip(await signTrip(dev, roundId))
    } catch (e) {
      setError((e as Error).message || '簽不上')
    } finally {
      setSigning(false)
    }
  }, [dev, roundId, signing])

  if (!dev) {
    return (
      <main className="reveal" data-screen="reveal">
        <p className="revealNote">這台裝置還沒有鑰匙。</p>
      </main>
    )
  }
  if (error) {
    return (
      <main className="reveal" data-screen="reveal">
        <p className="revealErr" data-part="reveal-error">{error}</p>
      </main>
    )
  }

  const face = data ? faceOf(data.places, data.winning_place_id) : null
  const winner = data && data.winning_place_id !== null
    ? data.places[String(data.winning_place_id)]
    : ''

  return (
    // The flood (§5 rule 1) — the winning place's own face colour becomes the whole ground, over
    // .45s ease-out. `data-face` carries it; the colour lives in CSS, so no palette value is
    // written in a component.
    <main
      className="reveal"
      data-screen="reveal"
      data-state={landed ? 'landed' : 'rolling'}
      data-face={landed && face ? face : undefined}
    >
      <div className="dice" data-part="dice">
        <Die value={data?.dice[0] ?? 1} tumbling={!landed} />
        <Die value={data?.dice[1] ?? 1} tumbling={!landed} />
      </div>

      {/* **The answer region holds its box from the first frame.** `opacity` alone moves — never
          `display`, never `height` — so the tumble→land sequence shifts 0.00 px and the answer is
          genuinely not on screen while the dice move. `aria-hidden` while rolling so a screen
          reader is not told the winner before the sighted reader gets it; `inert` would also stop
          the trip control being reachable early. */}
      <div className="answer" data-part="answer" aria-hidden={!landed} inert={!landed}>
        {/* **`sum` is in the member payload and is deliberately NOT rendered.** It is an innocent
            number — the two dice added up — but §1's table does not list it in member state, and
            §1a refuses *any bare number the eye can pair with a place*. A digit sitting directly
            above a restaurant's name is that shape exactly, whatever it happens to mean, and
            `RV-2` is written to walk text and attributes looking for precisely it. The dice
            already say what they rolled, in pips, which is the form that cannot be mistaken for a
            share of anything. */}
        <h1 className="winner" data-part="winner">{winner}</h1>

        {/* **The sentence.** Everything the evidence table used to carry now rests on nine
            characters, so they are load-bearing typography and not a caption: `text-lead`, full
            `ink`, the body face's regular weight. It does not animate and it is present from the
            first painted frame of the landed state — a fact that arrives late reads as an apology.

            **It is inert until `[OPEN-1]` is ruled**: plain text, no handler, no link styling, no
            tooltip, no icon. Inert is the reversible option — a door added later changes nothing
            already built, whereas a door removed later leaves a dead region people have learned to
            press. It claims that the allocation happened and that weight drove it. It does not
            claim the reader can check that, and it must not be dressed to imply so. */}
        <p className="sentence" data-part="sentence">三十六格已按權重分配</p>
      </div>

      {/* **§0b, owner-amended: the member sees the LIST, never the numbers.** 「使用者畫面我認為可
          以套用開發者的這頁，只是需要移除36格的畫面，以及權重點數」 — the same panel as the
          operator's, minus the grid and minus the counts. D105 removed the whole thing because
          「麻辣火鍋 0/36」 in a circle of five is one guess; **the guessable object was always the
          number, never the name** — the places were proposed openly by the people in the room.

          One component renders both states, and that is the point rather than a convenience: §0
          says the operator state is the member state *plus* two things, so the two states cannot
          drift into two layouts. `evidence` is null for a member because nothing arrived, and every
          numeric column is gated on it — so a member's screen cannot show a count even if someone
          later adds one to the markup without thinking.

          **No proposer name on any row** (owner-ruled 2026-08-19, separately): the winning place
          would reveal whose pick won, and a repeat winner becomes a pattern about a person. The
          spec's §0b still calls that question open — it was ruled after that line was written. */}
      {data && (
        <Evidence ev={evidence} places={data.places} winnerId={data.winning_place_id} />
      )}

      {/* D106 — the trip is named, the proposal never is. Signing is the one place a member's
          identity is recorded and kept; the proposal's author was erased by D14's trigger when the
          round closed, so there is no name here to leak and none to suppress. */}
      <div className="bar" data-part="bar">
        {trip ? (
          <p className="signed" data-part="trip">{trip.nickname} 說這一餐去了</p>
        ) : (
          <button type="button" onClick={() => void sign()} disabled={!landed || signing}>
            我們去了
          </button>
        )}
      </div>
    </main>
  )
}
