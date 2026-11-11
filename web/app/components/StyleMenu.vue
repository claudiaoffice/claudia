<script setup lang="ts">
// The style popover, the same in every app (E9.7, `style-editor-two-slots.svg`). It talks to a StyleHost and knows
// nothing else. Two modes:
//
// * `edit` (Format ▸ Edit this style…, Shift+F10): the slot switcher when the thing has two slots (D304), the styles
//   that fit the slot, and the look of one of them below, one section per facet. Clicking a gallery row only picks
//   which style the panel shows and edits next (UX-14) — a look, not an instruction — and never closes the menu.
// * `apply` (Format ▸ Apply style…, the shells' entry, D301): the styles that fit the slot, each drawn in its look;
//   a click applies it and closes. Nothing to edit.
import { computed, reactive } from 'vue'
import { menuCss } from '~/lib/style-css'
import { StyleEditor, galleryFor, type StyleHost } from '~/lib/style-host'

const props = withDefaults(defineProps<{ host: StyleHost; x: number; y: number; mode?: 'edit' | 'apply' }>(), { mode: 'edit' })
const emit = defineEmits<{ close: []; styles: [] }>()

const uses = computed(() => props.host.uses())
const editor = reactive(new StyleEditor(props.host)) as StyleEditor
const gallery = computed(() => galleryFor(props.host.styles, props.host.slot, props.host.model))
const title = computed(() => props.host.noun.toUpperCase())

function choose(name: string) {
  props.host.chooseSlot(name)
  editor.pick(null)
}

async function clicked(id: string) {
  if (props.mode === 'edit') return editor.pick(id)
  if (await props.host.apply(id)) emit('close')
}
</script>

<template>
  <Popover :x="x" :y="y" :width="mode === 'apply' ? 280 : 360" :label="mode === 'apply' ? 'Apply style' : 'Style'" @close="emit('close')">
    <div class="menu" :data-mode="mode" data-testid="style-menu">
      <header>
        <h3>{{ mode === 'apply' ? 'Apply style' : title }}</h3>
        <button class="all" type="button" data-testid="all-styles" @click="emit('styles')">All styles…</button>
      </header>
      <div v-if="host.slots.length > 1" class="slots" role="tablist" aria-label="Which part is styled" data-testid="slot-switcher">
        <button
          v-for="s in host.slots"
          :key="s.name"
          type="button"
          role="tab"
          :aria-selected="s.name === host.slot?.name"
          :data-slot="s.name"
          @click="choose(s.name)"
        >
          {{ s.label }}<span v-if="s.name === host.slot?.name && host.current" class="held"> · {{ host.current.name }}</span>
        </button>
      </div>
      <ul class="gallery" role="listbox" aria-label="Styles">
        <li v-for="s in gallery.own" :key="s.id" role="option" :aria-selected="s.id === editor.current?.id">
          <button type="button" :class="{ on: mode === 'edit' && s.id === editor.current?.id }" :disabled="host.readOnly && mode === 'apply'" :data-style="s.id" @click="clicked(s.id)">
            <span class="name"><span class="look" :style="menuCss(s.resolved)">{{ s.name }}</span></span>
            <span v-if="s.to_name" class="flag" title="Waiting for a name">to name</span>
            <span v-if="s.id === host.current?.id && (mode === 'apply' || s.id !== editor.current?.id)" class="here" title="This is the style of what you selected">here</span>
            <span class="count mono">{{ uses[s.id] ?? 0 }}</span>
          </button>
        </li>
        <template v-if="gallery.bundles.length">
          <li class="also" role="presentation">Whole styles that also set a {{ host.slot?.label.toLowerCase() }} — their {{ host.slot?.label.toLowerCase() }} part:</li>
          <li v-for="s in gallery.bundles" :key="s.id" role="option" :aria-selected="s.id === editor.current?.id">
            <button type="button" :class="{ on: mode === 'edit' && s.id === editor.current?.id }" :disabled="host.readOnly && mode === 'apply'" :data-style="s.id" @click="clicked(s.id)">
              <span class="name"><span class="look" :style="menuCss(s.resolved)">{{ s.name }}</span></span>
              <span v-if="s.id === host.current?.id" class="here">here</span>
              <span class="count mono">{{ uses[s.id] ?? 0 }}</span>
            </button>
          </li>
        </template>
      </ul>
      <StyleSpec v-if="mode === 'edit' && host.slot?.reads.length" :host="host" :editor="editor" />
    </div>
  </Popover>
</template>

<style scoped>
.menu {
  display: grid;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px 6px;
}
h3 {
  margin: 0;
  font: 600 11px/1 var(--font-ui);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}
.all {
  border: 0;
  background: none;
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  font-size: 12px;
  cursor: pointer;
}
.all:hover {
  text-decoration: underline;
}
.slots {
  display: flex;
  margin: 0 8px 8px;
  padding: 2px;
  border-radius: 8px;
  background: var(--mist);
}
.slots button {
  flex: 1;
  min-width: 0;
  height: 26px;
  padding: 0 8px;
  border: 0;
  border-radius: 6px;
  background: none;
  font-size: 12px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.slots button[aria-selected='true'] {
  background: var(--surface);
  color: var(--text);
  font-weight: 600;
  box-shadow: 0 1px 2px rgb(31 26 51 / 14%);
}
.held {
  font-weight: 400;
}
.gallery {
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
  max-height: 200px;
  overflow-y: auto;
}
.gallery button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 8px;
  border: 0;
  border-radius: 7px;
  background: none;
  text-align: left;
}
.gallery button:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.gallery button.on {
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.also {
  padding: 6px 10px 2px;
  font-size: 11px;
  color: var(--muted);
}
.name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  line-height: 1.3;
}
.flag {
  padding: 1px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--apricot) 28%, white);
  font-size: 10.5px;
  color: #7a4710;
}
.here {
  /* A quieter pill than .flag: not something to act on, just "this is what your selection actually has" while you
     are browsing a different style's look (UX-14). */
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--mist);
  font-size: 10.5px;
  color: var(--muted);
}
.count {
  min-width: 1.4em;
  text-align: right;
  font-size: 11px;
  color: var(--muted);
}
</style>
