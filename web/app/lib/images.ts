// Reading a picture file for an `add_image`-like method, and showing a decoded `ImageAsset` back: shared by every
// app that can put a picture on a document (creates today; composes and computes the same way, E10.8). No format
// sniffing or dimension reading here — the server decodes and validates the bytes (`claudia_core.decode_image`);
// a browser reads a chosen file's own width/height for free once it is shown as a preview `<img>`, so there is
// nothing for this module to duplicate beyond getting the bytes across the wire and back.

/** Mirrors `claudia_core.MAX_IMAGE_BYTES`: a quick client-side check so a file that cannot win is not uploaded for
 * nothing. The server enforces the real limit; this is only a courtesy. */
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024

/** What `claudia_core.decode_image` reads (`claudia_core.SUPPORTED_IMAGE_FORMATS`), as a file input's `accept`. */
export const IMAGE_FILE_ACCEPT = 'image/jpeg,image/gif,image/bmp,image/svg+xml,.jpg,.jpeg,.gif,.bmp,.svg'

const IMAGE_MIME: Record<string, string> = { jpeg: 'image/jpeg', gif: 'image/gif', bmp: 'image/bmp', svg: 'image/svg+xml' }

/** Base64 of a file's bytes, the shape `add_image`'s `data` parameter (and every app's own version of it) wants. */
export async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  const CHUNK = 0x8000 // spreading the whole array into String.fromCharCode can overflow the call stack on a big file
  for (let i = 0; i < bytes.length; i += CHUNK) binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  return btoa(binary)
}

/** A `data:` URL for a decoded `ImageAsset` (the shape `images`/`slide` sends), ready for an `<img>`'s `src`. */
export function imageDataUrl(asset: { format: string; data: string }): string {
  return `data:${IMAGE_MIME[asset.format] ?? 'application/octet-stream'};base64,${asset.data}`
}

/** The exact byte count a base64 string decodes to, for showing an asset's file size (the "Properties" dialog,
 * E10.10) without carrying the original file's size across the wire separately — `data`'s own length already
 * says it. Three base64 characters decode to four bytes, minus one byte per trailing `=` of padding. */
export function imageByteSize(data: string): number {
  if (data.length === 0) return 0
  const padding = data.endsWith('==') ? 2 : data.endsWith('=') ? 1 : 0
  return (data.length / 4) * 3 - padding
}

/** A byte count as a person reads it: plain bytes below 1 KB, a whole number of KB below 1 MB, one decimal place
 * of MB above that — matching how file managers on every platform already round these, so nothing here looks
 * unusually precise or unusually vague next to them. */
export function formatByteSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
