<script setup lang="ts">
// Server settings ▸ Templates (E10.22, D1537; board `notes/mockups/creates-templates-new-and-server.svg`, panel L): the
// templates a person can start a presentation from on this server. The built-in one is always there; the others are
// Claudia exports of a presentation without slides (File ▸ Save as template…), which only an administrator adds here.
// Adding is check first, then add: the file is sent to be checked, the sentence says what adding will do, and only
// "Add template" changes the server. Removing never changes a presentation made from the template. Every change
// answers with the whole page again.
import { computed, onMounted, ref } from 'vue'
import { adminApi, AdminApiError } from '~/lib/admin-api'
import { addSentence, checkDetails, removeSentence, type TemplateCheck, type TemplatesPage, type TemplateView } from '~/lib/admin-templates'
import { useI18n } from '~/lib/i18n'
import { languageName } from '~/lib/templates'

const { t } = useI18n()

const props = defineProps<{ token: string; server: string }>()

const page = ref<TemplatesPage | null>(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const dragging = ref(false)
const picker = ref<HTMLInputElement | null>(null)
/** The file being added, once the server has checked it, and what the server says it is. */
const adding = ref<{ file: File; check: TemplateCheck } | null>(null)
const removing = ref<TemplateView | null>(null)

const templates = computed(() => page.value?.templates ?? [])

function failed(e: unknown) {
  error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
}

onMounted(async () => {
  try {
    page.value = await adminApi.templatesPage(props.token)
  } catch (e) {
    failed(e)
  } finally {
    loading.value = false
  }
})

/** A file was chosen or dropped: the server checks it, and nothing is added yet. */
async function take(files: FileList | File[] | null) {
  const file = files?.[0]
  if (!file) return
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    adding.value = { file, check: await adminApi.checkTemplate(props.token, file, file.name) }
  } catch (e) {
    failed(e)
  } finally {
    busy.value = false
  }
}

function picked(event: Event) {
  const input = event.target as HTMLInputElement
  void take(input.files).then(() => {
    input.value = '' // so the same file can be chosen again
  })
}

function dropped(event: DragEvent) {
  dragging.value = false
  void take(event.dataTransfer?.files ?? null)
}

async function add() {
  const target = adding.value
  if (!target) return
  busy.value = true
  try {
    page.value = await adminApi.addTemplate(props.token, target.file, target.file.name)
    notice.value = t('Template added. Everyone who makes a presentation here can start from it.')
    adding.value = null
  } catch (e) {
    adding.value = null
    failed(e)
  } finally {
    busy.value = false
  }
}

async function remove() {
  const target = removing.value
  removing.value = null
  if (!target) return
  error.value = ''
  try {
    page.value = await adminApi.removeTemplate(props.token, target.id)
    notice.value = t('Template removed.')
  } catch (e) {
    failed(e)
  }
}
</script>

<template>
  <div v-if="!loading && page" class="templates-page">
    <div class="head">
      <h1>{{ t('Templates') }}</h1>
      <button class="btn primary" type="button" :disabled="busy" @click="picker?.click()">{{ t('Add template…') }}</button>
    </div>
    <p class="lead">{{ t('The templates anyone can start a presentation from on this server.') }}</p>
    <p v-if="notice" class="notice" role="status">{{ notice }}</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>

    <table>
      <thead>
        <tr>
          <th scope="col">{{ t('Name') }}</th>
          <th scope="col">{{ t('What it is for') }}</th>
          <th scope="col">{{ t('Layouts') }}</th>
          <th scope="col">{{ t('Language') }}</th>
          <th scope="col"><span class="sr-only">{{ t('Actions') }}</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="template in templates" :key="template.id">
          <th scope="row">{{ template.name }}</th>
          <td class="muted">{{ template.purpose }}</td>
          <td>{{ template.layouts.length }}</td>
          <td>{{ languageName(template.language) }}</td>
          <td class="action">
            <button v-if="template.removable" type="button" class="link danger" :aria-label="t('Remove {name}', { name: template.name })" @click="removing = template">{{ t('Remove') }}</button>
            <span v-else class="muted">{{ t('built in') }}</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="drop" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave="dragging = false" @drop.prevent="dropped">
      <label class="pick">
        {{ t('Drop a template file here, or choose one') }}
        <input ref="picker" type="file" accept=".zip,application/zip" class="sr-only" @change="picked" >
      </label>
      <span class="hint">{{ t('Anyone can make one with Save as template…; only the administrator can add it here.') }}</span>
      <span v-if="busy" class="hint" role="status">{{ t('Checking the file…') }}</span>
    </div>
    <p class="hint">{{ t('Presentations made from a template are not affected when it is removed.') }}</p>

    <Modal v-if="adding" :title="t('Add template')" :width="520" @close="adding = null">
      <p class="what"><strong>{{ adding.check.name }}</strong></p>
      <p class="muted">{{ adding.check.purpose }}</p>
      <p class="muted">{{ checkDetails(adding.check) }}</p>
      <p>{{ addSentence(adding.check, server, t) }}</p>
      <div class="buttons">
        <button class="btn primary" type="button" :disabled="busy" @click="add">{{ t('Add template') }}</button>
        <button class="btn" type="button" @click="adding = null">{{ t('Cancel') }}</button>
      </div>
    </Modal>
    <Modal v-if="removing" :title="t('Remove template')" :width="520" @close="removing = null">
      <p>{{ removeSentence(removing, t) }}</p>
      <div class="buttons">
        <button class="btn danger" type="button" @click="remove">{{ t('Remove template') }}</button>
        <button class="btn" type="button" @click="removing = null">{{ t('Cancel') }}</button>
      </div>
    </Modal>
  </div>
  <p v-else-if="error" class="error" role="alert">{{ error }}</p>
</template>

<style scoped>
.templates-page {
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
.lead {
  margin: 0 0 14px;
  font-size: 13.5px;
  color: var(--muted);
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
tbody th {
  font-weight: 600;
}
.muted {
  color: var(--muted);
}
.action {
  text-align: right;
}
.link {
  border: none;
  background: transparent;
  font: 13px var(--font-ui);
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}
.link.danger {
  color: var(--bad-text);
}
.drop {
  margin: 22px 0 8px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  border: 1.5px dashed var(--line-field);
  border-radius: 12px;
  text-align: center;
}
.drop.dragging {
  border-color: var(--ink);
  background: color-mix(in srgb, var(--line) 50%, transparent);
}
.pick {
  cursor: pointer;
  font: 500 14px var(--font-ui);
}
.pick:focus-within {
  outline: 2px solid var(--ink);
  outline-offset: 3px;
}
.hint {
  font-size: 12.5px;
  color: var(--muted);
}
.what {
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
