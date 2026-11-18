<script setup lang="ts">
// All the styles of the document: what each is for, how often it is used, a way to name the ones that were made by
// deviating and still carry the name they were given (E9.8) — and Edit beside Rename (D302, `all-styles-edit.svg`).
// Edit widens the dialog and opens the editor beside the list, one section per facet the style's kind can hold.
// Nothing is selected here, so there is no "this … only": a change always goes to every use.
// Delete… (a document's own style) and Hide / Show (a built-in or template one, which can only be hidden) sit beside them
// (E1.10, D783, D785); Alt + the underlined letter acts on the row the focus is on.
import { computed, reactive, ref } from 'vue'
import { menuCss, previewCss, type StyleView } from '~/lib/style-css'
import { StyleEditor, facetsOfKind, type StyleHost } from '~/lib/style-host'
import { useI18n } from '~/lib/i18n'
import { usesCount } from '~/lib/noun-phrases'
import { actionForKey, deletedLine, mnemonic, type DeleteHow, type RowAction } from '~/lib/style-deletion'

const { t } = useI18n()

const props = defineProps<{ host: StyleHost }>()
const emit = defineEmits<{ close: [] }>()

const onlyUnnamed = ref(false)
const uses = computed(() => props.host.uses())
const unnamed = computed(() => props.host.styles.filter((s) => s.to_name).length)
const showHidden = ref(false)
const hiddenCount = computed(() => props.host.styles.filter((s) => s.hidden).length)
const shown = computed(() => props.host.styles.filter((s) => (!onlyUnnamed.value || s.to_name) && (showHidden.value || !s.hidden)))
const renaming = ref<string | null>(null)
const deleting = ref<StyleView | null>(null)
/** What the last deletion did, as the announcement beside Undo and Name it… (`style-delete-and-hide.svg`, D). */
const announced = ref<{ line: string; standIn: string | null } | null>(null)
const typed = ref('')

const editor = reactive(new StyleEditor(props.host, true)) as StyleEditor
const editing = ref<string | null>(null)
const edited = computed(() => props.host.styles.find((s) => s.id === editing.value))
const facets = computed(() => (edited.value ? facetsOfKind(props.host.model, edited.value.kind) : []))
/** Under about 760 px there is no room for two panes: the editor replaces the list, with a way back. */
const narrow = ref(typeof window !== 'undefined' && window.innerWidth < 760)

function rename(id: string, name: string) {
  renaming.value = id
  typed.value = name
}
async function save(id: string) {
  const name = typed.value.trim()
  if (name && (await props.host.rename(id, name))) renaming.value = null
}
function edit(id: string) {
  editing.value = id
  editor.pick(id)
}
/** Only the document's own styles can be deleted; the others can only be hidden (D780). */
const canDelete = (s: StyleView) => !s.origin && !!props.host.deletion
const canHide = (s: StyleView) => !!s.origin && !!props.host.deletion
function deleted(done: { name: string; how: DeleteHow; standIn: string | null; target: string | undefined }) {
  const standIn = done.standIn ? (props.host.styles.find((s) => s.id === done.standIn)?.name ?? done.standIn) : null
  announced.value = { line: deletedLine(done.name, done.how, standIn, done.target), standIn: done.standIn }
}
async function undo() {
  if (await props.host.deletion?.undo()) announced.value = null
}
function nameIt(id: string) {
  announced.value = null
  rename(id, '')
}
function hide(id: string, hidden: boolean) {
  void props.host.deletion?.hide(id, hidden)
}

// The words of the row actions, so that Alt + the first letter of a label (translated with it) does what it says.
const LABELS = computed<Record<RowAction, string>>(() => ({ edit: t('Edit'), rename: t('Rename'), delete: t('Delete…'), hide: t('Hide'), show: t('Show') }))
function rowKey(event: KeyboardEvent) {
  if (!event.altKey || event.ctrlKey || event.metaKey) return
  const row = (event.target as HTMLElement).closest('li[data-style]')
  if (!row) return
  const offered = [...row.querySelectorAll<HTMLButtonElement>('button[data-action]')]
  const labels: Partial<Record<RowAction, string>> = {}
  for (const button of offered) labels[button.dataset.action as RowAction] = LABELS.value[button.dataset.action as RowAction]
  const action = actionForKey(event.key, labels)
  if (!action) return
  event.preventDefault()
  offered.find((button) => button.dataset.action === action)?.click()
}
function count(id: string) {
  const n = uses.value[id] ?? 0
  return usesCount(props.host.usesNoun ?? props.host.noun, n)
}
</script>

<template>
  <Modal :title="t('Styles')" :width="editing && !narrow ? 780 : 520" @close="emit('close')">
    <div class="panes" :class="{ two: editing && !narrow }">
      <div v-if="!(editing && narrow)" class="list-pane">
        <div v-if="announced" class="announce" role="status" data-testid="deleted">
          <span>{{ announced.line }}</span>
          <span class="links">
            <button v-if="announced.standIn" type="button" class="link" data-testid="name-it" @click="nameIt(announced.standIn)">{{ t('Name it…') }}</button>
            <button type="button" class="link" data-testid="undo-delete" @click="undo">{{ t('Undo') }}</button>
          </span>
        </div>
        <label v-if="hiddenCount && !editing" class="filter"><input v-model="showHidden" type="checkbox" data-testid="show-hidden" > {{ t('Show hidden styles') }}</label>
        <label v-if="unnamed && !editing" class="filter"><input v-model="onlyUnnamed" type="checkbox" > {{ t('Only the {unnamed} waiting for a name', { unnamed }) }}</label>
        <ul class="list" :class="{ compact: !!editing }" data-testid="styles-list" @keydown="rowKey">
          <li v-for="s in shown" :key="s.id" :data-style="s.id" :class="{ on: s.id === editing, hidden: s.hidden }">
            <template v-if="editing">
              <button type="button" class="pick" :data-edit="s.id" @click="edit(s.id)">
                <span class="sample"><span :style="menuCss(s.resolved)">{{ s.name }}</span></span>
                <span class="count mono">{{ uses[s.id] ?? 0 }}</span>
              </button>
            </template>
            <template v-else>
              <div class="sample" :style="previewCss(s.resolved)">{{ s.name }}</div>
              <form v-if="renaming === s.id" class="rename" @submit.prevent="save(s.id)" @keydown.esc.stop="renaming = null">
                <input v-model="typed" :aria-label="t('New name of {name}', { name: s.name })" autofocus autocomplete="off" >
                <button class="btn primary" type="submit" :disabled="!typed.trim()">{{ t('Save') }}</button>
              </form>
              <div v-else class="meta">
                <span v-if="s.hidden" class="flag hiddenflag">{{ t('hidden') }}</span>
                <span v-if="s.to_name" class="flag">{{ t('to name') }}</span>
                <span v-else-if="s.purpose" class="purpose">{{ s.purpose }}</span>
                <span class="count mono">{{ count(s.id) }}</span>
                <span v-if="!host.readOnly" class="links">
                  <button type="button" class="link" data-action="rename" :aria-keyshortcuts="`Alt+${mnemonic(LABELS.rename).key.toUpperCase()}`" :data-rename="s.id" @click="rename(s.id, s.to_name ? '' : s.name)">{{ s.to_name ? t('Name it') : t('Rename') }}</button>
                  <button type="button" class="link strong" data-action="edit" :aria-keyshortcuts="`Alt+${mnemonic(LABELS.edit).key.toUpperCase()}`" :data-edit="s.id" @click="edit(s.id)"><span class="mn">{{ mnemonic(LABELS.edit).key }}</span>{{ mnemonic(LABELS.edit).tail }}</button>
                  <button v-if="canDelete(s)" type="button" class="link" data-action="delete" :aria-keyshortcuts="`Alt+${mnemonic(LABELS.delete).key.toUpperCase()}`" :data-delete="s.id" @click="deleting = s"><span class="mn">{{ mnemonic(LABELS.delete).key }}</span>{{ mnemonic(LABELS.delete).tail }}</button>
                  <button v-if="canHide(s)" type="button" class="link" :data-action="s.hidden ? 'show' : 'hide'" :aria-keyshortcuts="`Alt+${mnemonic(s.hidden ? LABELS.show : LABELS.hide).key.toUpperCase()}`" :data-hide="s.id" @click="hide(s.id, !s.hidden)"><span class="mn">{{ mnemonic(s.hidden ? LABELS.show : LABELS.hide).key }}</span>{{ mnemonic(s.hidden ? LABELS.show : LABELS.hide).tail }}</button>
                </span>
              </div>
            </template>
          </li>
        </ul>
      </div>
      <section v-if="edited" class="editor-pane" data-testid="style-editor-pane" :aria-label="t('Edit {name}', { name: edited.name })">
        <button v-if="narrow" type="button" class="link back" @click="editing = null">{{ t('← Styles') }}</button>
        <header>
          <div>
            <h3 :style="previewCss(edited.resolved)">{{ edited.name }}</h3>
            <p v-if="edited.purpose" class="purpose">{{ edited.purpose }}</p>
          </div>
          <button v-if="!host.readOnly" type="button" class="link" :data-rename="edited.id" @click="(editing = null), rename(edited.id, edited.to_name ? '' : edited.name)">{{ edited.to_name ? t('Name it') : t('Rename') }}</button>
        </header>
        <StyleSpec :host="host" :editor="editor" :facets="facets" fixed />
      </section>
    </div>
    <p v-if="host.deletion && !host.readOnly && !editing" class="keys">{{ t('Alt + the underlined letter acts on the style the focus is on.') }}</p>
    <div class="buttons"><button class="btn" type="button" @click="emit('close')">{{ t('Close') }}</button></div>
    <DeleteStyleDialog v-if="deleting" :host="host" :style="deleting" @close="deleting = null" @deleted="deleted" />
  </Modal>
</template>

<style scoped>
.panes.two {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 16px;
}
.list-pane {
  display: grid;
  gap: 8px;
  align-content: start;
}
.filter {
  font-size: 13px;
  display: flex;
  gap: 8px;
  align-items: center;
}
.list {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 62vh;
  overflow-y: auto;
  display: grid;
  gap: 2px;
}
.list li {
  display: grid;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
}
.list.compact li {
  padding: 0;
}
.list li:hover,
.list li.on {
  background: color-mix(in srgb, var(--mist) 50%, transparent);
}
.list li.on {
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.pick {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 10px;
  border: 0;
  background: none;
  text-align: left;
}
.pick .sample {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.sample {
  font-size: 16px;
  line-height: 1.3;
}
.meta,
.rename {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: var(--muted);
}
.rename input {
  flex: 1;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
}
.flag {
  padding: 1px 6px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--apricot) 28%, white);
  color: #7a4710;
}
.count {
  font-size: 11.5px;
  color: var(--muted);
}
.links {
  margin-left: auto;
  display: inline-flex;
  gap: 12px;
}
.link {
  border: 0;
  background: none;
  padding: 0;
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  cursor: pointer;
  font-size: 12px;
}
.link.strong {
  font-weight: 600;
}
.link:hover {
  text-decoration: underline;
}
.editor-pane {
  display: grid;
  gap: 10px;
  align-content: start;
  min-width: 0;
}
.editor-pane header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.editor-pane h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}
.purpose {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.back {
  justify-self: start;
}
.mn {
  text-decoration: underline;
}
.hiddenflag {
  background: color-mix(in srgb, var(--mist) 60%, white);
  color: var(--text);
}
.list li.hidden .sample {
  opacity: 0.6;
}
.announce {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--ink);
  color: var(--paper);
  font-size: 13px;
}
.announce .link {
  color: inherit;
  font-weight: 600;
  text-decoration: underline;
  white-space: nowrap;
}
.keys {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
