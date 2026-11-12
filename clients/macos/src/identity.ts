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
}

export class UnknownAppError extends Error {
  constructor(name: string) {
    super(`there is no macOS client for '${name}' yet; available: ${APPS.join(', ')}`)
    this.name = 'UnknownAppError'
  }
}

/** The command that starts this app from a terminal or a launcher (`claudia-composes`), like the Linux client's. */
export function commandOf(identity: AppIdentity): string {
  return `claudia-${identity.name}`
}

const IDENTITIES: Readonly<Record<App, AppIdentity>> = {
  composes: {
    name: 'composes',
    title: 'Claudia Composes',
    applicationId: 'de.claudiaoffice.composes',
    model: 'claudia_composes:TextModel',
  },
  computes: {
    name: 'computes',
    title: 'Claudia Computes',
    applicationId: 'de.claudiaoffice.computes',
    model: 'claudia_computes:WorkbookModel',
  },
  creates: {
    name: 'creates',
    title: 'Claudia Creates',
    applicationId: 'de.claudiaoffice.creates',
    model: 'claudia_creates:SlideModel',
  },
}

export function isApp(value: unknown): value is App {
  return typeof value === 'string' && Object.hasOwn(IDENTITIES, value)
}

export function getIdentity(name: string): AppIdentity {
  if (!isApp(name)) throw new UnknownAppError(name)
  return IDENTITIES[name]
}

/** The app that a built file belongs to, from its place: `.../apps/<app>/ext/core.mjs` (or `.../shell/shell.js`) is
 * `<app>`. The fallback of the core when no one told it which app it is; `null` when the path says nothing. */
export function appFromPath(file: string): App | null {
  const parts = file.split(/[\\/]/)
  const index = parts.lastIndexOf('apps')
  const candidate = index >= 0 ? parts[index + 1] : undefined
  return candidate !== undefined && (APPS as readonly string[]).includes(candidate) ? (candidate as App) : null
}
