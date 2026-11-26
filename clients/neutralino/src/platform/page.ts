// What the shell page does differently on macOS and on Windows (D660): the menu, and where the page tells a person to
// look when the core does not answer. Browser-safe: no Node import, so
// that the shell page's bundle can hold it (the core's side is src/platform/host.ts).

import type { App } from '../identity.js'
import type { ManifestAction, ManifestListing, ShellMenuItem } from '../menu.js'
import { platformId, type PlatformId } from './id.js'
import { buildMacMenu, keptOnMacFrontPage } from './macos-menu.js'
import { buildWindowsMenu, keptOnWindowsFrontPage } from './windows-menu.js'

export interface PagePlatform {
  readonly id: PlatformId
  /** The native menu of one app from its manifest; `appTitle` names the application menu where there is one. */
  buildMainMenu(listing: ManifestListing, appTitle: string): ShellMenuItem[]
  /** What the front page's short menu keeps besides the actions the manifest marks `start`. */
  keepAtStart(action: ManifestAction): boolean
  /** Where the logs are, in words, for a window whose core does not answer. */
  whereTheLogsAre(app: App): string
  /** How to see the console of the shell page itself. */
  readonly howToSeeTheConsole: string
}

export const MACOS_PAGE: PagePlatform = {
  id: 'macos',
  buildMainMenu: buildMacMenu,
  keepAtStart: keptOnMacFrontPage,
  whereTheLogsAre: (app) =>
    `Its log: ~/Library/Application Support/Claudia/${app}/state/shell.log (or shell.log in ~/Library/Application Support/Claudia).`,
  howToSeeTheConsole: 'This window is a browser too: right-click and choose Inspect to see its console.',
}

export const WINDOWS_PAGE: PagePlatform = {
  id: 'windows',
  buildMainMenu: (listing) => buildWindowsMenu(listing),
  keepAtStart: keptOnWindowsFrontPage,
  whereTheLogsAre: (app) => `Its log: %LOCALAPPDATA%\\Claudia\\${app}\\state\\shell.log (or shell.log in %LOCALAPPDATA%\\Claudia).`,
  howToSeeTheConsole: "Start it again with --debug to open the window's web inspector and see its console.",
}

/** The page platform of this build (src/platform/id.ts). */
export function pagePlatform(id: PlatformId = platformId()): PagePlatform {
  return id === 'windows' ? WINDOWS_PAGE : MACOS_PAGE
}
