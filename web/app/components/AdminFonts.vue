<script setup lang="ts">
// Server settings ▸ Fonts (E3.13 f, D1041; board `notes/mockups/fonts-1-server-settings.svg`): the fonts every document
// on this server is laid out, shown and printed with. Collections as cards (the starter set as one), the families with
// what each stands in for, and every font the server does not use, with the reason in words. Add fonts… is a dialog
// (`AddFontsDialog.vue`); renaming and removing a collection added here are its card's own menu. The page has no
// Apply: each change is its own confirmed step, and the server answers with the whole page again.
import { computed, onMounted, ref } from 'vue'
import { adminApi, AdminApiError } from '~/lib/admin-api'
import {
  collectionMeta,
  collectionSummary,
  familyRows,
  filterCounts,
  loadPreview,
  previewStyle,
  problemText,
  stylesLabel,
  type FamilyFilter,
  type FontCollectionView,
  type FontsPage,
} from '~/lib/admin-fonts'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ token: string; server: string }>()

const page = ref<FontsPage | null>(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const filter = ref<FamilyFilter>('all')
const query = ref('')
const adding = ref(false)
const renaming = ref<FontCollectionView | null>(null)
const removing = ref<FontCollectionView | null>(null)
const menuFor = ref<string | null>(null)
const faces = ref<Record<string, string>>({})

const rows = computed(() => (page.value ? familyRows(page.value, filter.value, query.value) : []))
const counts = computed(() => (page.value ? filterCounts(page.value) : { all: 0, 'stand-ins': 0, 'not-usable': 0 }))
const filters = computed<{ id: FamilyFilter; label: string }[]>(() => [
  { id: 'all', label: t('All {n}', { n: counts.value.all }) },
  { id: 'stand-ins', label: t('Stand-ins {n}', { n: counts.value['stand-ins'] }) },
  { id: 'not-usable', label: t('Not usable {n}', { n: counts.value['not-usable'] }) },
])
const summaryLine = computed(() => {
  const c = page.value?.counts
  if (!c) return ''
  const families = c.families === 1 ? t('1 family') : t('{n} families', { n: c.families })
  const files = c.files === 1 ? t('1 file') : t('{n} files', { n: c.files })
  const collections = c.collections === 1 ? t('1 collection') : t('{n} collections', { n: c.collections })
  return `${families} · ${files} · ${collections}`
})
/** The families that stand in for an office font, for the sentence under the table. */
const sameWidths = computed(() =>
  (page.value?.families ?? []).filter((f) => f.stands_in_for.some((n) => !['serif', 'sans-serif', 'monospace'].includes(n))).map((f) => f.family),
)

function show(next: FontsPage) {
  page.value = next
  for (const family of next.families) {
    const style = previewStyle(family)
    if (!style || faces.value[family.family]) continue
    void loadPreview(style.sha256, props.token).then((face) => {
      if (face) faces.value = { ...faces.value, [family.family]: face }
    })
  }
}

async function run(step: () => Promise<FontsPage>, done = '') {
  error.value = ''
  notice.value = ''
  try {
    show(await step())
    notice.value = done
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
  }
}

onMounted(async () => {
  await run(() => adminApi.fontsPage(props.token))
  loading.value = false
})

function added(next: FontsPage) {
  adding.value = false
  show(next)
  notice.value = t('Fonts added. Documents laid out from now on use them, and so do LaTeX formulas.')
}

async function rename(name: string) {
  const target = renaming.value
  renaming.value = null
  if (target) await run(() => adminApi.renameFontCollection(props.token, target.id, name), t('Collection renamed.'))
}

async function remove() {
  const target = removing.value
  removing.value = null
  if (target) await run(() => adminApi.removeFontCollection(props.token, target.id), t('Collection removed.'))
}

function toggleMenu(id: string) {
  menuFor.value = menuFor.value === id ? null : id
}

function menuKey(event: KeyboardEvent) {
  if (event.key === 'Escape') menuFor.value = null
}
</script>

<template>
  <div v-if="!loading && page" class="fonts-page" @keydown="menuKey">
    <div class="head">
      <h1>{{ t('Fonts') }}</h1>
      <button class="btn primary" type="button" :disabled="!page.can_add" :title="page.can_add ? '' : t('This server has no folder to add fonts to.')" @click="adding = true">
        {{ t('Add fonts…') }}
      </button>
    </div>
    <p class="lead">{{ t('The fonts every document on this server is laid out, shown and printed with.') }}</p>

    <p class="summary">
      <span>{{ summaryLine }}</span>
      <button v-if="page.counts.not_usable" type="button" class="pill bad" @click="filter = 'not-usable'">
        {{ page.counts.not_usable === 1 ? t('1 file not usable') : t('{n} files not usable', { n: page.counts.not_usable }) }}
      </button>
    </p>
    <div role="status">
      <p v-if="notice" class="notice">{{ notice }}</p>
    </div>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <h2>{{ t('Collections') }}</h2>
    <ul class="cards">
      <li v-for="c in page.collections" :key="c.id" class="card">
        <div class="card-head">
          <h3>{{ c.name }}</h3>
          <div v-if="c.editable" class="menu-holder">
            <button type="button" class="more" :aria-label="t('More for {name}', { name: c.name })" aria-haspopup="menu" :aria-expanded="menuFor === c.id" @click="toggleMenu(c.id)">⋯</button>
            <ul v-if="menuFor === c.id" class="menu" role="menu">
              <li role="none"><button type="button" role="menuitem" @click="((menuFor = null), (renaming = c))">{{ t('Rename…') }}</button></li>
              <li role="none"><button type="button" role="menuitem" class="danger" @click="((menuFor = null), (removing = c))">{{ t('Remove collection…') }}</button></li>
            </ul>
          </div>
        </div>
        <p class="card-sub">{{ collectionSummary(c, t) }}</p>
        <MayGoBadge :may-go="c.may_go" />
        <p class="card-meta">{{ collectionMeta(c, t) }}</p>
      </li>
    </ul>

    <div class="families-head">
      <h2 id="families-title">{{ t('Families') }}</h2>
      <div class="filters" role="group" :aria-label="t('Show')">
        <button v-for="f in filters" :key="f.id" type="button" class="filter" :class="[f.id, { on: filter === f.id, some: counts[f.id] > 0 }]" :aria-pressed="filter === f.id" @click="filter = f.id">
          {{ f.label }}
        </button>
      </div>
    </div>
    <label class="search">
      <span class="sr-only">{{ t('Search families') }}</span>
      <input v-model="query" type="search" :placeholder="t('Search families…')" >
    </label>

    <table aria-labelledby="families-title">
      <thead>
        <tr>
          <th scope="col">{{ t('Family') }}</th>
          <th scope="col">{{ t('Font styles') }}</th>
          <th scope="col">{{ t('Collection') }}</th>
          <th scope="col">{{ t('May go') }}</th>
          <th scope="col">{{ t('Stands in for') }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in rows" :key="row.kind === 'family' ? row.family.family : row.problem.file">
          <template v-if="row.kind === 'family'">
            <tr :class="{ troubled: row.family.problems.length }">
              <th scope="row" class="family" :style="faces[row.family.family] ? { fontFamily: `'${faces[row.family.family]}', var(--font-ui)` } : undefined">{{ row.family.family }}</th>
              <td class="muted">{{ stylesLabel(row.family, t) }}</td>
              <td>{{ row.family.collection }}</td>
              <td><MayGoBadge :may-go="row.family.may_go" /></td>
              <td>{{ row.family.stands_in_for.join(', ') || '—' }}</td>
            </tr>
            <tr v-for="p in row.family.problems" :key="p.file" class="problem-row">
              <td colspan="5"><span aria-hidden="true">⚠ </span>{{ problemText(p, t) }}</td>
            </tr>
          </template>
          <tr v-else class="problem-row file">
            <th scope="row" class="mono">{{ row.problem.file }}</th>
            <td colspan="4"><span aria-hidden="true">⚠ </span>{{ problemText(row.problem, t) }}</td>
          </tr>
        </template>
        <tr v-if="!rows.length">
          <td colspan="5" class="muted">{{ t('No family matches.') }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="sameWidths.length" class="hint">
      {{ t('A stand-in is used when a document asks for a family this server lacks. {fonts} have the same widths as the fonts they stand in for, so lines and pages break as in the original.', { fonts: sameWidths.join(', ') }) }}
    </p>

    <AddFontsDialog v-if="adding" :token="token" :server="server" :access-secret-set="page.access_secret_set" :limits="page.limits" @close="adding = false" @added="added" />
    <PromptDialog v-if="renaming" :title="t('Rename collection')" :label="t('Name')" :ok="t('Rename')" :initial="renaming.name" required @ok="rename" @close="renaming = null" />
    <Modal v-if="removing" :title="t('Remove collection')" @close="removing = null">
      <p class="warning">
        {{ t('This removes {collection} from {server}, with its families: {families}. Documents that ask for them are shown with a stand-in from now on. The files are deleted from the server; there is no undo.', { collection: removing.name, server, families: removing.families.join(', ') }) }}
      </p>
      <div class="buttons">
        <button class="btn danger" type="button" @click="remove">{{ t('Remove collection') }}</button>
        <button class="btn" type="button" @click="removing = null">{{ t('Cancel') }}</button>
      </div>
    </Modal>
  </div>
  <p v-else-if="error" class="error" role="alert">{{ error }}</p>
</template>

<style scoped>
/* Text in a status colour, readable on the page in both themes (4.5:1, BITV): the colour mixed with the text colour,
 * which darkens it on a light page and lightens it on a dark one. */
.fonts-page {
  --ok-text: color-mix(in srgb, var(--teal) 72%, var(--text));
  --bad-text: color-mix(in srgb, var(--rose) 72%, var(--text));
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
h1 {
  margin: 0 0 4px;
  font: 500 23px/1.3 var(--font-display);
}
h2 {
  margin: 22px 0 10px;
  font: 500 17px var(--font-display);
}
.lead {
  margin: 0 0 14px;
  font-size: 13.5px;
  color: var(--muted);
}
.summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 6px;
  font-size: 13.5px;
}
.pill {
  border: none;
  border-radius: 999px;
  padding: 3px 10px;
  font: 12.5px var(--font-ui);
  cursor: pointer;
}
.pill.bad,
.filter.not-usable.some {
  background: color-mix(in srgb, var(--rose) 14%, transparent);
  color: var(--bad-text);
}
.notice {
  margin: 8px 0;
  font-size: 13px;
  color: var(--ok-text);
}
.error {
  margin: 8px 0;
  font-size: 13px;
  color: var(--bad-text);
}
.cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.card {
  border: 1px solid var(--line-field);
  border-radius: 12px;
  background: var(--surface);
  padding: 14px 16px;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
h3 {
  margin: 0;
  font: 600 14.5px var(--font-ui);
}
.card-sub {
  margin: 3px 0 8px;
  font-size: 12.5px;
  color: var(--muted);
}
.card :deep(.badge) {
  margin-top: 2px;
}
.card-meta {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: var(--muted);
}
.menu-holder {
  position: relative;
}
.more {
  border: none;
  background: transparent;
  color: var(--muted);
  font-size: 18px;
  line-height: 1;
  padding: 0 4px;
  border-radius: 6px;
  cursor: pointer;
}
.more:hover,
.more:focus-visible {
  background: var(--line);
}
.menu {
  position: absolute;
  right: 0;
  top: 24px;
  z-index: 2;
  list-style: none;
  margin: 0;
  padding: 4px;
  min-width: 190px;
  background: var(--surface);
  border: 1px solid var(--line-field);
  border-radius: 10px;
  box-shadow: var(--shadow);
}
.menu button {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  padding: 7px 10px;
  border-radius: 6px;
  font: 13px var(--font-ui);
  color: var(--text);
  cursor: pointer;
}
.menu button:hover,
.menu button:focus-visible {
  background: var(--line);
}
.menu .danger {
  color: var(--bad-text);
}
.families-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.filters {
  display: flex;
  gap: 6px;
}
.filter {
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 4px 11px;
  background: transparent;
  font: 12.5px var(--font-ui);
  color: var(--text);
  cursor: pointer;
}
.filter.on {
  background: var(--ink);
  color: var(--paper);
}
.filter.not-usable.on {
  background: var(--rose);
  color: #fff;
}
.search input {
  display: block;
  width: 100%;
  margin: 4px 0 12px;
  padding: 9px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 13px var(--font-ui);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
thead th {
  text-align: left;
  font: 600 11px var(--font-ui);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
  background: color-mix(in srgb, var(--line) 60%, transparent);
  padding: 9px 12px;
}
tbody th,
tbody td {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}
.family {
  font: 400 17px var(--font-ui);
}
.muted {
  color: var(--muted);
}
.mono {
  font: 12.5px var(--font-mono);
}
tr.troubled > *,
.problem-row > * {
  background: color-mix(in srgb, var(--rose) 5%, transparent);
}
tr.troubled > * {
  border-bottom: none;
}
.problem-row td {
  color: var(--bad-text);
  font-size: 12.5px;
  padding-top: 0;
}
.problem-row.file td,
.problem-row.file th {
  padding-top: 10px;
}
.hint {
  margin: 12px 0 0;
  font-size: 12.5px;
  color: var(--muted);
}
.warning {
  margin: 0;
}
.buttons {
  display: flex;
  gap: 10px;
}
.btn.danger {
  background: var(--rose);
  color: #fff;
  border-color: var(--rose);
}
</style>
