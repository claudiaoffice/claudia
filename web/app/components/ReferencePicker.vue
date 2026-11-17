<script setup lang="ts">
// Insert ▸ Cross-Reference…: the picker (step H, mock-up composes-references.svg, B). It opens at the caret and lists
// the whole document: the headings as an outline with their numbers (in creates the slide titles), the numbered items,
// then the named things, with search. A reference holds the target's id, so pointing at an unnamed heading names
// nothing. "Show as" says what it reads as; the default follows the target (a number when it has one). The same in
// composes and creates: the host is the session.
//
// Keys: type to search; ↑↓ choose; Tab to "Show as"; Enter puts it in; Esc closes. The list is a listbox with the
// search field as its combobox; every row is an option with its full text for screen readers.
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from '~/lib/i18n'
import { defaultShow, grouped, preview, SHOWS, type ReferenceTarget, type Show } from '~/lib/references'
import { showLabel } from '~/lib/reference-labels'

const { t } = useI18n()

const props = defineProps<{ x: number; y: number; targets: (query: string) => Promise<ReferenceTarget[]>; before?: string }>()
const emit = defineEmits<{ choose: [target: string, show: Show]; close: [] }>()

const query = ref('')
const found = ref<ReferenceTarget[]>([])
const active = ref(0)
const show = ref<Show | null>(null)
const field = ref<HTMLInputElement | null>(null)

async function search() {
  const asked = query.value
  const answer = await props.targets(asked)
  if (asked !== query.value) return // a newer search is on its way
  found.value = answer
  active.value = 0
}
watch(query, () => void search())
onMounted(() => {
  void search()
  field.value?.focus()
})

const groups = computed(() => grouped(found.value))
/** The rows in the order they are shown, so ↑↓ walk them across the groups. */
const rows = computed(() => groups.value.flatMap((g) => g.targets))
const chosen = computed(() => rows.value[active.value] ?? null)
const shows = computed<Show>(() => show.value ?? (chosen.value ? defaultShow(chosen.value) : 'number'))
watch(chosen, () => (show.value = null)) // another target: its own default

const groupLabel = (kind: ReferenceTarget['kind']) => (kind === 'heading' ? t('Headings') : kind === 'item' ? t('Numbered items') : t('Named things'))
const available = (s: Show) => !!chosen.value && (s !== 'name' || !!chosen.value.name) && (s !== 'number' || !!chosen.value.number) && (s !== 'number-text' || !!chosen.value.number)

function optionId(target: ReferenceTarget) {
  return `ref-target-${target.id}`
}
function rowLabel(target: ReferenceTarget): string {
  return [target.number, target.text || target.name || target.id].filter(Boolean).join(' ')
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    active.value = Math.min(rows.value.length - 1, active.value + 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    active.value = Math.max(0, active.value - 1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    put()
  }
}

function put() {
  if (chosen.value) emit('choose', chosen.value.id, shows.value)
}
</script>

<template>
  <Popover :x="x" :y="y" :width="440" :label="t('Cross-Reference')" @close="emit('close')">
    <div class="picker" data-testid="reference-picker" @keydown.esc.stop="emit('close')">
      <input
        ref="field"
        v-model="query"
        class="search"
        type="search"
        role="combobox"
        aria-autocomplete="list"
        aria-controls="ref-targets"
        :aria-expanded="rows.length > 0"
        :aria-activedescendant="chosen ? optionId(chosen) : undefined"
        :aria-label="t('Search headings, items and named things')"
        :placeholder="t('Search headings, items and named things')"
        autocomplete="off"
        @keydown="onKey"
      >
      <div id="ref-targets" class="list" role="listbox" :aria-label="t('What to point at')">
        <template v-for="g in groups" :key="g.kind">
          <div class="caption" role="presentation">{{ groupLabel(g.kind) }}</div>
          <div
            v-for="target in g.targets"
            :id="optionId(target)"
            :key="target.id"
            class="row"
            role="option"
            :aria-selected="chosen?.id === target.id"
            :class="{ on: chosen?.id === target.id }"
            :style="{ paddingLeft: `${8 + Math.max(0, (target.level ?? 1) - 1) * 16}px` }"
            @pointerdown.prevent="active = rows.indexOf(target)"
            @dblclick="put"
          >
            <span class="number">{{ target.number }}</span>
            <span class="words">{{ target.text || target.name || target.id }}</span>
            <span v-if="target.name && target.text" class="name">{{ target.name }}</span>
            <span class="sr">{{ rowLabel(target) }}</span>
          </div>
        </template>
        <p v-if="!rows.length" class="empty">{{ t('Nothing to point at with these words.') }}</p>
      </div>
      <div class="shows" role="radiogroup" :aria-label="t('Show as')">
        <span class="label">{{ t('Show as') }}</span>
        <button
          v-for="s in SHOWS"
          :key="s"
          type="button"
          role="radio"
          :aria-checked="shows === s"
          :class="{ on: shows === s }"
          :disabled="!available(s)"
          @click="show = s"
        >
          {{ showLabel(s) }}
        </button>
      </div>
      <p v-if="chosen" class="reads">{{ t('Reads:') }} {{ before ?? '' }}<u>{{ preview(chosen, shows) }}</u></p>
      <p class="keys">{{ t('↑↓ choose · Tab to “Show as” · Enter puts it in · Esc closes') }}</p>
    </div>
  </Popover>
</template>

<style scoped>
.picker {
  display: grid;
  gap: 8px;
}
.search {
  width: 100%;
  padding: 6px 8px;
  border: 1.5px solid var(--iris);
  border-radius: 6px;
  font: inherit;
}
.list {
  max-height: 280px;
  overflow: auto;
}
.caption {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 8px 0 2px;
}
.row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
}
.row.on {
  background: color-mix(in srgb, var(--iris) 16%, transparent);
  box-shadow: inset 3px 0 0 var(--iris);
}
.number {
  min-width: 2.4em;
  font-variant-numeric: tabular-nums;
  color: var(--muted);
}
.words {
  flex: 1;
}
.name {
  font-size: 12px;
  color: var(--muted);
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
.empty {
  color: var(--muted);
  font-style: italic;
}
.shows {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.shows .label {
  color: var(--muted);
  margin-right: 4px;
}
.shows button {
  font: inherit;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--line-field);
  background: var(--surface);
}
.shows button.on {
  border-color: var(--iris);
  font-weight: 600;
}
.reads,
.keys {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.reads u {
  text-decoration-color: var(--iris);
}
</style>
