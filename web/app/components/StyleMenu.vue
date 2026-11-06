<script setup lang="ts">
// The context menu for styling (E9.7), the same in every app: first the styles by purpose (you mark things by what they
// are for, D62), then how the style looks, as controls or as CSS. It talks to a StyleHost and knows nothing else.
import { computed } from 'vue'
import { previewCss } from '~/lib/style-css'
import type { StyleHost } from '~/lib/style-host'

const props = defineProps<{ host: StyleHost; x: number; y: number }>()
const emit = defineEmits<{ close: []; styles: [] }>()

const uses = computed(() => props.host.uses())

async function choose(id: string) {
  if (await props.host.apply(id)) emit('close')
}
</script>

<template>
  <Popover :x="x" :y="y" :width="340" label="Style" @close="emit('close')">
    <div class="menu" data-testid="style-menu">
      <header>
        <h3>{{ host.noun === 'paragraph' ? 'Paragraph style' : 'Style' }}</h3>
        <button class="all" type="button" data-testid="all-styles" @click="emit('styles')">All styles…</button>
      </header>
      <ul class="gallery" role="listbox" aria-label="Styles">
        <li v-for="s in host.styles" :key="s.id" role="option" :aria-selected="s.id === host.current?.id">
          <button type="button" :class="{ on: s.id === host.current?.id }" :disabled="host.readOnly" :data-style="s.id" @click="choose(s.id)">
            <span class="name" :style="previewCss(s.computed)">{{ s.name }}</span>
            <span v-if="s.to_name" class="flag" title="Waiting for a name">to name</span>
            <span class="count mono">{{ uses[s.id] ?? 0 }}</span>
          </button>
        </li>
      </ul>
      <StyleSpec :host="host" />
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
.gallery {
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
  max-height: 170px;
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
.count {
  min-width: 1.4em;
  text-align: right;
  font-size: 11px;
  color: var(--muted);
}
</style>
