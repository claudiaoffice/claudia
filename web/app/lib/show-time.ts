// Planned times (D343) as people say and read them: `2` is two minutes, `2:30` two and a half, `90s` ninety seconds.
// Whole seconds in the document, from one second to a day (the server's own limits, `MAX_SLIDE_SECONDS`).

export const MAX_SECONDS = 86400

/** The chips offered for a slide: 1, 2, 3, 5 and 10 minutes. */
export const PLAN_CHIPS = [60, 120, 180, 300, 600]

/** `2:05`, `1:02:05` for an hour or more; whole seconds. */
export function formatTime(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const two = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`
}

const UNITS: Record<string, number> = { h: 3600, m: 60, s: 1 }

/** What a person typed as whole seconds, or null for something that is no time. A bare number is minutes (a
 * comma or a point makes it a fraction of one); `m:ss` and `h:mm:ss` are clock times; `90s`, `2m`, `1h` and
 * `1m30s` say their units. Zero, and more than a day, are no time. */
export function parseTime(text: string): number | null {
  const t = text.trim().toLowerCase().replace(/\s+/g, '')
  let seconds: number | null = null
  let found: RegExpExecArray | null
  if ((found = /^(\d+)([.,]\d+)?(?:min)?$/.exec(t))) {
    seconds = Math.round(Number(`${found[1]}${(found[2] ?? '').replace(',', '.')}`) * 60)
  } else if ((found = /^(?:(\d+):)?(\d{1,2}):(\d{2})$/.exec(t))) {
    const [h, m, s] = [Number(found[1] ?? 0), Number(found[2]), Number(found[3])]
    if (m >= 60 && found[1] !== undefined) return null
    if (s >= 60) return null
    seconds = h * 3600 + m * 60 + s
  } else if (/^(?:\d+[hms])+$/.test(t)) {
    const seen = new Set<string>()
    seconds = 0
    for (const part of t.matchAll(/(\d+)([hms])/g)) {
      if (seen.has(part[2]!)) return null
      seen.add(part[2]!)
      seconds += Number(part[1]) * UNITS[part[2]!]!
    }
  }
  return seconds !== null && seconds >= 1 && seconds <= MAX_SECONDS ? seconds : null
}

/** One click of − or +: 30 seconds up to two minutes, a minute beyond; − never goes below 30 seconds or takes a plan
 * away (that is Clear), and + on no plan starts at 30 seconds. */
export function stepTime(seconds: number | null, direction: 1 | -1): number | null {
  if (seconds === null) return direction > 0 ? 30 : null
  const step = (direction > 0 ? seconds >= 120 : seconds > 120) ? 60 : 30
  const next = seconds + direction * step
  return Math.min(MAX_SECONDS, Math.max(30, next))
}
