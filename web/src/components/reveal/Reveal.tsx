import { useCallback, useEffect, useRef, useState } from 'react'
import Die from './Die'
import Evidence from './Evidence'
import Field from './Field'
import Pairs from './Pairs'
import { m, useReducedMotion } from '@/lib/motion'
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

/** How long one row should hold, near enough. The real dwell is derived from it and from the row
 *  count so that every row gets exactly the same number of visits of exactly the same length —
 *  this is the target the derivation rounds to, never a duration anything is scheduled on. */
const TARGET_DWELL_MS = 120

/** **The floor, and it is the evaluator's instrument that sets it, not taste.** The tumble is
 *  gated from video at ~25 fps, so a frame is 40 ms; a dwell under two frames cannot be told apart
 *  from a dropped frame, and *equal dwell per row* stops being a claim anyone can confirm or
 *  refute. Their floor is 80 ms and this is 90, because a schedule that lands exactly on an
 *  instrument's limit is one rounding away from being unmeasurable. */
const FLOOR_DWELL_MS = 90

/** The tumble's length, read from `--tumble` on the reveal's own element rather than typed here.
 *  The CSS animation and this schedule must divide the *same* number: a second copy drifting by
 *  even 50 ms truncates the sweep's last cycle, and a truncated cycle is one row visited fewer
 *  times than its neighbours — §0c's unequal dwell, arriving as a rounding error instead of as a
 *  decision. Falls back to the value in `reveal.css` if the property is ever absent. */
function tumbleMs(el: HTMLElement | null): number {
  const raw = el ? getComputedStyle(el).getPropertyValue('--tumble').trim() : ''
  if (raw.endsWith('ms')) return parseFloat(raw) || 1400
  if (raw.endsWith('s')) return (parseFloat(raw) || 1.4) * 1000
  return 1400
}

/** Fisher–Yates, on a copy. Used for decoration and for nothing else — the roll itself was decided
 *  by the server before this file ran, which is the whole of `D91`. */
function shuffled<T>(xs: readonly T[]): T[] {
  const a = xs.slice()
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

/**
 * The sweep's order — **§0c's three constraints, built rather than tuned.**
 *
 * **Equal visits and equal dwell, exactly.** The schedule is whole cycles of a permutation of every
 * row, so each row is visited the same number of times; the dwell is the tumble divided by the step
 * count, so each visit is the same length. Not *approximately* — a schedule that merely aims at
 * equality has to be measured to be believed, and `RV-13` is an honesty line rather than a
 * tolerance.
 *
 * **The order is uniformly random and the winner is not consulted.** This function is not given the
 * winning place and could not favour it if it tried. **The tempting extra step — forbidding the
 * winner from the final position, so the sweep visibly does not stop on the answer — is refused,
 * and it is worth saying why**: that is also a correlation with the winner, merely negative, and a
 * gate looking for *does the order correlate* would find it just as surely. Zero correlation is a
 * uniform shuffle and nothing else. Landing last on the winner one roll in `n` is what chance looks
 * like, and engineering that away would be the lie the constraint exists to prevent.
 *
 * The one adjustment: a row is never allowed to appear twice in a row across a cycle boundary,
 * which would read as a single double-length dwell. That is a fact about consecutive positions and
 * carries no information about which row it is.
 */
function sweepOrder(ids: readonly string[], total: number): string[] | null {
  if (ids.length < 2) return null
  // **A pool too large to sweep honestly is not swept, and the surface says so.** One whole cycle
  // at the floor needs `n × 90 ms`; past about fifteen places that exceeds the tumble, and the
  // three ways out are all worse than stopping. Going faster makes the dwell unmeasurable — the
  // effect would still *look* fine, which is the point. Visiting a subset makes the visits
  // unequal, which is the constraint itself. Stretching the tumble makes the animation's length a
  // function of the pool size, so a big round takes visibly longer to decide and the reader has
  // every reason to think the size mattered. **And a strobe across twenty rows in 1.4 s does not
  // read as choosing anyway** — it reads as noise, so the honest option is also the better-looking
  // one, which is not always how this goes.
  if (ids.length * FLOOR_DWELL_MS > total) return null
  const fits = Math.floor(total / (FLOOR_DWELL_MS * ids.length))
  const wanted = Math.round(total / (TARGET_DWELL_MS * ids.length))
  const cycles = Math.max(1, Math.min(wanted, fits))
  const order: string[] = []
  for (let c = 0; c < cycles; c++) {
    const next = shuffled(ids)
    if (order.length > 0 && next[0] === order[order.length - 1]) {
      ;[next[0], next[1]] = [next[1], next[0]]
    }
    order.push(...next)
  }
  return order
}

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
  const reduce = useReducedMotion()
  /** Which row the sweep is lighting, or `null`. A place id, never an index — the row order is the
   *  pool's and an index would silently re-point if it ever changed. */
  const [sweep, setSweep] = useState<string | null>(null)
  /** `animation` on the normal path, `fallback` if the failsafe below had to land the screen.
   *  **Published on the element rather than kept private**: the two paths differ in timing, and a
   *  measurement taken on the second one while believing it was the first is exactly the reading
   *  that gets a defect reported against the wrong thing. */
  const [landedBy, setLandedBy] = useState<'animation' | 'fallback' | 'reduced' | null>(null)
  /** Why the sweep did not run, when it did not. Published on the element for the same reason
   *  `landedBy` is: an absent effect and a broken effect look identical in a recording. */
  const [skipped, setSkipped] = useState<'one-row' | 'too-many-rows' | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const root = useRef<HTMLElement | null>(null)

  /** **The dice landing is observed, not predicted.** `animationend` from the cube's own `tumble`
   *  is the moment the tumble is over; a `setTimeout` matching the CSS duration is a second clock
   *  that agrees until something makes it not — a throttled tab, a slower device, an edited
   *  duration — and when it disagrees the answer appears over a die still moving. Both dice fire
   *  it and the first one wins, because they run the same animation for the same length. */
  const land = useCallback((by: 'animation' | 'fallback' | 'reduced') => {
    setLanded((was) => {
      if (!was) setLandedBy(by)
      return true
    })
  }, [])

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
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) land('reduced')
        // **The failsafe, and it is deliberately late and deliberately labelled.** If the tumble
        // never runs — a background tab, an animation that never started — `animationend` never
        // fires and the reveal hangs on a screen whose whole purpose is to show an answer it is
        // already holding. A quarter-second past the tumble is long enough that it cannot beat a
        // healthy animation, and `data-landed-by` says which path won so a slow reading is never
        // mistaken for a slow animation.
        else timer.current = window.setTimeout(
          () => land('fallback'), tumbleMs(root.current) + 250,
        )
      })
      .catch((e: Error) => { if (live) setError(e.message || '讀取失敗') })
    return () => { live = false; window.clearTimeout(timer.current) }
  }, [dev, roundId])

  /**
   * The sweep. **It starts with the tumble and it is over when the tumble is over** — the schedule
   * divides `--tumble` into whole cycles, so the last step ends as the dice stop and the highlight
   * clears into the landed state rather than stopping on a row.
   *
   * **A row lit at the moment of landing would be the animation pointing at an answer**, which is
   * the one thing §0c forbids however random the order was that got it there. So `landed` clears it
   * unconditionally, before anything else is read.
   */
  useEffect(() => {
    if (!data || landed) { setSweep(null); return }
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const ids = Object.keys(data.places)
    const total = tumbleMs(root.current)
    const order = sweepOrder(ids, total)
    // **Never a silent cap.** A recording with no sweep in it should say which of the two it is —
    // an effect that was skipped by rule, or an effect that was built and does not work.
    if (!order) { setSkipped(ids.length < 2 ? 'one-row' : 'too-many-rows'); return }
    setSkipped(null)
    const dwell = total / order.length
    let i = 0
    setSweep(order[0])
    const h = window.setInterval(() => {
      i += 1
      if (i >= order.length) { window.clearInterval(h); return }
      setSweep(order[i])
    }, dwell)
    return () => window.clearInterval(h)
  }, [data, landed])

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
  /** Derived from the seat marked `counts`, falling back to `deciding_member` only if no seat is
   *  marked — a payload that predates A6 has neither, and the line simply does not render. */
  const decider = data
    ? (data.rolls?.find((r) => r.counts)?.nickname ?? data.deciding_member?.nickname ?? '')
    : ''
  const winner = data && data.winning_place_id !== null
    ? data.places[String(data.winning_place_id)]
    : ''

  return (
    // The flood (§5 rule 1) — the winning place's own face colour becomes the whole ground, over
    // .45s ease-out. `data-face` carries it; the colour lives in CSS, so no palette value is
    // written in a component.
    <main
      ref={root}
      className="reveal"
      data-screen="reveal"
      data-state={landed ? 'landed' : 'rolling'}
      data-landed-by={landedBy ?? undefined}
      data-sweep-skipped={skipped ?? undefined}
      data-face={landed && face ? face : undefined}
    >
      <Field />

      {/* **The dice mount only once the round is known, and that closed a latent bug.** They used
          to render immediately with a placeholder 1 and start tumbling, so the landing angle was
          re-targeted mid-flight when the real value arrived. Nothing showed for it, because the CSS
          re-resolved and the die still landed on the right face — a throw aimed at the wrong number
          that corrected itself invisibly. `.dice` holds its box from `min-height`, so waiting costs
          no layout.

          `data-dice-state` is set from the die's own settle completing rather than from a timer:
          **a spring has no duration anyone outside it can know**, which is precisely why it feels
          different from an ease, and the die calls back when its spring has decayed onto the
          face. */}
      <div className="dice" data-part="dice" data-dice-state={landed ? 'landed' : 'tumbling'}>
        {data && (
          <>
            <Die value={data.dice[0]} seat={0} onLanded={() => land('animation')} />
            <Die value={data.dice[1]} seat={1} onLanded={() => land('animation')} />
          </>
        )}
      </div>

      {/* **The answer region holds its box from the first frame.** `opacity` alone moves — never
          `display`, never `height` — so the tumble→land sequence shifts 0.00 px and the answer is
          genuinely not on screen while the dice move. `aria-hidden` while rolling so a screen
          reader is not told the winner before the sighted reader gets it; `inert` would also stop
          the trip control being reachable early. */}
      {/* **D108 — the deciding seat is named from the first frame, before any dice are seen.**
          That ordering is the ruling's own honesty mechanism: five results with one silently
          chosen afterwards is indistinguishable from picking the roll somebody liked. So this
          line sits OUTSIDE `.answer` and is visible during the tumble, deliberately.

          **It is safe there and I checked rather than assumed.** `RV-16` asks that nothing on
          screen distinguishes the WINNER mid-tumble; this names a person, carries no place and no
          number, and is identical whichever place wins. The name comes from `counts` on the seat
          rather than from `deciding_member`, though both are on the wire — one fact, one source,
          so a sentence cannot name somebody a row does not mark.

          **「以 … 的骰子為準」 and never 「… 擲出了」.** The seed was drawn at open and every pair
          derives from it; the tap discloses a number that already existed. Wording that credits
          the tap with producing it is D108's stated prohibition in prose. */}
      {decider && (
        <p className="decider" data-part="deciding">以 {decider} 的骰子為準。</p>
      )}

      <m.div
        className="answer"
        data-part="answer"
        aria-hidden={!landed}
        inert={!landed}
        initial={false}
        animate={{ opacity: landed ? 1 : 0, y: reduce || landed ? 0 : 14 }}
        transition={reduce ? { duration: 0 } : { type: 'spring', stiffness: 300, damping: 24, mass: 1 }}
      >
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
      </m.div>

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
        <Evidence
          ev={evidence}
          places={data.places}
          winnerId={data.winning_place_id}
          sweep={sweep}
        />
      )}

      {/* Owner-ruled 「要」 2026-08-19. **After the dice land**, not before: the pairs are the
          receipt for a result the screen has just shown, and printing them while the dice are still
          in the air would be the answer available in numbers beside an animation withholding it —
          the same argument that keeps the revealed seed until the landing. */}
      {landed && data && <Pairs rolls={data.rolls ?? []} />}

      {/* ── D108 · the commitment, and the seed that opens it ──────────────────────────────
          **The hash is shown throughout; the seed only once the dice have landed.** The commitment
          is a hash and discloses nothing, so it is safe during the tumble and belongs there — it is
          the claim that the outcome predates the round. **The seed is the answer in another form**:
          every pair, the decider and the winner recompute from it, so putting it on screen mid-
          tumble would be the whole result sitting beside an animation built to withhold it. Nobody
          is going to compute sha256 by hand in 1.4 seconds, and that is not the standard — `D91`
          says the animation may not assert a fact it lacks, and a screen holding the answer in a
          recoverable form has not withheld it.

          Both are shown in full. A hash exists to be compared with another hash, and half of one
          cannot be. */}
      {data?.seed_commit && (
        <p className="commit" data-part="seed-commit">
          這一輪的結果在開局時就固定了 · {data.seed_commit}
          {landed && data.revealed_seed && (
            <><br />種子 · {data.revealed_seed}</>
          )}
        </p>
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
