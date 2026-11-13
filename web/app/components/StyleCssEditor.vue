<script setup lang="ts">
// The same style as plain CSS (D73): what the style sets itself, one declaration per line. The server reads it, so what
// is wrong is shown at once with its line; nothing is sent until it is right. The lines below say where the rest comes from.
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { formatCss, provenance, type CssCheck, type StyleView } from '~/lib/style-css'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  current: StyleView
  styles: StyleView[]
  /** CSS in this editor goes to a new style of its own, or into this one. */
  scope: 'new' | 'every'
  readOnly?: boolean
  check: (text: string) => Promise<CssCheck | null>
}>()
const emit = defineEmits<{ apply: [text: string] }>()

const base = computed(() => (props.scope === 'every' ? formatCss(props.current.css) : ''))
const text = ref(base.value)
const answer = ref<CssCheck | null>(null)
let timer: ReturnType<typeof setTimeout> | undefined
let asked = 0

// What the person is editing starts again when the style (or where the change goes) is another.
watch(
  () => [props.current.id, props.scope],
  () => {
    text.value = base.value
    answer.value = null
  },
)
// The style changed under us (a colleague, or the controls): follow it as long as the person has not written anything.
watch(base, (now, was) => {
  if (text.value === was) text.value = now
})

watch(text, (t) => {
  clearTimeout(timer)
  const turn = ++asked
  timer = setTimeout(async () => {
    const result = await props.check(t)
    if (turn === asked) answer.value = result
  }, 200)
})
onBeforeUnmount(() => clearTimeout(timer))

const problems = computed(() => (text.value.trim() === '' ? [] : answer.value?.problems ?? []))
const changed = computed(() => text.value.trim() !== base.value.trim())
const ok = computed(() => changed.value && !props.readOnly && problems.value.length === 0 && (props.scope === 'every' || text.value.trim() !== ''))
const inherited = computed(() => provenance(props.styles, props.current.id).filter((p) => p.inherited))
const nameOf = (id: string) => props.styles.find((s) => s.id === id)?.name ?? id

function apply() {
  if (ok.value) emit('apply', text.value)
}
</script>

<template>
  <div class="css" data-testid="css-view">
    <p class="hint">
      <template v-if="scope === 'every'">{{ t('What “{name}” sets itself. The rest comes from its parent.', { name: current.name }) }}</template>
      <template v-else>{{ t('CSS for this text only. It is added to “{name}”, in a new style.', { name: current.name }) }}</template>
    </p>
    <textarea
      v-model="text"
      class="mono"
      rows="7"
      spellcheck="false"
      autocapitalize="off"
      autocomplete="off"
      :aria-label="t('CSS of the style')"
      :readonly="readOnly"
      :placeholder="scope === 'new' ? 'color: #5b4bc4;\nfont-weight: bold;' : ''"
      @keydown.ctrl.enter.prevent="apply"
      @keydown.meta.enter.prevent="apply"
    />
    <ul v-if="problems.length" class="problems" role="alert">
      <li v-for="(p, i) in problems" :key="i">
        {{ p.message }}
      </li>
    </ul>
    <div class="actions">
      <button class="btn primary" type="button" :disabled="!ok" data-testid="css-apply" @click="apply">{{ t('Apply') }}</button>
      <span class="keys mono">{{ t('Ctrl+Enter') }}</span>
    </div>
    <details v-if="inherited.length" class="from">
      <summary>{{ t('From the styles it is based on') }}</summary>
      <ul>
        <li v-for="p in inherited" :key="p.property" class="mono">
          {{ p.property }}: {{ p.value }}; <span>{{ nameOf(p.from) }}</span>
        </li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.css {
  display: grid;
  gap: 8px;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  font-size: 12.5px;
  line-height: 1.55;
  resize: vertical;
  background: color-mix(in srgb, var(--mist) 28%, white);
  color: var(--ink); /* mixed with literal white, so this background stays light in dark mode too */
  tab-size: 2;
}
textarea:focus {
  outline: 2px solid color-mix(in srgb, var(--app) 40%, transparent);
  border-color: var(--app);
}
.problems {
  margin: 0;
  padding: 7px 10px;
  list-style: none;
  border-radius: 8px;
  background: color-mix(in srgb, var(--rose) 9%, white);
  color: #8f2450;
  font-size: 12px;
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.keys {
  font-size: 11px;
  color: var(--muted);
}
.from {
  font-size: 12px;
  color: var(--muted);
}
.from summary {
  cursor: pointer;
}
.from ul {
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 2px;
}
.from li span {
  color: var(--app-text); /* --app-dark as literal text fails contrast in dark mode — the owner's 2026-11-06 report */
  font-family: var(--font-ui);
}
</style>
