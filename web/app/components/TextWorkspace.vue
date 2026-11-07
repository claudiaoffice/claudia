<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { countWords } from '~/lib/blocks'
import { toMarkdown } from '~/lib/markdown'
import { SAMPLE_TEXT } from '~/lib/sample'
import { textStyleHost } from '~/lib/text-style-host'
import type { TextSession } from '~/lib/text-session'
import { copySelection, cutSelection } from '~/lib/clipboard'
import { applyAction, collectStates } from '~/lib/menu-dispatch'
import { chordLabel, installWindowShortcuts, sharedShortcuts } from '~/lib/shortcuts'
import { createShellBridge } from '~/lib/shell-bridge'
import { useTheme } from '~/lib/theme'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: TextSession }>()
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }] }>()

const session = props.session
const state = session.state
const { dark, toggle: toggleDark } = useTheme()

const dialog = ref<
  null | 'checkpoint' | 'share' | 'shortcuts' | 'about' | 'styles' | 'assign-owner' | 'accept-owner' | 'leave' | 'export' | 'delete'
>(null)
const styleMenu = ref<{ x: number; y: number } | null>(null)
const styleHost = textStyleHost(session)
const panelOpen = ref(true)
const active = ref<string | null>(null)
const editor = ref<{ focus: () => void; scrollToSuggestion: (id: string) => void; caretPoint: () => { x: number; y: number } } | null>(null)
const panel = ref<{ ask: (text?: string) => void } | null>(null)

// How I look at the text is mine alone (and is remembered in this browser).
function remembered<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key) as T | null
    return value && allowed.includes(value) ? value : fallback
  } catch {
    return fallback
  }
}
function remember(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* private window: nothing to remember */
  }
}
const view = ref<'flow' | 'page'>(remembered('claudia.composes.view', ['flow', 'page'], 'flow'))
const authors = ref(remembered('claudia.composes.authors', ['on', 'off'], 'off') === 'on')
watch(view, (v) => remember('claudia.composes.view', v))
watch(authors, (on) => remember('claudia.composes.authors', on ? 'on' : 'off'))

const readonly = computed(() => session.readOnly)
const words = computed(() => countWords(state.blocks))
const openSuggestions = computed(() => state.suggestions.filter((s) => s.state === 'open').length)

// ------------------------------------------------------------------------------ doing things
function pick(id: string) {
  active.value = id
  editor.value?.scrollToSuggestion(id)
}

async function checkpoint(label: string | null) {
  dialog.value = null
  await session.flush()
  if (await session.saveCheckpoint(label || null)) session.notice('Checkpoint saved.')
}

function ask(text: string) {
  panelOpen.value = true
  setTimeout(() => panel.value?.ask(text), 0)
}

async function download() {
  await session.flush()
  const blob = new Blob([toMarkdown(state.blocks)], { type: 'text/markdown' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${state.doc}.md`
  link.click()
  setTimeout(() => URL.revokeObjectURL(link.href), 1000)
}

function openStyleMenu(at = editor.value?.caretPoint() ?? { x: 80, y: 120 }) {
  styleMenu.value = at
}

function closeStyleMenu() {
  styleMenu.value = null
  editor.value?.focus()
}

function insertSample() {
  session.paste(SAMPLE_TEXT)
  editor.value?.focus()
}

// composes has one way to bring text in, however it arrives (typed, "Paste", or "Paste as plain text") — there is no
// separate rich-paste path yet, so the two Edit items below are, honestly, the same operation.
async function pasteFromClipboard() {
  let text: string
  try {
    text = await navigator.clipboard.readText()
  } catch {
    return // no permission, no secure context, or nothing textual on the clipboard — same as a native paste finding nothing
  }
  if (text) {
    session.paste(text)
    editor.value?.focus()
  }
}

// ------------------------------------------------------------------------------ menus, shortcuts and the shell
// D122: one structured list instead of a hand-rolled `keydown` handler; `hints` turns the same list into the menu's
// `hint` labels, so a shortcut and what the menu claims about it cannot drift apart.
const shortcuts = computed(() => [
  ...sharedShortcuts({
    undo: () => session.undo(),
    redo: () => session.redo(),
    save: () => {
      if (!readonly.value) void checkpoint(null)
    },
  }),
  { id: 'format.look', label: 'Edit this style…', chord: { key: 'F10', shift: true }, run: () => openStyleMenu() },
])
installWindowShortcuts(() => shortcuts.value)
const hints = computed<Record<string, string>>(() => Object.fromEntries(shortcuts.value.map((s) => [s.id, chordLabel(s.chord)])))

const menus = computed<Menu[]>(() => [
  {
    label: 'File',
    items: [
      { id: 'file.new', label: 'New', action: () => emit('leave', { startFresh: true }) },
      { id: 'file.open', label: 'Open…', action: () => emit('leave') },
      { label: '', separator: true },
      { id: 'file.save', label: 'Save', hint: hints.value['file.save'], action: () => checkpoint(null), disabled: readonly.value },
      { id: 'file.save-as', label: 'Save new checkpoint…', action: () => (dialog.value = 'checkpoint'), disabled: readonly.value },
      { id: 'file.download', label: 'Download', action: download },
      { label: '', separator: true },
      {
        id: 'file.manage',
        label: 'Manage',
        items: [
          { id: 'file.manage.share', label: 'Share…', action: () => (dialog.value = 'share'), disabled: state.me.role !== 'owner' },
          {
            id: 'file.manage.assign-owner',
            label: 'Assign new owner…',
            action: () => (dialog.value = 'assign-owner'),
            disabled: state.me.role !== 'owner',
          },
          { id: 'file.manage.accept-owner', label: 'Accept ownership…', action: () => (dialog.value = 'accept-owner'), disabled: state.me.role === 'viewer' },
          { id: 'file.manage.leave', label: 'Leave document…', action: () => (dialog.value = 'leave') },
          { id: 'file.manage.export', label: 'Export…', action: () => (dialog.value = 'export') },
          {
            id: 'file.manage.delete',
            label: 'Delete from server…',
            action: () => (dialog.value = 'delete'),
            disabled: state.me.role !== 'owner',
          },
        ],
      },
      { label: '', separator: true },
      { id: 'file.close', label: 'Close document', action: () => emit('leave') },
    ],
  },
  {
    label: 'Edit',
    items: [
      { id: 'edit.undo', label: state.canUndo ? `Undo ${state.undoLabel}` : 'Undo', hint: hints.value['edit.undo'], action: () => session.undo(), disabled: !state.canUndo },
      { id: 'edit.redo', label: state.canRedo ? `Redo ${state.redoLabel}` : 'Redo', hint: hints.value['edit.redo'], action: () => session.redo(), disabled: !state.canRedo },
      { label: '', separator: true },
      { id: 'edit.copy', label: 'Copy', hint: 'Ctrl+C', action: () => copySelection() },
      { id: 'edit.cut', label: 'Cut', hint: 'Ctrl+X', action: () => cutSelection(), disabled: readonly.value },
      { id: 'edit.paste', label: 'Paste', hint: 'Ctrl+V', action: () => pasteFromClipboard(), disabled: readonly.value },
      {
        id: 'edit.paste-as',
        label: 'Paste as',
        disabled: readonly.value,
        // The child's own `disabled` is what a shell actually reports per-action (`collectStates` walks each item on
        // its own terms, not by inheriting a parent's); the parent's `disabled` above only keeps the web menu from
        // opening the flyout at all — both need to agree, or a shell could show the leaf as enabled regardless.
        items: [{ id: 'edit.paste-as-plain', label: 'Plain text', action: () => pasteFromClipboard(), disabled: readonly.value }],
      },
    ],
  },
  {
    label: 'Format',
    items:
      state.styles.length === 0
        ? [{ label: 'No styles yet', disabled: true }]
        : [
            ...['title', 'heading-1', 'heading-2'].map((id) => styleItem(id)),
            { label: '', separator: true },
            ...['body'].map((id) => styleItem(id)),
            { label: '', separator: true },
            ...['quote', 'remark', 'definition'].map((id) => styleItem(id)),
            ...customStyleItems(),
            { label: '', separator: true },
            { id: 'format.look', label: 'Edit this style…', hint: hints.value['format.look'], action: () => openStyleMenu() },
            { id: 'format.all-styles', label: 'All styles…', action: () => (dialog.value = 'styles') },
          ],
  },
  {
    label: 'View',
    items: [
      { id: 'view.authors', label: 'Show who wrote what', checked: authors.value, action: (t) => (authors.value = t ? t === 'on' : !authors.value) },
      { id: 'view.panel', label: 'History and chat', checked: panelOpen.value, action: (t) => (panelOpen.value = t ? t === 'on' : !panelOpen.value) },
      {
        id: 'view.dark',
        label: 'Dark mode',
        checked: dark(),
        action: (t) => {
          if (t === undefined || (t === 'on') !== dark()) toggleDark()
        },
      },
      { label: '', separator: true },
      { label: 'Flow', checked: view.value === 'flow', action: () => (view.value = 'flow') },
      // One boolean action (GTK has no notion of two radio items), set/cleared explicitly by a shell, toggled by a web click.
      { id: 'view.page', label: 'Page', checked: view.value === 'page', action: (t) => (view.value = t === 'off' ? 'flow' : 'page') },
    ],
  },
  {
    label: 'Tools',
    items: [
      { id: 'tools.ask', label: 'Ask the assistant…', action: () => ask('@ai ') },
      { id: 'tools.review-text', label: 'Review this text', action: () => ask('@ai review this text') },
      { id: 'tools.review-paragraph', label: 'Review this paragraph', action: () => ask('@ai check this paragraph') },
      { label: '', separator: true },
      { id: 'tools.insert-sample', label: 'Insert sample text', action: insertSample, disabled: readonly.value },
    ],
  },
  { label: 'Config', items: [{ id: 'config.shortcuts', label: 'Shortcuts', action: () => (dialog.value = 'shortcuts') }] },
  {
    label: 'Help',
    items: [
      { id: 'help.ask', label: 'Ask ai', action: () => ask('@ai ') },
      { id: 'help.how-to', label: 'How do I…?', disabled: true },
      { id: 'help.docs', label: 'Documentation', disabled: true },
      { id: 'help.about', label: 'About claudia', action: () => (dialog.value = 'about') },
    ],
  },
])

/** One Format-menu entry for a built-in style, by id — kept as a function rather than inlining `state.styles.find`
 * three times over, since the three groups below (D127: structure · running text · called-out blocks) each pick a
 * fixed subset of the seven built-in ids, not a contiguous slice. */
function styleItem(id: string) {
  const s = state.styles.find((s) => s.id === id)
  return {
    label: s?.name ?? id,
    checked: session.currentStyle() === id,
    action: () => {
      void session.setStyle(id)
      editor.value?.focus()
    },
    disabled: readonly.value || !s,
  }
}
const BUILTIN_STYLE_IDS = new Set(['body', 'title', 'heading-1', 'heading-2', 'quote', 'remark', 'definition'])
/** A style made by deviating from a built-in (`next_style` in `model.py`) is not one of the three fixed groups above
 * — D127 only grouped the seven built-ins, so anything else gets its own trailing group rather than being folded
 * silently into one of them. */
function customStyleItems() {
  const custom = state.styles.filter((s) => !BUILTIN_STYLE_IDS.has(s.id))
  if (!custom.length) return []
  return [{ label: '', separator: true }, ...custom.map((s) => styleItem(s.id))]
}

// `reactive` as `createShellBridge`'s `wrap` (not wrapping its return value) so the template's `shell.nativeMenu`
// re-renders once the shell's `welcome` message actually arrives: `window.__claudiaShell.receive` must call back
// into the reactive bridge itself, or `welcome`'s capabilities land outside Vue's dependency tracking. The cast is
// `reactive()`'s own return type (`Reactive<ShellBridge>`) structurally losing `ShellBridge`'s private fields --
// still there at runtime, just invisible to this particular structural check.
const shell = createShellBridge('composes', undefined, (bridge) => reactive(bridge) as typeof bridge)
shell.onAction((id, target) => applyAction(menus.value, id, target))
onBeforeUnmount(() => shell.detach())
watch(menus, (m) => shell.reportStates(collectStates(m)), { immediate: true })

// Config ▸ Shortcuts (D122/D126): the structured list above, plus the things that are not a `keydown` shortcut at
// all — typing itself, and native Ctrl+C/X/V, which the browser already handles for whatever has focus.
const EXTRA_SHORTCUTS: [string, string][] = [
  ['Type', 'write; a word is sent when it ends, and the others see where you are'],
  ['Enter', 'end the paragraph (after a heading the next one is body text)'],
  ['Backspace / Delete', 'delete; at the edge of a paragraph it joins the one next to it'],
  ['Ctrl + Backspace / Delete', 'delete a word'],
  ['Ctrl + C / X / V', 'copy, cut and paste, also from and to other programs'],
  ['@ai review this text', 'the assistant suggests changes; you accept or reject each'],
]

// ------------------------------------------------------------------------------ notices
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  () => state.notice?.id,
  (id) => {
    clearTimeout(timer)
    if (id !== undefined) timer = setTimeout(() => state.notice?.id === id && (state.notice = null), 6000)
  },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="workspace" data-testid="text-workspace">
    <TopBar :session="session" :panel-open="panelOpen" @toggle-panel="panelOpen = !panelOpen" />
    <div v-if="state.status === 'reconnecting'" class="banner" role="alert">The connection was lost. Trying to get back… what you type now is not saved.</div>
    <MenuBar :class="{ hidden: shell.nativeMenu }" :menus="menus" />
    <StyleBar :session="session" :view="view" :authors="authors" @view="view = $event" @authors="authors = $event" @styled="editor?.focus()" @look="openStyleMenu" />
    <div class="main" :class="{ wide: !panelOpen }">
      <TextEditor ref="editor" :session="session" :view="view" :authors="authors" :active="active" @suggestion="pick" @style-menu="openStyleMenu" />
      <SidePanel v-show="panelOpen" ref="panel" :session="session">
        <template #top><SuggestionList :session="session" :active="active" @pick="pick" /></template>
      </SidePanel>
    </div>
    <footer class="foot">
      <div class="stats mono" aria-live="polite">
        <span><b data-testid="words">{{ words }}</b> {{ words === 1 ? 'word' : 'words' }}</span>
        <span><b>{{ state.blocks.length }}</b> {{ state.blocks.length === 1 ? 'paragraph' : 'paragraphs' }}</span>
        <span v-if="openSuggestions"><b>{{ openSuggestions }}</b> {{ openSuggestions === 1 ? 'suggestion' : 'suggestions' }}</span>
      </div>
      <span class="rev mono" :title="`line ${state.line}`">{{ state.revision ?? 'empty' }}</span>
    </footer>

    <PromptDialog
      v-if="dialog === 'checkpoint'"
      title="Save new checkpoint"
      label="Name of this state (you can leave it empty)"
      ok="Save"
      placeholder="before the review"
      @ok="checkpoint"
      @close="dialog = null"
    />
    <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" @close="closeStyleMenu" @styles="(styleMenu = null), (dialog = 'styles')" />
    <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
    <ShareDialog v-if="dialog === 'share'" :session="session" @close="dialog = null" />
    <AssignOwnerDialog v-if="dialog === 'assign-owner'" :session="session" @close="dialog = null" />
    <AcceptOwnershipDialog v-if="dialog === 'accept-owner'" :session="session" @close="dialog = null" />
    <LeaveDocumentDialog v-if="dialog === 'leave'" :session="session" @close="dialog = null" @left="((dialog = null), emit('leave'))" />
    <ExportDialog v-if="dialog === 'export'" :session="session" @close="dialog = null" />
    <DeleteDocumentDialog v-if="dialog === 'delete'" :session="session" @close="dialog = null" @deleted="((dialog = null), emit('leave'))" />
    <ShortcutsDialog
      v-if="dialog === 'shortcuts'"
      :shortcuts="shortcuts.map((s) => ({ label: s.label, hint: chordLabel(s.chord) }))"
      :extra="EXTRA_SHORTCUTS"
      @close="dialog = null"
    />
    <AboutDialog v-if="dialog === 'about'" app="composes" @close="dialog = null" />

    <div v-if="state.notice" class="toast" :class="state.notice.kind" role="status" @click="state.notice = null">{{ state.notice.text }}</div>

    <div v-if="state.status === 'closed'" class="gone" role="alertdialog">
      <div>
        <h2>You are not connected any more</h2>
        <p>{{ state.error || 'The connection was closed.' }}</p>
        <button class="btn primary" type="button" @click="emit('leave')">Back to the documents</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}
.main {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  min-height: 0;
}
.main.wide {
  grid-template-columns: minmax(0, 1fr);
}
.banner {
  background: var(--apricot);
  color: var(--ink);
  padding: 6px 16px;
  font-weight: 500;
}
.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 32px;
  padding: 0 14px;
  background: var(--surface);
  border-top: 1px solid var(--line);
  font-size: 12px;
  color: var(--muted);
}
.stats {
  display: flex;
  gap: 16px;
}
.stats b {
  color: var(--text);
  font-weight: 500;
}
.toast {
  position: absolute;
  left: 50%;
  bottom: 54px;
  transform: translateX(-50%);
  max-width: min(560px, calc(100% - 32px));
  background: var(--ink);
  color: var(--paper);
  padding: 9px 16px;
  border-radius: 999px;
  box-shadow: var(--shadow);
  z-index: 50;
  cursor: pointer;
}
.toast.warning {
  background: var(--apricot);
  color: var(--ink);
}
.toast.error {
  background: var(--rose);
  color: #fff;
}
.gone {
  position: absolute;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  background: rgb(247 243 236 / 92%);
  text-align: center;
}
.gone h2 {
  font: 400 26px var(--font-display);
  margin: 0 0 8px;
}
@media (max-width: 736px) {
  .main {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr) 40%;
  }
}
</style>
