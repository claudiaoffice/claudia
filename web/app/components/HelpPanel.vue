<script setup lang="ts">
// The Help tab (E13.5): one search box over two kinds of help — the function catalog ("Documentation", E13.6,
// computes only) and the "how do I" topics (E13.1/E13.3, every app). A third kind, the AI assistant, already
// exists as the chat on the other tab (Help ▸ "Ask ai" opens it directly) and is not duplicated here.
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from '~/lib/i18n'
import type { BaseSession, HelpTopic, HelpTopicSummary } from '~/lib/base-session'
import type { FunctionHelp, FunctionSummary } from '~/lib/session'

// `t` stays this bare for the same reason SidePanel.vue's does: `scripts/extract_i18n.py` only recognises an
// unqualified `t(...)` call.
const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()

/** Not every app's session has a function catalog (today only computes does, E13.6) — checked at runtime rather
 * than typed, so this component stays the one Help tab every app's SidePanel mounts, composes and creates
 * included, each simply showing one section fewer until they have their own cell-function-like extension point. */
const hasFunctions = computed(() => typeof (props.session as { listFunctions?: unknown }).listFunctions === 'function')

const query = ref('')
const searchBox = ref<HTMLInputElement | null>(null)
const functions = ref<FunctionSummary[]>([])
const topics = ref<HelpTopicSummary[]>([])
const open = ref<{ kind: 'function'; data: FunctionHelp } | { kind: 'topic'; data: HelpTopic } | null>(null)
const loading = ref(false)

let generation = 0
async function runSearch() {
  const mine = ++generation
  loading.value = true
  const [found, topicsFound] = await Promise.all([
    hasFunctions.value ? (props.session as unknown as { listFunctions(q: string): Promise<FunctionSummary[] | false> }).listFunctions(query.value) : Promise.resolve([]),
    props.session.helpSearch(query.value),
  ])
  if (mine !== generation) return // a newer search started before this one answered; drop the stale result
  functions.value = found === false ? [] : found
  topics.value = topicsFound === false ? [] : topicsFound
  loading.value = false
}
watch(query, runSearch)
runSearch()

async function openFunction(name: string) {
  const found = await (props.session as unknown as { functionHelp(name: string): Promise<FunctionHelp | false> }).functionHelp(name)
  if (found !== false) open.value = { kind: 'function', data: found }
}
async function openTopic(id: string) {
  const found = await props.session.helpTopic(id)
  if (found !== false) open.value = { kind: 'topic', data: found }
}
function back() {
  open.value = null
}

/** Help ▸ "How do I…?" / "Documentation" (SidePanel's `openHelp`): focus the search box; `mode` scrolls the
 * matching section into view, so either menu item lands somewhere sensible even before anything is typed. */
const docsSection = ref<HTMLElement | null>(null)
const howToSection = ref<HTMLElement | null>(null)
function focus(mode?: 'how-to' | 'docs') {
  open.value = null
  nextTick(() => {
    searchBox.value?.focus()
    const target = mode === 'docs' ? docsSection.value : mode === 'how-to' ? howToSection.value : null
    target?.scrollIntoView({ block: 'nearest' })
  })
}
defineExpose({ focus })
</script>

<template>
  <div class="help">
    <div class="searchRow">
      <svg class="icon" viewBox="0 0 20 20" width="15" height="15" aria-hidden="true"><circle cx="9" cy="9" r="6.5" fill="none" stroke="currentColor" stroke-width="1.6" /><path d="M14 14l4.5 4.5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
      <input ref="searchBox" v-model="query" type="search" :placeholder="t('Search help…')" aria-label="search help" >
    </div>

    <div v-if="open" class="topic">
      <button type="button" class="back" @click="back">← {{ t('Back to results') }}</button>
      <template v-if="open.kind === 'function'">
        <h3 class="mono">{{ open.data.signature }}</h3>
        <pre class="body">{{ open.data.help }}</pre>
      </template>
      <template v-else>
        <h3>{{ open.data.title }}</h3>
        <p v-if="open.data.tags.length" class="tags">{{ open.data.tags.join(' · ') }}</p>
        <pre class="body">{{ open.data.body }}</pre>
      </template>
    </div>

    <div v-else class="results">
      <section v-if="hasFunctions" ref="docsSection">
        <h2>{{ t('Documentation') }} <span class="count">{{ functions.length }}</span></h2>
        <ul v-if="functions.length" class="list">
          <li v-for="fn in functions" :key="fn.name">
            <button type="button" @click="openFunction(fn.name)">
              <span class="name mono">{{ fn.name }}</span>
              <span class="tooltip">{{ fn.tooltip }}</span>
            </button>
          </li>
        </ul>
        <p v-else-if="!loading" class="empty">No function matches "{{ query }}".</p>
      </section>

      <section ref="howToSection">
        <h2>{{ t('How do I…?') }} <span class="count">{{ topics.length }}</span></h2>
        <ul v-if="topics.length" class="list">
          <li v-for="topic in topics" :key="topic.id">
            <button type="button" @click="openTopic(topic.id)">
              <span class="name">{{ topic.title }}</span>
              <span v-if="topic.tags.length" class="tooltip">{{ topic.tags.join(' · ') }}</span>
            </button>
          </li>
        </ul>
        <p v-else-if="!loading" class="empty">No guide matches "{{ query }}".</p>
      </section>

      <p class="askHint">{{ t('Not finding it? Say') }} <b>@ai</b> {{ t('in the chat.') }}</p>
    </div>
  </div>
</template>

<style scoped>
.help {
  display: flex;
  flex-direction: column;
  min-height: 0;
  flex: 1 1 auto;
  padding: 10px 14px 12px;
}
.searchRow {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 0 auto;
  border: 1px solid rgb(231 225 244 / 22%);
  border-radius: 999px;
  background: rgb(255 255 255 / 6%);
  padding: 6px 12px;
  margin-bottom: 10px;
  color: rgb(230 224 245 / 70%);
}
.searchRow input {
  flex: 1;
  min-width: 0;
  background: transparent;
  color: #fff;
  font-size: 13px;
}
.searchRow input::placeholder {
  color: rgb(230 224 245 / 45%);
}
.results {
  overflow: auto;
  flex: 1;
  min-height: 0;
}
section + section {
  margin-top: 14px;
}
h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 6px;
  font: 500 11px var(--font-ui);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgb(230 224 245 / 62%);
}
.count {
  font-family: var(--font-mono);
  letter-spacing: 0;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.list button {
  display: flex;
  flex-direction: column;
  width: 100%;
  text-align: left;
  gap: 2px;
  padding: 6px 8px;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
}
.list button:hover {
  background: rgb(255 255 255 / 7%);
}
.list .name {
  font-size: 13px;
  color: #fff;
}
.list .tooltip {
  font-size: 11px;
  color: rgb(230 224 245 / 55%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty,
.askHint {
  font-size: 12px;
  color: rgb(230 224 245 / 50%);
  margin: 2px 0 0;
}
.askHint {
  margin-top: 16px;
}
.topic {
  overflow: auto;
  flex: 1;
  min-height: 0;
}
.back {
  background: none;
  color: var(--apricot);
  font-size: 11.5px;
  padding: 0 0 10px;
  cursor: pointer;
}
.topic h3 {
  margin: 0 0 6px;
  font-size: 14px;
  color: #fff;
}
.topic .tags {
  margin: 0 0 8px;
  font-size: 11px;
  color: rgb(230 224 245 / 55%);
}
.topic .body {
  font-family: var(--font-ui);
  font-size: 12.5px;
  line-height: 1.55;
  color: rgb(230 224 245 / 90%);
  white-space: pre-wrap;
  margin: 0;
}
</style>
