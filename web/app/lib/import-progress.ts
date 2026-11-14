// The one progress bar of an import (sheet 11, as the owner simplified it): three parts in one bar, for sending the
// file, reading it on the server and opening the new document. Sending is measured (the browser counts the bytes);
// reading and opening are not, so the part being done moves instead of showing a made-up amount.
import { translate as t } from './i18n'

export type ImportPhase = 'sending' | 'sent' | 'reading' | 'opening'

export interface ImportBar {
  /** How full each third is (0 to 1), or 'busy' for the one being done that cannot be measured. */
  parts: [number, number | 'busy', number | 'busy']
  /** Which third is being done (its label is the one in bold). */
  now: 0 | 1 | 2
  /** For `aria-valuenow`: the whole bar in percent, or `null` while it cannot be measured. */
  value: number | null
  /** For `aria-valuetext` and the line under the bar. */
  text: string
}

export function importBar(phase: ImportPhase, sent: number): ImportBar {
  const fraction = Math.min(1, Math.max(0, sent))
  switch (phase) {
    case 'sending':
      return {
        parts: [fraction, 0, 0],
        now: 0,
        value: Math.round((fraction * 100) / 3),
        text: t('Sending {percent}%', { percent: Math.round(fraction * 100) }),
      }
    case 'sent':
      return { parts: [1, 0, 0], now: 0, value: 33, text: t('Sent') }
    case 'reading':
      return { parts: [1, 'busy', 0], now: 1, value: null, text: t('Reading') }
    case 'opening':
      return { parts: [1, 1, 'busy'], now: 2, value: null, text: t('Opening') }
  }
}
