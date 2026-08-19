import { useCallback, useEffect, useRef, useState } from 'react'
import {
  device, openRound, propose, roll, searchPlaces, materialise, subscribe,
  type Candidate, type Device, type Pooled,
} from '@/lib/round'
import { Input } from '@/components/ui/input'

/**
 * A4 — the round screen: open, propose, roll.
 *
 * **The pool is fed by the stream, not by the response to the write.** D56 makes the snapshot the
 * stream's first event, so a screen that has connected already knows the state, and a `pooled`
 * event arrives the same way whether this device proposed or another one did. Appending locally on
 * a successful POST would be a second source of truth that agrees today and drifts the first time
 * two people propose at once.
 *
 * **Nothing here names who proposed what** (§3.0, D14). The `pooled` event carries a place and no
 * member, the snapshot's pool carries names and no authorship, and there is no column behind
 * either by the time the round closes. So the absence is structural rather than a field this
 * component declines to render — but it is still asserted, because the payload could grow one.
 *
 * **The roll does not navigate on its own response.** It waits for the `closed` event, so every
 * device in the circle moves to the reveal on the same signal at the same moment — which is the
 * whole point of the stream, and the difference between a shared moment and five separate ones.
 */
export default function Round() {
  const [dev] = useState<Device | null>(device)
  const [roundId, setRoundId] = useState<number | null>(null)
  const [pool, setPool] = useState<Pooled[]>([])
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<Candidate[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const seq = useRef(0)

  useEffect(() => {
    if (!dev) return
    return subscribe(dev, (e) => {
      if (e.type === 'snapshot') {
        setRoundId(e.open_round?.round_id ?? null)
        setPool(e.open_round?.pool ?? [])
      } else if (e.type === 'round_opened') {
        setRoundId(e.round.round_id)
        setPool(e.round.pool ?? [])
      } else if (e.type === 'pooled') {
        // Keyed by place, because D70 lets the same place be proposed twice and the second time
        // must change nothing a person can see.
        setPool((p) => (p.some((x) => x.place_id === e.place.place_id) ? p : [...p, e.place]))
      } else if (e.type === 'closed') {
        window.location.href = `/reveal?round=${e.result.round_id}`
      }
    }, setError)
  }, [dev])

  // The typeahead. Every keystroke carries a sequence number and a late response for an older
  // query is dropped — without it, a slow request for 「牛」 lands after a fast one for 「牛肉麵」
  // and the list silently reverts to the broader search.
  useEffect(() => {
    if (!dev || q.trim().length === 0) { setHits([]); return }
    const mine = ++seq.current
    const t = window.setTimeout(() => {
      void searchPlaces(dev, q.trim()).then((r) => { if (mine === seq.current) setHits(r) })
    }, 180)
    return () => window.clearTimeout(t)
  }, [dev, q])

  const add = useCallback(async (c: Candidate) => {
    if (!dev || busy) return
    setBusy(true)
    try {
      const id = c.place_id ?? (c.registry_no ? await materialise(dev, c.registry_no) : null)
      if (id === null) throw new Error('這一筆沒有可用的編號。')
      let r = roundId
      // Proposing with nothing open opens one first — the person's intent is to put this place
      // forward, and making them press 「開一輪」 first is a step the product invented for itself.
      if (r === null) { r = (await openRound(dev)).roundId; setRoundId(r) }
      await propose(dev, r, id)
      setQ('')
      setHits([])
      setError('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }, [dev, roundId, busy])

  if (!dev) {
    return (
      <main className="round" data-screen="round">
        <p className="roundNote">這台裝置還沒有鑰匙。</p>
      </main>
    )
  }

  return (
    <main className="round" data-screen="round">
      <h1 className="roundTitle">這一餐</h1>
      <p className="roundNote">一人提一家。提完了就擲，兩顆骰子一次定案。</p>

      <label className="roundSearch">
        <span className="roundLabel">找一家店</span>
        <Input
          data-part="place-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="店名的一部分"
          autoComplete="off"
        />
      </label>

      {/* **The refusal sits directly under the control that was refused, above the results.**
          Driven on 2026-08-19 with the error below the list: a four-place proposal answered 409,
          and the sentence explaining it rendered at y 786 under a pinned bar whose top edge is 824
          — **half of the one thing the person needed to read, behind a bar, below ten search
          results they had just been told they could not use.** The list stays open on purpose (a
          refusal is not a reason to throw away a search), so the message cannot live after it.

          It is not cleared on the next keystroke either, and that is deliberate: the reason a
          proposal was refused is still true while the person types the next query, and a message
          that vanishes the moment they touch the keyboard is one they will meet again by trying
          the same thing. It clears when a proposal succeeds. */}
      {error && <p className="roundErr" data-part="round-error">{error}</p>}

      {hits.length > 0 && (
        <ul className="hits" data-part="typeahead">
          {hits.map((c) => (
            <li key={c.registry_no ?? c.place_id} className="hit">
              <button type="button" disabled={busy} onClick={() => void add(c)}>
                {/* D92's composed name — sign, then address-derived, then registered. The API
                    composes it; nothing here re-derives a name, which is what keeps the format
                    the provenance. */}
                <span className="hitName">{c.name}</span>
                {c.district && <span className="hitWhere">{c.district}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      <section className="poolBlock" data-part="pool">
        <h2 className="roundH">這一輪的名單</h2>
        {pool.length === 0 ? (
          <p className="roundNote">還沒有人提。</p>
        ) : pool.length === 1 ? (
          // **The reason lives beside the list, not behind a press.** The API refuses a one-place
          // roll with 「一家店不是決定，是通知。」 and that sentence teaches something; but a
          // control that is pressable only to be refused teaches it by wasting a tap. So the bar
          // disables below two and the arithmetic is stated here, where a person reading the list
          // is already looking. States, never advises (D20) — it says what the round needs, not
          // what anyone should do about it.
          <>
            <ul className="rows">
              {pool.map((p) => (
                <li key={p.place_id} className="row" data-part="pool-row">
                  <span className="rowName">{p.name}</span>
                </li>
              ))}
            </ul>
            <p className="roundNote" data-part="need-two">
              一輪至少要兩家店。一家店不是決定，是通知。
            </p>
          </>
        ) : (
          <ul className="rows">
            {pool.map((p) => (
              // No proposer, no count, no share — §3.0 and B1. The row is the place and nothing
              // else, and the reveal is where numbers are allowed to exist at all.
              <li key={p.place_id} className="row" data-part="pool-row">
                <span className="rowName">{p.name}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="bar" data-part="bar">
        <button
          type="button"
          data-part="roll"
          disabled={roundId === null || pool.length < 2 || busy}
          onClick={() => {
            if (!dev || roundId === null) return
            setBusy(true)
            // No navigation here on purpose — the `closed` event moves every device at once.
            void roll(dev, roundId).catch((e: Error) => { setError(e.message); setBusy(false) })
          }}
        >
          擲骰
        </button>
      </div>
    </main>
  )
}
