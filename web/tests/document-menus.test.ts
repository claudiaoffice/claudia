import { describe, expect, it } from 'vitest'
import type { MenuItem } from '~/components/MenuBar.vue'
import {
  SEARCH_CHORD,
  SHARED_HINTS,
  askItem,
  clipboardItems,
  configMenu,
  darkItem,
  fileMenu,
  helpMenu,
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
    expect(ids(file.items)).toEqual(['file.new', 'file.open', 'file.save', 'file.save-as', 'file.download', 'file.manage', 'file.close'])
    expect(ids(byId(file.items, 'file.manage').items!)).toEqual([
      'file.manage.share',
      'file.manage.assign-owner',
      'file.manage.accept-owner',
      'file.manage.leave',
      'file.manage.export',
      'file.manage.delete',
    ])
  })

  it('opens the document window’s own dialogs, and leaves through the workspace', () => {
    const { c, calls } = context()
    const file = fileMenu(c)
    for (const id of ['file.new', 'file.open', 'file.save', 'file.save-as', 'file.download', 'file.manage.export', 'file.close']) {
      byId(file.items, id).action!()
    }
    expect(calls).toEqual(['leave:fresh', 'leave', 'save', 'open:checkpoint', 'open:export', 'open:export-format', 'leave'])
  })

  it('has Print… after Download only in an app that can print (composes, D906), with its shortcut', () => {
    const { c, calls } = context()
    const printing = fileMenu({ ...c, print: () => calls.push('print') })
    expect(ids(printing.items)).toEqual(['file.new', 'file.open', 'file.save', 'file.save-as', 'file.download', 'file.print', 'file.manage', 'file.close'])
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

describe('View, Tools, Config and Help pieces', () => {
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

  it('Config ▸ App Language lists LANGUAGES, ticks the current one, and chooses', () => {
    const chosen: string[] = []
    const config = configMenu(context().c, { current: 'de', choose: (tag) => chosen.push(tag) })
    expect(ids(config.items)).toEqual(['config.shortcuts', 'App Language'])
    const languages = config.items[1]!.items!
    expect(languages.map((l) => [l.id, l.label, l.checked])).toEqual(LANGUAGES.map(([tag, name]) => [`config.language.${tag}`, name, tag === 'de']))
    languages[0]!.action!()
    expect(chosen).toEqual([LANGUAGES[0]![0]])
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

describe('searchItem: Edit ▸ Search & replace… (D281, E5.15)', () => {
  it('is one entry with its shortcut, and opens the panel', () => {
    const { c } = context()
    const opened: string[] = []
    const item = searchItem(c, { open: () => opened.push('open') })
    expect([item.id, item.label, item.hint]).toEqual(['edit.search-replace', 'Search & replace…', 'Ctrl+F'])
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
