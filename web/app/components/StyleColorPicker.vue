<script setup lang="ts">
// A colour for one CSS property. The document's palette comes first — a colour is picked by what it *means*
// (D200) — and a colour of its own is still there, one step further in, saying what it costs (D202).
import { computed, ref, watch } from 'vue'
import { SWATCHES } from '~/lib/palette'
import { nameOf, nearestRole, offPalette, roleValue, swatchFor, type ColourRole } from '~/lib/roles'
import { toHex } from '~/lib/style-css'

const props = defineProps<{
  label: string
  /** What the style *names*: a palette role (`@accent`) or a literal colour. */
  value: string | undefined
  own: boolean
  disabled?: boolean
  /** The document's roles. Empty for a document without a palette, and then this is a plain colour picker. */
  roles?: ColourRole[]
  /** Offered as a wash of a role, for a fill: a border wants the colour itself. */
  washes?: boolean
}>()
const emit = defineEmits<{ pick: [color: string]; reset: [] }>()

const open = ref(false)
const roles = computed(() => props.roles ?? [])
const hex = computed(() => toHex(props.value))
const typed = ref(hex.value ?? '')
watch(hex, (h) => (typed.value = h ?? props.value ?? ''))

/** Shown on the button: the role's name where there is one, so a person reads a meaning and not a hex. */
const shown = computed(() => nameOf(props.value, roles.value))
const paint = computed(() => swatchFor(props.value, roles.value))
const strayed = computed(() => offPalette(props.value, roles.value))
const nearest = computed(() => nearestRole(props.value, roles.value))

/** Was the palette's own list left behind for a colour of its own? Opened on demand, and on a stray value. */
const literal = ref(false)
watch(strayed, (yes) => (literal.value = literal.value || yes), { immediate: true })

const valid = computed(() => /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(typed.value.trim()))
const WASHES = [100, 55, 24, 14, 8]

function commit() {
  if (valid.value) emit('pick', typed.value.trim())
}
function pick(color: string) {
  emit('pick', color)
  open.value = false
}
function chooseRole(role: string, opacity: number | null) {
  pick(roleValue(role, opacity))
}
/** The one click that adopts the nearest role: what "use Accent instead" does in the mock. */
function adopt() {
  if (nearest.value) chooseRole(nearest.value.id, null)
}
</script>

<template>
  <div class="colour" :data-testid="`colour-${label.toLowerCase().replace(/\s/g, '-')}`">
    <button class="swatch-btn" type="button" :disabled="disabled" :aria-expanded="open" :aria-label="`${label}: ${shown}`" :title="label" @click="open = !open">
      <i :style="{ background: paint || 'transparent' }" :class="{ empty: !paint || paint === 'transparent' }" />
      <span class="what">{{ label }}</span>
      <span class="is">{{ shown }}</span>
    </button>
    <div v-if="open" class="drop">
      <!-- the palette: a colour by what it means -->
      <template v-if="roles.length">
        <ul class="roles" role="listbox" :aria-label="`${label}, from the palette`">
          <li v-for="r in roles" :key="r.id" role="option" :aria-selected="value === `@${r.id}`">
            <button type="button" :class="{ on: value?.startsWith(`@${r.id}`) }" :data-role="r.id" @click="chooseRole(r.id, null)">
              <i :style="{ background: r.colour }" />
              <span class="name">{{ r.name }}</span>
              <span class="why">{{ r.purpose }}</span>
            </button>
          </li>
        </ul>
        <div v-if="washes" class="washes" role="group" :aria-label="`${label}, how strong`">
          <span class="legend">How strong</span>
          <button v-for="w in WASHES" :key="w" type="button" class="wash" :class="{ on: (value ?? '').endsWith(w === 100 ? '' : `/${w}`) && value?.startsWith('@') }" :disabled="!value?.startsWith('@')" :data-wash="w" @click="chooseRole((value ?? '').replace(/^@/, '').split('/')[0] ?? '', w === 100 ? null : w)">{{ w }}%</button>
        </div>
      </template>

      <!-- a colour of its own: allowed, one step further in, and told what it costs -->
      <button v-if="roles.length && !literal" class="leave" type="button" data-testid="off-palette" @click="literal = true">Off the palette…</button>
      <template v-else>
        <div class="row">
          <input v-model="typed" class="hex mono" spellcheck="false" :aria-label="`${label} as hex`" placeholder="#5b4bc4" @keydown.enter.prevent="commit" @blur="commit" >
          <input type="color" class="system" :value="hex ?? '#000000'" :aria-label="`${label}, system picker`" @change="pick(($event.target as HTMLInputElement).value)" >
        </div>
        <div class="grid">
          <button v-for="s in SWATCHES" :key="s.value" type="button" class="chip" :class="{ on: hex?.toLowerCase() === s.value.toLowerCase() }" :title="s.name" :aria-label="s.name" :style="{ background: s.value }" @click="pick(s.value)" />
        </div>
      </template>

      <p v-if="strayed" class="strayed" data-testid="off-palette-warning">
        This colour is not in the palette, so a palette change will leave it behind.
        <button v-if="nearest" type="button" @click="adopt">Use {{ nearest.name }} instead</button>
      </p>

      <button v-if="own" class="reset" type="button" @click="emit('reset')">Follow the parent style again</button>
    </div>
  </div>
</template>

<style scoped>
.colour {
  position: relative;
}
.swatch-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 30px;
  max-width: 100%;
  padding: 0 9px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  background: var(--surface);
  font-size: 13px;
}
.swatch-btn:hover:not(:disabled) {
  border-color: var(--app);
}
.swatch-btn i {
  width: 16px;
  height: 16px;
  flex: none;
  border-radius: 5px;
  box-shadow: inset 0 0 0 1px rgb(31 26 51 / 22%);
}
.swatch-btn i.empty {
  background: repeating-linear-gradient(45deg, #fff 0 3px, var(--mist) 3px 6px) !important;
}
.what {
  flex: none;
}
.is {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
  font-size: 12px;
}
.drop {
  position: absolute;
  z-index: 3;
  min-width: 232px;
  margin-top: 6px;
  padding: 10px;
  display: grid;
  gap: 10px;
  border: 1px solid var(--line-field); /* a floating panel's own edge, not a divider — same fix as Modal.vue */
  border-radius: 10px;
  background: var(--surface);
  box-shadow: 0 8px 24px rgb(31 26 51 / 14%);
}
.roles {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 1px;
  max-height: 208px;
  overflow-y: auto;
}
.roles button {
  display: grid;
  grid-template-columns: 16px 1fr;
  grid-template-areas: 'swatch name' 'swatch why';
  align-items: center;
  gap: 0 9px;
  width: 100%;
  padding: 5px 7px;
  border: 0;
  border-radius: 7px;
  background: none;
  text-align: left;
  cursor: pointer;
}
.roles button:hover {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.roles button.on {
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.roles i {
  grid-area: swatch;
  width: 16px;
  height: 16px;
  border-radius: 5px;
  box-shadow: inset 0 0 0 1px rgb(31 26 51 / 22%);
}
.roles .name {
  grid-area: name;
  font-size: 13px;
}
.roles .why {
  grid-area: why;
  font-size: 11px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.washes {
  display: flex;
  align-items: center;
  gap: 4px;
}
.legend {
  margin-right: 2px;
  font-size: 11px;
  color: var(--muted);
}
.wash {
  flex: 1;
  height: 24px;
  border: 1px solid var(--line-field);
  border-radius: 6px;
  background: var(--surface);
  font-size: 11px;
  color: var(--text);
}
.wash.on {
  border-color: var(--app);
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.leave {
  justify-self: start;
  border: 1px dashed var(--line-field);
  border-radius: 7px;
  padding: 4px 9px;
  background: var(--surface);
  font-size: 11.5px;
  color: var(--text);
  cursor: pointer;
}
.grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 6px;
}
.chip {
  aspect-ratio: 1;
  border: 0;
  border-radius: 6px;
  box-shadow: inset 0 0 0 1px rgb(31 26 51 / 20%);
  cursor: pointer;
}
.chip.on {
  outline: 2px solid var(--app);
  outline-offset: 2px;
}
.row {
  display: flex;
  gap: 8px;
}
.hex {
  flex: 1;
  min-width: 0;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
}
.system {
  width: 38px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  background: none;
}
.strayed {
  margin: 0;
  padding: 8px 9px;
  border-radius: 8px;
  /* Mixed with literal `white` so the warning stays light in either theme, as `.flag` elsewhere does. */
  background: color-mix(in srgb, var(--apricot) 14%, white);
  font-size: 11.5px;
  line-height: 1.45;
  color: var(--ink);
}
.strayed button {
  display: block;
  margin-top: 6px;
  border: 0;
  padding: 0;
  background: none;
  color: var(--app-dark);
  font-size: 11.5px;
  text-decoration: underline;
  cursor: pointer;
}
.reset {
  justify-self: start;
  border: 0;
  padding: 0;
  background: none;
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  font-size: 12px;
  text-decoration: underline;
  cursor: pointer;
}
</style>
