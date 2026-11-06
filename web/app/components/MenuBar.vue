<script setup lang="ts">
// UX-01: a real ARIA menu-button/menubar pattern, replacing the div soup `nav.menus` used to be (it had no roles that
// meant anything, no keyboard handling beyond a document-wide Escape, and no way to reach it without a mouse).
//
// The pattern, as agreed in `claudiaoffice-log/notes/mockups/menu-bar-states.svg` (panel D): DOM focus stays on the
// menu *button* the whole time, even while its dropdown is open — the item the person has moved to is tracked with
// `aria-activedescendant`, not by moving real focus into a floating panel. That keeps Escape trivial (focus was never
// anywhere else) and keeps one `keydown` listener on the bar doing all of the work, for the bar and for one level of
// submenu (`items`, used by "Paste as", "Row" and "Column" — D130).
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

export interface MenuItem {
  /** The shell-contract action id (`file.save`, …) for an item a native shell can also drive. Omit for an item that
   * only exists on the web (a style name, a shape from the library): see `lib/menu-dispatch.ts`. */
  id?: string
  label: string
  hint?: string
  /** `target` is `'on'`/`'off'` when the shell asked for a checkable item by name; a click never passes one. */
  action?: (target?: 'on' | 'off') => void
  disabled?: boolean
  separator?: boolean
  /** A choice that is on or off: shown with a tick. */
  checked?: boolean
  /** One level of flyout (Paste as ▸ Plain text; computes' Row ▸ and Column ▸, D130). Items of a submenu may carry
   * `id` too, and are included in `lib/menu-dispatch.ts`'s walk, but may not nest a submenu of their own. */
  items?: MenuItem[]
}
export interface Menu {
  label: string
  items: MenuItem[]
}

const props = defineProps<{ menus: Menu[] }>()

const root = ref<HTMLElement | null>(null)
const titleRefs = ref<HTMLButtonElement[]>([])
const openIndex = ref<number | null>(null)
/** Index into the open menu's clickable items (separators excluded), or the open submenu's, while one is open. */
const activeItem = ref<number | null>(null)
const activeSub = ref<number | null>(null)
/** Which title has the roving tabindex, independent of whether a menu is open. */
const focused = ref(0)
let typeahead = ''
let typeaheadTimer: ReturnType<typeof setTimeout> | undefined

const openMenu = computed(() => (openIndex.value === null ? null : props.menus[openIndex.value] ?? null))
const clickable = computed(() => (openMenu.value?.items ?? []).filter((it) => !it.separator))
const activeTop = computed<MenuItem | null>(() => (activeItem.value === null ? null : (clickable.value[activeItem.value] ?? null)))
const subItems = computed(() => activeTop.value?.items ?? [])
const activeSubItem = computed<MenuItem | null>(() => (activeSub.value === null ? null : (subItems.value[activeSub.value] ?? null)))

function idOf(menuIndex: number, item: MenuItem | null | undefined): string | undefined {
  return item ? `menuitem-${menuIndex}-${item.label}` : undefined
}
/** What `aria-activedescendant` should be right now (the submenu item wins once one is open). */
const activeDescendant = computed(() => {
  if (openIndex.value === null) return undefined
  if (activeSub.value !== null) return idOf(openIndex.value, activeSubItem.value)
  return idOf(openIndex.value, activeTop.value)
})

function titleId(i: number) {
  return `menu-title-${i}`
}

function choose(item: MenuItem) {
  if (item.disabled || item.separator || item.items) return
  close()
  item.action?.()
}

function open(i: number, { focusFirst = false }: { focusFirst?: boolean } = {}) {
  openIndex.value = i
  focused.value = i
  activeSub.value = null
  activeItem.value = focusFirst ? firstEnabled(0, 1) : null
  titleRefs.value[i]?.focus()
}

function close() {
  openIndex.value = null
  activeItem.value = null
  activeSub.value = null
}

function toggle(i: number) {
  if (openIndex.value === i) close()
  else open(i)
}

// ------------------------------------------------------------------------------------------------------- moving
function clamp(n: number, len: number): number {
  return len === 0 ? 0 : ((n % len) + len) % len
}
function firstEnabled(from: number, step: 1 | -1): number | null {
  const items = clickable.value
  if (!items.length) return null
  let i = from
  for (let tries = 0; tries < items.length; tries++, i = clamp(i + step, items.length)) {
    if (!items[i]!.disabled) return i
  }
  return null
}
function moveItem(step: 1 | -1) {
  if (!clickable.value.length) return
  const from = activeItem.value === null ? (step === 1 ? -1 : 0) : clamp(activeItem.value + step, clickable.value.length)
  activeItem.value = firstEnabled(from, step)
  activeSub.value = null
}
function moveSub(step: 1 | -1) {
  if (!subItems.value.length) return
  const from = activeSub.value === null ? (step === 1 ? 0 : subItems.value.length - 1) : clamp(activeSub.value + step, subItems.value.length)
  activeSub.value = from
}
function moveTitle(step: 1 | -1) {
  jumpTitle(clamp(focused.value + step, props.menus.length))
}
function jumpTitle(next: number) {
  if (openIndex.value !== null) open(next) // "switch menu, opening the neighbour" — panel D
  else {
    focused.value = next
    titleRefs.value[next]?.focus()
  }
}

function activate() {
  if (activeSub.value !== null) {
    const item = activeSubItem.value
    if (item && !item.disabled) {
      close()
      item.action?.()
    }
    return
  }
  const item = activeTop.value
  if (!item || item.disabled) return
  if (item.items) {
    activeSub.value = 0
    return
  }
  close()
  item.action?.()
}

/** Cyclic search starting just after whichever item is active now, wrapping around (a letter key "types ahead"). */
function onTypeahead(letter: string) {
  clearTimeout(typeaheadTimer)
  typeahead += letter.toLowerCase()
  typeaheadTimer = setTimeout(() => (typeahead = ''), 600)
  const inSub = activeSub.value !== null
  const items = inSub ? subItems.value : clickable.value
  const current = inSub ? activeSub.value : activeItem.value
  if (!items.length) return
  for (let step = 1; step <= items.length; step++) {
    const i = clamp((current ?? -1) + step, items.length)
    if (!items[i]!.disabled && items[i]!.label.toLowerCase().startsWith(typeahead)) {
      if (inSub) activeSub.value = i
      else activeItem.value = i
      return
    }
  }
}

// ------------------------------------------------------------------------------------------------------- keyboard
function onKeydown(event: KeyboardEvent) {
  const inSub = activeSub.value !== null
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      if (openIndex.value === null) open(focused.value, { focusFirst: true })
      else if (inSub) moveSub(1)
      else moveItem(1)
      return
    case 'ArrowUp':
      event.preventDefault()
      if (openIndex.value === null) open(focused.value, { focusFirst: true })
      else if (inSub) moveSub(-1)
      else moveItem(-1)
      return
    case 'ArrowRight':
      event.preventDefault()
      if (openIndex.value === null) moveTitle(1)
      else if (!inSub && activeTop.value?.items) activeSub.value = 0
      else if (!inSub) moveTitle(1)
      return
    case 'ArrowLeft':
      event.preventDefault()
      if (openIndex.value === null) moveTitle(-1)
      else if (inSub) activeSub.value = null
      else moveTitle(-1)
      return
    case 'Home':
      event.preventDefault()
      if (openIndex.value === null) jumpTitle(0)
      else if (inSub) activeSub.value = 0
      else activeItem.value = firstEnabled(0, 1)
      return
    case 'End':
      event.preventDefault()
      if (openIndex.value === null) jumpTitle(props.menus.length - 1)
      else if (inSub) activeSub.value = subItems.value.length - 1
      else activeItem.value = firstEnabled(clickable.value.length - 1, -1)
      return
    case 'Enter':
    case ' ':
      event.preventDefault()
      if (openIndex.value === null) open(focused.value, { focusFirst: true })
      else activate()
      return
    case 'Escape':
      if (inSub) activeSub.value = null
      else close()
      return
    default:
      if (event.key.length === 1 && openIndex.value !== null && !event.ctrlKey && !event.metaKey && !event.altKey) onTypeahead(event.key)
  }
}

// Alt or F10 anywhere on the page moves focus to the bar without opening it (panel D: "Reach the bar").
let altAlone = false
function onWindowKeydown(event: KeyboardEvent) {
  if (event.key === 'F10' && !event.ctrlKey && !event.shiftKey && !event.metaKey) {
    event.preventDefault()
    titleRefs.value[focused.value]?.focus()
    return
  }
  altAlone = event.key === 'Alt'
}
function onWindowKeyup(event: KeyboardEvent) {
  if (event.key === 'Alt' && altAlone) titleRefs.value[focused.value]?.focus()
  altAlone = false
}

function outside(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) close()
}
onMounted(() => {
  window.addEventListener('mousedown', outside)
  window.addEventListener('keydown', onWindowKeydown)
  window.addEventListener('keyup', onWindowKeyup)
})
onBeforeUnmount(() => {
  window.removeEventListener('mousedown', outside)
  window.removeEventListener('keydown', onWindowKeydown)
  window.removeEventListener('keyup', onWindowKeyup)
  clearTimeout(typeaheadTimer)
})
</script>

<template>
  <nav ref="root" class="menus" aria-label="menu" @keydown="onKeydown">
    <div role="menubar" class="bar">
      <div v-for="(menu, i) in menus" :key="menu.label" class="menu">
        <button
          :id="titleId(i)"
          :ref="(el) => (titleRefs[i] = el as HTMLButtonElement)"
          type="button"
          class="title"
          role="menuitem"
          :class="{ open: openIndex === i }"
          :tabindex="focused === i ? 0 : -1"
          aria-haspopup="menu"
          :aria-expanded="openIndex === i"
          :aria-controls="openIndex === i ? `menu-drop-${i}` : undefined"
          :aria-activedescendant="openIndex === i ? activeDescendant : undefined"
          @click="toggle(i)"
          @mouseenter="openIndex !== null && open(i)"
          @focus="focused = i"
        >
          {{ menu.label }}
        </button>
        <ul v-if="openIndex === i" :id="`menu-drop-${i}`" class="drop" role="menu" :aria-labelledby="titleId(i)">
          <template v-for="(item, j) in menu.items" :key="j">
            <li v-if="item.separator" class="sep" role="separator" />
            <li v-else class="item-wrap">
              <button
                :id="idOf(i, item)"
                type="button"
                :role="item.checked !== undefined ? 'menuitemcheckbox' : 'menuitem'"
                :aria-checked="item.checked"
                :aria-haspopup="item.items ? 'menu' : undefined"
                :aria-expanded="item.items ? activeTop === item : undefined"
                :disabled="item.disabled"
                :class="{ active: activeTop === item }"
                tabindex="-1"
                @click="choose(item)"
                @mouseenter="!item.disabled && (activeItem = clickable.indexOf(item)), (activeSub = null)"
              >
                <span><i v-if="item.checked !== undefined" class="tick" aria-hidden="true">{{ item.checked ? '✓' : '' }}</i>{{ item.label }}</span>
                <kbd v-if="item.hint">{{ item.hint }}</kbd>
                <span v-if="item.items" class="arrow" aria-hidden="true">▸</span>
              </button>
              <ul v-if="item.items && activeTop === item && activeSub !== null" class="drop sub" role="menu" :aria-label="item.label">
                <li v-for="(sub, k) in item.items" :key="k">
                  <button
                    :id="idOf(i, sub)"
                    type="button"
                    role="menuitem"
                    :disabled="sub.disabled"
                    :class="{ active: activeSubItem === sub }"
                    tabindex="-1"
                    @click="choose(sub)"
                    @mouseenter="!sub.disabled && (activeSub = subItems.indexOf(sub))"
                  >
                    <span>{{ sub.label }}</span>
                    <kbd v-if="sub.hint">{{ sub.hint }}</kbd>
                  </button>
                </li>
              </ul>
            </li>
          </template>
        </ul>
      </div>
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
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  height: 32px;
}
.bar {
  display: flex;
  gap: 2px;
  padding: 2px 10px;
  height: 100%;
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
.title:focus-visible {
  outline: 2px solid var(--app-dark);
  outline-offset: -2px;
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
.item-wrap {
  position: relative;
}
.drop button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 6px 10px;
  border-radius: 6px;
}
.drop button:hover:not(:disabled),
.drop button.active:not(:disabled) {
  background: var(--mist);
}
.drop button:disabled {
  color: var(--muted);
  cursor: default;
}
.arrow {
  color: var(--muted);
  font-size: 11px;
}
.drop.sub {
  top: -6px;
  left: 100%;
  margin-left: 6px;
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
