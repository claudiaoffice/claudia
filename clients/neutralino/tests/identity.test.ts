// Mirrors clients/linux/src/claudia_shell_gtk/identity.py's own tests: which Claudia app this shell can show, its
// bundle id and the server model behind it (D113's "an app is an entry point, an identity, a menu manifest").
import { describe, expect, it } from 'vitest'
import { APPS, UnknownAppError, appFromPath, commandOf, getIdentity, isApp } from '../src/identity.js'

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

  it('has an identity for every app, each with a title, a bundle id and a model', () => {
    for (const app of APPS) {
      const identity = getIdentity(app)
      expect(identity.name).toBe(app)
      expect(identity.applicationId).toBe(`de.claudiaoffice.${app}`)
      expect(identity.title).toMatch(/^Claudia /)
      expect(identity.model).toContain(':')
    }
  })

  it('names the command of each app like the Linux client does', () => {
    expect(commandOf(getIdentity('composes'))).toBe('claudia-composes')
    expect(commandOf(getIdentity('creates'))).toBe('claudia-creates')
  })

  it('knows an app name when it sees one, also for inherited object keys', () => {
    expect(isApp('computes')).toBe(true)
    expect(isApp('spreadsheets')).toBe(false)
    expect(isApp('constructor')).toBe(false)
    expect(isApp(undefined)).toBe(false)
  })
})

describe('appFromPath', () => {
  it('reads the app from where a built file lies', () => {
    expect(appFromPath('/Users/me/claudia/clients/macos/apps/computes/ext/core.mjs')).toBe('computes')
    expect(appFromPath('/x/apps/creates/shell/shell.js')).toBe('creates')
  })

  it('takes the last apps/ folder, and a path with spaces or backslashes is no problem', () => {
    expect(appFromPath('/apps/composes/y/apps/creates/ext/core.mjs')).toBe('creates')
    expect(appFromPath('C:\\My Files\\apps\\composes\\ext\\core.mjs')).toBe('composes')
  })

  it('knows nothing for a path that is not in an app folder', () => {
    expect(appFromPath('/tmp/core.mjs')).toBeNull()
    expect(appFromPath('/x/apps/other/ext/core.mjs')).toBeNull()
    expect(appFromPath('/x/apps')).toBeNull()
  })
})
