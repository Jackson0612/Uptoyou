/** The weather endpoint's shape, as the API actually answers it. */
export type Weather = {
  kind: 'forecast' | 'observation' | 'absent'
  township_code: string
  township_name: string
  hour: string
  measures: Record<string, string | null>
  absence_reason?: string
  source?: { dataset_id: string; detected_at: string; time_label: string }
}

/** The twelve 臺北市 townships, matching the `township_station` seed. */
export const TOWNSHIPS = [
  { code: '63000010', name: '松山區' }, { code: '63000020', name: '信義區' },
  { code: '63000030', name: '大安區' }, { code: '63000040', name: '中山區' },
  { code: '63000050', name: '中正區' }, { code: '63000060', name: '大同區' },
  { code: '63000070', name: '萬華區' }, { code: '63000080', name: '文山區' },
  { code: '63000090', name: '南港區' }, { code: '63000100', name: '內湖區' },
  { code: '63000110', name: '士林區' }, { code: '63000120', name: '北投區' },
] as const

/** The hour the API keys on, in Taipei time regardless of the reader's clock. */
export function currentTaipeiHour(now = new Date()): string {
  const taipei = new Date(now.getTime() + (8 * 60 + now.getTimezoneOffset()) * 60000)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${taipei.getFullYear()}-${pad(taipei.getMonth() + 1)}-${pad(taipei.getDate())}`
       + `T${pad(taipei.getHours())}:00:00+08:00`
}

export async function fetchWeather(township: string): Promise<Weather> {
  const hour = currentTaipeiHour()
  const r = await fetch(
    `/api/weather?township=${encodeURIComponent(township)}&hour=${encodeURIComponent(hour)}`,
    { cache: 'no-store' },
  )
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error(body.detail || `讀取失敗（${r.status}）`)
  }
  return r.json()
}

/**
 * `?? null` rather than a key check, and the distinction is load-bearing: the forecast half
 * carries `weather_code` with a value or with null, and the observation half has no code element
 * at all so the key is absent entirely. Reading it as `'weather_code' in measures` would be right
 * for two of the three states and wrong for the one that only appears when the read path falls
 * back — which is to say, not on any day you happened to be looking.
 */
export function conditionCode(w: Weather | null): string | null {
  return w?.measures?.weather_code ?? null
}

/** A dash covers three different situations and the screen deliberately does not distinguish
 *  them: no reading at all, a measure this dataset never carries, and a measure published null.
 *  "CWA left this field out of the 03:00 publication" is not a sentence someone deciding on
 *  lunch has any use for. */
export function measure(w: Weather | null, name: string): string {
  return (w && w.measures[name]) || '—'
}

/**
 * When this reading was fetched, in Taipei, as the approved page words it: 「今天 14:00 取得」.
 *
 * **It is a separate fact from the hour the reading is FOR, and the approved page shows both.**
 * `hour` says which hour the forecast describes; this says when we went and got it. A person
 * reading 「13:00 · 預報」 cannot tell whether that forecast was published minutes or a day ago,
 * and D34's whole argument is that the age of a reading is part of the reading.
 *
 * 「今天」 only when the fetch falls on today's Taipei date — otherwise the date is shown, because
 * 「今天」 on a stale reading is exactly the wrong reassurance.
 */
export function fetchedLabel(w: Weather | null, now = new Date()): string {
  const at = w?.source?.detected_at
  if (!at) return ''
  const shift = (d: Date) => new Date(d.getTime() + (8 * 60 + d.getTimezoneOffset()) * 60000)
  const t = shift(new Date(at))
  const today = shift(now)
  const pad = (n: number) => String(n).padStart(2, '0')
  const clock = `${pad(t.getHours())}:${pad(t.getMinutes())}`
  const sameDay = t.getFullYear() === today.getFullYear()
    && t.getMonth() === today.getMonth()
    && t.getDate() === today.getDate()
  return sameDay ? `今天 ${clock} 取得` : `${t.getMonth() + 1}/${t.getDate()} ${clock} 取得`
}
