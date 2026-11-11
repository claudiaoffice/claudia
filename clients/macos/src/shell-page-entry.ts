// The wiring of the shell page to the real browser and the real Neutralino (the logic is in shell-page.ts and is
// tested with fakes). tools/build-shell.mjs bundles this, with one app's generated menu, into
// apps/<app>/shell/shell.js, which apps/<app>/index.html loads after `js/neutralino.js`.

import { getIdentity, type App } from './identity.js'
import { buildMainMenu, type ManifestListing } from './menu.js'
import { ShellPage, type FrameLike, type NeutralinoLike, type StatusView } from './shell-page.js'

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id)
  if (found === null) throw new Error(`the page has no #${id}`)
  return found as T
}

/** The overlay of index.html: a title and a few lines, in red when something went wrong. */
function statusView(): StatusView {
  const overlay = element('status')
  const title = element('status-title')
  const details = element('status-details')
  return {
    show(text, more, error) {
      title.textContent = text
      details.textContent = more ?? ''
      overlay.classList.toggle('error', error)
      overlay.hidden = false
    },
    hide() {
      overlay.hidden = true
    },
  }
}

/** Starts the shell page for `app`. Called by the bundle's own last line. */
export function run(app: App, listing: ManifestListing, version: string): void {
  const identity = getIdentity(app)
  const neutralino = (window as unknown as { Neutralino?: NeutralinoLike }).Neutralino
  const status = statusView()
  if (neutralino === undefined) {
    // js/neutralino.js did not load: nothing here can work, and the person should be told rather than left with a blank window
    status.show(`${identity.title} cannot start`, "Neutralino's client library (js/neutralino.js) is missing. Run `npx @neutralinojs/neu update` in the app folder.", true)
    return
  }
  const page = new ShellPage({
    app,
    version,
    menu: buildMainMenu(listing, identity.title),
    neutralino,
    frame: element<HTMLIFrameElement>('frame') as unknown as FrameLike,
    status,
    onWindowMessage: (listener) => window.addEventListener('message', (event) => listener(event)),
    locale: navigator.language || undefined,
    log: (message) => console.log(`[claudia shell] ${message}`),
  })
  page.start().catch((problem: unknown) => {
    console.error('[claudia shell]', problem)
    status.show(`${identity.title} cannot start`, String((problem as Error)?.message ?? problem), true)
  })
}
