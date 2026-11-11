// Mirrors clients/linux/src/claudia_shell_gtk/identity.py's and clients/macos/tests/identity.test.ts's own tests:
// which Claudia app this shell can show, its application id and the server model behind it (D113's "an app is an entry
// point, an identity, a menu manifest").
import { describe, expect, it } from 'vitest'
import { APPS, UnknownAppError, appFromPath, commandOf, getIdentity, isApp } from '../src/identity.js'

describe('getIdentity', () => {
  it('returns composes with its application id and server model', () => {
    const identity = getIdentity('composes')
    expect(identity.name).toBe('composes')
    expect(identity.title).toBe('Claudia Composes')
    expect(identity.applicationId).toBe('de.claudiaoffice.composes')
    expect(identity.model).toBe('claudia_composes:TextModel')
  })

  it('shares the same application ids and models the Linux and macOS clients use, so no shell ever disagrees about one app', () => {
    // clients/linux/src/claudia_shell_gtk/identity.py's _APPS table and clients/macos/src/identity.ts's
    // IDENTITIES, kept in sync by hand (noted in this module's own docstring the same way D28's About links note
    // their own lack of a shared source).
    expect(getIdentity('computes').applicationId).toBe('de.claudiaoffice.computes')
    expect(getIdentity('creates').applicationId).toBe('de.claudiaoffice.creates')
    expect(getIdentity('computes').model).toBe('claudia_computes:WorkbookModel')
    expect(getIdentity('creates').model).toBe('claudia_creates:SlideModel')
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

  it('knows what is an app, and which app a built file belongs to by its place (the core uses it when nobody told it)', () => {
    expect(isApp('creates')).toBe(true)
    expect(isApp('toString')).toBe(false) // not an inherited property of the table
    expect(isApp(undefined)).toBe(false)
    expect(appFromPath('C:\\repo\\clients\\windows\\apps\\computes\\ext\\core.mjs')).toBe('computes')
    expect(appFromPath('/repo/clients/windows/apps/creates/shell/shell.js')).toBe('creates')
    expect(appFromPath('C:\\somewhere\\core.mjs')).toBeNull()
    expect(appFromPath('/repo/apps/spreadsheets/ext/core.mjs')).toBeNull()
  })

  it('names the command of an app like the Linux and macOS clients do', () => {
    expect(commandOf(getIdentity('composes'))).toBe('claudia-composes')
  })
})
