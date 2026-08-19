import type { CSSProperties } from 'react'

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
 * **A7 direction A — 拋擲, owner-ruled from three animated candidates 2026-08-19.** Each die is
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
 * **`hold` is the anti-collision offset.** A cube's rotated bounding box is its body diagonal, about
 * 1.7× its face, so two cubes spaced for their flat footprint pass through each other. The gap is
 * `design.md`'s and the landed frame is gated, so the separation is bought during the spin and
 * given back before the landing.
 */
const THROW = [
  { ex: '-430px', ey: '300px', turnx: '1080deg', turny: '720deg',  turnz: '-360deg', hold: '-70px' },
  { ex: '-330px', ey: '392px', turnx: '720deg',  turny: '1440deg', turnz: '360deg',  hold: '70px' },
] as const

export default function Die(
  { value, tumbling, seat }: { value: number; tumbling: boolean; seat: number },
) {
  const { x, y } = SHOW[value] ?? SHOW[1]
  const t = THROW[seat % THROW.length]
  return (
    <div className="die" data-part="die" data-value={value} aria-hidden="true">
      {/* **A7 — the CAMERA, and it is a separate element on purpose.** `.dieScene` carries where the
          viewer is standing; `.cube` carries where the die is pointing. They are different facts
          and folding them into one transform means a change to the camera silently re-aims the
          die, which is exactly the class of error that cannot be seen in a still frame.

          `dieScene` and not `scene`, for the reason `dieCell` is not `cell`: there are no CSS
          modules here, every class name in this directory is global, and a generic one is a
          collision waiting for the second screen that wants it. */}
      <div className="dieScene">
        <div
          className="cube"
          data-tumbling={tumbling ? 'yes' : 'no'}
          // The landing angle, handed to CSS as two numbers. The tumble's last keyframe adds four
          // and three whole turns to them, so the animation's end orientation and the resting
          // transform below are the SAME orientation — removing the animation cannot jump.
          style={{
            '--tx': `${x}deg`, '--ty': `${y}deg`,
            '--ex': t.ex, '--ey': t.ey,
            '--turnx': t.turnx, '--turny': t.turny, '--turnz': t.turnz,
            '--hold': t.hold,
          } as CSSProperties}
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
        </div>
      </div>
    </div>
  )
}
