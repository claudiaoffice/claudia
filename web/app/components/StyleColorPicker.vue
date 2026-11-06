<script setup lang="ts">
// A colour for one CSS property: the suite's colours, a hex field, and the system's picker for anything else.
import { computed, ref, watch } from 'vue'
import { SWATCHES } from '~/lib/palette'
import { toHex } from '~/lib/style-css'

const props = defineProps<{ label: string; value: string | undefined; own: boolean; disabled?: boolean }>()
const emit = defineEmits<{ pick: [color: string]; reset: [] }>()

const open = ref(false)
const hex = computed(() => toHex(props.value))
const typed = ref(hex.value ?? '')
watch(hex, (h) => (typed.value = h ?? props.value ?? ''))

const valid = computed(() => /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(typed.value.trim()))
function commit() {
  if (valid.value) emit('pick', typed.value.trim())
}
function pick(color: string) {
  emit('pick', color)
}
</script>

<template>
  <div class="colour" :data-testid="`colour-${label.toLowerCase().replace(/\s/g, '-')}`">
    <button class="swatch-btn" type="button" :disabled="disabled" :aria-expanded="open" :aria-label="`${label}: ${value ?? 'none'}`" :title="label" @click="open = !open">
      <i :style="{ background: value && value !== 'none' ? value : 'transparent' }" :class="{ empty: !value || value === 'transparent' }" />
      <span>{{ label }}</span>
    </button>
    <div v-if="open" class="drop">
      <div class="grid">
        <button v-for="s in SWATCHES" :key="s.value" type="button" class="chip" :class="{ on: hex?.toLowerCase() === s.value.toLowerCase() }" :title="s.name" :aria-label="s.name" :style="{ background: s.value }" @click="pick(s.value)" />
      </div>
      <div class="row">
        <input v-model="typed" class="hex mono" spellcheck="false" :aria-label="`${label} as hex`" placeholder="#5b4bc4" @keydown.enter.prevent="commit" @blur="commit" />
        <input type="color" class="system" :value="hex ?? '#000000'" :aria-label="`${label}, system picker`" @change="pick(($event.target as HTMLInputElement).value)" />
      </div>
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
  border-radius: 5px;
  box-shadow: inset 0 0 0 1px rgb(31 26 51 / 22%);
}
.swatch-btn i.empty {
  background: repeating-linear-gradient(45deg, #fff 0 3px, var(--mist) 3px 6px) !important;
}
.drop {
  margin-top: 6px;
  padding: 10px;
  display: grid;
  gap: 10px;
  border: 1px solid var(--line-field); /* a floating panel's own edge, not a divider — same fix as Modal.vue */
  border-radius: 10px;
  background: var(--surface);
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
