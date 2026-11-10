// Saving something the server gave us as a file on this computer. A plain helper (not part of any session) because
// nothing here needs a connection: by the time a dialog calls this, the data is already in hand.

/** Offer `blob` to the browser as a file called `filename`, then release the object URL. */
function offer(filename: string, blob: Blob): void {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}

/** Offer `data` to the browser as a file called `filename`, pretty-printed JSON. */
export function downloadJSON(filename: string, data: unknown): void {
  offer(filename, new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
}

/** Offer `text` to the browser as a file called `filename` (e.g. Markdown). */
export function downloadText(filename: string, text: string, mimeType = 'text/plain'): void {
  offer(filename, new Blob([text], { type: mimeType }))
}

/** Offer base64 `data` (as `exportOffice` returns it) to the browser as a file called `filename`. */
export function downloadBase64(filename: string, mimeType: string, data: string): void {
  const raw = atob(data)
  const bytes = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i)
  offer(filename, new Blob([bytes], { type: mimeType }))
}
