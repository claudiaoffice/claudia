// The actual file Neutralino's `injectScript` loads into the externally-hosted creates page (D159 option 2). Not
// unit-tested itself -- it is a few lines of real `Neutralino`/`window` wiring, calling straight into
// installBridge() (page-bridge.ts), which is the layer the tests in tests/page-bridge.test.ts exercise. Bundled
// by `npm run build:inject` (esbuild, one dependency-free IIFE: `injectScript` runs before any <script type=module>
// tags do, so this cannot rely on ES module resolution being set up yet).
//
// Which app's generated menu to use is fixed at bundle time via esbuild's --define (see package.json): this file
// is built once per packaged app, not chosen at runtime, since a given .app bundle only ever shows one app
// (D113's "an app is an entry point... under clients/<os>/apps/<app>/").

import { installBridge, type NeutralinoLike, type WindowLike } from './page-bridge.js'
import { installFileDialogBridge, type FileDialogNeutralino } from './file-dialog.js'
import type { ManifestListing } from './menu.js'

declare const __CLAUDIA_APP_TITLE__: string
declare const __CLAUDIA_MENU_JSON__: string

declare global {
  interface Window {
    Neutralino?: NeutralinoLike & FileDialogNeutralino
  }
}

function boot(): void {
  const neutralino = window.Neutralino
  if (!neutralino) {
    // Loaded in a plain browser tab, or Neutralino's own globals were not injected into this external page --
    // exactly the D159 unknown this package's README calls out. shell-bridge.ts still works without a shell
    // (it just never becomes `ready`), so there is nothing to do but leave the page to run that way.
    console.warn('[claudia-bridge] window.Neutralino is not present; running without a native shell')
    return
  }
  const listing = JSON.parse(__CLAUDIA_MENU_JSON__) as ManifestListing
  installBridge(neutralino, window as unknown as WindowLike, listing, __CLAUDIA_APP_TITLE__)
  installFileDialogBridge(neutralino, document)
}

boot()
