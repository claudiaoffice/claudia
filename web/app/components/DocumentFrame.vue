<script setup lang="ts">
// What a document window has, whatever the app (used by creates; the workspaces of computes and composes have their own
// copy of the same chrome and could move onto this): the top bar, menus, the panel with history and chat, the notices,
// the keys for undo, redo and save, and the dialogs to save and to share. The app fills in the rest through the slots:
// `toolbar` (under the menus), the main area (default), `footer` and `overlay` (its own dialogs).
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { applyAction, collectStates } from '~/lib/menu-dispatch'
import { chordLabel, installWindowShortcuts, sharedShortcuts, type ShortcutDef } from '~/lib/shortcuts'
import { createShellBridge } from '~/lib/shell-bridge'
import type { ExportFormatOption } from './ExportFormatDialog.vue'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: BaseSession; menus: Menu[]; exportFormats: ExportFormatOption[] }>()
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }]; saved: [] }>()

const state = props.session.state
const panelOpen = ref(true)
const dialog = ref<null | 'checkpoint' | 'share' | 'shortcuts' | 'about' | 'assign-owner' | 'accept-owner' | 'leave' | 'export' | 'export-format' | 'delete'>(null)
const panel = ref<{ ask: (text?: string) => void; openHelp: (mode?: 'how-to' | 'docs') => void } | null>(null)
const readonly = computed(() => state.me.role === 'viewer')

async function checkpoint(label: string | null) {
  dialog.value = null
  if (await props.session.saveCheckpoint(label || null)) props.session.notice('Checkpoint saved.')
  emit('saved')
}

/** Open the panel with the cursor in the chat box, ready to write to the assistant. */
function ask(text = '@ai ') {
  panelOpen.value = true
  setTimeout(() => panel.value?.ask(text), 0)
}

/** Help ▸ "How do I…?" / "Documentation" (D125's stubs, real now: E13.5). */
function openHelp(mode?: 'how-to' | 'docs') {
  panelOpen.value = true
  setTimeout(() => panel.value?.openHelp(mode), 0)
}

// D122: the shared shortcut map, same as the other two workspaces. `SlideWorkspace.vue` has nothing of its own to
// add to Undo/Redo/Save, so this is the complete list — kept here (not duplicated in the parent) since this is also
// where Ctrl+S's own dialog state (`dialog`) and `readonly` already live. Exposed so the parent's Config ▸ Shortcuts
// dialog can show the same list it is actually wired to.
const shortcuts = computed<ShortcutDef[]>(() => [
  ...sharedShortcuts({
    undo: () => props.session.undo(),
    redo: () => props.session.redo(),
    save: () => {
      if (!readonly.value) void checkpoint(null)
    },
  }),
])
installWindowShortcuts(() => shortcuts.value)

defineExpose({
  checkpoint,
  ask,
  openHelp,
  shortcuts,
  openDialog: (
    name: 'checkpoint' | 'share' | 'shortcuts' | 'about' | 'assign-owner' | 'accept-owner' | 'leave' | 'export' | 'export-format' | 'delete',
  ) => (dialog.value = name),
  /** View ▸ History and chat (D120's shared block) toggles the one `panelOpen` this frame owns — exposed as a
   * getter/setter pair, not the ref itself, so the parent's own `computed` menus still track it correctly. */
  isPanelOpen: () => panelOpen.value,
  togglePanel: () => (panelOpen.value = !panelOpen.value),
})

// The shell bridge is wired here, not per-app, since the menus (built by the parent) are what state is reported
// for, and the frame is what every creates document already mounts.
// `reactive` as `createShellBridge`'s `wrap` (not wrapping its return value) so the template's `shell.nativeMenu`
// re-renders once the shell's `welcome` message actually arrives: `window.__claudiaShell.receive` must call back
// into the reactive bridge itself, or `welcome`'s capabilities land outside Vue's dependency tracking. The cast is
// `reactive()`'s own return type (`Reactive<ShellBridge>`) structurally losing `ShellBridge`'s private fields --
// still there at runtime, just invisible to this particular structural check.
const shell = createShellBridge('creates', undefined, (bridge) => reactive(bridge) as typeof bridge)
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
  <div class="frame">
    <TopBar :session="session" :panel-open="panelOpen" @toggle-panel="panelOpen = !panelOpen" />
    <div v-if="state.status === 'reconnecting'" class="banner" role="alert">The connection was lost. Trying to get back… what you do now is not saved.</div>
    <MenuBar :class="{ hidden: shell.nativeMenu }" :menus="menus" />
    <slot name="toolbar" />
    <div class="main" :class="{ wide: !panelOpen }">
      <slot />
      <SidePanel v-show="panelOpen" ref="panel" :session="session" />
    </div>
    <slot name="footer" />

    <PromptDialog
      v-if="dialog === 'checkpoint'"
      title="Save new checkpoint"
      label="Name of this state (you can leave it empty)"
      ok="Save"
      placeholder="before the review"
      @ok="checkpoint"
      @close="dialog = null"
    />
    <ShareDialog v-if="dialog === 'share'" :session="session" @close="dialog = null" />
    <AssignOwnerDialog v-if="dialog === 'assign-owner'" :session="session" @close="dialog = null" />
    <AcceptOwnershipDialog v-if="dialog === 'accept-owner'" :session="session" @close="dialog = null" />
    <LeaveDocumentDialog v-if="dialog === 'leave'" :session="session" @close="dialog = null" @left="((dialog = null), emit('leave'))" />
    <ExportDialog v-if="dialog === 'export'" :session="session" @close="dialog = null" />
    <ExportFormatDialog v-if="dialog === 'export-format'" :session="session" :formats="exportFormats" @close="dialog = null" />
    <DeleteDocumentDialog v-if="dialog === 'delete'" :session="session" @close="dialog = null" @deleted="((dialog = null), emit('leave'))" />
    <ShortcutsDialog
      v-if="dialog === 'shortcuts'"
      :shortcuts="shortcuts.map((s) => ({ label: s.label, hint: chordLabel(s.chord) }))"
      :extra="[
        ['Click', 'select an object (colleagues cannot change it while you hold it)'],
        ['Drag', 'move it; the handles resize it'],
        ['Double-click, Enter', 'write in it; Enter keeps the text, Shift+Enter starts a line, Esc drops it'],
        ['Arrows', 'move it by 10 units; with Shift by 1'],
        ['Ctrl + C / X / V', 'copy, cut and paste, also from and to other programs'],
      ]"
      @close="dialog = null"
    />
    <AboutDialog v-if="dialog === 'about'" app="creates" @close="dialog = null" />
    <slot name="overlay" />

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
.frame {
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
