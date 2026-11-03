<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { countWords } from '~/lib/blocks'
import { toMarkdown } from '~/lib/markdown'
import { SAMPLE_TEXT } from '~/lib/sample'
import { textStyleHost } from '~/lib/text-style-host'
import type { TextSession } from '~/lib/text-session'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: TextSession }>()
const emit = defineEmits<{ leave: [] }>()

const session = props.session
const state = session.state

const dialog = ref<null | 'checkpoint' | 'share' | 'help' | 'styles'>(null)
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

// ------------------------------------------------------------------------------ menus and keys
const menus = computed<Menu[]>(() => [
  {
    label: 'File',
    items: [
      { label: 'Save', hint: 'Ctrl+S', action: () => checkpoint(null), disabled: readonly.value },
      { label: 'Save with a name…', action: () => (dialog.value = 'checkpoint'), disabled: readonly.value },
      { label: 'Save as Markdown…', action: download },
      { label: '', separator: true },
      { label: 'Share…', action: () => (dialog.value = 'share'), disabled: state.me.role !== 'owner' },
      { label: '', separator: true },
      { label: 'Close document', action: () => emit('leave') },
    ],
  },
  {
    label: 'Edit',
    items: [
      { label: state.canUndo ? `Undo ${state.undoLabel}` : 'Undo', hint: 'Ctrl+Z', action: () => session.undo(), disabled: !state.canUndo },
      { label: state.canRedo ? `Redo ${state.redoLabel}` : 'Redo', hint: 'Ctrl+Y', action: () => session.redo(), disabled: !state.canRedo },
    ],
  },
  {
    label: 'Format',
    items: [
      ...state.styles.map((s) => ({
        label: s.name,
        checked: session.currentStyle() === s.id,
        action: () => {
          void session.setStyle(s.id)
          editor.value?.focus()
        },
        disabled: readonly.value,
      })),
      { label: '', separator: true },
      { label: 'Look of this style…', hint: 'Shift+F10', action: () => openStyleMenu() },
      { label: 'All styles…', action: () => (dialog.value = 'styles') },
    ],
  },
  {
    label: 'View',
    items: [
      { label: 'Flow', checked: view.value === 'flow', action: () => (view.value = 'flow') },
      { label: 'Page', checked: view.value === 'page', action: () => (view.value = 'page') },
      { label: '', separator: true },
      { label: 'Show who wrote what', checked: authors.value, action: () => (authors.value = !authors.value) },
      { label: 'History and chat', checked: panelOpen.value, action: () => (panelOpen.value = !panelOpen.value) },
    ],
  },
  {
    label: 'Tools',
    items: [
      { label: 'Ask the assistant…', action: () => ask('@ai ') },
      { label: 'Review this text', action: () => ask('@ai review this text') },
      { label: 'Review this paragraph', action: () => ask('@ai check this paragraph') },
      { label: '', separator: true },
      { label: 'Insert sample text', action: insertSample, disabled: readonly.value },
    ],
  },
  { label: 'Help', items: [{ label: 'Keyboard', action: () => (dialog.value = 'help') }] },
])

function onWindowKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
  if (event.key === 'F10' && event.shiftKey) {
    event.preventDefault()
    openStyleMenu()
    return
  }
  if (!(event.ctrlKey || event.metaKey)) return
  const key = event.key.toLowerCase()
  if (key === 'z' && !event.shiftKey) {
    event.preventDefault()
    void session.undo()
  } else if (key === 'y' || (key === 'z' && event.shiftKey)) {
    event.preventDefault()
    void session.redo()
  } else if (key === 's') {
    event.preventDefault()
    if (!readonly.value) void checkpoint(null)
  }
}
onMounted(() => window.addEventListener('keydown', onWindowKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKey))

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
    <MenuBar :menus="menus" />
    <StyleBar :session="session" :view="view" :authors="authors" @view="view = $event" @authors="authors = $event" @styled="editor?.focus()" />
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
      title="Save with a name"
      label="Name of this state (you can leave it empty)"
      ok="Save"
      placeholder="before the review"
      @ok="checkpoint"
      @close="dialog = null"
    />
    <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" @close="closeStyleMenu" @styles="(styleMenu = null), (dialog = 'styles')" />
    <StylesDialog v-if="dialog === 'styles'" :host="styleHost" @close="dialog = null" />
    <ShareDialog v-if="dialog === 'share'" :session="session" @close="dialog = null" />
    <HelpDialog v-if="dialog === 'help'" app="composes" @close="dialog = null" />

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
