// The owner's third real-run bug: clicking Insert Image's "Choose a file..." did nothing at all on her Mac --
// WKWebView (the engine Neutralino's macOS binary embeds) shows no native Open panel for `<input type="file">`
// unless the host app implements a WKUIDelegate method for it, which this generic, unmodified binary does not
// (https://bugs.webkit.org/show_bug.cgi?id=139745 is the underlying WebKit limitation; WebKitGTK, which the Linux
// client's view uses, implements a default file-chooser for the same input, which is why this was never seen
// there). web/app/components/ImageImportDialog.vue's own top comment already anticipated exactly this: "a desktop
// client that can read the real path would pass it instead" -- this is that desktop client, built the same way
// page-bridge.ts's menu adapter is: so the web app needs no change at all. A capture-phase click listener on every
// `<input type="file">` swaps the (silently broken) native picker for `Neutralino.os.showOpenDialog()` +
// `filesystem.readBinaryFile()`, then hands the result back to the input as an ordinary `File` via `DataTransfer`,
// so whatever already listens for that input's `change` event runs completely unchanged.
//
// Pure decision logic (what filter an <input accept> becomes, what MIME type a chosen path gets) is separated from
// the live DOM/Neutralino wiring the same way page-bridge.ts separates routeMenuClick from installBridge() -- only
// the pure half has a test here; `installFileDialogBridge` needs a real DOM and a real Neutralino, like
// installBridge() does (see this package's README "Not verified").

export interface OpenDialogFilter {
  name: string
  extensions: string[]
}

/** Turns an `<input accept="...">` attribute into `os.showOpenDialog`'s filter extensions. `accept` lists MIME
 * types and/or bare extensions mixed together (`web/app/lib/images.ts`'s own `IMAGE_FILE_ACCEPT` does both:
 * "image/jpeg,image/gif,image/bmp,image/svg+xml,.jpg,.jpeg,.gif,.bmp,.svg") -- `showOpenDialog`'s filters want bare
 * extensions without the leading dot, so MIME tokens are dropped and only the `.ext` tokens are kept, lower-cased
 * and deduplicated, in the order the input listed them. An `accept` with no usable extension (empty, or MIME
 * types only) returns an empty list -- the caller then asks for no filter at all, same as a plain
 * `<input type="file">` with no `accept` would show every file. */
export function parseAcceptExtensions(accept: string): string[] {
  const extensions: string[] = []
  for (const token of accept.split(',')) {
    const trimmed = token.trim()
    if (!trimmed.startsWith('.')) continue
    const ext = trimmed.slice(1).toLowerCase()
    if (ext && !extensions.includes(ext)) extensions.push(ext)
  }
  return extensions
}

/** Mirrors (does not import -- clients/macos has no dependency on web/) `web/app/lib/images.ts`'s own `IMAGE_MIME`,
 * plus `png`: that map only covers the formats `claudia_core.decode_image` accepts today, but a File's own `.type`
 * is never actually inspected downstream (`fileToBase64` just reads the bytes) -- it only has to be a File at all,
 * so a slightly wider guess here costs nothing and does not need to be kept in lockstep with the server. */
const MIME_BY_EXTENSION: Readonly<Record<string, string>> = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  bmp: 'image/bmp',
  svg: 'image/svg+xml',
  png: 'image/png',
}

/** A best-guess MIME type for the synthetic `File` a native dialog's chosen path becomes. Unknown or missing
 * extensions fall back to the generic type nothing downstream of `fileToBase64` actually inspects. */
export function guessMimeType(path: string): string {
  const dot = path.lastIndexOf('.')
  if (dot === -1) return 'application/octet-stream'
  return MIME_BY_EXTENSION[path.slice(dot + 1).toLowerCase()] ?? 'application/octet-stream'
}

/** The path's last segment -- Mac paths only ('/'-separated), all `showOpenDialog` ever returns. */
export function basename(path: string): string {
  const slash = path.lastIndexOf('/')
  return slash === -1 ? path : path.slice(slash + 1)
}

// ------------------------------------------------------------------------------------------- the live wiring

/** The slice of the real `Neutralino` global this file calls, typed by hand like page-bridge.ts's `NeutralinoLike`
 * (Neutralino ships no first-party TypeScript types) -- kept separate from that interface because inject-entry.ts
 * is the only place both are needed together (as `NeutralinoLike & FileDialogNeutralino`), and each module should
 * only type what it itself calls. */
export interface FileDialogNeutralino {
  os: {
    showOpenDialog(
      title?: string,
      options?: { filters?: OpenDialogFilter[]; multiSelections?: boolean },
    ): Promise<string[]>
  }
  filesystem: {
    readBinaryFile(path: string): Promise<ArrayBuffer>
  }
}

async function pickFiles(neutralino: FileDialogNeutralino, input: HTMLInputElement): Promise<void> {
  const extensions = parseAcceptExtensions(input.accept)
  const filters = extensions.length > 0 ? [{ name: 'Allowed files', extensions }] : undefined
  const paths = await neutralino.os.showOpenDialog(undefined, { filters, multiSelections: input.multiple })
  if (paths.length === 0) return // the person cancelled the dialog
  const files: File[] = []
  for (const path of paths) {
    const buffer = await neutralino.filesystem.readBinaryFile(path)
    files.push(new File([buffer], basename(path), { type: guessMimeType(path) }))
  }
  const transfer = new DataTransfer()
  for (const file of files) transfer.items.add(file)
  input.files = transfer.files
  input.dispatchEvent(new Event('change', { bubbles: true }))
}

/**
 * Wires the fix into the page: a capture-phase `click` listener on `doc` that catches every click on an
 * `<input type="file">` -- including a programmatic `.click()`, which still dispatches a real, capturable click
 * event, exactly how `ImageImportDialog.vue`'s "Choose a file..." button triggers its hidden input -- stops the
 * browser's own (silently broken, on this binary) attempt, and runs `pickFiles` instead.
 */
export function installFileDialogBridge(neutralino: FileDialogNeutralino, doc: Pick<Document, 'addEventListener'>): void {
  doc.addEventListener(
    'click',
    (event) => {
      const target = event.target
      if (!(target instanceof HTMLInputElement) || target.type !== 'file') return
      event.preventDefault()
      void pickFiles(neutralino, target)
    },
    { capture: true },
  )
}
