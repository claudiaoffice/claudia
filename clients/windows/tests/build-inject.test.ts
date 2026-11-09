// tools/build-inject.mjs is a top-level script (`main()` runs the moment the file is imported, with real esbuild
// and filesystem side effects) rather than a module of pure functions, so it is not imported here the way
// identity.ts/paths.ts/etc. are -- doing so would try to run a real build. This test instead pins down, in
// isolation, the one property the 2026-11-09 Windows bug report turned on, so it cannot regress silently: a
// dynamic `import()` specifier has to be a URL, and Node only accepts a few schemes for it (file:, data:, node:).
// `node:path`'s `join()` returns a bare filesystem path, which Node tolerates as an import() specifier on POSIX
// (there is no "scheme:" prefix to misread) but NOT on Windows, where an absolute path starts with a drive
// letter -- "C:\...\dist\identity.js" parses as a URL with scheme "c:", which is not on that allow-list, and
// Node throws ERR_UNSUPPORTED_ESM_URL_SCHEME. This is exactly the error the owner hit running
// `npm run build:inject` from Git Bash on a Windows VM: `tools/build-inject.mjs` passed `join(ROOT, 'dist',
// 'identity.js')` to `import()` directly. The fix (applied in that file) is `pathToFileURL(identityPath).href`
// -- Node's own documented way to turn a filesystem path into a URL dynamic import() accepts on every OS.
import { pathToFileURL } from 'node:url'
import { describe, expect, it } from 'vitest'

describe('pathToFileURL before a dynamic import() of a filesystem path', () => {
  it('a bare Windows-shaped absolute path parses as an unsupported "c:" URL scheme -- the bug itself', () => {
    const winPath = 'C:\\Users\\dev\\claudia\\clients\\windows\\dist\\identity.js'
    expect(new URL(winPath).protocol).toBe('c:')
  })

  it('pathToFileURL() turns the same path into a URL with an allowed scheme ("file:"), on any host OS', () => {
    const winPath = 'C:\\Users\\dev\\claudia\\clients\\windows\\dist\\identity.js'
    expect(new URL(pathToFileURL(winPath).href).protocol).toBe('file:')
  })

  it('also covers the ordinary POSIX path this already worked for, so the fix cannot regress Linux/macOS', () => {
    const posixPath = '/home/dev/claudia/clients/windows/dist/identity.js'
    expect(new URL(pathToFileURL(posixPath).href).protocol).toBe('file:')
  })
})
