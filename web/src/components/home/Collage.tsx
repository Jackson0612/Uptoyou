import { useEffect, useRef, useState } from 'react'

/**
 * The home collage — four fixed cells, a pool of images, one cell swapping every 10 s.
 *
 * The geometry never moves. Each cell is a fixed box holding two absolutely-positioned images
 * that cross-fade on opacity alone, so a swap is 0.00 px of layout change (HC-3). Swapping `src`
 * instead would blank the box for the decode, and a white flash inside a bordered tile is louder
 * than the swap it was hiding.
 *
 * The pool is whatever exists: four today, ten when gpu-imggen delivers. Nothing here reads the
 * length except the selection rule, which handles any pool of five or more without change — and
 * degrades honestly below that, see `nextFile`.
 */

/** `alt` describes what is actually in the frame and travels WITH the image — an alt describing
 *  a different photograph is worse than no alt. A constant, not fetched (§6) and not derived from
 *  the filename, because a filename is not a sentence. */
export const POOL = [
  { file: '/img/collage-01.webp', alt: '牛肉麵：寬麵條、大塊紅燒牛肉、深褐色湯頭，厚陶碗放在木桌上' },
  { file: '/img/collage-02.webp', alt: '滷肉飯：白飯上鋪滿滷肉燥，旁邊一顆滷蛋與青菜' },
  { file: '/img/collage-03.webp', alt: '水餃：白瓷盤裡的水餃，一雙筷子夾起一顆，旁邊一碟醬油醋' },
  { file: '/img/collage-04.webp', alt: '鹽酥雞：炸得金黃的雞塊，撒上胡椒鹽與九層塔' },
] as const

const CELLS = 4
const INTERVAL_MS = 10_000
const FADE_MS = 400

type Slot = { file: string; alt: string; token: number }

export default function Collage() {
  const [cells, setCells] = useState<Slot[]>(() =>
    Array.from({ length: CELLS }, (_, i) => ({ ...POOL[i % POOL.length], token: i })),
  )
  const [leaving, setLeaving] = useState<Record<number, Slot | undefined>>({})
  const [rotating, setRotating] = useState(false)

  const cellsRef = useRef(cells); cellsRef.current = cells
  const nextCell = useRef(0)
  const token = useRef(CELLS)
  /** Files that have finished arriving. An image still in flight is SKIPPED, not waited for —
   *  a rotation that stalls on a slow network is worse than one that shows nine pictures. */
  const ready = useRef<Set<string>>(new Set(POOL.slice(0, CELLS).map((p) => p.file)))

  /** The next image in pool order that is not currently in any cell. A plain `pool[n++ % len]`
   *  puts the same dish in two cells about a fifth of the time, and a duplicate in a four-picture
   *  collage reads as a bug rather than as a rhythm. One line; it makes it unreachable. */
  function nextFile(after: string): { file: string; alt: string } | null {
    const shown = new Set(cellsRef.current.map((c) => c.file))
    const start = POOL.findIndex((p) => p.file === after)
    for (let i = 1; i <= POOL.length; i++) {
      const cand = POOL[(start + i) % POOL.length]
      if (!shown.has(cand.file) && ready.current.has(cand.file)) return cand
    }
    return null   // pool too small, or nothing eligible has arrived — hold this tick
  }

  // The rest of the pool is fetched AFTER load, at idle, so first paint costs what the four
  // visible images cost and the remainder arrive during the first cell's 40-second hold.
  useEffect(() => {
    const rest = POOL.slice(CELLS)
    if (!rest.length) return
    const warm = () => rest.forEach((p) => {
      const img = new Image()
      img.onload = () => ready.current.add(p.file)
      img.src = p.file
    })
    const idle = (window as unknown as {
      requestIdleCallback?: (cb: () => void) => number
    }).requestIdleCallback
    const id = idle ? idle(warm) : window.setTimeout(warm, 1200)
    return () => { if (!idle) window.clearTimeout(id as number) }
  }, [])

  useEffect(() => {
    // §5 rule 4, condition 3: under reduced motion the rotation does not START — not
    // started-and-ignored, because a timer nobody can see is still a timer. The four images
    // loaded first hold for the session, which is a legible frame by construction.
    const motionOff = window.matchMedia('(prefers-reduced-motion: reduce)')
    let timer: number | undefined

    const stop = () => { if (timer !== undefined) { window.clearInterval(timer); timer = undefined }
                         setRotating(false) }
    const start = () => {
      if (timer !== undefined || motionOff.matches || document.visibilityState !== 'visible') return
      setRotating(true)
      timer = window.setInterval(() => {
        const cell = nextCell.current
        nextCell.current = (cell + 1) % CELLS
        const cur = cellsRef.current[cell]
        const pick = nextFile(cur.file)
        if (!pick) return
        const incoming: Slot = { ...pick, token: token.current++ }
        setLeaving((l) => ({ ...l, [cell]: cur }))
        setCells((cs) => cs.map((c, i) => (i === cell ? incoming : c)))
        // the outgoing element leaves the DOM only after the transition has ended
        window.setTimeout(() => setLeaving((l) => ({ ...l, [cell]: undefined })), FADE_MS + 60)
      }, INTERVAL_MS)
    }

    // Hidden page: suspend, and resume WITHOUT catching up. A tab left open ten minutes would
    // otherwise burn sixty unseen swaps and the returning reader finds it mid-jump.
    const onVisibility = () => (document.visibilityState === 'visible' ? start() : stop())
    document.addEventListener('visibilitychange', onVisibility)
    motionOff.addEventListener('change', () => (motionOff.matches ? stop() : start()))
    start()
    return () => { stop(); document.removeEventListener('visibilitychange', onVisibility) }
  }, [])

  return (
    <div className="collage" data-part="collage"
         data-collage-state={rotating ? 'rotating' : 'static'}>
      {cells.map((slot, i) => (
        <figure className="cell" key={i} data-cell={String(i + 1)}>
          {leaving[i] && (
            <img data-collage-img src={leaving[i]!.file} alt="" aria-hidden="true"
                 key={leaving[i]!.token} style={{ opacity: 0 }} />
          )}
          <img data-collage-img key={slot.token} src={slot.file} alt={slot.alt}
               ref={(el) => { if (el) requestAnimationFrame(() => { el.style.opacity = '1' }) }}
               style={{ opacity: leaving[i] ? 0 : 1 }} />
        </figure>
      ))}
      <p className="tag"><b>36,499</b><span>家在冊</span></p>
    </div>
  )
}
