<script setup lang="ts">
// The pivot table's field panel (E6.30, D624, mock 1): floating and movable over the History & Chat dock like Search &
// replace. The source, a list of its fields with a tick each, four boxes — Filters, Columns, Rows, Values — with a chip
// for each field, two switches for the totals and a line naming the cells the pivot fills. Every chip has a ▾ menu with
// "Move to …", so nothing needs the mouse (BITV); a field can also be dragged between the boxes.
//
// What it shows is the pivot as the server has it (`pivot`); a change is shown at once and sent as `update_pivot`, and
// dropped again if the server refuses it (the person is told why). Esc closes it.
import { computed, ref, watch } from 'vue'
import { useDraggable } from '~/lib/use-draggable'
import { useI18n } from '~/lib/i18n'
import type { NameColumn } from '~/lib/names'
import {
  chipsOf,
  definitionHint,
  emptyDefinition,
  fillsLine,
  isTicked,
  moveChip,
  moveTargets,
  placeField,
  removeField,
  removeValue,
  sourceChoices,
  toggleField,
  zoneLabel,
  ZONES,
  type Chip,
  type PivotDefinition,
  type PivotInfo,
  type Placed,
  type Zone,
} from '~/lib/pivots'
import type { MenuItem } from './MenuBar.vue'
import type { Session } from '~/lib/session'

const { t } = useI18n()
const props = defineProps<{ session: Session; pivot: PivotInfo; readonly: boolean }>()
const emit = defineEmits<{
  close: []
  valueSettings: [index: number]
  members: [field: string]
  sql: []
}>()

const state = props.session.state
const root = ref<HTMLElement | null>(null)
const { offset, moving, start: startMove, key: moveKey } = useDraggable(root, 'pivot-panel')

/** The definition the panel draws: the one a change has just made (until the server's answer replaces it), else the pivot's. */
const pending = ref<PivotDefinition | null>(null)
const def = computed(() => pending.value ?? props.pivot.definition)
watch(() => props.pivot, () => (pending.value = null))
watch(() => props.pivot.name, () => (pending.value = null))

const source = computed(() => state.names.find((n) => n.scope === null && n.name.toLowerCase() === def.value.source.toLowerCase()) ?? null)
const columns = computed<NameColumn[]>(() => source.value?.columns ?? [])
const typeOf = (field: string) => columns.value.find((c) => c.name.toLowerCase() === field.toLowerCase())?.type
const find = ref('')
const shown = computed(() => {
  const wanted = find.value.trim().toLowerCase()
  return columns.value.filter((c) => !wanted || c.name.toLowerCase().includes(wanted))
})
const choices = computed(() => {
  const list = sourceChoices(state.names, state.pivots)
  return source.value && !list.includes(source.value) ? [source.value, ...list] : list
})
const changingSource = ref(false)
const hint = computed(() => definitionHint(def.value))
const fills = computed(() => fillsLine(props.pivot))
const disabled = computed(() => props.readonly)

async function change(next: PivotDefinition, placed?: Placed) {
  if (props.readonly) return
  pending.value = next
  const done = await props.session.updatePivot(props.pivot.name, next)
  if (!done) pending.value = null
  else if (placed?.displaced) {
    props.session.notice(
      t('{field} went back to the list: this version has one row field and one column field.', { field: placed.displaced }),
      'info',
    )
  }
}

const place = (placed: Placed) => change(placed.definition, placed)
const tick = (field: string) => place(toggleField(def.value, field, typeOf(field)))
const labels = computed(() => props.pivot.labels)
const chips = (zone: Zone) => chipsOf(def.value, zone, labels.value)
const rowCount = computed(() => source.value?.rows ?? 0)

function chooseSource(name: string) {
  changingSource.value = false
  if (name.toLowerCase() === def.value.source.toLowerCase()) return
  void change({ ...emptyDefinition(name), total_row: def.value.total_row, total_column: def.value.total_column })
}

// ------------------------------------------------------------------------------ the ▾ menu of a chip
const menu = ref<{ chip: Chip; x: number; y: number } | null>(null)
const menuItems = computed<MenuItem[]>(() => {
  const open = menu.value
  if (!open) return []
  const { chip } = open
  const items: MenuItem[] = moveTargets(chip.zone).map((to) => ({
    label: t('Move to {box}', { box: zoneLabel(to) }),
    action: () => void place(moveChip(def.value, chip, to, typeOf(chip.field))),
    disabled: disabled.value,
  }))
  items.push({ label: '', separator: true })
  if (chip.zone === 'values') items.push({ label: t('Value Field Settings…'), action: () => emit('valueSettings', chip.index) })
  if (chip.zone === 'filters') items.push({ label: t('Choose members…'), action: () => emit('members', chip.field) })
  items.push({
    label: t('Remove'),
    action: () => void change(chip.zone === 'values' ? removeValue(def.value, chip.index) : removeField(def.value, chip.field)),
    disabled: disabled.value,
  })
  return items
})
function openMenu(chip: Chip, event: MouseEvent | KeyboardEvent) {
  const box = (event.currentTarget as HTMLElement).getBoundingClientRect()
  menu.value = { chip, x: box.left, y: box.bottom + 4 }
}

// ------------------------------------------------------------------------------ dragging between the boxes
const MIME = 'application/x-claudia-pivot-field'
const over = ref<Zone | null>(null)
function dragStart(event: DragEvent, field: string, from: { zone: Zone; index: number } | null) {
  if (disabled.value || !event.dataTransfer) return event.preventDefault()
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData(MIME, JSON.stringify({ field, from }))
  event.dataTransfer.setData('text/plain', field)
}
function drop(event: DragEvent, zone: Zone) {
  over.value = null
  const raw = event.dataTransfer?.getData(MIME)
  if (!raw || disabled.value) return
  event.preventDefault()
  const { field, from } = JSON.parse(raw) as { field: string; from: { zone: Zone; index: number } | null }
  if (from) void place(moveChip(def.value, { zone: from.zone, field, index: from.index }, zone, typeOf(field)))
  else void place(placeField(def.value, field, zone, typeOf(field))) // from the list of fields: into the box, out of the one it was in
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && !menu.value) {
    event.stopPropagation()
    emit('close')
    return
  }
  moveKey(event)
}

defineExpose({ focus: () => root.value?.querySelector<HTMLElement>('input[type="search"]')?.focus() })
</script>

<template>
  <aside
    ref="root"
    class="pivot"
    :class="{ moving }"
    role="region"
    :aria-label="t('Pivot table')"
    :style="{ '--dx': `${offset.x}px`, '--dy': `${offset.y}px` }"
    data-testid="pivot-panel"
    @keydown="onKey"
  >
    <header @pointerdown="startMove">
      <svg class="grip" viewBox="0 0 10 16" width="10" height="16" aria-hidden="true"><circle cx="2.5" cy="3" r="1.4" /><circle cx="7.5" cy="3" r="1.4" /><circle cx="2.5" cy="8" r="1.4" /><circle cx="7.5" cy="8" r="1.4" /><circle cx="2.5" cy="13" r="1.4" /><circle cx="7.5" cy="13" r="1.4" /></svg>
      <h2>{{ t('Pivot table') }}</h2>
      <span class="name mono" data-testid="pivot-name">{{ pivot.name }}</span>
      <button type="button" class="close" :aria-label="t('Close the pivot table panel')" :title="t('Close · Esc')" @click="emit('close')">Esc</button>
    </header>

    <div class="body">
      <section :aria-label="t('Source')">
        <h3>{{ t('Source') }}</h3>
        <div class="source">
          <svg viewBox="0 0 20 16" width="20" height="16" aria-hidden="true"><rect x="1" y="1" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.4" /><path d="M1 6h18M7 6v9" stroke="currentColor" stroke-width="1.4" fill="none" /></svg>
          <template v-if="!changingSource">
            <strong>{{ def.source }}</strong>
            <span class="muted">{{ rowCount === 1 ? t('{count} row', { count: rowCount }) : t('{count} rows', { count: rowCount }) }}</span>
            <button type="button" class="link" :disabled="disabled" @click="changingSource = true">{{ t('Change…') }}</button>
          </template>
          <select v-else :aria-label="t('source of the pivot table')" :value="def.source" @change="chooseSource(($event.target as HTMLSelectElement).value)" @keydown.esc.stop="changingSource = false">
            <option v-for="n in choices" :key="n.name" :value="n.name">{{ n.name }}</option>
          </select>
        </div>
        <p v-if="!source" class="problem" role="alert">{{ t('There is no table called {name} (any more).', { name: def.source }) }}</p>
      </section>

      <section :aria-label="t('Fields')">
        <h3>{{ t('Fields') }}</h3>
        <input v-model="find" type="search" class="find" :placeholder="t('Find a field…')" :aria-label="t('find a field')" autocomplete="off" >
        <ul class="fields" role="group" :aria-label="t('Fields of the source')">
          <li v-for="c in shown" :key="c.name" :draggable="!disabled" @dragstart="dragStart($event, c.name, null)">
            <label>
              <input type="checkbox" :checked="isTicked(def, c.name)" :disabled="disabled" @change="tick(c.name)" >
              <span class="dot" :class="c.type" aria-hidden="true" />
              <span class="field mono">{{ c.name }}</span>
              <span class="type">{{ c.type === 'mixed' ? t('mixed') : c.type }}</span>
            </label>
          </li>
        </ul>
        <p class="hint">{{ t('Drag fields between the boxes, or use a chip’s ▾ menu.') }}</p>
      </section>

      <div class="boxes">
        <section
          v-for="zone in ZONES"
          :key="zone"
          class="box"
          :class="{ over: over === zone }"
          :aria-label="zoneLabel(zone)"
          :data-zone="zone"
          @dragover.prevent="over = zone"
          @dragleave="over = null"
          @drop="drop($event, zone)"
        >
          <h3>{{ zoneLabel(zone) }}</h3>
          <ul>
            <li v-for="chip in chips(zone)" :key="`${zone}:${chip.index}`" class="chip" :draggable="!disabled" @dragstart="dragStart($event, chip.field, { zone, index: chip.index })">
              <span class="label">{{ chip.label }}</span>
              <span v-if="chip.detail" class="detail">{{ chip.detail }}</span>
              <button type="button" class="more" :aria-label="t('{field}: move, settings or remove', { field: chip.label })" aria-haspopup="menu" @click="openMenu(chip, $event)">▾</button>
            </li>
          </ul>
        </section>
      </div>

      <p v-if="hint" class="hint" role="note">{{ hint }}</p>

      <div class="totals" role="group" :aria-label="t('Totals')">
        <label><input type="checkbox" :checked="def.total_row" :disabled="disabled" @change="change({ ...def, total_row: ($event.target as HTMLInputElement).checked })" > {{ t('Total row') }}</label>
        <label><input type="checkbox" :checked="def.total_column" :disabled="disabled" @change="change({ ...def, total_column: ($event.target as HTMLInputElement).checked })" > {{ t('Total column') }}</label>
      </div>
      <p class="fills" :class="{ problem: pivot.error !== null || !pivot.placed }" role="status" data-testid="pivot-fills">
        <svg viewBox="0 0 12 14" width="12" height="14" aria-hidden="true"><rect x="1.5" y="6" width="9" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3" /><path d="M3.5 6V4a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="currentColor" stroke-width="1.3" /></svg>
        {{ fills }}
      </p>
    </div>

    <footer>
      <button type="button" class="btn" :disabled="pivot.region === null" @click="emit('sql')">{{ t('Show as SQL…') }}</button>
      <button type="button" class="btn" @click="emit('close')">{{ t('Close') }}</button>
    </footer>
    <ContextMenu v-if="menu" :x="menu.x" :y="menu.y" :items="menuItems" :width="240" :label="t('Field menu')" @close="menu = null" />
  </aside>
</template>

<style scoped>
.pivot {
  position: fixed;
  z-index: 40;
  /* Where the search panel is (UX-39): left of History and chat, `--dx`/`--dy` are how far the person moved it. */
  top: calc(140px + var(--dy, 0px));
  right: calc(16px + var(--dock-width, 0px) - var(--dx, 0px));
  bottom: calc(56px - var(--dy, 0px));
  width: 390px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgb(31 26 51 / 22%);
  font-size: 13px;
  overflow: hidden;
}
header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px 8px 14px;
  border-bottom: 1px solid var(--line);
  cursor: grab;
  touch-action: none;
  user-select: none;
}
.moving header {
  cursor: grabbing;
}
.grip {
  flex: none;
  fill: var(--muted);
}
h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.name {
  flex: 1;
  min-width: 0;
  padding: 3px 12px;
  border: 1px solid var(--line-field);
  border-radius: 999px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mono {
  font-family: var(--font-mono, ui-monospace, monospace);
}
.close {
  border: 0;
  background: none;
  color: var(--muted);
  font-size: 12px;
  cursor: pointer;
  padding: 4px 6px;
}
.body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 16px 14px;
  display: grid;
  gap: 12px;
  align-content: start;
}
h3 {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.source {
  display: flex;
  align-items: center;
  gap: 10px;
}
.source select {
  flex: 1;
  padding: 5px 8px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
}
.muted {
  color: var(--muted);
}
.link {
  margin-left: auto;
  border: 0;
  background: none;
  color: var(--app-text, var(--iris));
  font-size: 13px;
  cursor: pointer;
}
.link:disabled {
  color: var(--muted);
  cursor: default;
}
.find {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  margin-bottom: 6px;
}
.fields,
.box ul {
  list-style: none;
  margin: 0;
  padding: 0;
}
.fields {
  max-height: 170px;
  overflow-y: auto;
}
.fields li label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  cursor: pointer;
}
.fields .field {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.type {
  color: var(--muted);
  font-size: 12px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
}
.dot.int {
  background: #f2a057;
}
.dot.real {
  background: var(--iris, #5b4bc4);
}
.hint {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.boxes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.box {
  min-height: 74px;
  padding: 8px;
  border: 1px solid var(--line-field);
  border-radius: 10px;
  background: color-mix(in srgb, var(--mist, #f4f1fa) 40%, transparent);
}
.box.over {
  border-color: var(--iris, #5b4bc4);
  background: color-mix(in srgb, var(--iris, #5b4bc4) 10%, transparent);
}
.chip {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  padding: 2px 2px 2px 8px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  cursor: grab;
}
.chip .label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chip .detail {
  color: var(--muted);
  font-size: 11px;
}
.more {
  border: 0;
  background: none;
  color: var(--text);
  padding: 4px 7px;
  cursor: pointer;
  border-radius: 6px;
}
.more:hover {
  background: var(--mist, #eee);
}
.totals {
  display: flex;
  gap: 18px;
}
.totals label {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fills {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.problem {
  color: var(--danger-dark, var(--rose));
  font-size: 12px;
}
footer {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 16px;
  border-top: 1px solid var(--line);
}
:focus-visible {
  outline: 2px solid var(--focus, var(--iris, #5b4bc4));
  outline-offset: 1px;
}
</style>
