// Which Claudia app this shell can show: its bundle id, display title, and the server model behind it. No
// Neutralino import here, the same discipline clients/linux/src/claudia_shell_gtk/manifest.py and
// clients/macos/src/identity.ts hold, so this stays testable without a window.
//
// Kept in step with clients/linux/src/claudia_shell_gtk/identity.py's `_APPS` table and
// clients/macos/src/identity.ts's `IDENTITIES` by hand: there is no shared source for the three (the same gap
// D28's own note names for the About dialog's links). A change to one application id or model name needs the
// same change made in all three files.

export type App = 'composes' | 'computes' | 'creates'

export const APPS: readonly App[] = ['composes', 'computes', 'creates']

export interface AppIdentity {
  /** Short name used in paths and the generated menu file name, e.g. `menu.composes.json`. */
  readonly name: App
  /** What the person sees, e.g. in the window title. */
  readonly title: string
  /** The bundle id (also this app's icon and, once packaged, its installer's product id). */
  readonly applicationId: string
  /** The server model the local server loads for this app (`module:Class`), passed to `claudia_server --model`. */
  readonly model: string
  /** Does `apps/<name>/` hold this app's icon and packaging metadata yet? Only `composes` does, for this first
   * version (this epic's scope cut for Windows — the same cut E5.11 made for computes/creates on macOS, just with
   * a different app chosen first: the Linux shell started with composes (E5.1), macOS started with creates
   * (E5.11); nothing says the OSes have to agree on which app comes first). */
  readonly packaged: boolean
}

export class UnknownAppError extends Error {
  constructor(name: string) {
    super(`there is no Windows client for '${name}' yet; available: ${APPS.join(', ')}`)
    this.name = 'UnknownAppError'
  }
}

const IDENTITIES: Readonly<Record<App, AppIdentity>> = {
  composes: {
    name: 'composes',
    title: 'Claudia Composes',
    applicationId: 'de.claudiaoffice.composes',
    model: 'claudia_composes:TextModel',
    packaged: true,
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
    packaged: false,
  },
}

export function getIdentity(name: App): AppIdentity {
  const identity = IDENTITIES[name]
  if (!identity) throw new UnknownAppError(name)
  return identity
}
