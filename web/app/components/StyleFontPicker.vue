<script setup lang="ts">
// The font of a style: a list in which every name is set in its own font, and a field for any other family the
// reader's computer may have.
import { computed, ref, watch } from 'vue'
import { FONTS, choiceOf } from '~/lib/fonts'
import { familyName, type Css } from '~/lib/style-css'

const props = defineProps<{ look: Css; own: boolean; disabled?: boolean }>()
const emit = defineEmits<{ pick: [family: string]; reset: [] }>()

const open = ref(false)
const name = computed(() => familyName(props.look) || 'Font')
const typed = ref('')
const current = computed(() => choiceOf(props.look))
watch(open, (o) => o && (typed.value = ''))

function pick(family: string) {
  emit('pick', family)
  open.value = false
}
</script>

<template>
  <div class="font" data-testid="font-picker">
    <button class="font-btn" type="button" :disabled="disabled" aria-haspopup="listbox" :aria-expanded="open" title="Font" @click="open = !open">
      <span :style="{ fontFamily: look['font-family'] }">{{ name }}</span
      ><span class="caret">▾</span>
    </button>
    <div v-if="open" class="drop">
      <ul role="listbox" aria-label="Fonts">
        <li v-for="f in FONTS" :key="f.name" role="option" :aria-selected="current?.name === f.name">
          <button type="button" :class="{ on: current?.name === f.name }" :style="{ fontFamily: f.stack }" :data-font="f.name" @click="pick(f.name)">{{ f.name }}</button>
        </li>
      </ul>
      <form class="other" @submit.prevent="typed.trim() && pick(typed)">
        <input v-model="typed" placeholder="Another font…" aria-label="Another font" spellcheck="false" >
      </form>
      <button v-if="own" class="reset" type="button" @click="emit('reset'); open = false">Follow the parent style again</button>
    </div>
  </div>
</template>

<style scoped>
.font {
  position: relative;
  flex: 1;
  min-width: 0;
}
.font-btn {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  background: var(--surface);
}
.font-btn:hover:not(:disabled) {
  border-color: var(--app);
}
.font-btn span:first-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.caret {
  color: var(--muted);
  font-size: 10px;
}
.drop {
  margin-top: 6px;
  display: grid;
  gap: 6px;
  padding: 6px;
  border: 1px solid var(--line-field); /* a floating panel's own edge, not a divider — same fix as Modal.vue */
  border-radius: 10px;
  background: var(--surface);
}
ul {
  margin: 0;
  padding: 0;
  list-style: none;
  max-height: 210px;
  overflow-y: auto;
}
li button {
  width: 100%;
  padding: 5px 8px;
  border: 0;
  border-radius: 6px;
  background: none;
  text-align: left;
  font-size: 15px;
}
li button:hover {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
li button.on {
  background: color-mix(in srgb, var(--app) 14%, transparent);
}
.other input {
  width: 100%;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
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
