<script setup lang="ts">
// UX-03: a native <dialog> instead of a hand-rolled backdrop div. `showModal()` gives the focus trap and the inert
// background for free — nothing here manages focus or walks the DOM for tabbable elements any more.
//
// D128: Esc always closes a dialog, including a "locked" one — the native default (Esc fires `cancel` then `close`)
// already does exactly that, so `locked` only has one job left: block a click on the backdrop. `locked` no longer
// touches Escape at all.
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useDraggable } from '~/lib/use-draggable'

const props = defineProps<{ title: string; width?: number; locked?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const dialog = ref<HTMLDialogElement | null>(null)

// UX-39: any dialog is moved by its title (the grip shows that it can be), or with Alt + the arrow keys. It stays where
// the person put it the next time the same dialog opens, while the page is open. `lib/dragging.ts` decides where it may go.
const { offset, moving, start, key, refit, justDragged } = useDraggable(dialog, props.title)

onMounted(() => {
  dialog.value?.showModal()
  void nextTick(refit)
  window.addEventListener('resize', refit)
})
onUnmounted(() => {
  window.removeEventListener('resize', refit)
  if (dialog.value?.open) dialog.value.close()
})

/** A click lands on the `<dialog>` element itself (not something inside it) only when it hit the backdrop area: the
 * element box fits its content, so anything within the content has its own, nested target. */
function backdropClick(event: MouseEvent) {
  if (event.target === dialog.value && !props.locked && !justDragged()) dialog.value?.close()
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
    :class="{ moving }"
    :style="{ ...(width ? { width: `min(${width}px, calc(100vw - 32px))` } : {}), '--dx': `${offset.x}px`, '--dy': `${offset.y}px` }"
    @click="backdropClick"
    @keydown="key"
    @close="emit('close')"
  >
    <header class="bar" @pointerdown="start">
      <svg class="grip" viewBox="0 0 10 16" width="10" height="16" aria-hidden="true"><circle cx="2.5" cy="3" r="1.4" /><circle cx="7.5" cy="3" r="1.4" /><circle cx="2.5" cy="8" r="1.4" /><circle cx="7.5" cy="8" r="1.4" /><circle cx="2.5" cy="13" r="1.4" /><circle cx="7.5" cy="13" r="1.4" /></svg>
      <h2>{{ title }}</h2>
    </header>
    <slot />
  </dialog>
</template>

<style scoped>
.modal {
  width: min(440px, calc(100vw - 32px));
  background: var(--surface);
  color: var(--text);
  /* `--shadow` alone used to carry the dialog's edge: a near-black shadow at low opacity, calibrated for a light
   * backdrop. Against a dark surface and backdrop (dark mode) it all but disappears — the owner's 2026-11-06 report
   * that a dialog's own boundary could not be seen. An explicit border is cheap insurance in both themes, not just
   * dark mode, and `--line-field` (not `--line`) because a dialog's edge is a control boundary, the 3:1 pairing. */
  border: 1px solid var(--line-field);
  border-radius: 16px;
  padding: 24px 26px;
  box-shadow: var(--shadow);
  display: grid;
  /* minmax(0, 1fr): a long unbreakable word (a file name) wraps instead of widening the dialog past the screen */
  grid-template-columns: minmax(0, 1fr);
  /* As tall as the content, and the rows never stretch: WebKitGTK sized the auto rows while `max-height` was the only
   * limit and kept them stretched in a window taller than the content (huge gaps, a pill button turned into a
   * circle). The gaps between rows come from `gap` alone. */
  height: fit-content;
  align-content: start;
  grid-auto-rows: max-content;
  max-height: calc(100vh - 32px);
  overflow: auto;
  gap: 14px;
  /* Where the person has moved it to (UX-39), as how far its edges are pushed from the centre they have by default: the
   * box keeps its size, and nothing is transformed, so a popover that a dialog opens still sits where it is meant to. */
  inset: var(--dy, 0px) calc(-1 * var(--dx, 0px)) calc(-1 * var(--dy, 0px)) var(--dx, 0px);
}
.modal::backdrop {
  background: rgb(31 26 51 / 38%);
}
/* The title is the handle: the grip says so, the cursor says so, and a drag that starts on it moves the dialog. */
.bar {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.moving .bar {
  cursor: grabbing;
}
.grip {
  flex: none;
  fill: var(--muted);
}
h2 {
  margin: 0;
  font: 400 24px/1.1 var(--font-display);
  overflow-wrap: anywhere;
}
</style>
