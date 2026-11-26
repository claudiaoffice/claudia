// The Mac's own ways for an installed app (E8.5, D1626): where its window runs from, and that the Neutralino inside the
// app is started as it is.
import { mkdtempSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { getIdentity } from '../../src/identity.js'
import { MACOS_HOST } from '../../src/platform/macos.js'
import { WINDOWS_HOST } from '../../src/platform/windows.js'

describe('MACOS_HOST', () => {
  it("runs an installed app's window from her Caches, which has no space in its path", () => {
    expect(MACOS_HOST.runFolder('composes', {}, '/Users/anna')).toBe('/Users/anna/Library/Caches/Claudia/run/composes')
  })

  it('starts the Neutralino inside an installed app as it is, and writes nothing next to it', () => {
    const app = mkdtempSync(join(tmpdir(), 'installed-'))
    try {
      const binary = join(app, 'claudia creates.app', 'Contents', 'MacOS', 'neutralino')
      expect(MACOS_HOST.windowBinary(app, binary, getIdentity('creates'), true)).toEqual({ binary })
      expect(readdirSync(app)).toEqual([])
    } finally {
      rmSync(app, { recursive: true, force: true })
    }
  })

  it('links node into the run folder, which a Mac needs for want of short names', () => {
    expect(MACOS_HOST.linkNodeIntoRun).toBe(true)
    expect(WINDOWS_HOST.linkNodeIntoRun).toBe(false)
  })
})

describe('WINDOWS_HOST.runFolder', () => {
  it('is in Claudia of her local application data, as before', () => {
    expect(WINDOWS_HOST.runFolder('creates', { LOCALAPPDATA: 'D:\\Local' }, 'C:\\Users\\me')).toBe(join('D:\\Local', 'Claudia', 'run', 'creates'))
  })
})
