<script setup lang="ts">
// All the styles of the document: what each is for, how often it is used, and a way to name the ones that were made by
// deviating and still carry the name they were given (E9.8).
import { computed, ref } from 'vue'
import { previewCss } from '~/lib/style-css'
import type { StyleHost } from '~/lib/style-host'

const props = defineProps<{ host: StyleHost }>()
const emit = defineEmits<{ close: [] }>()

const onlyUnnamed = ref(false)
const uses = computed(() => props.host.uses())
const unnamed = computed(() => props.host.styles.filter((s) => s.to_name).length)
const shown = computed(() => props.host.styles.filter((s) => !onlyUnnamed.value || s.to_name))
const editing = ref<string | null>(null)
const typed = ref('')

function edit(id: string, name: string) {
  editing.value = id
  typed.value = name
}
async function save(id: string) {
  const name = typed.value.trim()
  if (name && (await props.host.rename(id, name))) editing.value = null
}
</script>

<template>
  <Modal title="Styles" :width="520" @close="emit('close')">
    <label v-if="unnamed" class="filter"><input v-model="onlyUnnamed" type="checkbox" > Only the {{ unnamed }} waiting for a name</label>
    <ul class="list" data-testid="styles-list">
      <li v-for="s in shown" :key="s.id" :data-style="s.id">
        <div class="sample" :style="previewCss(s.resolved)">{{ s.name }}</div>
        <form v-if="editing === s.id" class="rename" @submit.prevent="save(s.id)" @keydown.esc.stop="editing = null">
          <input v-model="typed" :aria-label="`New name of ${s.name}`" autofocus autocomplete="off" >
          <button class="btn primary" type="submit" :disabled="!typed.trim()">Save</button>
        </form>
        <div v-else class="meta">
          <span v-if="s.to_name" class="flag">to name</span>
          <span v-else-if="s.purpose" class="purpose">{{ s.purpose }}</span>
          <span class="count mono">{{ uses[s.id] ?? 0 }} {{ (uses[s.id] ?? 0) === 1 ? host.noun : `${host.noun}s` }}</span>
          <button v-if="!host.readOnly" type="button" class="link" :data-rename="s.id" @click="edit(s.id, s.to_name ? '' : s.name)">{{ s.to_name ? 'Name it' : 'Rename' }}</button>
        </div>
      </li>
    </ul>
    <div class="buttons"><button class="btn" type="button" @click="emit('close')">Close</button></div>
  </Modal>
</template>

<style scoped>
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
.list li:hover {
  background: color-mix(in srgb, var(--mist) 50%, transparent);
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
.link {
  margin-left: auto;
  border: 0;
  background: none;
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  cursor: pointer;
}
.link:hover {
  text-decoration: underline;
}
.buttons {
  display: flex;
  justify-content: flex-end;
}
</style>
