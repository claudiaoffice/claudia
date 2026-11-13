<script setup lang="ts">
// All the styles of the document: what each is for, how often it is used, a way to name the ones that were made by
// deviating and still carry the name they were given (E9.8) — and Edit beside Rename (D302, `all-styles-edit.svg`).
// Edit widens the dialog and opens the editor beside the list, one section per facet the style's kind can hold.
// Nothing is selected here, so there is no "this … only": a change always goes to every use.
import { computed, reactive, ref } from 'vue'
import { menuCss, previewCss } from '~/lib/style-css'
import { StyleEditor, facetsOfKind, type StyleHost } from '~/lib/style-host'

const props = defineProps<{ host: StyleHost }>()
const emit = defineEmits<{ close: [] }>()

const onlyUnnamed = ref(false)
const uses = computed(() => props.host.uses())
const unnamed = computed(() => props.host.styles.filter((s) => s.to_name).length)
const shown = computed(() => props.host.styles.filter((s) => !onlyUnnamed.value || s.to_name))
const renaming = ref<string | null>(null)
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
function count(id: string) {
  const n = uses.value[id] ?? 0
  const noun = props.host.usesNoun ?? props.host.noun
  return `${n} ${n === 1 ? noun : `${noun}s`}`
}
</script>

<template>
  <Modal title="Styles" :width="editing && !narrow ? 780 : 520" @close="emit('close')">
    <div class="panes" :class="{ two: editing && !narrow }">
      <div v-if="!(editing && narrow)" class="list-pane">
        <label v-if="unnamed && !editing" class="filter"><input v-model="onlyUnnamed" type="checkbox" > Only the {{ unnamed }} waiting for a name</label>
        <ul class="list" :class="{ compact: !!editing }" data-testid="styles-list">
          <li v-for="s in shown" :key="s.id" :data-style="s.id" :class="{ on: s.id === editing }">
            <template v-if="editing">
              <button type="button" class="pick" :data-edit="s.id" @click="edit(s.id)">
                <span class="sample"><span :style="menuCss(s.resolved)">{{ s.name }}</span></span>
                <span class="count mono">{{ uses[s.id] ?? 0 }}</span>
              </button>
            </template>
            <template v-else>
              <div class="sample" :style="previewCss(s.resolved)">{{ s.name }}</div>
              <form v-if="renaming === s.id" class="rename" @submit.prevent="save(s.id)" @keydown.esc.stop="renaming = null">
                <input v-model="typed" :aria-label="`New name of ${s.name}`" autofocus autocomplete="off" >
                <button class="btn primary" type="submit" :disabled="!typed.trim()">Save</button>
              </form>
              <div v-else class="meta">
                <span v-if="s.to_name" class="flag">to name</span>
                <span v-else-if="s.purpose" class="purpose">{{ s.purpose }}</span>
                <span class="count mono">{{ count(s.id) }}</span>
                <span v-if="!host.readOnly" class="links">
                  <button type="button" class="link" :data-rename="s.id" @click="rename(s.id, s.to_name ? '' : s.name)">{{ s.to_name ? 'Name it' : 'Rename' }}</button>
                  <button type="button" class="link strong" :data-edit="s.id" @click="edit(s.id)">Edit</button>
                </span>
              </div>
            </template>
          </li>
        </ul>
      </div>
      <section v-if="edited" class="editor-pane" data-testid="style-editor-pane" :aria-label="`Edit ${edited.name}`">
        <button v-if="narrow" type="button" class="link back" @click="editing = null">← Styles</button>
        <header>
          <div>
            <h3 :style="previewCss(edited.resolved)">{{ edited.name }}</h3>
            <p v-if="edited.purpose" class="purpose">{{ edited.purpose }}</p>
          </div>
          <button v-if="!host.readOnly" type="button" class="link" :data-rename="edited.id" @click="(editing = null), rename(edited.id, edited.to_name ? '' : edited.name)">{{ edited.to_name ? 'Name it' : 'Rename' }}</button>
        </header>
        <StyleSpec :host="host" :editor="editor" :facets="facets" fixed />
      </section>
    </div>
    <div class="buttons"><button class="btn" type="button" @click="emit('close')">Close</button></div>
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
.buttons {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
