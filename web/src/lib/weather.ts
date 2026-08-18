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
