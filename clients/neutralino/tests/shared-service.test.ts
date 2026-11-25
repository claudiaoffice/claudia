// The service of a computer, "Shared on this computer" (E8.5 part 2, D1622, D1624): found through the service file
// its installer writes, and its setup code read only by the people who may read the service's files.
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { findSharedService } from '../src/shared-service.js'
import { MACOS_HOST } from '../src/platform/macos.js'
import { WINDOWS_HOST } from '../src/platform/windows.js'

let folder: string
beforeEach(() => {
  folder = mkdtempSync(join(tmpdir(), 'claudia-service-'))
})
afterEach(() => {
  chmodSync(folder, 0o700)
  for (const inner of ['state', join('state', 'admin')]) {
    try {
      chmodSync(join(folder, inner), 0o700)
    } catch {
      // not made by this test
    }
  }
  rmSync(folder, { recursive: true, force: true })
})

function serviceFile(content: unknown): string {
  const file = join(folder, 'service.json')
  writeFileSync(file, typeof content === 'string' ? content : JSON.stringify(content))
  return file
}

function serviceState(code?: string): string {
  const state = join(folder, 'state')
  mkdirSync(join(state, 'admin'), { recursive: true })
  if (code !== undefined) writeFileSync(join(state, 'admin', 'setup-code'), `${code}\n`)
  return state
}

describe('findSharedService', () => {
  it('finds the service where its service file says it is', () => {
    const found = findSharedService(serviceFile({ origin: 'http://127.0.0.1:8765', state: serviceState() }))
    expect(found?.origin).toBe('http://127.0.0.1:8765')
  })

  it('finds none without a service file, and says nothing: the service is not installed, or was removed', () => {
    const said: string[] = []
    expect(findSharedService(join(folder, 'service.json'), (line) => said.push(line))).toBeNull()
    expect(said).toEqual([])
  })

  it.each([
    ['not JSON', '{ not json'],
    ['no origin', { state: '/x' }],
    ['another computer', { origin: 'http://192.0.2.7:8765', state: '/x' }],
    ['a name that only starts like this computer', { origin: 'http://127.0.0.1.example.org:8765', state: '/x' }],
    ['not http', { origin: 'ftp://127.0.0.1:8765', state: '/x' }],
    ['a path in the origin', { origin: 'http://127.0.0.1:8765/admin', state: '/x' }],
    ['no state folder', { origin: 'http://127.0.0.1:8765' }],
  ])('finds none in a service file that is broken or points away from this computer, and logs it: %s', (_name, content) => {
    const said: string[] = []
    expect(findSharedService(serviceFile(content), (line) => said.push(line))).toBeNull()
    expect(said).toEqual([expect.stringContaining(join(folder, 'service.json'))])
  })

  it('reads the setup code for a person who may read the service\'s files', () => {
    const found = findSharedService(serviceFile({ origin: 'http://127.0.0.1:8765', state: serviceState('K7QM-4TXR-92HB') }))
    expect(found?.setupCode()).toEqual({ kind: 'code', code: 'K7QM-4TXR-92HB' })
  })

  it('says there is none once the service has an administrator', () => {
    const found = findSharedService(serviceFile({ origin: 'http://127.0.0.1:8765', state: serviceState() }))
    expect(found?.setupCode()).toEqual({ kind: 'none' })
  })

  it.skipIf(process.platform === 'win32' || process.getuid?.() === 0)('says that she may not read it when the service\'s files are closed to her', () => {
    const state = serviceState('K7QM-4TXR-92HB')
    chmodSync(join(state, 'admin'), 0o000)
    const found = findSharedService(serviceFile({ origin: 'http://127.0.0.1:8765', state }))
    expect(found?.setupCode()).toEqual({ kind: 'may not' })
  })

  it('reads the code anew every time: the service may have been started again', () => {
    const state = serviceState('K7QM-4TXR-92HB')
    const found = findSharedService(serviceFile({ origin: 'http://127.0.0.1:8765', state }))
    writeFileSync(join(state, 'admin', 'setup-code'), '2W9C-HQ4M-7KXA\n')
    expect(found?.setupCode()).toEqual({ kind: 'code', code: '2W9C-HQ4M-7KXA' })
  })
})

describe('where each system keeps the service file', () => {
  it('is in the Mac\'s folder for all people, and in Windows\' ProgramData', () => {
    expect(MACOS_HOST.sharedServiceFile({})).toBe('/Library/Application Support/Claudia/service.json')
    expect(WINDOWS_HOST.sharedServiceFile({ ProgramData: 'D:\\Data' })).toBe(join('D:\\Data', 'Claudia', 'service.json'))
    expect(WINDOWS_HOST.sharedServiceFile({})).toBe(join('C:\\ProgramData', 'Claudia', 'service.json'))
  })
})
