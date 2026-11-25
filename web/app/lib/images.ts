// Reading a picture file for an `add_image`-like method, and showing a decoded `ImageAsset` back: shared by every
// app that can put a picture on a document (creates and computes today, E10.8/E6.17; composes the same way).
// No format sniffing or dimension reading here — the server decodes and validates the bytes
// (`claudia_core.decode_image`); a browser reads a chosen file's own width/height for free once it is shown as a
// preview `<img>`, so there is nothing for this module to duplicate beyond getting the bytes across the wire and
// back.

/** How an image object's picture got here (E10.8). `source_path` is the file's full path if it was saved on import
 * (SEC-27), the same for everyone who can open the document, and `null` if not. Shared by every app's own image object
 * (`claudia_creates.SlideObject`, `claudia_computes.SheetObject`). */
export interface ImageImport {
  asset: string
  alt: string
  imported_by: string
  imported_at: string
  source: string
  source_name: string
  source_path: string | null
}
/** A decoded picture (E10.8): `data`/`first_frame` are base64, exactly as `claudia_core.ImageAsset.to_data()`
 * sends them. `first_frame` is set only when `animated` is true. */
export interface ImageAsset {
  id: string
  format: string
  width: number
  height: number
  animated: boolean
  data: string
  first_frame: string | null
}

/** Mirrors `claudia_core.MAX_IMAGE_BYTES`: a quick client-side check so a file that cannot win is not uploaded for
 * nothing. The server enforces the real limit; this is only a courtesy. */
export const MAX_IMAGE_BYTES = 8 * 1024 * 1024

/** What `claudia_core.decode_image` reads (`claudia_core.SUPPORTED_IMAGE_FORMATS`), as a file input's `accept`. */
export const IMAGE_FILE_ACCEPT =
  'image/jpeg,image/png,image/gif,image/bmp,image/svg+xml,.jpg,.jpeg,.png,.gif,.bmp,.svg'

const IMAGE_MIME: Record<string, string> = {
  jpeg: 'image/jpeg',
  png: 'image/png',
  gif: 'image/gif',
  bmp: 'image/bmp',
  svg: 'image/svg+xml',
}

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

/** What the person told the importer about a picture they chose (`ImageImportDialog.vue`): the file's bytes, base64
 * (`fileToBase64`), what it shows, and where it came from. `sourcePath` is `null` from a plain web browser, which
 * cannot know a file's full path, and `''` when the person asked not to save it (`sourcePathToSend`). */
export interface PictureImport {
  data: string
  /** The picture's own size in pixels, as the browser read it; it is never sent, only used to cap the size it is shown at. */
  natural?: { width: number; height: number }
  alt: string
  sourceName: string
  sourcePath: string | null
  decorative?: boolean
}

/** Insert ▸ Image offers "Don't save the path" only when it knows the path: a desktop shell's Open dialog says it, a
 * plain browser never does (SEC-27). */
export function offersPathChoice(path: string | null): path is string {
  return path !== null && path !== ''
}

/** The `sourcePath` Insert ▸ Image sends: the picked file's path, unless the person ticked "Don't save the path" — then
 * an empty one, which the server keeps as none (SEC-27). A saved path is read by everyone who can open the document. */
export function sourcePathToSend(path: string | null, dontSave: boolean): string | null {
  if (path === null) return null
  return dontSave ? '' : path
}

/** The most a new picture or container takes when it is put in a document (the owner, 2026-11-19): so that an import
 * does not fill the screen or the slide by accident. A picture smaller than that is shown at its own size. */
export const NEW_OBJECT_CAP = { w: 420, h: 240 }

/** The size to put a picture of `aspect` (width / height) at: `height` high, or narrower if that would be wider than
 * `maxWidth`, and never larger than the picture itself (`natural`, in pixels). A picture keeps its own proportions —
 * the server turns down any other size, within one pixel. */
export function pictureSize(
  aspect: number,
  height: number,
  maxWidth: number,
  natural?: { width: number; height: number },
): { w: number; h: number } {
  if (natural) {
    height = Math.min(height, natural.height)
    maxWidth = Math.min(maxWidth, natural.width)
  }
  const w = Math.round(height * aspect)
  if (w <= maxWidth) return larger({ w, h: height }, aspect)
  // narrowed: the height is rounded *down* and the width then follows it, so that it is the width that is off by at most
  // half a unit (rounding the height off the width could leave a wide picture several units out)
  const h = Math.max(1, Math.floor(maxWidth / aspect))
  return larger({ w: Math.min(maxWidth, Math.round(h * aspect)), h }, aspect)
}

/** Mirrors `claudia_core.MIN_OBJECT_SIZE`: the server turns down an object narrower or lower than this. */
export const MIN_OBJECT_SIDE = 20

/** A tiny picture (an icon) is shown at the least size an object may have, with its proportions. */
function larger(size: { w: number; h: number }, aspect: number): { w: number; h: number } {
  if (size.w >= MIN_OBJECT_SIDE && size.h >= MIN_OBJECT_SIDE) return size
  const h = Math.max(MIN_OBJECT_SIDE, Math.ceil(MIN_OBJECT_SIDE / aspect))
  return { w: Math.round(h * aspect), h }
}
