<script setup lang="ts">
// A floating panel at a point of the window (a context menu, a picker). It stays inside the window, closes on Escape or a
// click outside, and never takes the text selection away from the page: only the fields in it take the focus.
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

/** `anchor`: the button that opened it; pressing it is not "outside", so that the button can close the panel itself.
 * `bare`: skip the default card chrome (padding, surface background, border, shadow) for a panel that draws its
 * own, such as the connection indicator's dark tooltip — only the positioning and the close behavior are shared. */
const props = defineProps<{ x: number; y: number; label: string; width?: number; anchor?: HTMLElement | null; bare?: boolean }>()
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
  const target = event.target as Node
  if (box.value && !box.value.contains(target) && !props.anchor?.contains(target)) emit('close')
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
  <div
    ref="box"
    class="popover"
    :class="{ bare }"
    role="dialog"
    :aria-label="label"
    :style="{ left: `${at.left}px`, top: `${at.top}px`, width: `${width ?? 320}px` }"
    @mousedown="(e) => (e.target as HTMLElement).closest('input,textarea,select') || e.preventDefault()"
  >
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
  border: 1px solid var(--line-field); /* a floating panel's own edge, not a divider — same fix as Modal.vue */
  border-radius: 12px;
  box-shadow: var(--shadow), 0 18px 48px rgb(31 26 51 / 14%);
}
.popover.bare {
  padding: 0;
  background: none;
  border: none;
  border-radius: 0;
  box-shadow: none;
  overflow: visible;
}
</style>
