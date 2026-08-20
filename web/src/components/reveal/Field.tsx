import { m, useReducedMotion } from '@/lib/motion'
import { PIPS } from './Die'

/**
 * The ground the dice are thrown onto — 網點即骰點, evaluator-ruled 2026-08-20 under D101's
 * delegation.
 *
 * **The owner's complaint was 單調 and the licence was a static image; the ruling spends it on
 * pattern instead.** The halftone dot is print's own texture AND the die's pip — the one mark this
 * product owns — so the ground can be busy without importing a second visual language. Riso-print
 * logic: paper, spot colours, halftone. Pure CSS tiles, **zero image assets**, so §6's dead-wifi
 * rule is untouched by a decision about decoration.
 *
 * **The glow is gone. Print does not glow.** It survived two tunings on the argument that a light
 * source is not a shadow, and the ruling retires the whole idea rather than the sizing: a page that
 * behaves like paper cannot have a lamp behind it.
 *
 * **Tumble — neutral, and neutral is a D91 requirement rather than a taste.** A field of even dots
 * plus a denser table band at the bottom edge for the dice to land on. **No cluster may read as a
 * die face before the result exists**, because a ground that answers first is the animation
 * asserting something it does not yet have.
 *
 * **Staged — the ground repeats the truth, it never invents it.** This round's real pair prints as
 * two poster-scale faces in a darker step of the flood's own colour. They are the *stored* dice, so
 * `RV-16` is untouched — nothing appears before landed, and nothing on screen mid-tumble
 * distinguishes the winner. The tone sits under the text layer: **copy is always the brightest
 * layer.**
 *
 * **A face needs its border to read as a face.** Cropped bare dots read as blobs, which is the
 * rubric's own named slop; the 4px tone rule is what makes the shape legible while it bleeds off
 * the edge.
 */

/** Slow enough to be felt rather than watched, and out of phase so the two layers never move
 *  together — synchronised drift reads as the page wobbling rather than as paper breathing. */
const DRIFT = [
  { d: 6.5, delay: 0, x: [0, 7, 0], y: [0, -9, 0] },
  { d: 7.4, delay: -2.6, x: [0, -6, 0], y: [0, 8, 0] },
]

/** The two printed faces: which corner each bleeds off, and its fixed angle. **Fixed, never
 *  random** — a ground that lands differently on every load reads as a glitch, and this one is a
 *  record of a result rather than an effect. */
const POSTER = [
  { className: 'posterA', rotate: -5 },
  { className: 'posterB', rotate: 4 },
]

function PosterFace({ value, className, rotate }: { value: number; className: string; rotate: number }) {
  return (
    <span className={`poster ${className}`} style={{ transform: `rotate(${rotate}deg)` }}>
      {Array.from({ length: 9 }, (_, i) => i + 1).map((cell) => (
        <span key={cell} className="posterCell">
          {PIPS[value]?.includes(cell) && <i className="posterPip" />}
        </span>
      ))}
    </span>
  )
}

export default function Field({ dice, staged }: { dice?: readonly number[]; staged: boolean }) {
  const reduce = useReducedMotion()
  /** Reduced motion stops the drift **on a legible frame** rather than removing the layers — the
   *  halftone is texture, not motion, and it is what the screen looks like. */
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
      {/* The table the dice land on — present only while they are in the air, because once they
          have landed the composition is a printed page and not a table. */}
      {!staged && <span className="tableBand" />}
      {/* **Gated on `staged` AND on the values existing.** Two conditions rather than one: `staged`
          is the screen's own state and `dice` is what the server stored, and a ground drawn from a
          state without a value is exactly the ground that could answer first. */}
      {staged && dice && dice.length >= 2 && (
        <span className="posters">
          {POSTER.map((p, i) => (
            <PosterFace key={p.className} value={dice[i]} className={p.className} rotate={p.rotate} />
          ))}
        </span>
      )}
    </div>
  )
}
