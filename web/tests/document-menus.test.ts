import { describe, expect, it } from 'vitest'
import type { Menu, MenuItem } from '~/components/MenuBar.vue'
import {
  SEARCH_CHORD,
  SHARED_HINTS,
  askItem,
  clipboardItems,
  preferencesMenu,
  darkItem,
  fileMenu,
  helpMenu,
  goToTargetItem,
  insertMenu,
  panelItem,
  searchItem,
  undoRedoItems,
  type DocumentMenuContext,
  type FrameDialog,
} from '~/lib/document-menus'
import { LANGUAGES } from '~/lib/i18n'
import { chordLabel } from '~/lib/shortcuts'

const t = (msgid: string, vars?: Record<string, string | number>) =>
  vars ? msgid.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name])) : msgid

function context(role: 'owner' | 'editor' | 'viewer' = 'owner') {
  const calls: string[] = []
  const c: DocumentMenuContext = {
    t,
    role,
    open: (dialog: FrameDialog) => calls.push(`open:${dialog}`),
    leave: (opts) => calls.push(opts?.startFresh ? 'leave:fresh' : 'leave'),
    save: () => calls.push('save'),
  }
  return { c, calls }
}

const ids = (items: MenuItem[]) => items.filter((i) => !i.separator).map((i) => i.id ?? i.label)
const byId = (items: MenuItem[], id: string): MenuItem => {
  for (const item of items) {
    if (item.id === id) return item
    const found = item.items?.find((sub) => sub.id === id)
    if (found) return found
  }
  throw new Error(`no ${id}`)
}

describe('fileMenu: the same File menu in every app (D120, D141)', () => {
  it('has the shared items in their order, Manage as a submenu', () => {
    const { c } = context()
    const file = fileMenu(c)
    expect(file.label).toBe('File')
    expect(ids(file.items)).toEqual(['file.new', 'file.open', 'file.open-file', 'file.save', 'file.save-as', 'file.download', 'file.manage', 'file.close'])
    expect(ids(byId(file.items, 'file.manage').items!)).toEqual([
      'file.manage.share',
      'file.manage.change-password',
      'file.manage.assign-owner',
      'file.manage.accept-owner',
      'file.manage.leave',
      'file.manage.export',
      'file.manage.redact',
      'file.manage.delete',
    ])
  })

  it('opens the document window’s own dialogs, and leaves through the workspace', () => {
    const { c, calls } = context()
    const file = fileMenu(c)
    for (const id of ['file.new', 'file.open', 'file.open-file', 'file.save', 'file.save-as', 'file.download', 'file.manage.change-password', 'file.manage.export', 'file.close']) {
      byId(file.items, id).action!()
    }
    expect(calls).toEqual(['leave:fresh', 'open:open', 'open:open-file', 'save', 'open:checkpoint', 'open:download', 'open:change-password', 'open:export-format', 'leave'])
  })

  it('has Print… after Download only in an app that can print (composes, D906), with its shortcut', () => {
    const { c, calls } = context()
    const printing = fileMenu({ ...c, print: () => calls.push('print') })
    expect(ids(printing.items)).toEqual(['file.new', 'file.open', 'file.open-file', 'file.save', 'file.save-as', 'file.download', 'file.print', 'file.manage', 'file.close'])
    const print = byId(printing.items, 'file.print')
    expect([print.label, print.hint]).toEqual(['Print…', 'Ctrl+P'])
    print.action!()
    expect(calls).toEqual(['print'])
    expect(ids(fileMenu(c).items)).not.toContain('file.print')
  })

  it('shows the save shortcut the window really listens for', () => {
    expect(byId(fileMenu(context().c).items, 'file.save').hint).toBe(SHARED_HINTS['file.save'])
    expect(SHARED_HINTS).toEqual({ 'edit.undo': 'Ctrl+Z', 'edit.redo': 'Ctrl+Shift+Z', 'file.save': 'Ctrl+S' })
  })

  it('lets only an owner share, hand over or delete, and keeps a viewer from saving', () => {
    const owner = fileMenu(context('owner').c).items
    const editor = fileMenu(context('editor').c).items
    const viewer = fileMenu(context('viewer').c).items
    for (const id of ['file.manage.share', 'file.manage.assign-owner', 'file.manage.delete']) {
      expect([byId(owner, id).disabled, byId(editor, id).disabled, byId(viewer, id).disabled]).toEqual([false, true, true])
    }
    expect([byId(owner, 'file.manage.accept-owner').disabled, byId(viewer, 'file.manage.accept-owner').disabled]).toEqual([false, true])
    expect([byId(editor, 'file.save').disabled, byId(viewer, 'file.save').disabled]).toEqual([false, true])
    expect(byId(viewer, 'file.manage.leave').disabled).toBeFalsy()
  })

  it('lets owners and editors redact, a viewer not (D727), and opens the pick for it', () => {
    const roles = ['owner', 'editor', 'viewer'].map((role) => byId(fileMenu(context(role).c).items, 'file.manage.redact'))
    expect(roles.map((item) => item.disabled)).toEqual([false, false, true])
    expect(roles[0]!.label).toBe('Redact History…')
    const { c, calls } = context()
    byId(fileMenu(c).items, 'file.manage.redact').action!()
    expect(calls).toEqual(['open:redact'])
  })
})

describe('undoRedoItems and clipboardItems: the shared block at the top of Edit', () => {
  it('names what would be undone and redone, and is off when there is nothing', () => {
    const { c } = context()
    const done: string[] = []
    const history = { canUndo: true, undoLabel: 'Edit cell', canRedo: false, redoLabel: '', undo: () => done.push('undo'), redo: () => done.push('redo') }
    const [undo, redo] = undoRedoItems(c, history)
    expect([undo!.label, undo!.hint, undo!.disabled]).toEqual(['Undo Edit cell', 'Ctrl+Z', false])
    expect([redo!.label, redo!.disabled]).toEqual(['Redo', true])
    undo!.action!()
    expect(done).toEqual(['undo'])
  })

  it('pastes through the app, and a viewer may copy but not cut or paste — the submenu agrees with its parent', () => {
    let pasted = 0
    const items = clipboardItems(context('viewer').c, () => pasted++)
    expect(ids(items)).toEqual(['edit.copy', 'edit.cut', 'edit.paste', 'edit.paste-as'])
    expect(byId(items, 'edit.copy').disabled).toBeFalsy()
    expect([byId(items, 'edit.cut').disabled, byId(items, 'edit.paste').disabled]).toEqual([true, true])
    expect([byId(items, 'edit.paste-as').disabled, byId(items, 'edit.paste-as-plain').disabled]).toEqual([true, true])
    clipboardItems(context('editor').c, () => pasted++).find((i) => i.id === 'edit.paste')!.action!()
    expect(pasted).toBe(1)
  })
})

describe('View, Tools, Preferences and Help pieces', () => {
  it('panel and dark mode follow a shell asking by name, and toggle on a click', () => {
    let open = true
    const panel = panelItem(context().c, { open: () => open, toggle: () => (open = !open) })
    expect([panel.id, panel.checked]).toEqual(['view.panel', true])
    panel.action!('on')
    expect(open).toBe(true)
    panel.action!('off')
    expect(open).toBe(false)
    panel.action!()
    expect(open).toBe(true)

    let dark = false
    const item = darkItem(context().c, { on: () => dark, toggle: () => (dark = !dark) })
    item.action!('off')
    expect(dark).toBe(false)
    item.action!('on')
    expect(dark).toBe(true)
  })

  it('Preferences ▸ App Language lists LANGUAGES, ticks the current one, and chooses', () => {
    const chosen: string[] = []
    const preferences = preferencesMenu(context().c, { current: 'de', choose: (tag) => chosen.push(tag) })
    expect(ids(preferences.items)).toEqual(['config.shortcuts', 'config.ai', 'App Language'])
    const languages = preferences.items[2]!.items!
    expect(languages.map((l) => [l.id, l.label, l.checked])).toEqual(LANGUAGES.map(([tag, name]) => [`config.language.${tag}`, name, tag === 'de']))
    languages[0]!.action!()
    expect(chosen).toEqual([LANGUAGES[0]![0]])
  })

  it('Preferences ▸ AI… opens the dialog about who answers @ai in this document, with its key shown', () => {
    const { c, calls } = context()
    const ai = preferencesMenu(c, { current: 'en', choose: () => {} }).items.find((i) => i.id === 'config.ai')!
    expect(ai.label).toBe('AI…')
    expect(ai.hint).toBe('Ctrl+Shift+Alt+E')
    ai.action!()
    expect(calls).toEqual(['open:ai'])
  })

  it('Help asks the assistant, opens the help tab in its two modes, and shows About', () => {
    const { c, calls } = context()
    const asked: string[] = []
    const help = helpMenu(c, { ask: (text) => asked.push(text), openHelp: (mode) => asked.push(`help:${mode}`) })
    expect(ids(help.items)).toEqual(['help.ask', 'help.how-to', 'help.docs', 'help.about'])
    help.items.forEach((i) => i.action!())
    expect(asked).toEqual(['@ai ', 'help:how-to', 'help:docs'])
    expect(calls).toEqual(['open:about'])
    expect(askItem(c, (text) => asked.push(text)).id).toBe('tools.ask')
  })
})

describe('searchItem: Edit ▸ Search & Replace… (D281, E5.15)', () => {
  it('is one entry with its shortcut, and opens the panel', () => {
    const { c } = context()
    const opened: string[] = []
    const item = searchItem(c, { open: () => opened.push('open') })
    expect([item.id, item.label, item.hint]).toEqual(['edit.search-replace', 'Search & Replace…', 'Ctrl+F'])
    item.action!()
    expect(opened).toEqual(['open'])
  })

  it('may be used by somebody who can only look: finding changes nothing', () => {
    expect(searchItem(context('viewer').c, { open: () => {} }).disabled).toBeFalsy()
  })

  it('shows the shortcut the window really listens for', () => {
    expect(searchItem(context().c, { open: () => {} }).hint).toBe(chordLabel(SEARCH_CHORD))
  })
})

describe('insertMenu: Insert ▸ Container in every app (D560)', () => {
  const containerOf = (menu: Menu) => menu.items.find((i) => i.items)!.items!
  const types = [{ type: 'latex', title: 'LaTeX' }, { type: 'mermaid', title: 'Mermaid' }]
  it('offers the three kinds with their keys, the ones the server cannot make off', () => {
    const { c } = context('editor')
    const added: string[] = []
    const menu = insertMenu(c, { types, add: (k) => added.push(k) })
    expect(menu.label).toBe('Insert')
    const sub = containerOf(menu)
    expect(ids(sub)).toEqual(['insert.container.latex', 'insert.container.mermaid', 'insert.container.typst'])
    expect(sub.map((i) => i.disabled)).toEqual([false, false, true])
    expect(sub.map((i) => i.hint)).toEqual(['Ctrl+Shift+Alt+F', 'Ctrl+Shift+Alt+G', 'Ctrl+Shift+Alt+Y'])
    sub[1]!.action!()
    expect(added).toEqual(['mermaid'])
  })
  it('is off for somebody who can only look', () => {
    const { c } = context('viewer')
    const sub = containerOf(insertMenu(c, { types, add: () => {} }))
    expect(sub.every((i) => i.disabled)).toBe(true)
  })
})

describe('insertMenu: Insert ▸ Table of Contents, in creates Agenda (E9.31)', () => {
  const contentsOf = (menu: Menu) => menu.items.find((i) => i.id === 'insert.contents')!
  it("comes first, under the app's own name, with its key", () => {
    const { c } = context('editor')
    let added = 0
    const item = contentsOf(insertMenu(c, { types: [], add: () => {} }, { label: 'Agenda', add: () => added++, possible: true }))
    expect(item.label).toBe('Agenda')
    expect(item.hint).toBe('Ctrl+Shift+Alt+I')
    expect(item.disabled).toBe(false)
    item.action!()
    expect(added).toBe(1)
  })
  it('is shown and off where there is nothing to list (computes), or for somebody who can only look', () => {
    expect(contentsOf(insertMenu(context('editor').c, { types: [], add: () => {} })).disabled).toBe(true)
    const viewer = insertMenu(context('viewer').c, { types: [], add: () => {} }, { label: 'x', add: () => {}, possible: true })
    expect(contentsOf(viewer).disabled).toBe(true)
  })
})

describe('Insert ▸ Cross-Reference… and Edit ▸ Go to Target (step H)', () => {
  it('puts the picker first in Insert, with its key, and is off where there is nothing to point from', () => {
    let opened = 0
    const item = insertMenu(context('editor').c, { types: [], add: () => {} }, undefined, { add: () => opened++, possible: true }).items[0]!
    expect([item.id, item.hint, item.disabled]).toEqual(['insert.cross-reference', 'Ctrl+F2', false])
    item.action!()
    expect(opened).toBe(1)
    expect(insertMenu(context('editor').c, { types: [], add: () => {} }).items[0]!.disabled).toBe(true)
  })
  it('goes to the target with Ctrl+Alt+Enter, only where there is a reference', () => {
    let went = 0
    const item = goToTargetItem(context('editor').c, { run: () => went++, possible: () => true })
    expect([item.id, item.hint, item.disabled]).toEqual(['edit.go-to-target', 'Ctrl+Alt+Enter', false])
    item.action!()
    expect(went).toBe(1)
    expect(goToTargetItem(context('editor').c, { run: () => {}, possible: () => false }).disabled).toBe(true)
  })
})
