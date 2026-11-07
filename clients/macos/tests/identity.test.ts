// Mirrors clients/linux/src/claudia_shell_gtk/identity.py's own tests: which Claudia app this shell can show, its
// bundle id and the server model behind it (D113's "an app is an entry point, an identity, a menu manifest").
import { describe, expect, it } from 'vitest'
import { APPS, UnknownAppError, getIdentity } from '../src/identity.js'

describe('getIdentity', () => {
  it('returns creates with its bundle id and server model', () => {
    const identity = getIdentity('creates')
    expect(identity.name).toBe('creates')
    expect(identity.title).toBe('Claudia Creates')
    expect(identity.applicationId).toBe('de.claudiaoffice.creates')
    expect(identity.model).toBe('claudia_creates:SlideModel')
  })

  it('shares the same application ids and models the Linux client uses, so the two shells never disagree about one app', () => {
    // clients/linux/src/claudia_shell_gtk/identity.py's _APPS table, kept in sync by hand (noted in this module's
    // own docstring the same way D28's About links note their own lack of a shared source).
    expect(getIdentity('composes').applicationId).toBe('de.claudiaoffice.composes')
    expect(getIdentity('computes').applicationId).toBe('de.claudiaoffice.computes')
    expect(getIdentity('composes').model).toBe('claudia_composes:TextModel')
    expect(getIdentity('computes').model).toBe('claudia_computes:WorkbookModel')
  })

  it('rejects an app name with no identity, naming the ones that exist', () => {
    expect(() => getIdentity('spreadsheets' as never)).toThrow(UnknownAppError)
    try {
      getIdentity('spreadsheets' as never)
    } catch (error) {
      expect(String(error)).toContain('composes')
      expect(String(error)).toContain('computes')
      expect(String(error)).toContain('creates')
    }
  })

  it('lists APPS in the same order every time (used to build e.g. a --help list)', () => {
    expect(APPS).toEqual(['composes', 'computes', 'creates'])
  })

  it('only creates has a packaged app directory today (E5.11s scope cut, like E5.1 did for computes/creates on Linux)', () => {
    expect(getIdentity('creates').packaged).toBe(true)
    expect(getIdentity('composes').packaged).toBe(false)
    expect(getIdentity('computes').packaged).toBe(false)
  })
})
