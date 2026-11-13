// The Random generator (E6.22, D292, D293): the distributions RANDOM draws from, what each needs, and the checks and
// pictures the dialog works with. The numbers themselves come from the server (`random_preview`): the same
// quantile functions every RANDOM cell uses, so a preview is not an approximation of the cell.

export interface ParamSpec {
  key: string
  default: number
  /** The slider's range and step; the number field next to it takes any value. */
  slider: [min: number, max: number, step: number]
}

export interface DistSpec {
  id: string
  continuous: boolean
  /** Excel has a formula for it; without one the file holds the value (D292). */
  excel: boolean
  params: ParamSpec[]
}

const p = (key: string, value: number, min: number, max: number, step: number): ParamSpec => ({ key, default: value, slider: [min, max, step] })

/** The twelve distributions of `RANDOM`, in the order the dialog lists them. */
export const DISTRIBUTIONS: DistSpec[] = [
  { id: 'uniform', continuous: true, excel: true, params: [p('low', 0, -1000, 1000, 1), p('high', 100, -1000, 1000, 1)] },
  { id: 'normal', continuous: true, excel: true, params: [p('mean', 1000, 0, 2000, 10), p('spread', 150, 1, 1000, 1)] },
  { id: 'lognormal', continuous: true, excel: true, params: [p('mean of ln', 7, 0, 12, 0.1), p('spread of ln', 0.4, 0.01, 3, 0.01)] },
  { id: 'triangular', continuous: true, excel: false, params: [p('low', 9, 0, 100, 0.5), p('mode', 11, 0, 100, 0.5), p('high', 14, 0, 100, 0.5)] },
  { id: 'pert', continuous: true, excel: true, params: [p('low', 9, 0, 100, 0.5), p('mode', 11, 0, 100, 0.5), p('high', 14, 0, 100, 0.5)] },
  { id: 'exponential', continuous: true, excel: true, params: [p('rate', 0.1, 0.01, 2, 0.01)] },
  { id: 'weibull', continuous: true, excel: true, params: [p('shape', 2, 0.1, 10, 0.1), p('scale', 1000, 1, 5000, 10)] },
  { id: 'beta', continuous: true, excel: true, params: [p('alpha', 2, 0.1, 20, 0.1), p('beta', 5, 0.1, 20, 0.1)] },
  { id: 'gamma', continuous: true, excel: true, params: [p('shape', 2, 0.1, 20, 0.1), p('scale', 500, 1, 5000, 10)] },
  { id: 'binomial', continuous: false, excel: true, params: [p('trials', 20, 1, 200, 1), p('chance', 0.3, 0, 1, 0.01)] },
  { id: 'poisson', continuous: false, excel: false, params: [p('mean', 4, 0.1, 50, 0.1)] },
  { id: 'discrete', continuous: false, excel: true, params: [] },
]

export function distribution(id: string): DistSpec {
  const found = DISTRIBUTIONS.find((d) => d.id === id)
  if (!found) throw new Error(`there is no distribution ${id}`)
  return found
}

export function defaultParams(spec: DistSpec): number[] {
  return spec.params.map((x) => x.default)
}

/** Why the numbers are not usable, as a code the dialog puts into words, or `null` when they are. The server checks
 * again; this is so the dialog can say it before asking. */
export type Problem = 'number' | 'positive' | 'order' | 'chance' | 'integer' | 'limits'

const POSITIVE: Record<string, number[]> = {
  normal: [1],
  lognormal: [1],
  exponential: [0],
  weibull: [0, 1],
  beta: [0, 1],
  gamma: [0, 1],
  poisson: [0],
}

export function validate(spec: DistSpec, params: number[], low: number | null, high: number | null): Problem | null {
  if (params.some((x) => !Number.isFinite(x))) return 'number'
  if ((POSITIVE[spec.id] ?? []).some((i) => !(params[i]! > 0))) return 'positive'
  if (spec.id === 'uniform' && !(params[0]! < params[1]!)) return 'order'
  if ((spec.id === 'triangular' || spec.id === 'pert') && !(params[0]! <= params[1]! && params[1]! <= params[2]! && params[0]! < params[2]!)) return 'order'
  if (spec.id === 'binomial') {
    if (!Number.isInteger(params[0]!) || params[0]! < 1) return 'integer'
    if (params[1]! < 0 || params[1]! > 1) return 'chance'
  }
  if (low !== null && high !== null && !(low < high)) return 'limits'
  return null
}

/** What to ask `random_preview` for: the cut only when it is on (and the distribution can be cut). */
export function previewRequest(
  id: string,
  params: number[],
  cut: { on: boolean; low: number | null; high: number | null },
): { distribution: string; params: number[]; low?: number | null; high?: number | null } {
  const request: { distribution: string; params: number[]; low?: number | null; high?: number | null } = { distribution: id, params }
  if (cut.on && distribution(id).continuous) {
    request.low = cut.low
    request.high = cut.high
  }
  return request
}

/** The values and weights typed for a discrete distribution, one pair a line ("10 1", "20, 3"; a value alone has the
 * weight 1), as the flat list `RANDOM("discrete", …)` takes; or the number of the first line that cannot be read. */
export function parseDiscrete(text: string): number[] | { line: number } {
  const flat: number[] = []
  const lines = text.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!.trim()
    if (line === '') continue
    const words = line.split(/[\s,;]+/)
    const [value, weight] = [Number(words[0]), words.length === 1 ? 1 : Number(words[1])]
    if (words.length > 2 || !Number.isFinite(value) || !Number.isFinite(weight) || weight < 0) return { line: i + 1 }
    flat.push(value, weight)
  }
  return flat.length === 0 ? { line: 1 } : flat
}

export interface Bin {
  from: number
  to: number
  count: number
}

/** The draws counted into `bins` equal bins from the least to the greatest; draws that are all alike are one bin. */
export function histogram(draws: number[], bins: number): Bin[] {
  if (draws.length === 0) return []
  const low = Math.min(...draws)
  const high = Math.max(...draws)
  if (low === high) return [{ from: low, to: high, count: draws.length }]
  const width = (high - low) / bins
  const out: Bin[] = Array.from({ length: bins }, (_, i) => ({ from: low + i * width, to: low + (i + 1) * width, count: 0 }))
  out[bins - 1]!.to = high
  for (const x of draws) out[Math.min(bins - 1, Math.floor((x - low) / width))]!.count++
  return out
}

/** The least and greatest value of the middle `mass` of the draws (0.68: "68 % of the values fall between"). */
export function spanOf(draws: number[], mass: number): [number, number] | null {
  if (draws.length === 0) return null
  const sorted = [...draws].sort((a, b) => a - b)
  const at = (share: number) => sorted[Math.min(sorted.length - 1, Math.floor(share * sorted.length))]!
  return [at((1 - mass) / 2), at((1 + mass) / 2)]
}
