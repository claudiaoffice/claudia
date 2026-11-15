<script setup lang="ts">
// Format ▸ Rotate ▸ Rotate By… (D1024): the angle of the object you have selected, in whole degrees, as a number, on a dial
// and with quick buttons. While it is open the slide shows each angle as a preview only (nothing is sent); Done sends the
// one turn, and Cancel or Escape puts the object back as it was. The number is the accessible control: the dial is a
// second way to the same value, so a keyboard or a screen reader never needs it.
import { nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from '~/lib/i18n'
import { QUICK_TURNS, degreesText, parseAngle, quickTurn, turnFromPointer } from '~/lib/turning'

const { t } = useI18n()
const props = defineProps<{ x: number; y: number; rotation: number }>()
const emit = defineEmits<{ preview: [angle: number]; done: [angle: number]; cancel: [] }>()

const angle = ref(props.rotation)
const text = ref(String(props.rotation))
const field = ref<HTMLInputElement | null>(null)
const dial = ref<SVGSVGElement | null>(null)

watch(angle, (value) => emit('preview', value))
onMounted(async () => {
  await nextTick()
  field.value?.focus()
  field.value?.select()
})

/** What was typed, as far as it is a number; the field is put right when it is left. */
function typed() {
  const value = parseAngle(text.value)
  if (value !== null) angle.value = value
}
function settle() {
  text.value = String(angle.value)
}
function set(value: number) {
  angle.value = value
  text.value = String(value)
}

/** What a quick button says: the angles are the same in every language, only "Upright" is a word. */
const labelOf = (id: string) => ({ minus15: '−15°', plus15: '+15°', quarter: '90°', half: '180°', threeQuarters: '270°' })[id as 'minus15'] ?? t('Upright')

// The dial: straight up is 0°, clockwise, as the handle on the slide is.
let turningDial = false
function fromDial(event: PointerEvent) {
  const box = dial.value!.getBoundingClientRect()
  const centre = { x: box.left + box.width / 2, y: box.top + box.height / 2 }
  set(turnFromPointer(centre, { x: event.clientX, y: event.clientY }, { shift: event.shiftKey, alt: event.altKey }))
}
function dialDown(event: PointerEvent) {
  turningDial = true
  ;(event.currentTarget as Element).setPointerCapture(event.pointerId)
  fromDial(event)
}
function dialMove(event: PointerEvent) {
  if (turningDial) fromDial(event)
}
function dialUp() {
  turningDial = false
}

function done() {
  typed()
  emit('done', parseAngle(text.value) ?? angle.value)
}
</script>

<template>
  <Popover :x="x" :y="y" :width="264" :label="t('Rotate object')" @close="emit('cancel')">
    <form class="rotate" @submit.prevent="done">
      <label class="angle">
        {{ t('Angle') }}
        <span class="entry">
          <input
            ref="field"
            v-model="text"
            type="text"
            inputmode="numeric"
            :aria-describedby="'rotate-unit'"
            @input="typed"
            @blur="settle"
          />
          <span id="rotate-unit">{{ t('degrees clockwise') }}</span>
        </span>
      </label>
      <svg
        ref="dial"
        class="dial"
        viewBox="-50 -50 100 100"
        aria-hidden="true"
        @pointerdown="dialDown"
        @pointermove="dialMove"
        @pointerup="dialUp"
        @pointercancel="dialUp"
      >
        <circle r="44" class="face" />
        <line v-for="tick in [0, 90, 180, 270]" :key="tick" class="tick" x1="0" y1="-44" x2="0" y2="-38" :transform="`rotate(${tick})`" />
        <g :transform="`rotate(${angle})`">
          <line class="needle" x1="0" y1="0" x2="0" y2="-36" />
          <circle class="knob" cx="0" cy="-36" r="6" />
        </g>
      </svg>
      <p class="said" aria-live="polite">{{ t('Turned to {degrees}', { degrees: degreesText(angle) }) }}</p>
      <div class="quick" role="group" :aria-label="t('Quick turns')">
        <button v-for="q in QUICK_TURNS" :key="q.id" class="btn" type="button" @click="set(quickTurn(angle, q))">{{ labelOf(q.id) }}</button>
      </div>
      <div class="buttons">
        <button class="btn primary" type="submit">{{ t('Done') }}</button>
        <button class="btn" type="button" @click="emit('cancel')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Popover>
</template>

<style scoped>
.rotate {
  display: grid;
  gap: 10px;
  padding: 6px;
}
.angle {
  display: grid;
  gap: 4px;
}
.entry {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 13px;
}
input {
  width: 5em;
  font: inherit;
  text-align: right;
}
.dial {
  width: 112px;
  height: 112px;
  justify-self: center;
  touch-action: none;
  cursor: grab;
}
.face {
  fill: color-mix(in srgb, var(--ink) 4%, var(--paper));
  stroke: var(--line);
  stroke-width: 1.5;
}
.tick {
  stroke: var(--muted);
  stroke-width: 1.5;
}
.needle {
  stroke: var(--iris);
  stroke-width: 2;
}
.knob {
  fill: #fff;
  stroke: var(--iris);
  stroke-width: 2;
}
.said {
  margin: 0;
  text-align: center;
  color: var(--muted);
  font-size: 13px;
}
.quick {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
