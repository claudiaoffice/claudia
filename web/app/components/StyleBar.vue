<script setup lang="ts">
// The toolbar row of a text: the style of the paragraph (you mark text by what it is for, D62) and how to look at the text.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { colorOf } from '~/lib/people'
import type { TextSession } from '~/lib/text-session'

const props = defineProps<{ session: TextSession; view: 'flow' | 'page'; authors: boolean }>()
const emit = defineEmits<{ view: [view: 'flow' | 'page']; authors: [on: boolean]; styled: [] }>()

const state = props.session.state
const open = ref(false)
const root = ref<HTMLElement | null>(null)

const current = () => state.styles.find((s) => s.id === props.session.currentStyle()) ?? state.styles[0]

function choose(id: string) {
  open.value = false
  void props.session.setStyle(id)
  emit('styled')
}

function outside(event: PointerEvent) {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('pointerdown', outside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))

const writers = () => [state.me.user, ...state.people.map((p) => p.user)].filter((u, i, all) => all.indexOf(u) === i)
</script>

<template>
  <div class="stylebar" role="toolbar" aria-label="Text">
    <div ref="root" class="style-picker">
      <button
        class="style-btn"
        type="button"
        aria-haspopup="listbox"
        :aria-expanded="open"
        :disabled="session.readOnly"
        title="Style: mark text by what it is for"
        data-testid="style-button"
        @mousedown.prevent
        @click="open = !open"
      >
        <span>{{ current()?.name ?? 'Body text' }}</span
        ><span class="caret">▾</span>
      </button>
      <ul v-if="open" class="style-list" role="listbox" aria-label="Styles">
        <li v-for="s in state.styles" :key="s.id" role="option" :aria-selected="s.id === current()?.id">
          <button class="style-opt" :class="{ current: s.id === current()?.id }" type="button" :data-style="s.id" @mousedown.prevent @click="choose(s.id)">
            <span class="name">{{ s.name }}</span
            ><span class="purpose">{{ s.purpose }}</span>
          </button>
        </li>
      </ul>
    </div>

    <span class="grow" />

    <span v-if="authors" class="legend" aria-label="authorship colours">
      <span v-for="user in writers()" :key="user" :style="{ '--c': colorOf(state, user) }"><i />{{ user }}</span>
    </span>
    <button class="tool" :class="{ on: authors }" type="button" :aria-pressed="authors" title="Show who wrote what" data-testid="authors" @mousedown.prevent @click="emit('authors', !authors)">Authors</button>
    <div class="segmented" role="group" aria-label="View">
      <button type="button" :aria-pressed="view === 'flow'" title="Flow: the text runs to the width of the window" @mousedown.prevent @click="emit('view', 'flow')">Flow</button>
      <button type="button" :aria-pressed="view === 'page'" title="Page: the text on a page" data-testid="page-view" @mousedown.prevent @click="emit('view', 'page')">Page</button>
    </div>
  </div>
</template>

<style scoped>
.stylebar {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 44px;
  padding: 0 14px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
  scrollbar-width: none;
}
.stylebar > * {
  flex-shrink: 0;
}
.grow {
  flex: 1;
}
.tool {
  height: 30px;
  padding: 0 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  font-weight: 500;
}
.tool:hover {
  background: var(--mist);
}
.tool.on {
  background: color-mix(in srgb, var(--app) 16%, transparent);
  color: var(--app-dark);
}
.style-picker {
  position: relative;
}
.style-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 190px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  font-weight: 500;
}
.style-btn:hover:not(:disabled) {
  border-color: var(--app);
}
.style-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.caret {
  color: var(--muted);
  font-size: 10px;
}
.style-list {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 40;
  width: 300px;
  margin: 0;
  padding: 5px;
  list-style: none;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}
.style-opt {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
}
.style-opt:hover {
  background: var(--mist);
}
.style-opt.current {
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.name {
  font-weight: 500;
}
.purpose {
  color: var(--muted);
  font-size: 12px;
}
.segmented {
  display: inline-flex;
  padding: 2px;
  border-radius: 9px;
  background: var(--mist);
}
.segmented button {
  height: 26px;
  padding: 0 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  font-weight: 500;
  font-size: 13px;
  color: var(--muted);
}
.segmented button[aria-pressed='true'] {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 2px rgb(31 26 51 / 14%);
}
.legend {
  display: inline-flex;
  gap: 10px;
  margin-right: 6px;
  font-size: 12px;
  color: var(--muted);
}
.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.legend i {
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--c);
}
</style>
