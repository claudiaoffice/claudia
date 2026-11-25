// What the entries every document window has do, whatever the app (D120's shared blocks, D1644): File, Undo and Redo,
// the clipboard, Search and Replace…, History & Chat, Replay…, Back Where I Was, Dark Mode, Ask ai…, Preferences and
// Help. Each workspace adds its own handlers to these. Where an entry stands and when it fits is the definition's
// (`menus.generated.ts`); this only says what it does. The calls are `t('...')` on purpose, for `scripts/extract_i18n.py`.
import { copySelection, cutSelection } from '../clipboard'
import type { Translate } from '../fits/conditions'
import { LANGUAGES } from '../i18n'
import type { Handler, Handlers } from './assemble'

/** The dialogs the document window itself owns (`DocumentFrame.vue`); an app's own dialogs stay with the app. */
export type FrameDialog =
  | 'checkpoint'
  | 'share'
  | 'shortcuts'
  | 'about'
  | 'assign-owner'
  | 'accept-owner'
  | 'leave'
  | 'change-password'
  | 'download'
  | 'export-format'
  | 'delete'
  | 'redact'
  | 'open'
  | 'open-file'
  | 'ai'

/** What the shared entries need from the window they are in. */
export interface WindowContext {
  t: Translate
  /** Open one of the window's own dialogs. */
  open: (dialog: FrameDialog) => void
  /** Back to the documents; `startFresh` for File ▸ New. */
  leave: (opts?: { startFresh?: boolean }) => void
  /** File ▸ Print…: the print preview (D906). */
  print: () => void
  history: {
    undo: () => void
    redo: () => void
    /** What would be undone or redone, by name ("Add Container"); empty when there is nothing. */
    undoLabel: () => string
    redoLabel: () => string
  }
  /** Where pasted text goes is the app's. */
  paste: () => void
  search: () => void
  panel: { open: () => boolean; toggle: () => void }
  /** View ▸ Replay…: `null` when it can start, else why not. */
  replay: { start: () => void; notNow: () => string | null }
  back: () => void
  theme: { on: () => boolean; toggle: () => void }
  ask: (text: string) => void
  help: (mode: 'how-to' | 'docs') => void
  language: { current: () => string; choose: (tag: string) => void }
}

export function windowHandlers(c: WindowContext): Handlers {
  const { t } = c
  const dialog = (name: FrameDialog): Handler => ({ run: () => c.open(name) })
  const languages: Record<string, Handler> = Object.fromEntries(
    LANGUAGES.map(([tag, autonym]) => [
      `config.language.${tag}`,
      // each language under its own name, never translated; choosing the one in use leaves it chosen
      { run: () => c.language.choose(tag), label: () => autonym, checked: () => c.language.current() === tag },
    ]),
  )
  return {
    'file.new': { run: () => c.leave({ startFresh: true }) },
    'file.open': dialog('open'),
    'file.open-file': dialog('open-file'),
    'file.save-as': dialog('checkpoint'),
    'file.download': dialog('download'),
    'file.print': { run: () => c.print() },
    // Share… has a sentence of its own for who may not (D1650)
    'file.manage.share': { ...dialog('share'), why: { role: t('Only an owner can share this document.') } },
    'file.manage.change-password': dialog('change-password'),
    'file.manage.export': dialog('export-format'),
    'file.manage.redact': dialog('redact'),
    'file.close': { run: () => c.leave() },
    'edit.undo': {
      run: () => c.history.undo(),
      label: () => (c.history.undoLabel() ? t('Undo {label}', { label: c.history.undoLabel() }) : t('Undo')),
    },
    'edit.redo': {
      run: () => c.history.redo(),
      label: () => (c.history.redoLabel() ? t('Redo {label}', { label: c.history.redoLabel() }) : t('Redo')),
    },
    // Copy has a sentence of its own for a viewer (D1640, D1650)
    'edit.copy': { run: () => copySelection(), why: { role: t('Only editors and owners can copy from this document.') } },
    'edit.cut': { run: () => cutSelection() },
    'edit.paste': { run: () => c.paste() },
    'edit.paste-as-plain': { run: () => c.paste() },
    'edit.search-replace': { run: () => c.search() },
    'view.panel': { run: () => c.panel.toggle(), checked: () => c.panel.open() },
    'view.replay': { run: () => c.replay.start(), notNow: c.replay.notNow },
    'view.back': { run: () => c.back() },
    'view.dark': { run: () => c.theme.toggle(), checked: () => c.theme.on() },
    'tools.ask': { run: () => c.ask('@ai ') },
    'config.shortcuts': dialog('shortcuts'),
    'config.ai': dialog('ai'),
    ...languages,
    'help.how-to': { run: () => c.help('how-to') },
    'help.docs': { run: () => c.help('docs') },
    'help.about': dialog('about'),
  }
}

/** An entry this app shows and cannot do yet, greyed with the reason (View ▸ Who Wrote What outside composes). */
export function notYet(t: Translate): Handler {
  return { run: () => {}, notNow: () => t('This is not here yet.'), checked: () => false }
}
