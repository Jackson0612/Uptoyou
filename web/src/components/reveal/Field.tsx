import { m, useReducedMotion } from '@/lib/motion'

/**
 * The ground the dice are thrown onto — halftone, light, and drift.
 *
 * **This exists because the motion was never the problem.** Six animations were rejected as 廉價
 * and the seventh would have been too: the field they played on was a flat cream rectangle with two
 * white cubes on it and nothing else, and no amount of easing fixes an empty room. The evaluator
 * read 120 frames of the reference the owner pointed at and found its quality came from three small
 * things happening at once rather than from one big animation. All three are here; none of them is
 * an animation of the dice.
 *
 * **1 · Halftone, bleeding from two corners.** Texture that reads while nothing is moving, which is
 * the state this screen is in for most of the time anyone looks at it. Two fields at different dot
 * pitches so the corners have depth rather than a pattern. Drawn in `currentColor`, so it is ink on
 * the paper ground and the on-flood pair after the flood — one declaration, both states, and it can
 * never end up as ink on ink.
 *
 * **2 · A light source, not a shadow.** The object is *lit*; it is not *raised*. The distinction is
 * load-bearing and the evaluator learned it the expensive way: they put the glow **behind the dice**
 * and it washed them into pale grey-green plastic with muted pips. **The light belongs on the
 * ground around the object and never on the object's own face** — so this sits under `.dice` in the
 * stack and the die faces keep their solid paper fill and hard ink pips, untouched.
 *
 * **3 · Ambient drift, phase-offset per layer.** The reference's cards never stop moving and never
 * move together — between two frames 45 apart they had each shifted differently. **Slow, small, and
 * out of phase is the whole trick**: sync it and it reads as the page wobbling.
 *
 * **What deliberately does NOT drift: the dice.** They were thrown and they landed. A resting die
 * that floats is the animation asserting something that did not happen, which is the same argument
 * `D91` makes about everything else on this screen. The room breathes; the objects sit still.
 */

/** Slow enough to be felt rather than watched. Each layer carries its own duration AND its own
 *  delay, because two layers on one duration drift apart only until the browser catches up. */
const DRIFT = [
  { d: 6.5, delay: 0, x: [0, 7, 0], y: [0, -9, 0] },
  { d: 7.4, delay: -2.6, x: [0, -6, 0], y: [0, 8, 0] },
  { d: 6.9, delay: -4.1, x: [0, 4, 0], y: [0, 6, 0] },
]

export default function Field() {
  const reduce = useReducedMotion()
  /** Reduced motion stops the drift **on a legible frame** rather than removing the layers — the
   *  halftone and the light are texture, not motion, and they are what the screen looks like. */
  const drift = (i: number) =>
    reduce
      ? {}
      : {
          animate: { x: DRIFT[i].x, y: DRIFT[i].y },
          transition: {
            duration: DRIFT[i].d,
            delay: DRIFT[i].delay,
            repeat: Infinity,
            ease: 'easeInOut' as const,
          },
        }

  return (
    <div className="field" data-part="field" aria-hidden="true">
      <m.span className="halftone halftoneA" {...drift(0)} />
      <m.span className="halftone halftoneB" {...drift(1)} />
      <m.span className="glow" {...drift(2)} />
    </div>
  )
}
