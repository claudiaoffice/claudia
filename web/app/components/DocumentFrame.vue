<script setup lang="ts">
// What a document window has, whatever the app (used by creates; the workspaces of computes and composes have their own
// copy of the same chrome and could move onto this): the top bar, menus, the panel with history and chat, the notices,
// the keys for undo, redo and save, and the dialogs to save and to share. The app fills in the rest through the slots:
// `toolbar` (under the menus), the main area (default), `footer` and `overlay` (its own dialogs).
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import type { Menu } from './MenuBar.vue'

const props = defineProps<{ session: BaseSession; menus: Menu[] }>()
const emit = defineEmits<{ leave: []; saved: [] }>()

const state = props.session.state
const panelOpen = ref(true)
const dialog = ref<null | 'checkpoint' | 'share'>(null)
const panel = ref<{ ask: (text?: string) => void } | null>(null)
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

defineExpose({
  checkpoint,
  ask,
  openDialog: (name: 'checkpoint' | 'share') => (dialog.value = name),
})

function onWindowKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
  if (!(event.ctrlKey || event.metaKey)) return
  const key = event.key.toLowerCase()
  if (key === 'z' && !event.shiftKey) {
    event.preventDefault()
    props.session.undo()
  } else if (key === 'y' || (key === 'z' && event.shiftKey)) {
    event.preventDefault()
    props.session.redo()
  } else if (key === 's') {
    event.preventDefault()
    if (!readonly.value) checkpoint(null)
  }
}
onMounted(() => window.addEventListener('keydown', onWindowKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKey))

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
    <MenuBar :menus="menus" />
    <slot name="toolbar" />
    <div class="main" :class="{ wide: !panelOpen }">
      <slot />
      <SidePanel v-show="panelOpen" ref="panel" :session="session" />
    </div>
    <slot name="footer" />

    <PromptDialog
      v-if="dialog === 'checkpoint'"
      title="Save with a name"
      label="Name of this state (you can leave it empty)"
      ok="Save"
      placeholder="before the review"
      @ok="checkpoint"
      @close="dialog = null"
    />
    <ShareDialog v-if="dialog === 'share'" :session="session" @close="dialog = null" />
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
