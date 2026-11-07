// Saving something the server gave us as a file on this computer. A plain helper (not part of any session) because
// nothing here needs a connection: by the time a dialog calls this, the data is already in hand.

/** Offer `data` to the browser as a file called `filename`, pretty-printed JSON. */
export function downloadJSON(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}
