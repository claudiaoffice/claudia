// Server settings ▸ Security (D1267): how slow password hashing should be for new documents. The server measures what
// that means for its machine; this page only asks for a time and says what came out.

import { translate as t } from './i18n'
import type { KdfView } from './admin-api'

/** The range the server accepts, in seconds (`kdf_policy.py`). */
export const TARGET_MIN = 0.1
export const TARGET_MAX = 30

export type Parsed = { ok: true; value: number } | { ok: false; message: string }

/** The seconds a person typed (a decimal comma is fine), or a sentence saying what is accepted. */
export function parseTarget(text: string): Parsed {
  const value = Number(text.trim().replace(',', '.'))
  if (text.trim() === '' || !Number.isFinite(value) || value < TARGET_MIN || value > TARGET_MAX) {
    return { ok: false, message: t('Enter a number of seconds from {min} to {max}.', { min: TARGET_MIN, max: TARGET_MAX }) }
  }
  return { ok: true, value }
}

/** What the page says about the cost in force; empty for a server that keeps no documents of its own. */
export function costSentence(kdf: KdfView | null): string {
  if (kdf === null) return ''
  const memory = Math.round(kdf.memory_kib / 1024)
  if (kdf.measured) return t('New documents use {memory} MiB and {passes} passes.', { memory, passes: kdf.iterations })
  return t('Measuring this machine… New documents use {memory} MiB and {passes} passes until then.', { memory, passes: kdf.iterations })
}
