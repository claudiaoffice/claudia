<script setup lang="ts">
// The look of a style, in two views of the same thing: controls (colour, font, size, bold…) or the CSS itself (D73).
// The switch is remembered. It is used by every app: it only talks to the StyleHost it is given.
import { computed, reactive, ref, watch } from 'vue'
import { isBold as boldIn, isItalic as italicIn } from '~/lib/style-css'
import { StyleEditor, type StyleHost } from '~/lib/style-host'

const props = defineProps<{ host: StyleHost }>()
const emit = defineEmits<{ edited: [] }>()

const editor = reactive(new StyleEditor(props.host)) as StyleEditor
const current = computed(() => props.host.current)
const uses = computed(() => props.host.uses()[current.value?.id ?? ''] ?? 0)
const own = (property: string) => !!current.value && property in current.value.css
const off = computed(() => props.host.readOnly)
const isBold = computed(() => boldIn(editor.look))
const isItalic = computed(() => italicIn(editor.look))

const KEY = 'claudia.style-view'
function remembered(): 'controls' | 'css' {
  try {
    return localStorage.getItem(KEY) === 'css' ? 'css' : 'controls'
  } catch {
    return 'controls'
  }
}
const view = ref<'controls' | 'css'>(remembered())
watch(view, (v) => {
  try {
    localStorage.setItem(KEY, v)
  } catch {
    /* nothing to remember in a private window */
  }
})

async function run(job: Promise<boolean>) {
  if (await job) emit('edited')
}

const naming = ref('')
const nameField = ref<HTMLInputElement | null>(null)
async function name() {
  if (await editor.name(naming.value)) naming.value = ''
}

const ALIGN = [
  ['left', 'Left'],
  ['center', 'Centre'],
  ['right', 'Right'],
  ['justify', 'Justify'],
] as const
</script>

<template>
  <section v-if="current" class="spec" data-testid="style-spec" aria-label="Look">
    <header class="head">
      <h3>Look</h3>
      <div class="switch" role="group" aria-label="View of the style">
        <button type="button" :aria-pressed="view === 'controls'" data-testid="view-controls" @click="view = 'controls'">Controls</button>
        <button type="button" :aria-pressed="view === 'css'" data-testid="view-css" @click="view = 'css'">CSS</button>
      </div>
    </header>

    <div class="scope" role="radiogroup" :aria-label="`Where a change goes`">
      <label :class="{ on: editor.scope === 'new' }">
        <input type="radio" name="scope" value="new" :checked="editor.scope === 'new'" :disabled="off" @change="editor.setScope('new')" />
        <span>This {{ host.noun }} only</span>
      </label>
      <label :class="{ on: editor.scope === 'every' }">
        <input type="radio" name="scope" value="every" :checked="editor.scope === 'every'" :disabled="off" @change="editor.setScope('every')" />
        <span>Every use of “{{ current.name }}”<em v-if="uses"> ({{ uses }})</em></span>
      </label>
    </div>

    <div v-if="view === 'controls'" class="controls" data-testid="controls">
      <div class="row">
        <StyleFontPicker :look="editor.look" :own="own('font-family')" :disabled="off" @pick="run(editor.setFamily($event))" @reset="run(editor.reset('font-family'))" />
        <StyleSizeField :look="editor.look" :disabled="off" @step="run(editor.stepSize($event))" @size="(v, u) => run(editor.setSize(v, u))" />
      </div>
      <div class="row">
        <div class="marks" role="group" aria-label="Font properties">
          <button type="button" class="b" :aria-pressed="isBold" :disabled="off" title="Bold" data-testid="bold" @click="run(editor.toggleBold())">B</button>
          <button type="button" class="i" :aria-pressed="isItalic" :disabled="off" title="Italic" data-testid="italic" @click="run(editor.toggleItalic())">I</button>
          <button type="button" class="u" :aria-pressed="editor.hasDecoration('underline')" :disabled="off" title="Underline" data-testid="underline" @click="run(editor.toggleDecoration('underline'))">U</button>
          <button type="button" class="s" :aria-pressed="editor.hasDecoration('line-through')" :disabled="off" title="Strike through" data-testid="strike" @click="run(editor.toggleDecoration('line-through'))">S</button>
        </div>
        <div class="marks" role="group" aria-label="Alignment">
          <button v-for="[value, label] in ALIGN" :key="value" type="button" :aria-pressed="(editor.look['text-align'] ?? 'left') === value" :disabled="off" :title="label" :data-align="value" @click="run(editor.setAlign(value))">
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path :d="value === 'left' ? 'M2 3h12M2 6.5h8M2 10h12M2 13.5h8' : value === 'center' ? 'M2 3h12M4 6.5h8M2 10h12M4 13.5h8' : value === 'right' ? 'M2 3h12M6 6.5h8M2 10h12M6 13.5h8' : 'M2 3h12M2 6.5h12M2 10h12M2 13.5h12'" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
            </svg>
          </button>
        </div>
      </div>
      <div class="row">
        <StyleColorPicker label="Text" :value="editor.look.color" :own="own('color')" :disabled="off" @pick="run(editor.setColor('color', $event))" @reset="run(editor.reset('color'))" />
        <StyleColorPicker label="Background" :value="editor.look['background-color']" :own="own('background-color')" :disabled="off" @pick="run(editor.setColor('background-color', $event))" @reset="run(editor.reset('background-color'))" />
      </div>
    </div>

    <StyleCssEditor v-else :current="current" :styles="host.styles" :scope="editor.scope" :read-only="off" :check="(t) => host.check(t)" @apply="run(editor.setText($event))" />

    <form v-if="editor.invitesName" class="name" data-testid="name-invitation" @submit.prevent="name">
      <label>
        <span>This style is called “{{ current.name }}”. Give it a name that says what it is for?</span>
        <input ref="nameField" v-model="naming" placeholder="Name" autocomplete="off" aria-label="Name of the style" />
      </label>
      <div class="actions">
        <button class="btn primary" type="submit" :disabled="!naming.trim()">Name it</button>
        <button class="btn" type="button" @click="editor.dismissNaming()">Not now</button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.spec {
  display: grid;
  gap: 10px;
  padding: 10px 8px 8px;
  border-top: 1px solid var(--line);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
h3 {
  margin: 0;
  font: 600 11px/1 var(--font-ui);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}
.switch {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: var(--mist);
}
.switch button {
  height: 22px;
  padding: 0 10px;
  border: 0;
  border-radius: 6px;
  background: none;
  font-size: 12px;
  font-weight: 500;
  color: var(--muted);
}
.switch button[aria-pressed='true'] {
  background: var(--surface);
  color: var(--text);
  box-shadow: 0 1px 2px rgb(31 26 51 / 14%);
}
.scope {
  display: grid;
  gap: 2px;
}
.scope label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 7px;
  font-size: 13px;
  cursor: pointer;
}
.scope label.on {
  background: color-mix(in srgb, var(--app) 11%, transparent);
}
.scope em {
  font-style: normal;
  color: var(--muted);
}
.scope input {
  accent-color: var(--app);
}
.controls {
  display: grid;
  gap: 8px;
}
.row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.marks {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow: hidden;
}
.marks button {
  width: 30px;
  height: 28px;
  border: 0;
  background: var(--surface);
  display: grid;
  place-items: center;
  font-size: 14px;
}
.marks button + button {
  border-left: 1px solid var(--line);
}
.marks button:hover:not(:disabled) {
  background: var(--mist);
}
.marks button[aria-pressed='true'] {
  background: color-mix(in srgb, var(--app) 18%, white);
  color: var(--app-dark);
}
.b {
  font-weight: 700;
}
.i {
  font-style: italic;
  font-family: var(--font-display);
}
.u {
  text-decoration: underline;
}
.s {
  text-decoration: line-through;
}
.name {
  display: grid;
  gap: 8px;
  padding: 10px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--apricot) 14%, white);
  font-size: 12.5px;
}
.name label {
  display: grid;
  gap: 6px;
}
.name input {
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>
