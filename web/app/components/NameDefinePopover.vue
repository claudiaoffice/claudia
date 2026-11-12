<script setup lang="ts">
// Naming the selected cells (E6.5, mock 1): what the Name Box opens when a new word is typed with cells selected, and
// when the word is a name that already exists and more than its own cell is selected (then it moves the name).
// A first row of text defaults to a header — that makes the cells a table, which grows with its last row.
import { computed, onMounted, ref } from 'vue'
import { draftOf, nameProblem, PURPOSES, type NameDraft, type NameInfo, type NameRegion, type Purpose } from '~/lib/names'

const props = defineProps<{
  x: number
  y: number
  name: string
  /** The name this moves, when the typed word was one that exists. */
  existing: NameInfo | null
  region: NameRegion
  /** `Data!A1:D4`, to say what is being named. */
  refersTo: string
  sheetName: string
  /** The sheet the name is scoped to when "this sheet only" is chosen. */
  sheet: string
  headerGuess: boolean
  taken: (name: string, scope: string | null) => boolean
}>()
const emit = defineEmits<{ define: [draft: NameDraft]; close: [] }>()

const name = ref(props.name)
const header = ref(props.existing?.header ?? props.headerGuess)
const grows = ref(props.existing?.grows ?? true)
const purpose = ref<Purpose>(props.existing?.purpose ?? 'data')
const onlyHere = ref(props.existing ? props.existing.scope !== null : false)
const field = ref<HTMLInputElement | null>(null)
onMounted(() => field.value?.select())

const scope = computed(() => (onlyHere.value ? props.sheet : null))
const problem = computed(() => nameProblem(name.value.trim()))
const replaces = computed(() => !problem.value && props.taken(name.value.trim(), scope.value) && name.value.trim().toLowerCase() !== props.existing?.name.toLowerCase())

function submit() {
  if (problem.value) return
  emit('define', draftOf({ name: name.value, scope: scope.value, region: props.region, header: header.value, grows: grows.value, purpose: purpose.value }))
}
</script>

<template>
  <Popover :x="x" :y="y" :width="340" :label="existing ? `move ${existing.name}` : 'name these cells'" @close="emit('close')">
    <form class="define" data-testid="name-define" @submit.prevent="submit">
      <h3>{{ existing ? `Move “${existing.name}” here` : 'Name these cells' }}</h3>
      <label class="field">
        Name
        <input ref="field" v-model="name" class="mono" autocomplete="off" spellcheck="false" aria-label="name" >
      </label>
      <p v-if="problem" class="problem" role="alert">{{ problem }}</p>
      <p v-else-if="replaces" class="problem soft" role="status">A name like this exists already and will point here.</p>
      <p class="refers">Refers to <span class="mono">{{ refersTo }}</span></p>
      <label class="check"><input v-model="header" type="checkbox" ><span>First row is a header <small>— a table: <span class="mono">{{ name.trim() || 'Name' }}[Column]</span>, <span class="mono">FROM {{ name.trim() || 'Name' }}</span></small></span></label>
      <label class="check" :class="{ off: !header }"><input v-model="grows" type="checkbox" :disabled="!header" ><span>Grows with its last row</span></label>
      <fieldset class="purpose">
        <legend>Cells are</legend>
        <label v-for="p in PURPOSES.filter((q) => q.value !== 'result')" :key="p.value" class="pill" :class="{ on: purpose === p.value }">
          <input v-model="purpose" type="radio" :value="p.value" ><span class="swatch" :style="{ background: `var(--purpose-${p.value})` }" />{{ p.label }}
        </label>
      </fieldset>
      <label class="check"><input v-model="onlyHere" type="checkbox" ><span>Only on {{ sheetName }} <small>— other sheets can have a name of their own</small></span></label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="problem !== null">{{ existing ? 'Move name' : 'Define' }}</button>
        <button class="btn" type="button" @click="emit('close')">Cancel</button>
      </div>
    </form>
  </Popover>
</template>

<style scoped>
.define {
  display: grid;
  gap: 10px;
  padding: 8px 10px 10px;
}
h3 {
  margin: 0;
  font: 500 17px var(--font-display);
}
.refers {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.problem {
  margin: -4px 0 0;
  color: var(--danger-dark, var(--rose));
  font-size: 12px;
}
.problem.soft {
  color: var(--muted);
}
.check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-weight: normal;
  font-size: 13px;
}
.check input {
  flex: none;
  width: auto;
  margin-top: 3px;
}
.check span {
  flex: 1;
  min-width: 0;
}
.check.off {
  color: var(--muted);
}
small {
  color: var(--muted);
  font-size: 11px;
}
fieldset.purpose {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  border: 0;
  margin: 0;
  padding: 0;
}
fieldset.purpose legend {
  font-size: 13px;
  padding: 0;
  margin-bottom: 4px;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 9px;
  border: 1px solid var(--line-field);
  border-radius: 999px;
  font-size: 12px;
  font-weight: normal;
  cursor: pointer;
}
.pill.on {
  border-color: var(--app);
  box-shadow: 0 0 0 1px var(--app);
}
.pill input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}
.swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid var(--line-field);
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
