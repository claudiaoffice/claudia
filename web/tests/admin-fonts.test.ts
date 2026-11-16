import { describe, expect, it } from 'vitest'
import {
  checkLine,
  collectionMeta,
  familyRows,
  filterCounts,
  mayGoLabel,
  problemText,
  previewStyle,
  scopeSentences,
  stylesLabel,
  type FileCheckView,
  type FontsPage,
} from '~/lib/admin-fonts'
import { createAdminApi } from '~/lib/admin-api'
import { createTranslator } from '~/lib/i18n'

const t = createTranslator({})

const page: FontsPage = {
  format: 1,
  counts: { families: 3, files: 6, collections: 2, not_usable: 2 },
  collections: [
    { id: 'shipped', name: 'Shipped with Claudia', origin: 'shipped', editable: false, licence: 'OFL-1.1', may_go: 'anywhere', families: ['Arimo', 'Inter'], files: 4, problems: 0, added_by: '', added: '', source: '' },
    { id: 'city', name: 'City house fonts', origin: 'added', editable: true, licence: 'Contract', may_go: 'this-server', families: ['Hausschrift Sans'], files: 2, problems: 1, added_by: 'anna', added: '2026-11-15', source: '' },
  ],
  families: [
    { family: 'Arimo', styles: [{ style: 'Regular', weight: 400, italic: false, sha256: 'a', outlines: 'truetype', variable: false }], collection: 'Shipped with Claudia', collection_id: 'shipped', may_go: 'anywhere', stands_in_for: ['Arial', 'Helvetica'], problems: [] },
    {
      family: 'Hausschrift Sans',
      styles: [
        { style: 'Bold', weight: 700, italic: false, sha256: 'hb', outlines: 'truetype', variable: false },
        { style: 'Regular', weight: 400, italic: false, sha256: 'hr', outlines: 'truetype', variable: false },
        { style: 'Italic', weight: 400, italic: true, sha256: 'hi', outlines: 'truetype', variable: false },
      ],
      collection: 'City house fonts',
      collection_id: 'city',
      may_go: 'this-server',
      stands_in_for: [],
      problems: [{ file: 'H-BoldItalic.ttf', code: 'forbids-embedding', detail: '2', family: 'Hausschrift Sans', style: 'Bold Italic' }],
    },
    { family: 'Inter', styles: [{ style: 'Regular', weight: 400, italic: false, sha256: 'i', outlines: 'truetype', variable: true }, { style: 'Italic', weight: 400, italic: true, sha256: 'ii', outlines: 'truetype', variable: true }], collection: 'Shipped with Claudia', collection_id: 'shipped', may_go: 'anywhere', stands_in_for: ['sans-serif'], problems: [] },
  ],
  problems: [
    { file: 'H-BoldItalic.ttf', code: 'forbids-embedding', detail: '2', family: 'Hausschrift Sans', style: 'Bold Italic', collection: 'City house fonts' },
    { file: 'broken.ttf', code: 'not-a-font', detail: '', family: null, style: null, collection: 'City house fonts' },
  ],
  access_secret_set: true,
  can_add: true,
}

describe('the families table', () => {
  it('lists every family for All, in the order the server gives', () => {
    expect(familyRows(page, 'all', '').map((r) => r.kind === 'family' && r.family.family)).toEqual(['Arimo', 'Hausschrift Sans', 'Inter'])
  })

  it('lists the families that stand in for an office font for Stand-ins (not those for a generic family)', () => {
    expect(familyRows(page, 'stand-ins', '').map((r) => r.kind === 'family' && r.family.family)).toEqual(['Arimo'])
  })

  it('lists the families with a problem and the files no family could be read from for Not usable', () => {
    const rows = familyRows(page, 'not-usable', '')
    expect(rows.map((r) => (r.kind === 'family' ? r.family.family : r.problem.file))).toEqual(['Hausschrift Sans', 'broken.ttf'])
  })

  it('finds a family by its name or by a font it stands in for, whatever the case', () => {
    expect(familyRows(page, 'all', 'helv').map((r) => r.kind === 'family' && r.family.family)).toEqual(['Arimo'])
    expect(familyRows(page, 'all', 'INTER').map((r) => r.kind === 'family' && r.family.family)).toEqual(['Inter'])
  })

  it('counts each filter', () => {
    expect(filterCounts(page)).toEqual({ all: 3, 'stand-ins': 1, 'not-usable': 2 })
  })

  it('says how many styles a family has, of how many, and whether it is variable', () => {
    const [arimo, house, inter] = page.families
    expect(stylesLabel(arimo!, t)).toBe('1')
    expect(stylesLabel(house!, t)).toBe('3 of 4')
    expect(stylesLabel(inter!, t)).toBe('variable · 2')
  })

  it('previews a family in its upright regular style', () => {
    expect(previewStyle(page.families[1]!)?.sha256).toBe('hr')
  })
})

describe('words for the page', () => {
  it('says who may receive the fonts in a word (the page adds its sign), never colour alone', () => {
    expect(mayGoLabel('anywhere', t)).toBe('Anywhere')
    expect(mayGoLabel('this-server', t)).toBe('This server')
  })

  it('says why a font is not used, by its code', () => {
    expect(problemText(page.families[1]!.problems[0]!, t)).toBe('Bold Italic is not used: the file forbids embedding (fsType 2), so no PDF could carry it.')
    expect(problemText(page.problems[1]!, t)).toBe('broken.ttf is not a font that can be read.')
  })

  it('says where each collection comes from', () => {
    expect(collectionMeta(page.collections[0]!, t)).toBe('Always here. A font of the same family and style in another collection is used instead.')
    expect(collectionMeta(page.collections[1]!, t)).toBe('Added by anna, 2026-11-15. 1 file not used.')
  })
})

describe('Add fonts…', () => {
  const added: FileCheckView = { name: 'H-Regular.ttf', verdict: 'added', code: '', detail: '', family: 'Hausschrift Sans', style: 'Regular', outlines: 'truetype', licence: '' }

  it('says what each file becomes', () => {
    expect(checkLine(added, t)).toEqual({ badge: 'Will be added', tone: 'ok', note: '' })
    expect(checkLine({ ...added, code: 'replaces', detail: 'Shipped with Claudia' }, t)).toEqual({
      badge: 'Replaces a font',
      tone: 'warn',
      note: 'Replaces Hausschrift Sans Regular from Shipped with Claudia, for every document on this server.',
    })
    expect(checkLine({ ...added, verdict: 'left-out', code: 'forbids-embedding', detail: '2', style: 'Bold Italic' }, t).badge).toBe('Left out')
    expect(checkLine({ ...added, outlines: 'cff' }, t).note).toBe('Shown on screen; print and PDF cannot use its outlines yet and use a stand-in.')
  })

  it('states the scope before anything changes, with the server and who receives the fonts', () => {
    const lines = scopeSentences({ adds: 3, families: ['Hausschrift Sans'], server: 'Studio server', mayGo: 'this-server', accessSecretSet: false }, t)
    expect(lines).toEqual([
      'Adds 3 fonts in 1 family to Studio server. From now on every document here that asks for Hausschrift Sans is laid out, shown and printed with them.',
      'Only people using this server receive them.',
      'This server has no access secret, so everyone who can reach it counts as its people.',
    ])
  })
})

describe('the admin API for fonts', () => {
  it('holds a file with its name in a header and the bytes as the body', async () => {
    let seen: { url: string; init?: RequestInit } = { url: '' }
    const api = createAdminApi((async (url: string, init?: RequestInit) => {
      seen = { url: String(url), init }
      return { status: 200, ok: true, json: async () => ({ token: 'k', name: 'a b.ttf', size: 3 }) } as Response
    }) as typeof fetch)
    const file = new Blob([new Uint8Array([1, 2, 3])])
    await expect(api.holdFontFile('tok', file, 'a b.ttf')).resolves.toEqual({ token: 'k', name: 'a b.ttf', size: 3 })
    const headers = seen.init?.headers as Record<string, string>
    expect(seen.url).toBe('/api/admin/fonts/files')
    expect(headers['x-claudia-name']).toBe('a%20b.ttf')
    expect(headers.authorization).toBe('Bearer tok')
    expect(seen.init?.body).toBe(file)
  })

  it('names a collection by its id in the address', async () => {
    const urls: string[] = []
    const api = createAdminApi((async (url: string, init?: RequestInit) => {
      urls.push(`${init?.method} ${String(url)}`)
      return { status: 200, ok: true, json: async () => page } as Response
    }) as typeof fetch)
    await api.renameFontCollection('t', 'city/x', 'New')
    await api.removeFontCollection('t', 'city')
    expect(urls).toEqual(['PATCH /api/admin/fonts/collections/city%2Fx', 'DELETE /api/admin/fonts/collections/city'])
  })
})
