/**
 * A4 — the round's endpoints and the circle's live stream.
 *
 * **The stream is fetch-SSE, not `EventSource`, and that is forced rather than chosen.**
 * `EventSource` cannot set an `Authorization` header, and D67 puts the device secret in one — so
 * the alternative would be a token in the query string, which lands in the proxy's access log and
 * in the browser's history. A `fetch` reader costs about twenty lines and keeps the credential in
 * the one place that is not written down.
 */

export type Device = { token: string; circle: string }

export function device(): Device | null {
  const token = localStorage.getItem('upto_token')
  const circle = localStorage.getItem('upto_circle')
  return token && circle ? { token, circle } : null
}

export function remember(d: Device): void {
  localStorage.setItem('upto_token', d.token)
  localStorage.setItem('upto_circle', d.circle)
}

function auth(d: Device): HeadersInit {
  return { authorization: `Bearer ${d.token}` }
}

/**
 * **The surface's own words, never the wire's.** The API's 401 detail is written for whoever is
 * holding a terminal — *a bearer token is required (D67)* — and a person who pasted a key into a
 * box needs to be told that the key did not work, not which decision number governs it. Every
 * other status keeps the API's sentence, because those are written for a person already.
 */
export async function verify(d: Device): Promise<void> {
  const r = await fetch(`/api/circles/${encodeURIComponent(d.circle)}/preferences`, {
    headers: auth(d),
    cache: 'no-store',
  })
  if (r.ok) return
  if (r.status === 401) throw new Error('這把鑰匙開不了這個圈子。再確認一次貼上的內容。')
  if (r.status === 404) throw new Error('找不到這個圈子。')
  const body = await r.json().catch(() => ({}))
  throw new Error(body.detail || `連不上（${r.status}）`)
}

export type Candidate = {
  kind: string
  place_id: number | null
  registry_no: string | null
  name: string
  name_source: string
  district: string | null
}

export async function searchPlaces(d: Device, q: string): Promise<Candidate[]> {
  const r = await fetch(
    `/api/circles/${encodeURIComponent(d.circle)}/places?q=${encodeURIComponent(q)}`,
    { headers: auth(d), cache: 'no-store' },
  )
  if (!r.ok) return []
  return (await r.json()).candidates ?? []
}

/** A reference candidate the circle has never touched has **no `place`
 *  row yet** — D28's rule that a place is always a row of ours. This makes one, and the endpoint
 *  answers quietly if the row already exists, so calling it twice is not an error. */
export async function materialise(d: Device, registryNo: string): Promise<number> {
  const r = await fetch(`/api/circles/${encodeURIComponent(d.circle)}/places`, {
    method: 'POST',
    headers: { ...auth(d), 'content-type': 'application/json' },
    body: JSON.stringify({ registry_no: registryNo }),
  })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail || `加不進來（${r.status}）`)
  return body.place_id ?? body.id
}

export async function openRound(d: Device): Promise<{ roundId: number; conflict: boolean }> {
  const r = await fetch(`/api/circles/${encodeURIComponent(d.circle)}/rounds`, {
    method: 'POST',
    headers: { ...auth(d), 'content-type': 'application/json' },
    body: JSON.stringify({}),
  })
  const body = await r.json().catch(() => ({}))
  if (r.status === 201) return { roundId: body.round_id, conflict: false }
  // **D68: a losing simultaneous open gets 409 carrying the WINNING round.** The person who lost
  // the race wanted a round open; one is. Joining it is what they meant, so this is not an error
  // to report — it is the same success by another path, and the flag exists only so the screen can
  // say so rather than pretend nothing happened.
  if (r.status === 409) {
    const won = body.round_id ?? body.detail?.round_id
    if (won) return { roundId: won, conflict: true }
  }
  throw new Error(body.detail || `開不了（${r.status}）`)
}

/** **D70: a repeat proposal succeeds quietly.** Proposal count is not a weight, so proposing the
 *  same place twice is not a conflict and must not be reported as one. */
export async function propose(d: Device, roundId: number, placeId: number): Promise<void> {
  const r = await fetch(`/api/rounds/${roundId}/proposals`, {
    method: 'POST',
    headers: { ...auth(d), 'content-type': 'application/json' },
    body: JSON.stringify({ place_id: placeId }),
  })
  if (r.status === 201 || r.status === 200) return
  const body = await r.json().catch(() => ({}))
  throw new Error(body.detail || `提不進去（${r.status}）`)
}

export async function roll(d: Device, roundId: number): Promise<void> {
  const r = await fetch(`/api/rounds/${roundId}/roll`, { method: 'POST', headers: auth(d) })
  if (r.ok) return
  const body = await r.json().catch(() => ({}))
  throw new Error(body.detail || `擲不出來（${r.status}）`)
}

export type Pooled = { place_id: number; name: string }

/** The four event shapes as the server actually publishes them, captured off the wire rather than
 *  read off the router — `round_opened` nests its payload under `round`, `pooled` under `place`,
 *  and `closed` under `result`, and none of those is guessable from the others. */
export type StreamEvent =
  | { type: 'snapshot'; open_round: OpenRound | null; last_result: { round_id: number } | null }
  | { type: 'round_opened'; round: OpenRound }
  | { type: 'pooled'; round_id: number; place: Pooled }
  | { type: 'closed'; result: { round_id: number } }

export type OpenRound = {
  round_id: number
  target_hour: string
  target_hour_typed: boolean
  opened_at: string
  pool: Pooled[]
}

/**
 * Subscribe to the circle. **D56: the snapshot IS the stream's first event** — there is no
 * endpoint beside it, so a screen that connects is a screen that already knows the state, and a
 * reconnect resyncs by the same code path rather than by a second one that can drift.
 *
 * Returns an abort function. The reader is deliberately tolerant of a partial frame: SSE arrives
 * as bytes and a `data:` line can be split across chunks, so the buffer is drained on blank lines
 * rather than per chunk — the bug that shape hides is a JSON parse error under load and never in
 * a demo.
 */
export function subscribe(
  d: Device,
  onEvent: (e: StreamEvent) => void,
  onError?: (m: string) => void,
): () => void {
  const ac = new AbortController()
  void (async () => {
    try {
      const r = await fetch(`/api/circles/${encodeURIComponent(d.circle)}/stream`, {
        headers: auth(d),
        signal: ac.signal,
      })
      if (!r.ok || !r.body) throw new Error(`連不上即時更新（${r.status}）`)
      const reader = r.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let cut: number
        while ((cut = buffer.indexOf('\n\n')) !== -1) {
          const frame = buffer.slice(0, cut)
          buffer = buffer.slice(cut + 2)
          for (const line of frame.split('\n')) {
            if (!line.startsWith('data:')) continue
            try {
              onEvent(JSON.parse(line.slice(5).trim()))
            } catch {
              // A frame we cannot parse is dropped rather than taking the stream down: the next
              // event resyncs, and D56's snapshot means a reconnect is always authoritative.
            }
          }
        }
      }
    } catch (e) {
      if (!ac.signal.aborted) onError?.((e as Error).message || '即時更新斷了')
    }
  })()
  return () => ac.abort()
}
