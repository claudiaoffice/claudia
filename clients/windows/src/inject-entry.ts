// The actual file Neutralino's `injectScript` loads into the externally-hosted composes page (D159 option 2). Not
// unit-tested itself -- it is a few lines of real `Neutralino`/`window` wiring, calling straight into
// installBridge() (page-bridge.ts), which is the layer the tests in tests/page-bridge.test.ts exercise. Bundled by
// `npm run build:inject` (esbuild, one dependency-free IIFE: `injectScript` runs before any <script type=module>
// tags do, so this cannot rely on ES module resolution being set up yet).
//
// Which app's generated menu to use is fixed at bundle time via esbuild's --define (see package.json): this file
// is built once per packaged app, not chosen at runtime, since a given installed client only ever shows one app
// (D113's "an app is an entry point... under clients/<os>/apps/<app>/").
//
// Unlike clients/macos/src/inject-entry.ts, this file does not call installFileDialogBridge(): there is no
// file-dialog.ts in this package. The bug that workaround exists for on macOS is WKWebView-specific (WebKit shows
// no native picker for a plain `<input type="file">` unless the host app implements a WKUIDelegate method for it --
// bugs.webkit.org/show_bug.cgi?id=139745) -- WebView2 is Chromium, and Chromium has handled `<input type="file">`
// with its own native picker since long before Neutralino existed. So the expectation is that Insert Image's
// "Choose a file..." already works on Windows with no shell-side help, unlike the owner's own real-run finding on
// her Mac (notes/e0-3-neutralino-windows-macos.md, e5-11-macos-client.md's "Second run" section). **This is a
// hypothesis, not a confirmed result** -- nobody has clicked that button on a real Windows machine with this
// client yet, and clients/windows/README.md's "Not verified" says so. If it turns out WebView2 needs the same
// workaround after all, a Windows file-dialog.ts can be added the same way macOS's was: the DOM/Neutralino
// surfaces (`Neutralino.os.showOpenDialog`, `Neutralino.filesystem.readBinaryFile`) are identical between the two
// shells (notes/e0-3-neutralino-windows-macos.md §7: "File open/save dialogs are the native ones on both OSes").

import { installBridge, type NeutralinoLike, type WindowLike } from './page-bridge.js'
import type { ManifestListing } from './menu.js'

declare const __CLAUDIA_APP_TITLE__: string
declare const __CLAUDIA_MENU_JSON__: string

declare global {
  interface Window {
    Neutralino?: NeutralinoLike
  }
}

function boot(): void {
  const neutralino = window.Neutralino
  if (!neutralino) {
    // Loaded in a plain browser tab, or Neutralino's own globals were not injected into this external page --
    // exactly the question this package's README calls out as not yet re-confirmed on Windows. shell-bridge.ts
    // still works without a shell (it just never becomes `ready`), so there is nothing to do but leave the page to
    // run that way.
    console.warn('[claudia-bridge] window.Neutralino is not present; running without a native shell')
    return
  }
  const listing = JSON.parse(__CLAUDIA_MENU_JSON__) as ManifestListing
  installBridge(neutralino, window as unknown as WindowLike, listing, __CLAUDIA_APP_TITLE__)
}

boot()
