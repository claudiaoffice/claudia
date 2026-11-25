// Where the settings pages get a setup code from (SEC-12, D1372, D1373): a link from the server's log, or the desktop
// app's welcome; and when the setup page shows a field for it.
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  codeField,
  forgetSetupCode,
  mustAskAdministrator,
  onAskAdministrator,
  rememberAskAdministrator,
  normalizeSetupCode,
  onSetupCode,
  rememberedSetupCode,
  rememberSetupCode,
  takeCodeFromAddress,
} from '../app/lib/setup-code'
import { forgetBrowser, refuseEveryCall } from './refusing-browser'

function memory(): Storage {
  const items = new Map<string, string>()
  return {
    getItem: (k: string) => items.get(k) ?? null,
    setItem: (k: string, v: string) => void items.set(k, v),
    removeItem: (k: string) => void items.delete(k),
    clear: () => items.clear(),
    key: () => null,
    get length() {
      return items.size
    },
  }
}

describe('normalizeSetupCode', () => {
  it('ignores case, dashes and spaces, and reads O as 0 and I or L as 1', () => {
    expect(normalizeSetupCode(' k7qm-4txr 92hb ')).toBe('K7QM4TXR92HB')
    expect(normalizeSetupCode('oqlm-4txr-92hb')).toBe('0Q1M4TXR92HB')
    expect(normalizeSetupCode('OQIM4TXR92HB')).toBe('0Q1M4TXR92HB')
  })
})

describe('takeCodeFromAddress', () => {
  it('takes the code from #setup=… and leaves the address without it', () => {
    const replaceState = vi.fn()
    const code = takeCodeFromAddress({ pathname: '/admin', search: '', hash: '#setup=K7QM-4TXR-92HB' }, { replaceState })
    expect(code).toBe('K7QM-4TXR-92HB')
    expect(replaceState).toHaveBeenCalledWith(null, '', '/admin')
  })

  it('keeps the rest of the fragment and the query', () => {
    const replaceState = vi.fn()
    const code = takeCodeFromAddress({ pathname: '/admin/', search: '?x=1', hash: '#fonts&setup=K7QM4TXR92HB' }, { replaceState })
    expect(code).toBe('K7QM4TXR92HB')
    expect(replaceState).toHaveBeenCalledWith(null, '', '/admin/?x=1#fonts')
  })

  it('leaves an address without a code alone', () => {
    const replaceState = vi.fn()
    expect(takeCodeFromAddress({ pathname: '/admin/', search: '', hash: '#fonts' }, { replaceState })).toBeNull()
    expect(takeCodeFromAddress({ pathname: '/', search: '', hash: '' }, { replaceState })).toBeNull()
    expect(replaceState).not.toHaveBeenCalled()
  })
})

describe('remembering a code for this tab', () => {
  afterEach(forgetBrowser)

  it('keeps the code and where it came from, until it is forgotten', () => {
    const storage = memory()
    expect(rememberedSetupCode(storage)).toBeNull()
    rememberSetupCode('K7QM-4TXR-92HB', 'link', storage)
    expect(rememberedSetupCode(storage)).toEqual({ code: 'K7QM-4TXR-92HB', from: 'link' })
    rememberSetupCode('2W9C-HQ4M-7KXA', 'app', storage)
    expect(rememberedSetupCode(storage)).toEqual({ code: '2W9C-HQ4M-7KXA', from: 'app' })
    forgetSetupCode(storage)
    expect(rememberedSetupCode(storage)).toBeNull()
  })

  it('tells a page that waits for it when a code arrives', () => {
    const storage = memory()
    const heard = vi.fn()
    const stop = onSetupCode(heard)
    rememberSetupCode('2W9C-HQ4M-7KXA', 'app', storage)
    expect(heard).toHaveBeenCalledWith({ code: '2W9C-HQ4M-7KXA', from: 'app' })
    stop()
    rememberSetupCode('K7QM-4TXR-92HB', 'link', storage)
    expect(heard).toHaveBeenCalledTimes(1)
  })

  it('ignores what is not stored as it stores it, and storage that throws', () => {
    const storage = memory()
    storage.setItem('claudia.admin.setup-code', '{"code": 5}')
    expect(rememberedSetupCode(storage)).toBeNull()
    storage.setItem('claudia.admin.setup-code', '{not json')
    expect(rememberedSetupCode(storage)).toBeNull()
    refuseEveryCall()
    expect(() => rememberSetupCode('K7QM-4TXR-92HB', 'link')).not.toThrow()
    expect(rememberedSetupCode()).toEqual({ code: 'K7QM-4TXR-92HB', from: 'link' }) // kept in memory instead
    forgetSetupCode()
    expect(rememberedSetupCode()).toBeNull()
  })
})

describe('codeField', () => {
  const link = { code: 'K7QM-4TXR-92HB', from: 'link' as const }
  const app = { code: 'K7QM-4TXR-92HB', from: 'app' as const }

  it('shows no field when the server asks for no code (an older server)', () => {
    expect(codeField(false, null, 'unchecked')).toBe('none')
  })

  it('shows an empty field when the page was given no code, or the given one was refused', () => {
    expect(codeField(true, null, 'unchecked')).toBe('typed')
    expect(codeField(true, link, 'refused')).toBe('typed')
    expect(codeField(true, app, 'refused')).toBe('typed')
  })

  it('shows a code from a link filled in, and none at all for a code from the desktop app', () => {
    expect(codeField(true, link, 'unchecked')).toBe('from-link')
    expect(codeField(true, link, 'ok')).toBe('from-link')
    expect(codeField(true, app, 'unchecked')).toBe('none')
    expect(codeField(true, app, 'ok')).toBe('none')
  })
})

describe('ask an administrator of this computer (E8.5, D1624)', () => {
  it('is kept for this tab as the desktop app says it, and told to a page that waits for it', () => {
    const store = memory()
    const heard: boolean[] = []
    const stop = onAskAdministrator((ask) => heard.push(ask))
    expect(mustAskAdministrator(store)).toBe(false)
    rememberAskAdministrator(true, store)
    expect(mustAskAdministrator(store)).toBe(true)
    rememberAskAdministrator(false, store)
    expect(mustAskAdministrator(store)).toBe(false)
    stop()
    rememberAskAdministrator(true, store)
    expect(heard).toEqual([true, false])
  })
})
