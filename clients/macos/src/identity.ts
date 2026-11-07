// Which Claudia app this shell can show: its bundle id, display title, and the server model behind it. No
// Neutralino import here, the same discipline clients/linux/src/claudia_shell_gtk/manifest.py holds for GTK, so
// this stays testable without a window.
//
// Kept in step with clients/linux/src/claudia_shell_gtk/identity.py's `_APPS` table by hand: there is no shared
// source for the two (the same gap D28's own note names for the About dialog's links). A change to one application
// id or model name needs the same change made in both files.

export type App = 'composes' | 'computes' | 'creates'

export const APPS: readonly App[] = ['composes', 'computes', 'creates']

export interface AppIdentity {
  /** Short name used in paths and the generated menu file name, e.g. `menu.creates.json`. */
  readonly name: App
  /** What the person sees, e.g. in the macOS application menu and the window title. */
  readonly title: string
  /** The bundle id (also this app's icon and, once packaged, its `.app` directory name). */
  readonly applicationId: string
  /** The server model the local server loads for this app (`module:Class`), passed to `claudia_server --model`. */
  readonly model: string
  /** Does `apps/<name>/` hold this app's icon and packaging metadata yet? Only `creates` does, for this first
   * version (E5.11's scope cut — the same cut E5.1 made for computes/creates on Linux). */
  readonly packaged: boolean
}

export class UnknownAppError extends Error {
  constructor(name: string) {
    super(`there is no macOS client for '${name}' yet; available: ${APPS.join(', ')}`)
    this.name = 'UnknownAppError'
  }
}

const IDENTITIES: Readonly<Record<App, AppIdentity>> = {
  composes: {
    name: 'composes',
    title: 'Claudia Composes',
    applicationId: 'de.claudiaoffice.composes',
    model: 'claudia_composes:TextModel',
    packaged: false,
  },
  computes: {
    name: 'computes',
    title: 'Claudia Computes',
    applicationId: 'de.claudiaoffice.computes',
    model: 'claudia_computes:WorkbookModel',
    packaged: false,
  },
  creates: {
    name: 'creates',
    title: 'Claudia Creates',
    applicationId: 'de.claudiaoffice.creates',
    model: 'claudia_creates:SlideModel',
    packaged: true,
  },
}

export function getIdentity(name: App): AppIdentity {
  const identity = IDENTITIES[name]
  if (!identity) throw new UnknownAppError(name)
  return identity
}
