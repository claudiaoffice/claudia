/**
 * Canonical JSON: sorted keys, no whitespace, integers only. Two equal layouts give the same text, so its SHA-256 is a
 * fingerprint that can be compared across machines and engines.
 *
 * @module
 */

/** The canonical text of `value`; `TypeError` for a float, a non-finite number or a value JSON cannot hold. */
export function canonicalJson(value: unknown): string {
  if (value === null) return 'null'
  switch (typeof value) {
    case 'number':
      if (!Number.isSafeInteger(value)) throw new TypeError(`canonicalJson: not a safe integer: ${value}`)
      return String(value)
    case 'string':
      return JSON.stringify(value)
    case 'boolean':
      return value ? 'true' : 'false'
    case 'object': {
      if (Array.isArray(value)) return '[' + value.map(canonicalJson).join(',') + ']'
      if (value instanceof Uint8Array) throw new TypeError('canonicalJson: bytes are not JSON')
      const keys = Object.keys(value as object).filter((k) => (value as Record<string, unknown>)[k] !== undefined).sort()
      return '{' + keys.map((k) => JSON.stringify(k) + ':' + canonicalJson((value as Record<string, unknown>)[k])).join(',') + '}'
    }
    default:
      throw new TypeError(`canonicalJson: cannot hold ${typeof value}`)
  }
}
