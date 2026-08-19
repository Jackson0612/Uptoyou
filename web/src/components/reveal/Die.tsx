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
 * **`ex`/`ey` are inside the viewport at 1440, and `RV-15` is why.** The evaluator's prototype threw
 * from above the frame; this screen's dice sit 24 px from the top, so *above* is off-screen and the
 * throw would read as the dice appearing rather than being thrown. They come up from the empty
 * space below instead — which during the tumble is exactly where the answer is not yet.
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
  { ex: -430, ey: 300, turnx: 1080, turny: 720,  turnz: -360, hold: -62 },
  { ex: -330, ey: 392, turnx: 720,  turny: 1440, turnz: 360,  hold: 62 },
] as const

/** How far short of the landing angle the tumble stops, so the spring has something to rock over.
 *  Small on purpose: a spring's overshoot is a percentage of the distance it is given, and a spring
 *  handed 1080° would rock a quarter-turn past the face. Handed 34°, it rocks about 3° — a die
 *  settling onto a face, which is the thing the owner said the timed version was not. */
const ROCK_X = 34
const ROCK_Y = 26

/** How far below its resting place, and how much smaller, the die flies. **This is the clearance
 *  D109's camera used to provide** — a cube presents its body diagonal while it tumbles, about 1.7×
 *  its face, and at full size that runs off the top of this screen. It arrives at its real size on
 *  the settle, which also reads as the die coming toward the viewer rather than merely stopping. */
const FLY_Y = 40
const FLY_SCALE = 0.74

export default function Die(
  { value, seat, onLanded }: { value: number; seat: number; onLanded?: () => void },
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
    void (async () => {
      // **The tumble carries the whole path, and it flies SMALL and LOW on purpose.** D109's
      // camera used to provide this clearance with a dolly and a downward offset; retracting the
      // camera took the clearance with it, and the first spring build ran the dice straight off the
      // top of the window — measured, not guessed.  The headroom now belongs to the object's own
      // path, which is one fewer element that has to arrive on time.
      //
      // A tween and not a spring: a spring's settling time does not depend on how far it travels,
      // so three whole turns on a spring stiff enough to feel crisp is a blur, and one loose enough
      // to read overshoots by a quarter-turn.
      await animate(
        scope.current,
        {
          x: [t.ex, t.hold], y: [t.ey, FLY_Y], scale: [0.68, FLY_SCALE],
          rotateX: [0, TX - ROCK_X], rotateY: [0, TY - ROCK_Y], rotateZ: [0, t.turnz],
        },
        { duration: 1.05, ease: [0.16, 0.62, 0.3, 1] },
      )
      if (!alive) return
      // **The settle — one spring carrying the arrival and the rock together.** The evaluator's
      // numbers, on distances small enough for them to mean what they say: the die rises the last
      // 28 px, grows into its resting size and rocks a couple of degrees past its face before
      // decaying onto it. That overshoot is the point — a critically-damped landing is what
      // 「timed rather than felt」 looks like.
      await animate(
        scope.current,
        { x: 0, y: 0, scale: 1, rotateX: TX, rotateY: TY },
        {
          // **Two springs, and the split is the whole of the collision fix.** Measured with one
          // spring carrying everything: the cubes overlapped by 27.7 px and clipped the window by
          // 5.8 px, both at t≈1300 ms — inside the settle, not the tumble. At full size a cube
          // rotated even 30° is wider than the 4 px the resting gap leaves between them, so
          // arriving at size and rocking at the same time is a guaranteed intersection.
          //
          // So the ROTATION rocks fast and the BODY arrives slowly behind it: by the time the die
          // is at its resting size and its resting x, it is already square-on and narrow.
          default: { type: 'spring', stiffness: 120, damping: 26, mass: 1 },
          rotateX: { type: 'spring', stiffness: 260, damping: 18, mass: 1 },
          rotateY: { type: 'spring', stiffness: 260, damping: 18, mass: 1 },
        },
      )
      if (alive) onLanded?.()
    })()
    return () => { alive = false }
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
        // runs in an effect, which is after the browser has painted — so the die was drawn once at
        // its RESTING place and then jumped off-screen to start the throw. Measured: the first
        // sampled frame reported the landed hull exactly. A frame is 16 ms and nobody would name
        // it, but it is the answer's own position shown before the throw, and `RV-15` asks what the
        // first painted frame contains. `initial` is applied before paint, so the first frame is
        // the entry.
        initial={reduce ? false : { x: t.ex, y: t.ey, scale: 0.68 }}
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
