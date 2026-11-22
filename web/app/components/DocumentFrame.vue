<script setup lang="ts">
import { lookOnly } from '~/lib/replay'
// What a document window has, whatever the app: the top bar, the menus, the panel with history and chat, the notices,
// the keys for undo, redo and save, the dialogs to save, share, hand over, export and delete, and the "not connected
// any more" screen. computes, composes and creates all mount it; each fills in the rest through the slots: `toolbar`
// (under the menus), the main area (default), `side-top` (above the panel's tabs), `footer`, and `overlay` (its own
// dialogs and popovers). The menus themselves are the app's, built mostly from `lib/document-menus.ts`.
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import type { Thing } from '~/lib/tags'
import type { FrameDialog } from '~/lib/document-menus'
import type { Picked } from '~/lib/redaction'
import { applyAction, collectStates } from '~/lib/menu-dispatch'
import { cycleRegions, windowRegions } from '~/lib/regions'
import { chordLabel, installWindowShortcuts, menuShortcuts, regionShortcuts, sharedShortcuts, type ShortcutDef } from '~/lib/shortcuts'
import { createShellBridge } from '~/lib/shell-bridge'
import type { AnySession } from '~/lib/open'
import { openedFromDocument } from '~/lib/switch-session'
import type { ExportFormatOption } from './ExportFormatDialog.vue'
import type { Menu } from './MenuBar.vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    session: BaseSession
    app: 'computes' | 'composes' | 'creates'
    menus: Menu[]
    exportFormats: ExportFormatOption[]
    /** This app's own shortcuts, on top of Undo, Redo and Save (D122). */
    extraShortcuts?: ShortcutDef[]
    /** Preferences ▸ Shortcuts: what is not a single key chord (the mouse, typing), as [keys, what it does]. */
    shortcutNotes?: [string, string][]
  }>(),
  { extraShortcuts: () => [], shortcutNotes: () => [] },
)
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }]; saved: [] }>()

const state = props.session.state
const panelOpen = ref(true)
const dialog = ref<FrameDialog | null>(null)
const panel = ref<{
  ask: (text?: string) => void
  openHelp: (mode?: 'how-to' | 'docs', topic?: string) => void
  replay: () => void
  reference: (thing: Thing) => void
  pickToRedact: () => void
  clearRedactionPick: () => void
} | null>(null)
/** What the person picked to redact, while the dialog for it is open (E3.14). */
const redaction = ref<Picked | null>(null)
const readonly = computed(() => lookOnly(state))
const frame = ref<HTMLElement | null>(null)

/** F6 / Shift+F6: on to the next (or back to the previous) part of the window (WCAG 2.1.2, 2.4.1). */
function moveBetweenRegions(backwards: boolean) {
  if (frame.value) cycleRegions(windowRegions(frame.value), document.activeElement, backwards)
}

/** Save a checkpoint. What is still being typed is sent first, so the checkpoint holds it (composes, `flush`). */
async function checkpoint(label: string | null) {
  dialog.value = null
  await props.session.flush()
  if (await props.session.saveCheckpoint(label || null)) props.session.notice(t('Checkpoint saved.'))
  emit('saved')
}

/** Open one of the window's own dialogs. An export reads the document as it stands this instant, so whatever is
 * still being typed is sent first. */
async function openDialog(name: FrameDialog) {
  if (name === 'download' || name === 'export-format') await props.session.flush()
  if (name === 'redact') return pickToRedact()
  dialog.value = name
}

/** File ▸ Manage ▸ Redact History…: the panel opens with a pick box on every row it may redact (E3.14, D727); the
 * dialog opens once something is picked. */
function pickToRedact() {
  panelOpen.value = true
  setTimeout(() => panel.value?.pickToRedact(), 0)
}
async function redact(picked: Picked) {
  await props.session.flush() // what is still being typed belongs to the history that is planned
  redaction.value = picked
}
function redacted() {
  redaction.value = null
  panel.value?.clearRedactionPick()
}

/** File ▸ Open… opened another document: the window shows it in place of this one (`app.vue`). */
function showOpened(next: AnySession) {
  dialog.value = null
  openedFromDocument.value = next
}

/** Open the panel with the cursor in the chat box, ready to write to the assistant. */
function ask(text = '@ai ') {
  panelOpen.value = true
  setTimeout(() => panel.value?.ask(text), 0)
}

/** View ▸ Replay history…: open the panel and start looking at the document as it was (E5.19, D551). */
function replayHistory() {
  panelOpen.value = true
  setTimeout(() => panel.value?.replay(), 0)
}

/** Edit ▸ Reference in Chat: a tag for this thing goes into the message being written (E5.20, D551). */
async function referenceThing(id: string) {
  const thing = await props.session.thingToReference(id)
  if (!thing) return props.session.notice(t('That cannot be pointed at yet.'), 'warning')
  panelOpen.value = true
  setTimeout(() => panel.value?.reference(thing), 0)
}

/** Help ▸ "How do I…?" / "Documentation" (D125's stubs, real now: E13.5), and a link to one `topic` from the app. The
 * dock opens if it was closed, so the help is on the screen where the person asked for it. */
function openHelp(mode?: 'how-to' | 'docs', topic?: string) {
  panelOpen.value = true
  setTimeout(() => panel.value?.openHelp(mode, topic), 0)
}

// D122: the shared shortcut map and the app's own, in one list that both the window's key handler and
// Preferences ▸ Shortcuts read, so the dialog shows exactly what is wired. Then every other menu entry's key from the one
// table of all clients (UX-35): an entry with a key runs as if it were clicked.
const shortcuts = computed<ShortcutDef[]>(() => {
  const own = [
    ...sharedShortcuts({
      undo: () => props.session.undo(),
      redo: () => props.session.redo(),
      save: () => {
        if (!readonly.value) void checkpoint(null)
      },
    }),
    ...regionShortcuts({ next: () => moveBetweenRegions(false), previous: () => moveBetweenRegions(true) }),
    ...props.extraShortcuts,
  ]
  return [...own, ...menuShortcuts(props.menus, new Set(own.map((d) => d.id)))]
})
installWindowShortcuts(() => shortcuts.value)

defineExpose({
  checkpoint,
  ask,
  openHelp,
  replayHistory,
  referenceThing,
  openDialog,
  /** View ▸ History and chat (D120's shared block) toggles the one `panelOpen` this frame owns — exposed as a
   * getter/setter pair, not the ref itself, so the parent's own `computed` menus still track it correctly. */
  isPanelOpen: () => panelOpen.value,
  togglePanel: () => (panelOpen.value = !panelOpen.value),
})

// The shell bridge is wired here, not per app: the menus (built by the parent) are what state is reported for, and
// the frame is what every document mounts.
// `reactive` as `createShellBridge`'s `wrap` (not wrapping its return value) so the template's `shell.nativeMenu`
// re-renders once the shell's `welcome` message actually arrives: `window.__claudiaShell.receive` must call back
// into the reactive bridge itself, or `welcome`'s capabilities land outside Vue's dependency tracking. The cast is
// `reactive()`'s own return type (`Reactive<ShellBridge>`) structurally losing `ShellBridge`'s private fields --
// still there at runtime, just invisible to this particular structural check.
const shell = createShellBridge(props.app, undefined, (bridge) => reactive(bridge) as typeof bridge, 'document')
shell.onAction((id, target) => applyAction(props.menus, id, target))
onBeforeUnmount(() => shell.detach())
watch(() => props.menus, (m) => shell.reportStates(collectStates(m)), { immediate: true })

// A notice goes away by itself.
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
  <div ref="frame" class="frame" :class="{ wide: !panelOpen }">
    <TopBar :session="session" :panel-open="panelOpen" @toggle-panel="panelOpen = !panelOpen" />
    <div v-if="state.preview" class="banner preview" role="status" data-testid="redaction-preview">{{ t('Preview of the redaction: the marked places as they would be. Nothing has changed yet.') }}</div>
    <div v-if="state.status === 'reconnecting'" class="banner" role="alert">{{ t('The connection was lost. Trying to get back… what you do now is not saved.') }}</div>
    <FontReportBanner :session="session" />
    <MenuBar data-region="menus" :class="{ hidden: shell.nativeMenu }" :menus="menus" />
    <slot name="toolbar" />
    <div class="main" :class="{ wide: !panelOpen }">
      <slot />
      <SidePanel v-show="panelOpen" ref="panel" data-region="panel" :session="session" @redact="redact">
        <template #top><slot name="side-top" /></template>
      </SidePanel>
    </div>
    <BackChip :session="session" />
    <slot name="footer" />

    <PromptDialog
      v-if="dialog === 'checkpoint'"
      :title="t('Save new checkpoint')"
      :label="t('Name of this state (you can leave it empty)')"
      :ok="t('Save')"
      :placeholder="t('before the review')"
      @ok="checkpoint"
      @close="dialog = null"
    />
    <ShareDialog v-if="dialog === 'share'" :session="session" @close="dialog = null" />
    <AssignOwnerDialog v-if="dialog === 'assign-owner'" :session="session" @close="dialog = null" />
    <AcceptOwnershipDialog v-if="dialog === 'accept-owner'" :session="session" @close="dialog = null" />
    <ChangePasswordDialog
      v-if="dialog === 'change-password'"
      :session="session"
      @close="dialog = null"
      @changed="((dialog = null), session.notice(t('Your password for {doc} is changed.', { doc: session.state.doc }), 'info'))"
    />
    <LeaveDocumentDialog v-if="dialog === 'leave'" :session="session" @close="dialog = null" @left="((dialog = null), emit('leave'))" />
    <DownloadDialog v-if="dialog === 'download'" :session="session" @close="dialog = null" />
    <ExportFormatDialog v-if="dialog === 'export-format'" :session="session" :formats="exportFormats" @close="dialog = null" />
    <RedactionDialog v-if="redaction" :session="session" :picked="redaction" @close="redaction = null" @done="redacted" />
    <DeleteDocumentDialog v-if="dialog === 'delete'" :session="session" @close="dialog = null" @deleted="((dialog = null), emit('leave'))" />
    <ShortcutsDialog
      v-if="dialog === 'shortcuts'"
      :shortcuts="shortcuts.map((s) => ({ label: s.label, hint: chordLabel(s.chord) }))"
      :extra="shortcutNotes"
      @close="dialog = null"
    />
    <AboutDialog v-if="dialog === 'about'" :app="app" @close="dialog = null" />
    <OpenDialog
      v-if="dialog === 'open' || dialog === 'open-file'"
      modal
      :pick-file="dialog === 'open-file'"
      :shell-bridge="shell"
      @close="dialog = null"
      @opened="showOpened"
    />
    <slot name="overlay" />

    <div v-if="state.notice" class="toast" :class="state.notice.kind" role="status" @click="state.notice = null">{{ state.notice.text }}</div>

    <div v-if="state.status === 'waiting'" class="gone" role="alertdialog" data-testid="waiting-for-an-editor">
      <div>
        <h2>{{ state.doc || t('This document') }}</h2>
        <p>{{ state.error }}</p>
        <p class="trying">{{ t('Trying again every few seconds…') }}</p>
        <button class="btn" type="button" @click="emit('leave')">{{ t('Close') }}</button>
      </div>
    </div>

    <div v-if="state.status === 'closed'" class="gone" role="alertdialog">
      <div>
        <h2>{{ t('You are not connected any more') }}</h2>
        <p>{{ state.error || t('The connection was closed.') }}</p>
        <button class="btn primary" type="button" @click="emit('leave')">{{ t('Back to the documents') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.frame {
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
  /* How much of the right edge History and chat takes (the column of `.main`): a floating panel (the search panel,
   * D282) keeps to the left of it, so that it never covers what it opens there, like the help. */
  --dock-width: 340px;
}
.frame.wide {
  --dock-width: 0px;
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
/* The preview of a redaction (D721): the colour of the marks, and words that say nothing has changed yet. */
.banner.preview {
  background: var(--iris);
  color: #fff;
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
.gone .trying {
  color: var(--muted, #5b5470);
  font-size: 13px;
}
.gone h2 {
  font: 400 26px var(--font-display);
  margin: 0 0 8px;
}
@media (max-width: 736px) {
  .frame {
    --dock-width: 0px;
  }
  .main {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr) 40%;
  }
}
</style>
