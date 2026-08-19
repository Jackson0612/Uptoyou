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

/** The rotation that brings a value to the front. Derived from `VALUE_ON` by hand once and pinned
 *  here, because a lookup is checkable and a computation over Euler angles is not. */
const SHOW: Record<number, string> = {
  1: 'rotateX(0deg) rotateY(0deg)',
  2: 'rotateX(0deg) rotateY(-90deg)',
  3: 'rotateX(-90deg) rotateY(0deg)',
  4: 'rotateX(90deg) rotateY(0deg)',
  5: 'rotateX(0deg) rotateY(90deg)',
  6: 'rotateX(0deg) rotateY(180deg)',
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

export default function Die({ value, tumbling }: { value: number; tumbling: boolean }) {
  return (
    <div className="die" data-part="die" data-value={value} aria-hidden="true">
      <div
        className="cube"
        data-tumbling={tumbling ? 'yes' : 'no'}
        style={tumbling ? undefined : { transform: SHOW[value] }}
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
  )
}
