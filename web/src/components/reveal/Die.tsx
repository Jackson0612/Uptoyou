import { useEffect } from 'react'
import { m, useAnimate, useReducedMotion } from '@/lib/motion'

/**
 * `DIE` — the cube from `design.md` §4. A real object with six faces, not a picture of a number.
 *
 * **One variable, `--die`, and the `translateZ` that closes the cube derives from it** (`calc(var(--die) / 2)`
 * in `reveal.css`). Change the value; never change the derivation — a hand-typed half is how a cube
 * develops a seam at one breakpoint and nobody sees it at the others.
 *
 * **The pips are round, and that is the system's single radius exemption** (§3). Squaring them makes
 * the face read as a grid rather than as a die.
 *
 * **Face 1 and face 4 carry red pips**, which is what a Taiwanese die looks like — `--color-pipred`,
 * its own token, deliberately not following the accent (`design.md` §1: reusing the accent measured
 * 2.74:1 on the die's face, under the 3:1 floor for a graphical object).
 *
 * **`D91`: the cube's box never changes size.** A transform moves no layout, so the tumble and the
 * landing shift 0.00 px by construction rather than by tuning — which is the only way that clause
 * can be true across three breakpoints without being re-measured at each.
 */

/** Which side of the cube each value lives on. Opposite faces sum to seven, as on a real die —
 *  1/6, 2/5, 3/4 — so the object survives being looked at from any angle mid-tumble. */
const SIDES = ['front', 'back', 'right', 'left', 'top', 'bottom'] as const
const VALUE_ON: Record<(typeof SIDES)[number], number> = {
  front: 1, back: 6, right: 2, left: 5, top: 3, bottom: 4,
}

/** The rotation that brings a value to the front, in DEGREES on each axis. Derived from `VALUE_ON`
 *  by hand once and pinned here, because a lookup is checkable and a computation over Euler angles
 *  is not.
 *
 *  **Numbers rather than transform strings, and A7 is why.** They are handed to CSS as `--tx` /
 *  `--ty` so the tumble's own final keyframe can be `calc(1440deg + var(--tx))` — four whole turns
 *  plus the landing angle. That makes the animation END on the landing orientation instead of
 *  stopping somewhere generic and then being transitioned to it. A string cannot be added to. */
const SHOW: Record<number, { x: number; y: number }> = {
  1: { x: 0,   y: 0 },
  2: { x: 0,   y: -90 },
  3: { x: -90, y: 0 },
  4: { x: 90,  y: 0 },
  5: { x: 0,   y: 90 },
  6: { x: 0,   y: 180 },
}

/** The pip positions on a 3×3 grid, by value. Index 1–9, reading left to right, top to bottom. */
const PIPS: Record<number, number[]> = {
  1: [5],
  2: [1, 9],
  3: [1, 5, 9],
  4: [1, 3, 7, 9],
  5: [1, 3, 5, 7, 9],
  6: [1, 3, 4, 6, 7, 9],
}

const RED = new Set([1, 4])

/**
 * **A7 direction A — 拋擲, owner-ruled from three animated candidates 2026-08-19; rebuilt on
 * springs the same night after 「這些動畫沒有達到我的標準」.**
 *
 * **D109's camera swing is retracted and is gone from this file.** What replaced it is not another
 * camera: the die simply never leaves an axis it cannot land square-on from, so 「square-on at
 * rest」 is now a property of the target angles rather than of a second element correcting for
 * them. One fewer moving part, and the constraint it existed to satisfy is satisfied harder.
 * Each die is
 * thrown from its own point, spins its own number of turns, and holds its own outward offset while
 * it spins. **All three differ per die on purpose**: two cubes given one motion read as one object
 * cut in half, which is the failure the ruling's 「一擲定案」 depends on not having.
 *
 * **THE DICE TUMBLE IN PLACE. There is no fly-in, and `ex`/`ey` are gone** (owner-ruled
 * 2026-08-20). The argument is `D108`'s and it is about honesty rather than taste: **the roll
 * already exists before anyone taps.** The seed is committed at open, every pair is derived from
 * it, and the tap reveals rather than throws. Dice flying in from off-frame say *being thrown
 * now* — an entrance animating an event that happened earlier, which is `D91`'s prohibition
 * pointed at the entry instead of at the exit.
 *
 * **What was dropped is the travel, not the clearance.** The tween no longer carries `x`/`y`, and
 * the cube starts at the tumbling posture rather than arriving at it: held apart by `hold`, lifted
 * by `FLY_Y`, and small at `FLY_SCALE`. All three are still spent and still given back by the
 * settle, so the landed frame is `design.md`'s gap exactly and the body diagonal still clears the
 * top of the window. `turnz`, the camera-free landing angles and every measured clearance are
 * untouched — the change is the entry alone.
 *
 * **`RV-15` is unaffected and is now easier to satisfy.** The question it asks is what the *first
 * painted frame* contains: it must hold both dice and must not hold the answer's own position.
 * The first frame is the tumbling posture — lifted, small, unrotated — which is neither off-screen
 * nor the landed hull.
 *
 * **`turnz` is what actually breaks the lockstep, and the two attempts before it did not — for a
 * reason worth writing down, because it is a property of the keyframes and not of the numbers.**
 * The dice first shared `1080/720` against `720/1080`, then `720/1440`, and both times they flew in
 * visible lockstep, showing the same face at the same angle. Changing the totals cannot fix it:
 * every keyframe is `turns ± 360deg` or `turns + tx`, and turns are whole revolutions, so **at each
 * keyframe both cubes are at the same orientation mod 360 and the rotation travelled BETWEEN two
 * keyframes is the same for both by construction.** Only the die's own landing angle differed, and
 * one axis of difference is not enough to look like two objects.
 *
 * `turnz` is a whole turn in opposite directions — invisible at the landing, since ±360° is the
 * identity, and a barrel roll neither cube can borrow from the other at any instant in between.
 *
 * **Screenshotting the frame is what caught this, twice. Nothing in the numbers looks wrong.**
 *
 * **`hold` is the anti-collision offset, and it had to be rebuilt from scratch after the camera
 * was retracted.** The first spring build dropped it with the CSS keyframes and the two cubes
 * passed **17.7 px through each other** in flight — measured, and invisible in any still frame that
 * happens to catch them apart. A cube's rotated bounding box is its body diagonal, about 1.7× its
 * face, so two cubes spaced for their flat footprint intersect. The separation is spent while they
 * are wide and given back by the settle, so the landed frame is `design.md`'s gap exactly.
 *
 * **The old `hold`:** A cube's rotated bounding box is its body diagonal, about
 * 1.7× its face, so two cubes spaced for their flat footprint pass through each other. The gap is
 * `design.md`'s and the landed frame is gated, so the separation is bought during the spin and
 * given back before the landing.
 */
const THROW = [
  { turnx: 1080, turny: 720,  turnz: -360, hold: -62 },
  { turnx: 720,  turny: 1440, turnz: 360,  hold: 62 },
] as const

/** How far short of the landing angle the tumble stops, so the spring has something to rock over.
 *  Small on purpose: a spring's overshoot is a percentage of the distance it is given, and a spring
 *  handed 1080° would rock a quarter-turn past the face. Handed 34°, it rocks about 3° — a die
 *  settling onto a face, which is the thing the owner said the timed version was not. */
const ROCK_X = 34
const ROCK_Y = 26

/** How far below its resting place, and how much smaller, the die **sits while it spins**. **This
 *  is the clearance D109's camera used to provide** — a cube presents its body diagonal while it
 *  tumbles, about 1.7× its face, and at full size that runs off the top of this screen. Since the
 *  in-place ruling these are the starting posture rather than a waypoint travelled to: the die is
 *  already lifted and already small on the first painted frame. It arrives at its real size on the
 *  settle, which reads as the die coming toward the viewer rather than merely stopping. */
const FLY_Y = 40
const FLY_SCALE = 0.74

/** Resolve once `el`'s computed transform has held identical for three consecutive frames.
 *  Bounded, so a browser that never settles cannot hang the reveal — the cap is generous enough
 *  that reaching it means something is wrong rather than merely slow. */
function stillness(el: Element, frames = 3, capMs = 1200): Promise<void> {
  return new Promise((resolve) => {
    const start = performance.now()
    let prev = ''
    let same = 0
    const tick = () => {
      const now = getComputedStyle(el).transform
      same = now === prev ? same + 1 : 0
      prev = now
      if (same >= frames || performance.now() - start > capMs) resolve()
      else requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

export default function Die(
  { value, seat, onLanded, onProgress }: {
    value: number; seat: number; onLanded?: () => void; onProgress?: () => void
  },
) {
  const { x, y } = SHOW[value] ?? SHOW[1]
  const t = THROW[seat % THROW.length]
  const reduce = useReducedMotion()
  const [scope, animate] = useAnimate()
  const TX = t.turnx + x
  const TY = t.turny + y

  useEffect(() => {
    // **Reduced motion is honoured by never starting, not by animating to the same place fast.**
    // With no `animate` call the element keeps `.cube`'s own resting transform from the stylesheet,
    // which IS the landed frame — §5 rule 3's "the end states still apply, instantly".
    if (reduce || !scope.current) return
    let alive = true
    // **A heartbeat, so the failsafe can be a watchdog instead of a race (`RV-19`).** The old
    // failsafe was `--tumble + 250`, a constant tuned near the sequence's length; the springs made
    // the real sequence ~2190 ms against a 1400 ms `--tumble`, so the timer won **every** run and
    // `land('animation')` never spoke. The screen was landing on a clock while the dice were still
    // moving, and `HOLD_MS` was accidentally compensating for it.
    //
    // This pings once per animation frame for as long as the sequence is alive. What the watchdog
    // then measures is **frames not arriving** — a dead tab, a chain that threw — which is what a
    // failsafe is actually for, and which no change to a spring or a duration can ever outgrow.
    let beating = true
    const beat = () => { if (beating && alive) { onProgress?.(); requestAnimationFrame(beat) } }
    requestAnimationFrame(beat)
    void (async () => {
      // **Rotation only — the die spins where it stands.** Since the in-place ruling the tween
      // carries no `x`, `y` or `scale`: the cube is already lifted, already held apart and already
      // small, placed there by `initial` before the first paint. It spins about its own centre and
      // nothing translates until the settle gives the three offsets back.
      //
      // **The clearance did not go with the travel.** D109's camera used to provide the headroom
      // with a dolly; retracting the camera took it, and the first spring build ran the dice
      // straight off the top of the window — measured, not guessed. `FLY_Y` and `FLY_SCALE` are
      // still what keeps the body diagonal on screen; they are simply held for the whole spin now
      // instead of being arrived at.
      //
      // A tween and not a spring: a spring's settling time does not depend on how far it travels,
      // so three whole turns on a spring stiff enough to feel crisp is a blur, and one loose enough
      // to read overshoots by a quarter-turn.
      await animate(
        scope.current,
        { rotateX: [0, TX - ROCK_X], rotateY: [0, TY - ROCK_Y], rotateZ: [0, t.turnz] },
        { duration: 1.05, ease: [0.16, 0.62, 0.3, 1] },
      )
      if (!alive) return
      // **The rock, then the arrival — sequential, and the order is the collision fix.**
      // While the die rocks it is still at `FLY_SCALE` and still held apart, so a cube 34° off its
      // face cannot reach its neighbour. It arrives at full size only once it is square-on and
      // narrow. The earlier build ran both together and measured 27.7 px of intersection.
      await animate(
        scope.current,
        { rotateX: TX, rotateY: TY },
        { type: 'spring', stiffness: 260, damping: 18, mass: 1 },
      )
      if (!alive) return
      // **Critically damped, and the last thing to move.** D111's hold begins when the dice have
      // stopped, so what ends the sequence has to end when it says it does.
      //
      // Measured on the version this replaces, where the body sprang slowly UNDERNEATH the rock:
      // `animate().finished` resolved at 1653 ms and the element's own matrix was still translating
      // — **2.03 px, not a sub-pixel tail** — until 1962 ms. A zero-duration snap afterwards did
      // not stop it; the running spring simply won. So the fix is not a stronger terminator, it is
      // **not having a long slow animation still in flight when the sequence claims to be over.**
      await animate(
        scope.current,
        { x: 0, y: 0, scale: 1 },
        { type: 'spring', stiffness: 260, damping: 34, mass: 1, restDelta: 0.25, restSpeed: 2 },
      )
      if (!alive) return
      // **The stop is OBSERVED, not inferred from the promise, and that is the whole of D111's
      // first clause working.** Measured across four builds: `animate().finished` resolves
      // **290–350 ms before this element's own matrix stops changing**, and the residual is a ~2 px
      // translation — small, but not the sub-pixel tail it first looked like. Two rest thresholds
      // shortened it; a zero-duration snap was simply out-run by the animation still in flight;
      // re-sequencing so the last spring is short and critically damped did not close it either.
      //
      // So the sequence stops guessing. It watches the element until its computed transform has
      // been identical for three consecutive frames, and only then reports. **The hold that follows
      // is then a hold after a real stop rather than after a promise about one** — and the same
      // frames a person sees are the ones the rule is measured on.
      await stillness(scope.current)
      beating = false
      if (alive) onLanded?.()
    })()
    return () => { alive = false; beating = false }
    // Mount-only: the round's dice are fixed before this component exists, so a re-run would be a
    // second throw of the same result.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="die" data-part="die" data-value={value} aria-hidden="true">
      <m.div
        ref={scope}
        className="cube"
        // **`initial` and not the effect, and the difference is one painted frame.** `useAnimate`
        // runs in an effect, which is after the browser has painted — so without this the die is
        // drawn once at its RESTING place and only then jumps into its spinning posture. Measured
        // on the fly-in build: the first sampled frame reported the landed hull exactly. A frame is
        // 16 ms and nobody would name it, but it is the answer's own position shown before the
        // roll, and `RV-15` asks what the first painted frame contains.
        //
        // **Since the in-place ruling this carries the whole starting posture** — held apart,
        // lifted and small — because there is no longer a travel keyframe to establish it. The
        // three values are the same ones the settle gives back, written once here and once there.
        initial={reduce ? false : { x: t.hold, y: FLY_Y, scale: FLY_SCALE }}
        style={{ ['--tx' as string]: `${x}deg`, ['--ty' as string]: `${y}deg` }}
      >
        {SIDES.map((side) => {
          const v = VALUE_ON[side]
          return (
            <div key={side} className={`face ${side}`} data-face={v}>
              {Array.from({ length: 9 }, (_, i) => i + 1).map((cell) => (
                <span key={cell} className="dieCell">
                  {PIPS[v].includes(cell) && (
                    <i className="pip" data-red={RED.has(v) ? 'yes' : 'no'} />
                  )}
                </span>
              ))}
            </div>
          )
        })}
      </m.div>
    </div>
  )
}
