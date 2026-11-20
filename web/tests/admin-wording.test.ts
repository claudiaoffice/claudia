// What the administrator pages say about the access secret and about losing every administrator (UX-61,
// `claudiaoffice-log/specs/server/administrators.feature`). Both pages used to call the access secret a recovery key:
// the server has no such recovery, and nobody can sign in with the secret. The texts are read from the components'
// sources, where the person's language is looked up by them (`t('…')`), so the English is the msgid itself.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/** The English texts a component shows through `t(...)`. */
function texts(component: string): string[] {
  const source = readFileSync(new URL(`../app/components/${component}`, import.meta.url), 'utf8')
  return [...source.matchAll(/\bt\('((?:[^'\\]|\\.)*)'/g)].map((m) => m[1]!.replace(/\\'/g, "'"))
}

const RECOVERY = /recovery key/i

describe('naming the first administrator (FirstAdminSetup.vue)', () => {
  const said = texts('FirstAdminSetup.vue')

  it('does not call the access secret a recovery key', () => {
    expect(said.filter((s) => RECOVERY.test(s))).toEqual([])
  })

  it('says who can name a new first administrator if every one is locked out', () => {
    expect(said).toContain(
      'Keep this password safe. If every administrator is ever locked out, only someone with access to the computer the server runs on can name a new first administrator.',
    )
  })
})

describe('Access & documents (AdminAccessDocuments.vue)', () => {
  const said = texts('AdminAccessDocuments.vue')

  it('does not call the access secret a recovery key', () => {
    expect(said.filter((s) => RECOVERY.test(s))).toEqual([])
  })

  it('says what the access secret lets people do', () => {
    expect(said).toContain(
      "Whoever knows it may make documents and see their list; nobody signs in here with it. Administrators sign in with their own name and password. Rotating it doesn't sign anyone out.",
    )
  })
})
