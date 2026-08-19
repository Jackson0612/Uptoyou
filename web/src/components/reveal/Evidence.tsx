import { FACES, type Evidence as EvidenceData, type Places } from '@/lib/reveal'

/**
 * A3's second half — `TABLE` and `ALLOC36`, **operator state only** (`D105`, `design.md` §4b).
 *
 * **This is an addition, not a toggle.** It renders only when the response carried the accounting,
 * which happens only for a credential issued with `--operator`. Nothing in the member state moves,
 * resizes or re-flows when it is present: it appends below the answer region, so a person who has
 * seen both recognises the second as the first.
 *
 * **`D91`'s third clause: the table and the grid are drawn from ONE source.** Both read
 * `allocation` — the grid colours a cell per outcome, the table prints the same count as `n/36`.
 * Two derivations of "the same" shares is how a grid comes to disagree with the table beside it,
 * and a disagreement there destroys precisely the credibility both exist to build. So `share()`
 * exists once and both callers use it.
 *
 * **No 「示意」 caveat, and its absence is deliberate** (§5). The grid *was* an illustration on the
 * home screen and is not one here — it is this round's real allocation. A caveat left on a true
 * figure is worse than no caveat, because it teaches the reader to discount a real number.
 */

/** The 36 outcomes, in pool order, each carrying the face of the place that holds it. Built from
 *  `allocation` alone so the grid cannot drift from the table. */
function cells(ev: EvidenceData, places: Places): { face: string; placeId: string }[] {
  const out: { face: string; placeId: string }[] = []
  Object.keys(places).forEach((placeId, seat) => {
    const n = ev.allocation[placeId] ?? 0
    const face = FACES[seat % FACES.length]
    for (let i = 0; i < n; i++) out.push({ face, placeId })
  })
  return out
}

export default function Evidence({ ev, places }: { ev: EvidenceData; places: Places }) {
  const grid = cells(ev, places)
  const seats = Object.keys(places)

  return (
    <section className="evidence" data-part="evidence" data-state="operator">
      {/* ALLOC36 — beside the table as evidence, never above it as decoration. Cells are ≥ 36 px
          square (§3's rescue floor): below that the colour blocks stop being countable and the
          figure reads as a texture rather than as thirty-six things. */}
      <div className="alloc36" data-part="alloc36" aria-hidden="true">
        {grid.map((c, i) => (
          <span key={i} className="allocCell" data-face={c.face} />
        ))}
      </div>

      <table className="evTable" data-part="table">
        <thead>
          <tr>
            <th scope="col" className="evPlace">提名</th>
            <th scope="col" className="evNum">格數</th>
            {/* 「權重來源」 rather than 「理由」: what this column prints is the contributor and the
                factor it applied. A *reason* is a sentence, and D13 lets one travel only at `table`
                visibility — so most rows would have carried a column heading promising something
                the payload is not allowed to hand over. */}
            <th scope="col" className="evWhy">權重來源</th>
          </tr>
        </thead>
        <tbody>
          {seats.map((placeId, seat) => {
            const n = ev.allocation[placeId] ?? 0
            const factors = ev.panel[placeId]?.factors ?? []
            return (
              <tr key={placeId} data-part="table-row">
                <td className="evPlace">
                  {/* CHIP — identity, never quantity. The square says which place; the number
                      beside it says how much, and the two never merge into a coloured bar. */}
                  <span className="chip" data-face={FACES[seat % FACES.length]} />
                  {places[placeId]}
                </td>
                {/* tabular-nums and right-aligned, so the column reads as a column */}
                <td className="evNum">{n}<span className="evOf">/36</span></td>
                <td className="evWhy">
                  {factors.length === 0
                    ? <span className="evNone">—</span>
                    : factors.map((f, i) => (
                        <span key={i} className="evFactor">
                          {/* **The contributor and the factor travel; the REASON does not, unless
                              D13 lets it.** A `represented_member` reason reaches that member alone
                              and nobody else, the operator included — this view audits the
                              arithmetic, not the people. `null` here is the database enforcing
                              that, not this component choosing to be discreet. */}
                          {f.contributor} ×{f.effect}
                          {f.reason && <span className="evReason">（{f.reason}）</span>}
                        </span>
                      ))}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
