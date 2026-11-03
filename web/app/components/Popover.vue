<script setup lang="ts">
// A floating panel at a point of the window (a context menu, a picker). It stays inside the window, closes on Escape or a
// click outside, and never takes the text selection away from the page: only the fields in it take the focus.
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps<{ x: number; y: number; label: string; width?: number }>()
const emit = defineEmits<{ close: [] }>()

const box = ref<HTMLElement | null>(null)
const at = ref({ left: props.x, top: props.y })

async function fit() {
  await nextTick()
  const el = box.value
  if (!el) return
  const margin = 8
  const { innerWidth, innerHeight } = window
  const left = Math.max(margin, Math.min(props.x, innerWidth - el.offsetWidth - margin))
  const top = props.y + el.offsetHeight + margin > innerHeight ? Math.max(margin, innerHeight - el.offsetHeight - margin) : props.y
  at.value = { left, top }
}

function outside(event: PointerEvent) {
  if (box.value && !box.value.contains(event.target as Node)) emit('close')
}
function key(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
  }
}
let watcher: ResizeObserver | undefined
onMounted(() => {
  void fit()
  if (box.value && typeof ResizeObserver !== 'undefined') {
    watcher = new ResizeObserver(() => void fit()) // the panel grows when the person opens the CSS or a picker
    watcher.observe(box.value)
  }
  document.addEventListener('pointerdown', outside, true)
  window.addEventListener('keydown', key, true)
  window.addEventListener('resize', fit)
})
onBeforeUnmount(() => {
  watcher?.disconnect()
  document.removeEventListener('pointerdown', outside, true)
  window.removeEventListener('keydown', key, true)
  window.removeEventListener('resize', fit)
})
defineExpose({ fit })
</script>

<template>
  <div ref="box" class="popover" role="dialog" :aria-label="label" :style="{ left: `${at.left}px`, top: `${at.top}px`, width: `${width ?? 320}px` }" @mousedown="(e) => (e.target as HTMLElement).closest('input,textarea,select') || e.preventDefault()">
    <slot />
  </div>
</template>

<style scoped>
.popover {
  position: fixed;
  z-index: 55;
  max-height: calc(100vh - 16px);
  overflow-y: auto;
  padding: 6px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 12px;
  box-shadow: var(--shadow), 0 18px 48px rgb(31 26 51 / 14%);
}
</style>
