<script setup lang="ts">
// UX-03: a native <dialog> instead of a hand-rolled backdrop div. `showModal()` gives the focus trap and the inert
// background for free — nothing here manages focus or walks the DOM for tabbable elements any more.
//
// D128: Esc always closes a dialog, including a "locked" one — the native default (Esc fires `cancel` then `close`)
// already does exactly that, so `locked` only has one job left: block a click on the backdrop. `locked` no longer
// touches Escape at all.
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{ title: string; width?: number; locked?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const dialog = ref<HTMLDialogElement | null>(null)

onMounted(() => dialog.value?.showModal())
onUnmounted(() => dialog.value?.open && dialog.value.close())

/** A click lands on the `<dialog>` element itself (not something inside it) only when it hit the backdrop area: the
 * element box fits its content, so anything within the content has its own, nested target. */
function backdropClick(event: MouseEvent) {
  if (event.target === dialog.value && !props.locked) dialog.value?.close()
}

/** For the one dialog that has no close action at all (`RecoveryKeyDialog`: losing the only copy of a recovery key
 * is not an Esc-sized mistake to allow) to put itself back up after an Esc the person should not have been able to
 * make. Everything else lets `close` through and goes away, per D128. */
defineExpose({ reopen: () => dialog.value?.showModal() })
</script>

<template>
  <dialog
    ref="dialog"
    class="modal"
    :aria-label="title"
    :style="width ? { width: `min(${width}px, calc(100vw - 32px))` } : undefined"
    @click="backdropClick"
    @close="emit('close')"
  >
    <h2>{{ title }}</h2>
    <slot />
  </dialog>
</template>

<style scoped>
.modal {
  width: min(440px, calc(100vw - 32px));
  background: var(--surface);
  color: var(--text);
  border: 0;
  border-radius: 16px;
  padding: 24px 26px;
  box-shadow: var(--shadow);
  display: grid;
  gap: 14px;
}
.modal::backdrop {
  background: rgb(31 26 51 / 38%);
}
h2 {
  margin: 0;
  font: 400 24px/1.1 var(--font-display);
}
</style>
