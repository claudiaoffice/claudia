<script setup lang="ts">
// The quick list of styles in a toolbar (`computes-cell-styles.svg`, panel A, note 1): the style of what is selected
// on the button, and a list of the styles that fit it, each drawn in its look (never its size), ticked where the
// selection has it. Choosing one applies it to the whole selection. "Edit this style…" at the bottom opens the
// popover. It talks to a StyleHost and knows nothing of the app — computes puts it in the formula-bar row, at the
// place composes' style list has in its toolbar.
import { computed, ref } from 'vue'
import { menuCss } from '~/lib/style-css'
import { galleryFor, type StyleHost } from '~/lib/style-host'

const props = defineProps<{ host: StyleHost; hint?: string }>()
const emit = defineEmits<{ look: []; styled: [] }>()

const at = ref<{ x: number; y: number } | null>(null)
const button = ref<HTMLElement | null>(null)
const offered = computed(() => galleryFor(props.host.styles, props.host.slot, props.host.model))
const current = computed(() => props.host.current)
const off = computed(() => props.host.readOnly || !current.value)

function toggle() {
  const r = button.value?.getBoundingClientRect()
  at.value = at.value ? null : { x: (r?.right ?? 0) - 240, y: (r?.bottom ?? 0) + 4 }
}

async function choose(id: string) {
  at.value = null
  if (await props.host.apply(id)) emit('styled')
}

function look() {
  at.value = null
  emit('look')
}
</script>

<template>
  <div class="picker">
    <span class="caption" aria-hidden="true">Style</span>
    <button
      ref="button"
      class="btn"
      type="button"
      aria-haspopup="listbox"
      :aria-expanded="!!at"
      :disabled="off"
      :title="`Style: mark the ${host.noun} by what it is for`"
      data-testid="style-picker"
      @mousedown.prevent
      @click="toggle"
    >
      <span class="name"><span class="look" :style="current ? menuCss(current.resolved) : undefined">{{ current?.name ?? '—' }}</span></span>
      <span class="caret">▾</span>
    </button>
    <Popover v-if="at" :x="at.x" :y="at.y" :width="240" :anchor="button" label="Styles" @close="at = null">
      <ul class="list" role="listbox" aria-label="Styles">
        <li v-for="s in [...offered.own, ...offered.bundles]" :key="s.id" role="option" :aria-selected="s.id === current?.id">
          <button type="button" :data-style="s.id" @click="choose(s.id)">
            <span class="tick" aria-hidden="true">{{ s.id === current?.id ? '✓' : '' }}</span>
            <span class="look" :style="menuCss(s.resolved)">{{ s.name }}</span>
          </button>
        </li>
      </ul>
      <button type="button" class="edit" data-testid="picker-look" @click="look">
        <span>Edit this style…</span><span v-if="hint" class="hint mono">{{ hint }}</span>
      </button>
    </Popover>
  </div>
</template>

<style scoped>
.picker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.caption {
  font-size: 12px;
  color: var(--muted);
}
.btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 150px;
  height: 30px;
  padding: 0 8px 0 10px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  background: var(--surface);
}
.btn:hover:not(:disabled) {
  border-color: var(--app);
}
.btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
  font-size: 13px;
}
.caret {
  color: var(--muted);
  font-size: 10px;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 280px;
  overflow-y: auto;
}
.list button,
.edit {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 8px;
  border: 0;
  border-radius: 7px;
  background: none;
  text-align: left;
  font-size: 13.5px;
}
.list button:hover,
.edit:hover {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.tick {
  width: 14px;
  color: var(--app-text);
}
.edit {
  justify-content: space-between;
  margin-top: 4px;
  border-top: 1px solid var(--line);
  border-radius: 0 0 7px 7px;
  font-size: 13px;
}
.hint {
  font-size: 11px;
  color: var(--muted);
}
</style>
