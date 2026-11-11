// What the shell page and the native core say to each other, and the names they say it under. Shared by both ends
// (core-entry.ts, the Node extension, and shell-page.ts, the page) so the two cannot drift apart. The messages
// travel through Neutralino: page -> core with `Neutralino.extensions.dispatch`, core -> page with `app.broadcast`.
// Both sides check what they receive: the core does not trust the page (a framed web app cannot reach this channel,
// but the checks cost nothing), and the page does not trust a stray broadcast.

import type { CoreMessage, CoreRequest } from './core.js'

/** The extension's id in neutralino.config.json. */
export const CORE_ID = 'de.claudiaoffice.core'
/** The event the page dispatches to the core. */
export const TO_CORE = 'claudia.core'
/** The event the core broadcasts to the page. */
export const FROM_CORE = 'claudiaCore'

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

/** Is `value` a request that the core understands? */
export function isRequest(value: unknown): value is CoreRequest {
  if (!isRecord(value)) return false
  switch (value.kind) {
    case 'start':
    case 'want_servers':
      return true
    case 'connect':
      return typeof value.address === 'string' && value.address.length <= 255
    case 'servers':
      return Array.isArray(value.servers)
    default:
      return false
  }
}

/** Is `value` a message that the page understands? */
export function isCoreMessage(value: unknown): value is CoreMessage {
  if (!isRecord(value)) return false
  switch (value.kind) {
    case 'show':
      return typeof value.origin === 'string' && value.origin.length > 0
    case 'status':
      return (
        typeof value.title === 'string' &&
        typeof value.error === 'boolean' &&
        (value.details === undefined || typeof value.details === 'string')
      )
    case 'servers':
      return Array.isArray(value.servers)
    case 'connect_failed':
      return typeof value.code === 'string' && typeof value.message === 'string'
    default:
      return false
  }
}
