// Which operating system this build of the Neutralino client is for (D660): macOS or Windows. The two share every
// line of this package but the few in src/platform/, and this says which of those few apply.
//
// The bundles (the shell page and the core of each app, tools/build-shell.mjs) are built for one platform: esbuild
// sets CLAUDIA_PLATFORM, so a Windows build behaves like Windows wherever it runs (CI runs it on Linux). The launcher
// and the tests run from tsc's output or the sources, where nothing sets it: there the operating system decides, and
// anything that is not Windows is taken for macOS (the other POSIX system this client runs on).

export type PlatformId = 'macos' | 'windows'

export const PLATFORMS: readonly PlatformId[] = ['macos', 'windows']

declare const CLAUDIA_PLATFORM: PlatformId | undefined

/** The platform of this build, else of the operating system it runs on (`nodePlatform` is `process.platform`). */
export function platformId(nodePlatform: string | undefined = globalThis.process?.platform): PlatformId {
  if (typeof CLAUDIA_PLATFORM !== 'undefined') return CLAUDIA_PLATFORM
  return nodePlatform === 'win32' ? 'windows' : 'macos'
}

/** A platform named on a command line (`--platform windows`); refuses anything else. */
export function parsePlatform(name: string): PlatformId {
  if ((PLATFORMS as readonly string[]).includes(name)) return name as PlatformId
  throw new Error(`no such platform '${name}'; available: ${PLATFORMS.join(', ')}`)
}
