<script setup lang="ts">
// The look of a style, in two views of the same thing: controls (colour, font, size, bold…) or the CSS itself (D73).
// The switch is remembered. It is used by every app: it only talks to the StyleHost it is given.
//
// The StyleEditor comes from the caller (StyleMenu.vue) rather than being made here, so that picking a different
// style to look at in the gallery and editing it below share the one piece of state (UX-14): `editor.current` is
// whichever style was picked, not necessarily `host.current` (the caret's own paragraph).
//
// The controls come in one section per facet (D303, `style-editor-two-slots.svg`): Text, Paragraph, Box, Outline,
// always in that order, and only those of `facets` — the facets the slot being styled reads, or, in the All styles
// dialog, those the style's kind can hold. A facet that is not there is left out, not disabled (D209).
import { computed, ref, watch } from 'vue'
import { isBold as boldIn, isItalic as italicIn } from '~/lib/style-css'
import { flatten, readable } from '~/lib/roles'
import { SIDES, facetsOfSlot, type Side, type StyleEditor, type StyleHost } from '~/lib/style-host'
import { useI18n } from '~/lib/i18n'
import { goToThis, thisOnly } from '~/lib/noun-phrases'

const { t } = useI18n()

const props = defineProps<{
  host: StyleHost
  editor: StyleEditor
  /** The facets to show; the slot's own by default. */
  facets?: string[]
  /** No "this … only": the All styles dialog, where nothing is selected and every change goes to every use. */
  fixed?: boolean
}>()
const host = props.host
const emit = defineEmits<{ edited: [] }>()

const editor = props.editor
const current = computed(() => editor.current)
const uses = computed(() => props.host.uses()[current.value?.id ?? ''] ?? 0)
const own = (property: string) => !!current.value && property in current.value.css
const off = computed(() => props.host.readOnly)
const isBold = computed(() => boldIn(editor.look))
const isItalic = computed(() => italicIn(editor.look))
const shown = computed(() => new Set(props.facets ?? facetsOfSlot(props.host.slot)))

const SIDE_CHOICES = ['all', ...SIDES] as const
function sideTitle(side: (typeof SIDE_CHOICES)[number]): string {
  switch (side) {
    case 'all':
      return t('All four sides')
    case 'top':
      return t('The top side')
    case 'right':
      return t('The right side')
    case 'bottom':
      return t('The bottom side')
    default:
      return t('The left side')
  }
}
const VERTICAL = ['top', 'middle', 'bottom'] as const
/** Box properties only some things have: a cell's vertical alignment and wrapping. */
const extras = computed(() => new Set(props.host.extras ?? []))
/** The sides the border controls work on: all four, or one. */
const side = ref<'all' | Side>(editor.borderSide())
// A different style picked (gallery, All styles list): open the border controls on the side it has a border on.
watch(() => editor.current?.id, () => (side.value = editor.borderSide()))
const sidesNow = computed<readonly Side[]>(() => (side.value === 'all' ? SIDES : [side.value]))
/** What the chosen side has — for "all", the top's, which is what a style that sets all four the same has. */
const borderNow = computed(() => editor.border(side.value === 'all' ? 'top' : side.value))
const borderColour = computed(() => borderNow.value?.colour ?? '@structure')

/** The words of this style, on the background they will really sit on — in plain words, never as a ratio (D202).
 *
 * Both colours come from `look`, which is already resolved, so a role and a literal are checked the same way. Two
 * things have to be right or the warning fires when it should not, which is how a warning gets ignored:
 *
 *  * a translucent background is **flattened** over what is behind it first. A shape's fill is `@accent/14`, and
 *    read as full-strength iris it looks far too dark to put words on — while what is actually there is a pale
 *    wash a shade off the page.
 *  * what is behind it is the document's own `page` role, which no style names, so it has to be asked of the
 *    palette rather than read off the style.
 *
 * With no colour of its own on either side there is nothing to check, and nothing is said. */
const unreadable = computed(() => {
  const page = host.roles.find((r) => r.id === 'page')?.colour
  const ink = flatten(editor.look.color, page)
  const own = editor.look['background-color'] ?? (shown.value.has('outline') ? editor.look.fill : undefined)
  const behind = flatten(own, page)
  if (!ink || !behind || readable(ink, behind)) return null
  return own ? t('The words will be hard to read on this background.') : t('These words will be hard to read.')
})

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

/** The alignment shown pressed: the style's, or — where a thing can align by its content — none of the four. */
const alignNow = computed(() => (props.host.alignOf ? (current.value ? props.host.alignOf(current.value.id) : undefined) : (editor.look['text-align'] ?? 'left')))

const ALIGN = computed(
  () =>
    [
      ['left', t('Left')],
      ['center', t('Centre')],
      ['right', t('Right')],
      ['justify', t('Justify')],
    ] as const,
)
</script>

<template>
  <section v-if="current" class="spec" data-testid="style-spec" :aria-label="t('Look')">
    <header class="head">
      <h3>{{ t('Look') }}</h3>
      <div class="switch" role="group" :aria-label="t('View of the style')">
        <button type="button" :aria-pressed="view === 'controls'" data-testid="view-controls" @click="view = 'controls'">{{ t('Controls') }}</button>
        <button type="button" :aria-pressed="view === 'css'" data-testid="view-css" @click="view = 'css'">{{ t('CSS') }}</button>
      </div>
    </header>

    <div v-if="!fixed" class="scope" role="radiogroup" :aria-label="t('Where a change goes')">
      <label :class="{ on: editor.scope === 'new' }" :title="editor.canDeviate ? undefined : goToThis(host.noun)">
        <input type="radio" name="scope" value="new" :checked="editor.scope === 'new'" :disabled="off || !editor.canDeviate" @change="editor.setScope('new')" >
        <span>{{ host.these ?? thisOnly(host.noun) }}</span>
      </label>
      <label v-if="host.narrow" class="narrow" :class="{ off: editor.scope !== 'new' }">
        <input type="checkbox" :checked="host.narrow.on" :disabled="off || editor.scope !== 'new'" data-testid="narrow" @change="host.narrow.set(($event.target as HTMLInputElement).checked)" >
        <span>{{ host.narrow.label }}</span>
      </label>
      <label :class="{ on: editor.scope === 'every' }">
        <input type="radio" name="scope" value="every" :checked="editor.scope === 'every'" :disabled="off" @change="editor.setScope('every')" >
        <span>{{ t('Every use of “{name}”', { name: current.name }) }}<em v-if="uses"> ({{ uses }})</em></span>
      </label>
    </div>
    <p v-else class="every" data-testid="every-use">{{ t('A change here changes every use of “{name}”', { name: current.name }) }}<em v-if="uses"> ({{ uses }})</em>.</p>

    <div v-if="view === 'controls'" class="controls" data-testid="controls">
      <section v-if="shown.has('text')" class="facet" data-facet="text" :aria-label="t('Text')">
        <h4>{{ t('Text') }}</h4>
        <div class="row">
          <StyleFontPicker :look="editor.look" :own="own('font-family')" :disabled="off" @pick="run(editor.setFamily($event))" @reset="run(editor.reset('font-family'))" />
          <StyleSizeField :look="editor.look" :disabled="off" @step="run(editor.stepSize($event))" @size="(v, u) => run(editor.setSize(v, u))" />
        </div>
        <div class="row">
          <div class="marks" role="group" :aria-label="t('Font properties')">
            <button type="button" class="b" :aria-pressed="isBold" :disabled="off" :title="t('Bold')" data-testid="bold" @click="run(editor.toggleBold())">B</button>
            <button type="button" class="i" :aria-pressed="isItalic" :disabled="off" :title="t('Italic')" data-testid="italic" @click="run(editor.toggleItalic())">I</button>
            <button type="button" class="u" :aria-pressed="editor.hasDecoration('underline')" :disabled="off" :title="t('Underline')" data-testid="underline" @click="run(editor.toggleDecoration('underline'))">U</button>
            <button type="button" class="s" :aria-pressed="editor.hasDecoration('line-through')" :disabled="off" :title="t('Strike through')" data-testid="strike" @click="run(editor.toggleDecoration('line-through'))">S</button>
          </div>
          <StyleColorPicker :label="t('Text')" :value="editor.named('color')" :own="own('color')" :disabled="off" :roles="host.roles" @pick="run(editor.setColor('color', $event))" @reset="run(editor.reset('color'))" />
        </div>
      </section>

      <section v-if="shown.has('paragraph')" class="facet" data-facet="paragraph" :aria-label="t('Paragraph')">
        <h4>{{ t('Paragraph') }}</h4>
        <div class="row">
          <div class="marks" role="group" :aria-label="t('Alignment')">
            <button v-if="host.alignOf" type="button" class="auto" :aria-pressed="alignNow === undefined" :disabled="off" :title="t('By content: numbers right, text left')" data-align="auto" @click="run(editor.reset('text-align'))">{{ t('Auto') }}</button>
            <button v-for="[value, label] in ALIGN" :key="value" type="button" :aria-pressed="alignNow === value" :disabled="off" :title="label" :data-align="value" @click="run(editor.setAlign(value))">
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path :d="value === 'left' ? 'M2 3h12M2 6.5h8M2 10h12M2 13.5h8' : value === 'center' ? 'M2 3h12M4 6.5h8M2 10h12M4 13.5h8' : value === 'right' ? 'M2 3h12M6 6.5h8M2 10h12M6 13.5h8' : 'M2 3h12M2 6.5h12M2 10h12M2 13.5h12'" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
            </button>
          </div>
        </div>
        <label class="row check" :title="t('Break long words at the end of a line where the text\'s language allows (in the pages and the PDF)')">
          <input type="checkbox" :checked="editor.hyphenates" :disabled="off" data-testid="hyphenate" @change="run(editor.setHyphens(($event.target as HTMLInputElement).checked))" >
          <span>{{ t('Hyphenate') }}</span>
        </label>
      </section>

      <section v-if="shown.has('box')" class="facet" data-facet="box" :aria-label="t('Box')" data-testid="box-controls">
        <h4>{{ t('Box') }}</h4>
        <div class="row">
          <StyleColorPicker :label="t('Background')" :value="editor.named('background-color')" :own="own('background-color')" :disabled="off" :roles="host.roles" washes @pick="run(editor.setColor('background-color', $event))" @reset="run(editor.reset('background-color'))" />
        </div>
        <div class="row border">
          <div class="marks sides" role="group" :aria-label="t('Which side the border is on')">
            <button v-for="s in SIDE_CHOICES" :key="s" type="button" :aria-pressed="side === s" :disabled="off" :title="sideTitle(s)" :data-side="s" @click="side = s">
              {{ s === 'all' ? '▢' : s === 'top' ? '▔' : s === 'right' ? '▕' : s === 'bottom' ? '▁' : '▏' }}
            </button>
          </div>
          <span class="stepper">
            <button type="button" :aria-label="t('Thinner border')" :disabled="off" data-testid="border-thinner" @click="run(editor.setBorder(sidesNow, (borderNow?.width ?? 0) - 1, borderColour))">−</button>
            <output class="mono" data-testid="border-width">{{ borderNow?.width ?? 0 }}</output>
            <button type="button" :aria-label="t('Thicker border')" :disabled="off" data-testid="border-thicker" @click="run(editor.setBorder(sidesNow, (borderNow?.width ?? 0) + 1, borderColour))">+</button>
          </span>
          <StyleColorPicker :label="t('Border')" :value="borderNow?.colour" :own="!!borderNow" :disabled="off" :roles="host.roles" @pick="run(editor.setBorder(sidesNow, Math.max(1, borderNow?.width ?? 1), $event))" @reset="run(editor.setBorder(sidesNow, 0, borderColour))" />
        </div>
        <div v-if="extras.has('vertical-align')" class="row">
          <span class="label">{{ t('Vertical') }}</span>
          <div class="marks words" role="group" :aria-label="t('Vertical alignment')" data-testid="vertical">
            <button v-for="v in VERTICAL" :key="v" type="button" :aria-pressed="editor.vertical === v" :disabled="off" :data-vertical="v" @click="run(editor.setVertical(v))">{{ v }}</button>
          </div>
        </div>
        <label v-if="extras.has('white-space')" class="row check">
          <input type="checkbox" :checked="editor.wraps" :disabled="off" data-testid="wrap" @change="run(editor.setWrap(($event.target as HTMLInputElement).checked))" >
          <span>{{ t('Wrap long text') }}</span>
        </label>
        <div class="row">
          <label class="width">
            <span>{{ t('Padding') }}</span>
            <span class="stepper">
              <button type="button" :aria-label="t('Less padding')" :disabled="off" data-testid="padding-less" @click="run(editor.setPadding(editor.padding - 2))">−</button>
              <output class="mono" data-testid="padding">{{ editor.padding }}</output>
              <button type="button" :aria-label="t('More padding')" :disabled="off" data-testid="padding-more" @click="run(editor.setPadding(editor.padding + 2))">+</button>
            </span>
            <span class="unit">{{ t('px') }}</span>
          </label>
        </div>
      </section>

      <!-- An outline is a shape's paint, in SVG's words because a shape is not a rectangle (D178). -->
      <section v-if="shown.has('outline')" class="facet" data-facet="outline" :aria-label="t('Outline')" data-testid="outline-controls">
        <h4>{{ t('Outline') }}</h4>
        <div class="row">
          <StyleColorPicker :label="t('Fill')" :value="editor.named('fill')" :own="own('fill')" :disabled="off" :roles="host.roles" washes @pick="run(editor.setFill($event))" @reset="run(editor.reset('fill'))" />
          <StyleColorPicker :label="t('Stroke')" :value="editor.named('stroke')" :own="own('stroke')" :disabled="off" :roles="host.roles" @pick="run(editor.setStroke($event))" @reset="run(editor.reset('stroke'))" />
        </div>
        <div class="row">
          <label class="width">
            <span>{{ t('Width') }}</span>
            <span class="stepper">
              <button type="button" :aria-label="t('Thinner')" :disabled="off" data-testid="thinner" @click="run(editor.stepStrokeWidth(-1))">−</button>
              <output class="mono" data-testid="stroke-width">{{ editor.strokeWidth }}</output>
              <button type="button" :aria-label="t('Thicker')" :disabled="off" data-testid="thicker" @click="run(editor.stepStrokeWidth(1))">+</button>
            </span>
            <span class="unit">{{ t('px') }}</span>
          </label>
        </div>
      </section>
      <p v-if="unreadable" class="unreadable" data-testid="unreadable">{{ unreadable }}</p>
    </div>

    <StyleCssEditor v-else :current="current" :styles="host.styles" :scope="editor.scope" :read-only="off" :check="(t) => host.check(t)" @apply="run(editor.setText($event))" />

    <form v-if="editor.invitesName" class="name" data-testid="name-invitation" @submit.prevent="name">
      <label>
        <span>{{ t('This style is called “{name}”. Give it a name that says what it is for?', { name: current.name }) }}</span>
        <input ref="nameField" v-model="naming" :placeholder="t('Name')" autocomplete="off" :aria-label="t('Name of the style')" >
      </label>
      <div class="actions">
        <button class="btn primary" type="submit" :disabled="!naming.trim()">{{ t('Name it') }}</button>
        <button class="btn" type="button" @click="editor.dismissNaming()">{{ t('Not now') }}</button>
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
.scope label.narrow {
  padding-left: 30px; /* under its "only" choice, which it narrows */
}
.scope label.narrow.off {
  color: var(--muted);
  cursor: default;
}
.row .label {
  align-self: center;
  min-width: 56px;
  font-size: 12.5px;
  color: var(--muted);
}
.marks button.auto {
  width: auto;
  padding: 0 8px;
  font-size: 12px;
}
.marks.words button {
  width: auto;
  padding: 0 10px;
  font-size: 12.5px;
}
.row.check {
  align-items: center;
  font-size: 13px;
}
.row.check input {
  accent-color: var(--app);
}
.controls {
  display: grid;
  gap: 10px;
}
.facet {
  display: grid;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--line);
}
.facet:first-child {
  padding-top: 0;
  border-top: 0;
}
.facet h4 {
  margin: 0;
  font: 600 10.5px/1 var(--font-ui);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
}
.every {
  margin: 0;
  padding: 7px 9px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--app) 9%, transparent);
  font-size: 12.5px;
}
.every em {
  font-style: normal;
  color: var(--muted);
}
.border {
  align-items: center;
  flex-wrap: wrap;
}
.row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.marks {
  display: inline-flex;
  border: 1px solid var(--line-field); /* the group's own edge, not a divider — the owner's 2026-11-06 report */
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
  /* Mixed with literal `white`, not `transparent`: this background stays light regardless of theme (same as
   * `StylesDialog.vue`'s `.flag`), so `--app-dark` as its text is already theme-stable too — leave both as they
   * are; swapping the text alone to `--app-text` would break it (light text on a background that never darkens). */
  background: color-mix(in srgb, var(--app) 18%, white);
  color: var(--app-dark);
}
.width {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line-field); /* the group's own edge, not a divider */
  border-radius: 8px;
  overflow: hidden;
}
.stepper button {
  width: 28px;
  height: 28px;
  border: 0;
  background: var(--surface);
  font-size: 15px;
  line-height: 1;
}
.stepper button:hover:not(:disabled) {
  background: var(--mist);
}
.stepper output {
  min-width: 34px;
  padding: 0 4px;
  border-inline: 1px solid var(--line);
  text-align: center;
  font-size: 12px;
  line-height: 28px;
}
.unit {
  color: var(--muted);
}
.unreadable {
  margin: 0;
  padding: 7px 9px;
  border-radius: 8px;
  /* Literal `white` so it stays light in either theme, as `.name` below does. */
  background: color-mix(in srgb, var(--apricot) 14%, white);
  font-size: 11.5px;
  color: var(--ink);
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
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>
