<script setup lang="ts">
// The handles of a selected object, drawn once for all three apps (D1221): the eight (or four) resize handles, and the
// turn handle on its stem with the angle chip. It fills the box of the object (the parent is positioned and has the
// object's size), draws no outline of its own, and knows nothing of what it is handling: a press on a handle is the app's
// to answer, through `useObjectInteraction`. The turn handle is a slider for a screen reader (arrow keys turn it, BITV).
import { computed } from 'vue'
import type { Handle } from '~/lib/geometry'
import { degreesText } from '~/lib/turning'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()
const props = defineProps<{
  handles: Handle[]
  /** Show the turn handle (an object that turns, that can be changed). */
  turnable: boolean
  /** The angle the object has on screen, whole degrees. */
  turn: number
  /** The angle chip is showing: a turn is under way. */
  turning?: boolean
  /** The turn handle would be off the area at the top: it goes below the object instead. */
  below?: boolean
}>()
const emit = defineEmits<{ handle: [event: PointerEvent, handle: Handle]; turnDown: [event: PointerEvent]; turnKey: [event: KeyboardEvent] }>()

const CURSOR: Record<Handle, string> = { nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize', n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize' }
const AT: Record<Handle, [number, number]> = { nw: [0, 0], n: [0.5, 0], ne: [1, 0], e: [1, 0.5], se: [1, 1], s: [0.5, 1], sw: [0, 1], w: [0, 0.5] }
const styleOf = (h: Handle) => ({ left: `${AT[h][0] * 100}%`, top: `${AT[h][1] * 100}%`, cursor: CURSOR[h] })
const said = computed(() => degreesText(props.turn))
</script>

<template>
  <div class="frame" :class="{ below }">
    <template v-if="turnable">
      <span class="stem" aria-hidden="true" />
      <span
        class="turn"
        role="slider"
        tabindex="0"
        data-handle="turn"
        :aria-label="t('Rotate object')"
        aria-orientation="horizontal"
        aria-valuemin="0"
        aria-valuemax="359"
        :aria-valuenow="turn"
        :aria-valuetext="said"
        :title="t('Turn: drag, or arrow keys (Shift for 15°)')"
        @pointerdown="emit('turnDown', $event)"
        @keydown="emit('turnKey', $event)"
      />
    </template>
    <span v-if="turning" class="chip" :style="{ transform: `translateX(-50%) rotate(${-turn}deg)` }" aria-hidden="true">{{ said }}</span>
    <span v-for="h in handles" :key="h" class="handle" :data-handle="h" :style="styleOf(h)" @pointerdown="emit('handle', $event, h)" />
  </div>
</template>

<style scoped>
.frame {
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.handle {
  position: absolute;
  width: 11px;
  height: 11px;
  margin: -6px 0 0 -6px;
  background: #fff;
  border: 2px solid var(--iris);
  border-radius: 3px;
  pointer-events: auto;
}
/* The turn handle (D1024): 19 px to see on a stem, in a 32 px square to hit; the stem and the angle chip turn with the object. */
.stem {
  position: absolute;
  left: 50%;
  top: -22px;
  width: 2px;
  height: 22px;
  margin-left: -1px;
  background: var(--iris);
}
.turn {
  position: absolute;
  left: 50%;
  top: -54px;
  width: 32px;
  height: 32px;
  margin-left: -16px;
  display: grid;
  place-items: center;
  cursor: grab;
  pointer-events: auto;
  border-radius: 50%;
}
.turn::before {
  content: '';
  width: 19px;
  height: 19px;
  box-sizing: border-box;
  border-radius: 50%;
  background: #fff;
  border: 2px solid var(--iris);
}
.below .stem {
  top: auto;
  bottom: -22px;
}
.below .turn {
  top: auto;
  bottom: -54px;
}
.below .chip {
  top: auto;
  bottom: -88px;
}
.turn:focus-visible {
  outline: 3px solid var(--iris);
  outline-offset: 1px;
}
.chip {
  position: absolute;
  left: 50%;
  top: -88px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--ink);
  color: var(--paper);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  pointer-events: none;
}
</style>
