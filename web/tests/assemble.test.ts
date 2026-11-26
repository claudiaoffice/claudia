// The menus assembled from the definition (D1644): the definition's entries × the workspace's handlers × the verdicts
// of `fits/`. Hidden entries are left out, greyed ones are `disabled`, lines and empty submenus collapse, an empty menu
// says why (D1603), and every action has its handler (the seam agreed for slice 4 of the menu work).
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import type { MenuItem } from '~/components/MenuBar.vue'
import type { Facts } from '~/lib/fits/facts'
import { DEFAULT_POLICY, policyFromAddress, type FitPolicy } from '~/lib/fits/policy'
import { assembleMenus, handlerGaps, type Handlers } from '~/lib/menus/assemble'
import { DEFINITIONS, type AppDef } from '~/lib/menus.generated'

const t = (msgid: string, vars: Record<string, string | number> = {}) =>
  msgid.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`))

function facts(over: Partial<Facts> = {}): Facts {
  return {
    role: 'owner',
    client: 'web',
    ai: true,
    tools: new Set(['latex']),
    document: { undo: false, redo: false, references: false, randomNumbers: false, backPlace: false, slides: 1 },
    selection: [],
    ...over,
  }
}

const anyone = 'role: anyone'
const editors = 'role: editor or owner'

/** A small app: an Edit menu with two groups and a submenu, an Insert menu only editors use, and one context menu. */
const APP: AppDef = {
  menus: [
    {
      label: 'Edit',
      sections: [
        [{ id: 'edit.undo', label: 'Undo', fits: `${editors} · document: something to undo`, kind: 'page' }],
        [
          { id: 'edit.copy', label: 'Copy', fits: `${editors} · selection: something`, kind: 'editing' },
          { label: 'Paste As', items: [{ id: 'edit.paste-as-plain', label: 'Plain Text', fits: editors, kind: 'editing' }] },
        ],
        [{ id: 'edit.search-replace', label: 'Search and Replace…', fits: anyone, kind: 'page' }],
      ],
    },
    {
      label: 'Insert',
      sections: [
        [{ id: 'insert.container.latex', label: 'LaTeX', fits: `${editors} · server: has the tool for LaTeX`, kind: 'page' }],
        [{ id: 'insert.container.typst', label: 'Typst', fits: `${editors} · server: has the tool for Typst`, kind: 'page' }],
      ],
    },
    {
      label: 'View',
      sections: [[{ id: 'view.dark', label: 'Dark Mode', fits: anyone, kind: 'page', checkable: true }]],
    },
  ],
  contexts: [{ id: 'object', label: 'Object', sections: [[{ id: 'edit.delete', label: 'Delete', fits: editors, kind: 'page' }]] }],
  keysOnly: [{ id: 'edit.nonbreaking-hyphen', label: 'Non-breaking Hyphen', fits: editors, kind: 'page' }],
}

function handlers(over: Partial<Handlers> = {}): Handlers {
  return {
    'edit.undo': { run: vi.fn() },
    'edit.copy': { run: vi.fn() },
    'edit.paste-as-plain': { run: vi.fn() },
    'edit.search-replace': { run: vi.fn() },
    'insert.container.latex': { run: vi.fn() },
    'insert.container.typst': { run: vi.fn() },
    'view.dark': { run: vi.fn(), checked: () => false },
    'edit.delete': { run: vi.fn() },
    'edit.nonbreaking-hyphen': { run: vi.fn() },
    ...over,
  }
}

function assemble(over: Partial<Facts> = {}, policy: FitPolicy = DEFAULT_POLICY, own = handlers(), notice = vi.fn()) {
  return assembleMenus({ definition: APP, handlers: own, facts: () => facts(over), policy, t, notice, locale: 'en' })
}

/** What a menu shows, in a line each: `—` for a separator, `(off)` for a greyed entry, `▸` for a submenu's items. */
function shown(items: readonly MenuItem[]): string[] {
  return items.flatMap((item) =>
    item.separator
      ? ['—']
      : [`${item.label}${item.disabled ? ' (off)' : ''}`, ...(item.items ?? []).map((sub) => `▸ ${sub.label}${sub.disabled ? ' (off)' : ''}`)],
  )
}

describe('the menu bar, assembled from the definition (D1644)', () => {
  it('keeps every title, in the definition’s order, whoever I am (D1603)', () => {
    expect(assemble({ role: 'viewer' }).bar.map((m) => m.label)).toEqual(['Edit', 'Insert', 'View'])
  })

  it('leaves out what does not fit, and the line before a group with nothing left', () => {
    expect(shown(assemble().bar[0]!.items)).toEqual(['Paste As', '▸ Plain Text', '—', 'Search and Replace…'])
  })

  it('greys what does not fit when its reason is set to grey (D1606)', () => {
    const items = assemble({}, policyFromAddress('?fits=document:grey,selection:grey')).bar[0]!.items
    expect(shown(items)).toEqual(['Undo (off)', '—', 'Copy (off)', 'Paste As', '▸ Plain Text', '—', 'Search and Replace…'])
  })

  it('greys or hides one entry by its own setting, whatever its reason’s (D1653)', () => {
    const items = assemble({}, policyFromAddress('?fits-entry=edit.undo:grey')).bar[0]!.items
    expect(shown(items)[0]).toBe('Undo (off)')
  })

  it('greys a submenu whose entries are all greyed', () => {
    const items = assemble({ role: 'viewer' }, policyFromAddress('?fits=role:grey')).bar[0]!.items
    expect(shown(items)).toEqual(['Undo (off)', '—', 'Copy (off)', 'Paste As (off)', '▸ Plain Text (off)', '—', 'Search and Replace…'])
  })

  it('leaves out a submenu with nothing left in it', () => {
    expect(shown(assemble({ role: 'viewer' }).bar[0]!.items)).toEqual(['Search and Replace…'])
  })

  it('shows a menu with nothing left as its one greyed line saying why (D1603)', () => {
    expect(shown(assemble({ role: 'viewer' }).bar[1]!.items)).toEqual([
      'Nothing to insert: you can only look at this document. (off)',
    ])
  })

  it('says the why of the first reason in the order of D1642 on that line', () => {
    const insert = assemble({ tools: new Set() }).bar[1]!.items
    expect(shown(insert)).toEqual(['Nothing to insert: this server has no LaTeX set up. (off)'])
  })

  it('keeps the why as it is written in a language that writes on after a colon with a capital', () => {
    const menus = assembleMenus({ definition: APP, handlers: handlers(), facts: () => facts({ role: 'viewer' }), policy: DEFAULT_POLICY, t, notice: vi.fn(), locale: 'de' })
    expect(menus.bar[1]!.items[0]!.label).toBe('Nothing to insert: You can only look at this document.')
  })

  it('labels an entry in the person’s language, or as its handler says (Undo Add Container)', () => {
    const de = (msgid: string) => ({ 'Search and Replace…': 'Suchen und Ersetzen…' })[msgid] ?? msgid
    const own = handlers({ 'edit.undo': { run: vi.fn(), label: () => 'Undo Add Container' } })
    const menus = assembleMenus({ definition: APP, handlers: own, facts: () => facts({ document: { ...facts().document, undo: true } }), policy: DEFAULT_POLICY, t: de, notice: vi.fn(), locale: 'de' })
    expect(shown(menus.bar[0]!.items)).toEqual(['Undo Add Container', '—', 'Paste As', '▸ Plain Text', '—', 'Suchen und Ersetzen…'])
  })

  it('greys an entry its workspace cannot run now, with the workspace’s own sentence', () => {
    const own = handlers({ 'edit.search-replace': { run: vi.fn(), notNow: () => 'Not while the history replays.' } })
    const menus = assemble({}, DEFAULT_POLICY, own)
    expect(shown(menus.bar[0]!.items).at(-1)).toBe('Search and Replace… (off)')
    expect(menus.states['edit.search-replace']).toEqual({ enabled: false, visible: true })
  })
})

describe('choosing an entry', () => {
  it('runs the handler of an entry that fits', () => {
    const own = handlers()
    assemble({}, DEFAULT_POLICY, own).bar[0]!.items.at(-1)!.action!()
    expect(own['edit.search-replace']!.run).toHaveBeenCalled()
  })

  it('judges again when it runs, and says why instead of running when it no longer fits (D1603, D1604)', () => {
    let role: Facts['role'] = 'owner'
    const own = handlers()
    const notice = vi.fn()
    const menus = assembleMenus({ definition: APP, handlers: own, facts: () => facts({ role }), policy: DEFAULT_POLICY, t, notice, locale: 'en' })
    role = 'viewer'
    expect(menus.run('edit.paste-as-plain')).toBe(true)
    expect(own['edit.paste-as-plain']!.run).not.toHaveBeenCalled()
    expect(notice).toHaveBeenCalledWith('You can only look at this document.')
  })

  it('runs a hidden entry by its id (a shell or a key), and says why when it does not fit', () => {
    const notice = vi.fn()
    const menus = assemble({ role: 'viewer' }, DEFAULT_POLICY, handlers(), notice)
    menus.run('insert.container.latex')
    expect(notice).toHaveBeenCalledWith('You can only look at this document.')
  })

  it('says an entry’s own sentence instead of its condition’s (D1650)', () => {
    const notice = vi.fn()
    const own = handlers({ 'edit.delete': { run: vi.fn(), why: { role: 'Only editors and owners can delete.' } } })
    assemble({ role: 'viewer' }, DEFAULT_POLICY, own, notice).run('edit.delete')
    expect(notice).toHaveBeenCalledWith('Only editors and owners can delete.')
  })

  it('turns a switch to what a shell asks for, and only when it is not that already', () => {
    let on = false
    const own = handlers({ 'view.dark': { run: vi.fn(() => (on = !on)), checked: () => on } })
    const menus = assemble({}, DEFAULT_POLICY, own)
    menus.run('view.dark', 'off')
    expect(on).toBe(false)
    menus.run('view.dark', 'on')
    menus.run('view.dark', 'on')
    expect(on).toBe(true)
    expect(assemble({}, DEFAULT_POLICY, own).bar[2]!.items[0]!.checked).toBe(true)
  })

  it('does not know an id the definition has not', () => {
    expect(assemble().run('file.nothing')).toBe(false)
  })
})

describe('what the shell is told (D1645)', () => {
  it('says every action’s state, also of an entry that is left out, and whether it is left out (slice 6)', () => {
    const states = assemble({ role: 'viewer' }).states
    expect(states['insert.container.latex']).toEqual({ enabled: false, visible: false })
    expect(states['edit.search-replace']).toEqual({ enabled: true, visible: true })
    expect(states['view.dark']).toEqual({ enabled: true, visible: true, checked: false })
  })

  it('says a greyed entry stays', () => {
    const states = assemble({ role: 'viewer' }, policyFromAddress('?fits=role:grey')).states
    expect(states['insert.container.latex']).toEqual({ enabled: false, visible: true })
  })

  it('names only what stands in the menu bar: the shells draw nothing else, and a key of the rest reaches the page', () => {
    const states = assemble().states
    expect(states['edit.delete']).toBeUndefined()
    expect(states['edit.nonbreaking-hyphen']).toBeUndefined()
  })

  it('names the menus with nothing left, with the line that says why (D1603)', () => {
    expect(assemble({ role: 'viewer' }).empty).toEqual({ insert: 'Nothing to insert: you can only look at this document.' })
    expect(assemble().empty).toEqual({})
  })
})

describe('the collapse rule all three draw by (clients/contract/fixtures/menu-collapse.json)', () => {
  type Spec = string | { submenu: string; items: string[] }
  const fixture = JSON.parse(readFileSync(resolve(__dirname, '../../clients/contract/fixtures/menu-collapse.json'), 'utf8')) as {
    cases: { name: string; sections: Spec[][]; drawn: Spec[] }[]
  }
  const action = (label: string) => ({ id: `test.${label.replace('~', '')}`, label, fits: label.startsWith('~') ? 'role: owner' : anyone, kind: 'page' as const })

  it.each(fixture.cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    const app: AppDef = {
      menus: [{ label: 'Test', sections: c.sections.map((section) => section.map((e) => (typeof e === 'string' ? action(e) : { label: e.submenu, items: e.items.map(action) }))) }],
      contexts: [],
      keysOnly: [],
    }
    const own = Object.fromEntries(c.sections.flat().flatMap((e) => (typeof e === 'string' ? [e] : e.items)).map((l) => [action(l).id, { run: vi.fn() }]))
    const menus = assembleMenus({ definition: app, handlers: own, facts: () => facts({ role: 'viewer' }), policy: DEFAULT_POLICY, t, notice: vi.fn(), locale: 'en' })
    const drawn = menus.bar[0]!.items.filter((item) => !(item.disabled && !item.id)).map((item): Spec =>
      item.separator ? '-' : item.items ? { submenu: item.label, items: item.items.map((sub) => sub.label) } : item.label,
    )
    expect(drawn).toEqual(c.drawn)
  })
})

describe('a context menu', () => {
  it('holds what fits, by the rule of its own place', () => {
    expect(shown(assemble().context('object'))).toEqual(['Delete'])
  })

  it('runs what the place that opens it does, where it says so', () => {
    const here = { run: vi.fn() }
    const own = handlers()
    assemble({}, DEFAULT_POLICY, own).context('object', { 'edit.delete': here })[0]!.action!()
    expect(here.run).toHaveBeenCalled()
    expect(own['edit.delete']!.run).not.toHaveBeenCalled()
  })

  it('opens the choices of an entry whose place has them (Wrap Text… ▸)', () => {
    const modes = [{ label: 'Square', action: vi.fn() }]
    expect(shown(assemble().context('object', { 'edit.delete': { run: vi.fn(), items: () => modes } }))).toEqual(['Delete', '▸ Square'])
  })

  it('with nothing left, is its one greyed line saying why (D1603)', () => {
    expect(shown(assemble({ role: 'viewer' }).context('object'))).toEqual(['You can only look at this document. (off)'])
  })
})

describe('every action has its handler, and every handler its action', () => {
  it('names what is missing and what is left over', () => {
    const own = handlers({ 'edit.gone': { run: vi.fn() } })
    delete (own as Record<string, unknown>)['edit.delete']
    expect(handlerGaps(APP, own)).toEqual({ missing: ['edit.delete'], unknown: ['edit.gone'] })
  })

  it('does not ask for a handler of what the shell does itself (Quit)', () => {
    const app: AppDef = { menus: [{ label: 'File', sections: [[{ id: 'file.quit', label: 'Quit', fits: 'client: desktop only', kind: 'shell' }]] }], contexts: [], keysOnly: [] }
    expect(handlerGaps(app, {})).toEqual({ missing: [], unknown: [] })
  })

  it('parses every rule of the three apps', () => {
    for (const app of Object.values(DEFINITIONS)) {
      const menus = assembleMenus({ definition: app, handlers: {}, facts: () => facts(), policy: DEFAULT_POLICY, t, notice: vi.fn(), locale: 'en' })
      expect(menus.bar.length).toBe(app.menus.length)
    }
  })
})

describe('the listing of Preferences ▸ Shortcuts (D1604, D1642)', () => {
  it('lists every action of the menu bar once, by menu, with its place, its key and when it fits', () => {
    const [edit] = assemble({ role: 'viewer' }).listing()
    expect(edit!.title).toBe('Edit')
    expect(edit!.rows.map((r) => r.label)).toEqual(['Undo', 'Copy', 'Paste As ▸ Plain Text', 'Search and Replace…'])
    expect(edit!.rows[0]).toMatchObject({ id: 'edit.undo', keys: 'Ctrl+Z', when: 'editors and owners, when there is something to undo', fits: false, tag: 'not for you' })
    expect(edit!.rows[3]).toMatchObject({ when: 'everyone', fits: true, tag: null })
  })

  it('tags what is missing now as "not now" and what the server lacks as "not here"', () => {
    const groups = assemble({ tools: new Set() }).listing()
    expect(groups[0]!.rows[0]).toMatchObject({ id: 'edit.undo', fits: false, tag: 'not now' })
    expect(groups[1]!.rows[0]).toMatchObject({ id: 'insert.container.latex', fits: false, tag: 'not here' })
  })

  it('tags an entry its workspace cannot run now as "not now"', () => {
    const own = handlers({ 'view.dark': { run: vi.fn(), notNow: () => 'Not now.' } })
    const view = assemble({}, DEFAULT_POLICY, own).listing()[2]!
    expect(view.rows[0]).toMatchObject({ id: 'view.dark', fits: false, tag: 'not now' })
  })

  it('lists what only a context menu has under that menu', () => {
    const groups = assemble().listing()
    expect(groups.map((g) => g.title)).toEqual(['Edit', 'Insert', 'View', 'Context menu: Object', 'Keys without an entry'])
    expect(groups[3]!.rows.map((r) => r.id)).toEqual(['edit.delete'])
  })

  it('lists a key without an entry by itself', () => {
    expect(assemble().listing().at(-1)!.rows[0]).toMatchObject({ id: 'edit.nonbreaking-hyphen', label: 'Non-breaking Hyphen', keys: 'Ctrl+_' })
  })
})
