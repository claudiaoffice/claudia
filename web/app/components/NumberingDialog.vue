<script setup lang="ts">
// Format ▸ List ▸ All Numbering…: the numbering manager (E9.22, `composes-numbered-headings.svg`, D), All Styles' twin
// (D302): the document's schemes on the left, the chosen one on the right. Per level the number format (or a bullet, or
// nothing), the text before and after it and which levels it shows; the indent and the gap; a preview; and Used by, the
// lists and the styles a change reaches. Every change is one step in the history, for everybody. A built-in scheme can
// be changed and reset, one of the document's own removed while no list uses it. The same in every app whose
// paragraphs can be numbered: the host is the session, which sends the requests.
//
// Keys as in All Styles: Tab moves through the list and the editor, Esc closes. Every field has a label for screen
// readers; the preview is aria-hidden, the Used by sentence is not.
import { computed, ref, watch } from 'vue'
import { useI18n } from '~/lib/i18n'
import {
  BUILT_IN_SCHEMES,
  LEVELS,
  NUMBER_FORMATS,
  markerOf,
  usersOf,
  type LevelFormat,
  type NumberFormat,
  type NumberingHost,
  type SchemeInfo,
} from '~/lib/numbering'

const { t } = useI18n()

const props = defineProps<{ host: NumberingHost; initial?: string }>()
const emit = defineEmits<{ close: [] }>()

const chosenId = ref(props.initial ?? props.host.schemes[0]?.id ?? '')
const chosen = computed(() => props.host.schemes.find((s) => s.id === chosenId.value) ?? props.host.schemes[0])
/** The levels shown: four, or all nine on request (the mock-up's "Show all levels"). */
const allLevels = ref(false)
const shownLevels = computed(() => (allLevels.value ? LEVELS : 4))
const users = computed(() => (chosen.value ? usersOf(chosen.value.id, props.host.lists, props.host.styles) : { lists: [], styles: [] }))
const builtIn = computed(() => !!chosen.value && BUILT_IN_SCHEMES.includes(chosen.value.id))
const naming = ref(false)
const newName = ref('')
watch(chosenId, () => (naming.value = false))

const FORMAT_LABELS: Record<NumberFormat, string> = {
  decimal: '1, 2, 3',
  'lower-alpha': 'a, b, c',
  'upper-alpha': 'A, B, C',
  'lower-roman': 'i, ii, iii',
  'upper-roman': 'I, II, III',
  bullet: '•',
  none: '—',
}
const formatLabel = (f: NumberFormat) => (f === 'bullet' ? t('Bullet') : f === 'none' ? t('Nothing') : FORMAT_LABELS[f])

/** What a scheme draws on its first levels, for the list on the left. */
function sample(scheme: SchemeInfo): string {
  return [[1], [1, 1], [1, 1, 1]].map((path) => markerOf(scheme, path)).join('   ')
}

/** The preview: the first levels counted as a short text would count them. */
const preview = computed(() => {
  const s = chosen.value
  if (!s) return []
  const paths = [[1], [1, 1], [1, 1, 1], [1, 2], [2]]
  return paths.map((path) => ({ level: path.length - 1, marker: markerOf(s, path) }))
})

function showsLabel(level: number, from: number): string {
  return from === level ? t('this level') : t('levels {from}–{to}', { from: from + 1, to: level + 1 })
}

/** Send the scheme with one level changed; the server says whether it may be. */
function changeLevel(level: number, change: Partial<LevelFormat>) {
  const s = chosen.value
  if (!s || props.host.readOnly) return
  const levels = s.levels.map((each, i) => (i === level ? { ...each, ...change } : each))
  const own = levels[level]!
  if (change.format === 'bullet' && !own.bullet) own.bullet = '•'
  if (own.format === 'bullet' || own.format === 'none') own.from_level = level
  void props.host.changeScheme({ ...s, levels })
}

function changeNumber(field: 'indent' | 'gap', value: string) {
  const s = chosen.value
  const n = Number.parseFloat(value)
  if (!s || props.host.readOnly || !Number.isFinite(n)) return
  void props.host.changeScheme({ ...s, [field]: n })
}

function rename(value: string) {
  const s = chosen.value
  if (!s || props.host.readOnly || !value.trim() || value.trim() === s.name) return
  void props.host.changeScheme({ ...s, name: value.trim() })
}

async function create() {
  const s = chosen.value
  const name = newName.value.trim()
  if (!s || !name) return
  const made = await props.host.newScheme(s.id, name)
  if (made) {
    chosenId.value = made
    naming.value = false
    newName.value = ''
  }
}

async function remove() {
  const s = chosen.value
  if (s && (await props.host.removeScheme(s.id))) chosenId.value = props.host.schemes[0]?.id ?? ''
}
</script>

<template>
  <Modal :title="t('All Numbering')" :width="780" @close="emit('close')">
    <div class="panes">
      <section class="list-pane" :aria-label="t('Schemes')">
        <h3 class="caption">{{ t('Schemes') }}</h3>
        <ul class="list" data-testid="schemes-list">
          <li v-for="s in host.schemes" :key="s.id" :class="{ on: s.id === chosen?.id }">
            <button type="button" class="pick" :data-scheme="s.id" :aria-pressed="s.id === chosen?.id" @click="chosenId = s.id">
              <span class="name">{{ s.name }}</span>
              <span class="sample mono" aria-hidden="true">{{ sample(s) }}</span>
              <span class="count">{{ t('{count} lists', { count: usersOf(s.id, host.lists, host.styles).lists.length }) }}</span>
            </button>
          </li>
        </ul>
        <form v-if="naming" class="rename" @submit.prevent="create" @keydown.esc.stop="naming = false">
          <input v-model="newName" :aria-label="t('Name of the new scheme')" autofocus autocomplete="off" >
          <button class="btn primary" type="submit" :disabled="!newName.trim()">{{ t('Make') }}</button>
        </form>
        <button v-else-if="!host.readOnly" type="button" class="link" data-testid="new-scheme" @click="naming = true">{{ t('+ New scheme') }}</button>
      </section>

      <section v-if="chosen" class="editor-pane" data-testid="scheme-editor" :aria-label="t('Edit {name}', { name: chosen.name })">
        <div class="row">
          <label>{{ t('Name') }} <input :value="chosen.name" :disabled="host.readOnly" data-testid="scheme-name" @change="rename(($event.target as HTMLInputElement).value)" ></label>
          <span class="kind">{{ chosen.kind === 'number' ? t('numbers') : t('bullets') }}</span>
        </div>
        <table class="levels">
          <thead>
            <tr>
              <th scope="col">{{ t('Level') }}</th>
              <th scope="col">{{ t('Number') }}</th>
              <th scope="col">{{ t('Before') }}</th>
              <th scope="col">{{ t('After') }}</th>
              <th scope="col">{{ t('Shows') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="level in shownLevels" :key="level" :data-level="level - 1">
              <th scope="row">{{ level }}</th>
              <td>
                <select
                  :value="chosen.levels[level - 1]?.format"
                  :disabled="host.readOnly"
                  :aria-label="t('Number of level {level}', { level })"
                  @change="changeLevel(level - 1, { format: ($event.target as HTMLSelectElement).value as NumberFormat })"
                >
                  <option v-for="f in NUMBER_FORMATS" :key="f" :value="f">{{ formatLabel(f) }}</option>
                </select>
                <input
                  v-if="chosen.levels[level - 1]?.format === 'bullet'"
                  class="sign"
                  maxlength="4"
                  :value="chosen.levels[level - 1]?.bullet"
                  :disabled="host.readOnly"
                  :aria-label="t('Bullet of level {level}', { level })"
                  @change="changeLevel(level - 1, { bullet: ($event.target as HTMLInputElement).value })"
                >
              </td>
              <td><input class="affix" maxlength="20" :value="chosen.levels[level - 1]?.before" :disabled="host.readOnly" :aria-label="t('Text before level {level}', { level })" @change="changeLevel(level - 1, { before: ($event.target as HTMLInputElement).value })" ></td>
              <td><input class="affix" maxlength="20" :value="chosen.levels[level - 1]?.after" :disabled="host.readOnly" :aria-label="t('Text after level {level}', { level })" @change="changeLevel(level - 1, { after: ($event.target as HTMLInputElement).value })" ></td>
              <td>
                <select
                  :value="chosen.levels[level - 1]?.from_level"
                  :disabled="host.readOnly || ['bullet', 'none'].includes(chosen.levels[level - 1]?.format ?? '')"
                  :aria-label="t('Levels level {level} shows', { level })"
                  @change="changeLevel(level - 1, { from_level: Number(($event.target as HTMLSelectElement).value) })"
                >
                  <option v-for="from in level" :key="from" :value="from - 1">{{ showsLabel(level - 1, from - 1) }}</option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
        <label class="all"><input v-model="allLevels" type="checkbox" > {{ t('Show all levels') }}</label>
        <div class="row">
          <label>{{ t('Indent per level') }} <input type="number" min="0" max="10" step="0.1" :value="chosen.indent" :disabled="host.readOnly" @change="changeNumber('indent', ($event.target as HTMLInputElement).value)" > em</label>
          <label>{{ t('Gap between items') }} <input type="number" min="0" max="5" step="0.05" :value="chosen.gap" :disabled="host.readOnly" @change="changeNumber('gap', ($event.target as HTMLInputElement).value)" > em</label>
        </div>
        <div class="preview" aria-hidden="true" data-testid="scheme-preview">
          <div v-for="(line, i) in preview" :key="i" :style="{ paddingLeft: `${line.level * chosen.indent}em` }"><span class="marker">{{ line.marker }}</span> {{ t('Item') }}</div>
        </div>
        <p class="used" data-testid="scheme-used">
          <template v-if="users.lists.length || users.styles.length">
            {{ t('Used by {lists} lists and the styles {styles}. A change renumbers them for everybody, as one step in the history.', { lists: users.lists.length, styles: users.styles.map((s) => s.name).join(', ') || '—' }) }}
          </template>
          <template v-else>{{ t('No list uses this scheme.') }}</template>
        </p>
        <div class="buttons left">
          <button v-if="builtIn && !host.readOnly" type="button" class="btn" data-testid="reset-scheme" @click="host.resetScheme(chosen.id)">{{ t('Reset to built-in') }}</button>
          <button v-if="!builtIn && !host.readOnly" type="button" class="btn" :disabled="users.lists.length > 0" :title="users.lists.length ? t('A list uses this scheme') : undefined" data-testid="remove-scheme" @click="remove">{{ t('Remove') }}</button>
        </div>
      </section>
    </div>
    <div class="buttons"><button class="btn" type="button" @click="emit('close')">{{ t('Close') }}</button></div>
  </Modal>
</template>

<style scoped>
.panes {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
}
.caption {
  font-size: 12px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--ink-soft);
  margin: 0 0 6px;
}
.list {
  list-style: none;
  margin: 0 0 8px;
  padding: 0;
  display: grid;
  gap: 4px;
}
.pick {
  width: 100%;
  display: grid;
  text-align: left;
  gap: 2px;
  padding: 6px 8px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  color: var(--ink);
  cursor: pointer;
}
.on .pick {
  border-color: var(--app);
  box-shadow: inset 3px 0 0 var(--app);
}
.sample,
.count,
.kind {
  font-size: 12px;
  color: var(--ink-soft);
}
.editor-pane {
  display: grid;
  gap: 10px;
  align-content: start;
}
.row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
}
.levels {
  border-collapse: collapse;
  font-size: 13px;
}
.levels th,
.levels td {
  padding: 3px 6px;
  text-align: left;
}
.levels thead th {
  font-size: 11px;
  text-transform: uppercase;
  color: var(--ink-soft);
}
.affix {
  width: 6em;
}
.sign {
  width: 3em;
  margin-left: 4px;
}
.preview {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 13px;
  display: grid;
  gap: 2px;
}
.marker {
  display: inline-block;
  min-width: 2.5em;
  font-variant-numeric: tabular-nums;
}
.used {
  font-size: 13px;
  margin: 0;
}
.buttons.left {
  justify-content: flex-start;
}
.rename {
  display: flex;
  gap: 6px;
}
</style>
