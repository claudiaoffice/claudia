<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

export interface MenuItem {
  label: string
  hint?: string
  action?: () => void
  disabled?: boolean
  separator?: boolean
  /** A choice that is on or off: shown with a tick. */
  checked?: boolean
}
export interface Menu {
  label: string
  items: MenuItem[]
}

defineProps<{ menus: Menu[] }>()

const openIndex = ref<number | null>(null)
const root = ref<HTMLElement | null>(null)

function choose(item: MenuItem) {
  if (item.disabled || item.separator) return
  openIndex.value = null
  item.action?.()
}
function outside(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) openIndex.value = null
}
function escape(event: KeyboardEvent) {
  if (event.key === 'Escape') openIndex.value = null
}
onMounted(() => {
  window.addEventListener('mousedown', outside)
  window.addEventListener('keydown', escape)
})
onBeforeUnmount(() => {
  window.removeEventListener('mousedown', outside)
  window.removeEventListener('keydown', escape)
})
</script>

<template>
  <nav ref="root" class="menus" aria-label="menu">
    <div v-for="(menu, i) in menus" :key="menu.label" class="menu">
      <button
        type="button"
        class="title"
        :class="{ open: openIndex === i }"
        @click="openIndex = openIndex === i ? null : i"
        @mouseenter="openIndex !== null && (openIndex = i)"
      >
        {{ menu.label }}
      </button>
      <ul v-if="openIndex === i" class="drop" role="menu">
        <template v-for="(item, j) in menu.items" :key="j">
          <li v-if="item.separator" class="sep" role="separator" />
          <li v-else>
            <button type="button" role="menuitem" :aria-checked="item.checked" :disabled="item.disabled" @click="choose(item)">
              <span><i v-if="item.checked !== undefined" class="tick" aria-hidden="true">{{ item.checked ? '✓' : '' }}</i>{{ item.label }}</span>
              <kbd v-if="item.hint">{{ item.hint }}</kbd>
            </button>
          </li>
        </template>
      </ul>
    </div>
  </nav>
</template>

<style scoped>
.tick {
  display: inline-block;
  width: 1.3em;
  font-style: normal;
  color: var(--app);
}
.menus {
  display: flex;
  gap: 2px;
  padding: 2px 10px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  height: 32px;
}
.menu {
  position: relative;
}
.title {
  border: 0;
  background: transparent;
  padding: 4px 10px;
  border-radius: 6px;
  height: 28px;
}
.title:hover,
.title.open {
  background: var(--mist);
}
.drop {
  position: absolute;
  top: 30px;
  left: 0;
  z-index: 40;
  min-width: 250px;
  list-style: none;
  margin: 0;
  padding: 6px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.drop button {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 6px 10px;
  border-radius: 6px;
}
.drop button:hover:not(:disabled) {
  background: var(--mist);
}
.drop button:disabled {
  color: var(--muted);
  cursor: default;
}
kbd {
  font: 400 12px var(--font-mono);
  color: var(--muted);
}
.sep {
  height: 1px;
  background: var(--line);
  margin: 5px 4px;
}
</style>
