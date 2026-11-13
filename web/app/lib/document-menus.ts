// The menu items every document window has, whatever the app (D120's shared blocks, D141's File ▸ Manage): built
// once here and assembled by each workspace with its own app-specific items around them. Before this, computes,
// composes and creates each spelled the same eighteen entries out by hand, and a change had to be made three times.
//
// Plain functions over a small context, with no Vue and no DOM, so a test can check what each app's menus share
// without mounting a component. The calls are `t('...')` on purpose: `scripts/extract_i18n.py` finds the strings
// here exactly as it does in a component.

import type { Menu, MenuItem } from '../components/MenuBar.vue'
import { copySelection, cutSelection } from './clipboard'
import { LANGUAGES } from './i18n'
import { chordLabel, sharedShortcuts } from './shortcuts'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string
type Toggle = (target?: 'on' | 'off') => void

/** The dialogs the document window itself owns (`DocumentFrame.vue`); an app's own dialogs stay with the app. */
export type FrameDialog =
  | 'checkpoint'
  | 'share'
  | 'shortcuts'
  | 'about'
  | 'assign-owner'
  | 'accept-owner'
  | 'leave'
  | 'export'
  | 'export-format'
  | 'delete'

/** What the shared items need from the window they are in. */
export interface DocumentMenuContext {
  t: Translate
  /** The person's role in this document: `owner`, `editor` or `viewer`. */
  role: string
  /** Open one of the window's own dialogs. */
  open: (dialog: FrameDialog) => void
  /** Back to the documents; `startFresh` for File ▸ New. */
  leave: (opts?: { startFresh?: boolean }) => void
  /** File ▸ Save: a checkpoint without a name. */
  save: () => void
  /** File ▸ Print…: open the print preview (D906). Only an app that can lay out pages gives it; composes does. */
  print?: () => void
}

/** The shortcut of File ▸ Print… (D906). */
export const PRINT_CHORD = { key: 'p', ctrl: true } as const

/** The menu hints for the shortcuts every window listens for (`sharedShortcuts`), so the two cannot drift apart. */
export const SHARED_HINTS: Readonly<Record<string, string>> = Object.fromEntries(
  sharedShortcuts({ undo: () => {}, redo: () => {}, save: () => {} }).map((s) => [s.id, chordLabel(s.chord)]),
)

const separator: MenuItem = { label: '', separator: true }

/** A checkable item a shell can set by name (`'on'`/`'off'`) and a click toggles. */
function toggling(isOn: () => boolean, toggle: () => void): Toggle {
  return (target) => {
    if (target === undefined || (target === 'on') !== isOn()) toggle()
  }
}

export function fileMenu(c: DocumentMenuContext): Menu {
  const { t } = c
  const owner = c.role === 'owner'
  const viewer = c.role === 'viewer'
  return {
    label: t('File'),
    items: [
      { id: 'file.new', label: t('New'), action: () => c.leave({ startFresh: true }) },
      { id: 'file.open', label: t('Open…'), action: () => c.leave() },
      separator,
      { id: 'file.save', label: t('Save'), hint: SHARED_HINTS['file.save'], action: () => c.save(), disabled: viewer },
      { id: 'file.save-as', label: t('Save new checkpoint…'), action: () => c.open('checkpoint'), disabled: viewer },
      { id: 'file.download', label: t('Download'), action: () => c.open('export') },
      ...(c.print ? [{ id: 'file.print', label: t('Print…'), hint: chordLabel(PRINT_CHORD), action: c.print }] : []),
      separator,
      {
        id: 'file.manage',
        label: t('Manage'),
        items: [
          { id: 'file.manage.share', label: t('Share…'), action: () => c.open('share'), disabled: !owner },
          { id: 'file.manage.assign-owner', label: t('Assign new owner…'), action: () => c.open('assign-owner'), disabled: !owner },
          { id: 'file.manage.accept-owner', label: t('Accept ownership…'), action: () => c.open('accept-owner'), disabled: viewer },
          { id: 'file.manage.leave', label: t('Leave document…'), action: () => c.open('leave') },
          { id: 'file.manage.export', label: t('Export…'), action: () => c.open('export-format') },
          { id: 'file.manage.delete', label: t('Delete from server…'), action: () => c.open('delete'), disabled: !owner },
        ],
      },
      separator,
      { id: 'file.close', label: t('Close document'), action: () => c.leave() },
    ],
  }
}

/** Edit's first two items: what would be undone or redone, by name. */
export function undoRedoItems(
  c: DocumentMenuContext,
  h: { canUndo: boolean; undoLabel: string; canRedo: boolean; redoLabel: string; undo: () => void; redo: () => void },
): MenuItem[] {
  const { t } = c
  return [
    {
      id: 'edit.undo',
      label: h.canUndo ? t('Undo {label}', { label: h.undoLabel }) : t('Undo'),
      hint: SHARED_HINTS['edit.undo'],
      action: () => h.undo(),
      disabled: !h.canUndo,
    },
    {
      id: 'edit.redo',
      label: h.canRedo ? t('Redo {label}', { label: h.redoLabel }) : t('Redo'),
      hint: SHARED_HINTS['edit.redo'],
      action: () => h.redo(),
      disabled: !h.canRedo,
    },
  ]
}

/** Copy, Cut, Paste and Paste as ▸ Plain text. Where pasted text goes is the app's: `paste` brings it in. */
export function clipboardItems(c: DocumentMenuContext, paste: () => void): MenuItem[] {
  const { t } = c
  const viewer = c.role === 'viewer'
  return [
    { id: 'edit.copy', label: t('Copy'), hint: 'Ctrl+C', action: () => copySelection() },
    { id: 'edit.cut', label: t('Cut'), hint: 'Ctrl+X', action: () => cutSelection(), disabled: viewer },
    { id: 'edit.paste', label: t('Paste'), hint: 'Ctrl+V', action: () => paste(), disabled: viewer },
    {
      id: 'edit.paste-as',
      label: t('Paste as'),
      disabled: viewer,
      // The child's own `disabled` is what a shell actually reports per action (`collectStates` walks each item on
      // its own terms, not by inheriting a parent's); the parent's only keeps the web menu from opening the flyout.
      // Both have to agree, or a shell could show the leaf as enabled.
      items: [{ id: 'edit.paste-as-plain', label: t('Plain text'), action: () => paste(), disabled: viewer }],
    },
  ]
}

/** View ▸ History and chat. */
export function panelItem(c: DocumentMenuContext, panel: { open: () => boolean; toggle: () => void }): MenuItem {
  const { t } = c
  return { id: 'view.panel', label: t('History and chat'), checked: panel.open(), action: toggling(panel.open, panel.toggle) }
}

/** View ▸ Dark mode. */
export function darkItem(c: DocumentMenuContext, theme: { on: () => boolean; toggle: () => void }): MenuItem {
  const { t } = c
  return { id: 'view.dark', label: t('Dark mode'), checked: theme.on(), action: toggling(theme.on, theme.toggle) }
}

/** View ▸ Show who wrote what, for an app that does not track authorship of its content yet: shown, and off. */
export function authorsItemUnavailable(c: DocumentMenuContext): MenuItem {
  const { t } = c
  return { id: 'view.authors', label: t('Show who wrote what'), checked: false, disabled: true }
}

/** Tools ▸ Ask the assistant…, the one Tools item every app has. */
export function askItem(c: DocumentMenuContext, ask: (text: string) => void): MenuItem {
  const { t } = c
  return { id: 'tools.ask', label: t('Ask the assistant…'), action: () => ask('@ai ') }
}

/** Config: Shortcuts, and App Language from `LANGUAGES` (each language under its own name, never translated). */
export function configMenu(c: DocumentMenuContext, language: { current: string; choose: (tag: string) => void }): Menu {
  const { t } = c
  return {
    label: t('Config'),
    items: [
      { id: 'config.shortcuts', label: t('Shortcuts'), action: () => c.open('shortcuts') },
      {
        label: t('App Language'),
        items: LANGUAGES.map(([tag, autonym]) => ({
          id: `config.language.${tag}`,
          label: autonym,
          checked: language.current === tag,
          action: () => language.choose(tag),
        })),
      },
    ],
  }
}

/** Help: ask the assistant, the help tab's two modes (E13.5), About. */
export function helpMenu(
  c: DocumentMenuContext,
  panel: { ask: (text: string) => void; openHelp: (mode: 'how-to' | 'docs') => void },
): Menu {
  const { t } = c
  return {
    label: t('Help'),
    items: [
      { id: 'help.ask', label: t('Ask ai'), action: () => panel.ask('@ai ') },
      { id: 'help.how-to', label: t('How do I…?'), action: () => panel.openHelp('how-to') },
      { id: 'help.docs', label: t('Documentation'), action: () => panel.openHelp('docs') },
      { id: 'help.about', label: t('About claudia'), action: () => c.open('about') },
    ],
  }
}
