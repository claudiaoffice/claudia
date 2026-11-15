// Saving something the server gave us as a file on this computer. A plain helper (not part of any session) because
// nothing here needs a connection: by the time a dialog calls this, the data is already in hand.
//
// In a browser tab the file is offered as a download: the browser saves it where it saves downloads, and shows that.
// In a desktop window the shell asks where to save it, with its own Save dialog, and says where it went (D501); a web
// view there would put it into some folder without a word.
import { currentShell, type SaveOutcome } from './shell-bridge'

/** What became of a file: `downloaded` (a browser tab: the browser has it), `saved` to `path` (a desktop window), or
 * `cancelled` (the person closed the Save dialog). An `Error` when the shell could not write it. */
export type Saved = { kind: 'downloaded' } | SaveOutcome

/** Offer `blob` to the browser as a file called `filename`, then release the object URL. */
function offer(filename: string, blob: Blob): void {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}

/** Save `blob` as `filename` on this computer: through the shell's Save dialog in a desktop window, as a download in a
 * browser tab. */
export async function saveBlob(filename: string, blob: Blob): Promise<Saved> {
  const shell = currentShell()
  if (shell?.handlesFiles) return shell.saveFile(filename, blob)
  offer(filename, blob)
  return { kind: 'downloaded' }
}

/** Save `data` as a file called `filename`, pretty-printed JSON. */
export function downloadJSON(filename: string, data: unknown): Promise<Saved> {
  return saveBlob(filename, new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
}

/** Save `text` as a file called `filename` (e.g. Markdown). */
export function downloadText(filename: string, text: string, mimeType = 'text/plain'): Promise<Saved> {
  return saveBlob(filename, new Blob([text], { type: mimeType }))
}

/** Save base64 `data` (as `exportOffice` returns it) as a file called `filename`. */
export function downloadBase64(filename: string, mimeType: string, data: string): Promise<Saved> {
  const raw = atob(data)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  return saveBlob(filename, new Blob([bytes], { type: mimeType }))
}
