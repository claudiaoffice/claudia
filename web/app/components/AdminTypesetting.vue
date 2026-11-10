<script setup lang="ts">
// Server settings — Typesetting. How formulas, help pages and exports are typeset with LaTeX, for every document
// on this server. The mockup also sketched `kpsewhich`/`biber` rows and a file-browse dialog; `typeset_diagnosis`
// only ever reports on `xelatex` and `pdftocairo` (the two fields `TypesetSettings` actually has — server_settings.py,
// admin_api.py's `_diagnose_typeset`), and there's no file-picker wired to a server path here, so this page sticks
// to editable text fields for the two programs it can actually change.
import { onMounted, ref } from 'vue'
import { adminApi, AdminApiError, type ServerSettingsView } from '~/lib/admin-api'

const props = defineProps<{ token: string }>()

const settings = ref<ServerSettingsView | null>(null)
const xelatex = ref('')
const pdftocairo = ref('')
const busy = ref(false)
const loading = ref(true)
const error = ref('')

function sync(s: ServerSettingsView) {
  settings.value = s
  xelatex.value = s.typeset.xelatex ?? ''
  pdftocairo.value = s.typeset.pdftocairo ?? ''
}

onMounted(async () => {
  try {
    sync(await adminApi.getSettings(props.token))
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    loading.value = false
  }
})

function cancel() {
  if (settings.value) sync(settings.value)
  error.value = ''
}

async function apply() {
  busy.value = true
  error.value = ''
  try {
    sync(await adminApi.setTypeset(props.token, { xelatex: xelatex.value.trim() || null, pdftocairo: pdftocairo.value.trim() || null }))
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="!loading && settings">
    <h1>Typesetting</h1>
    <p class="lead">How formulas, help pages and exports are typeset with LaTeX, for every document on this server.</p>

    <h2>Detected on this machine</h2>
    <div class="card">
      <div v-for="row in [['xelatex', settings.typeset_diagnosis.xelatex], ['pdftocairo', settings.typeset_diagnosis.pdftocairo]] as const" :key="row[0]" class="program">
        <span class="dot" :class="{ bad: !row[1]?.ok }" aria-hidden="true" />
        <span class="name">{{ row[0] }}</span>
        <span class="detail">{{ row[1]?.detail }}</span>
      </div>
    </div>

    <h2>Installation</h2>
    <label class="field">
      xelatex
      <input v-model="xelatex" class="mono" placeholder="(auto-detect on PATH)" />
    </label>
    <label class="field">
      pdftocairo
      <input v-model="pdftocairo" class="mono" placeholder="(auto-detect on PATH)" />
    </label>
    <p class="hint">A full path, the folder it lives in, or a bare program name to look up on the PATH. Blank looks for the usual name.</p>

    <h2>Sandbox</h2>
    <div class="card sandbox">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="lock">
        <rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" />
      </svg>
      <div>
        <div class="title">Sandboxed execution</div>
        <div class="sub">No shell access, no network, no files outside the job — always on, whichever installation you point to.</div>
      </div>
    </div>

    <AdminPageFooter :changed="settings.changed.typeset ?? null" :busy="busy" :error="error" @cancel="cancel" @apply="apply" />
  </div>
</template>

<style scoped>
h1 {
  margin: 0 0 4px;
  font: 500 23px/1.3 var(--font-display);
}
h2 {
  margin: 20px 0 10px;
  font: 600 13px var(--font-ui);
  color: var(--muted);
}
.lead {
  margin: 0 0 22px;
  font-size: 13.5px;
  color: var(--muted);
}
.card {
  border: 1px solid var(--line-field);
  border-radius: 12px;
  background: var(--surface);
  margin-bottom: 16px;
}
.program {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-top: 1px solid var(--line);
}
.program:first-child {
  border-top: none;
}
.dot {
  width: 7px;
  height: 7px;
  flex: none;
  border-radius: 50%;
  background: var(--teal);
}
.dot.bad {
  background: var(--apricot);
}
.name {
  width: 88px;
  flex: none;
  font: 13px var(--font-mono);
}
.detail {
  flex: 1;
  min-width: 0;
  font: 12.5px var(--font-mono);
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.field {
  display: block;
  font: 500 12.5px var(--font-ui);
  margin-bottom: 6px;
  color: var(--muted);
}
.field input {
  display: block;
  width: 100%;
  max-width: 420px;
  margin-top: 6px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 12.5px var(--font-mono);
}
.hint {
  margin: -6px 0 16px;
  font-size: 12px;
  color: var(--muted);
}
.sandbox {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  margin-bottom: 20px;
}
.lock {
  flex: none;
  opacity: 0.6;
}
.title {
  font: 500 14px var(--font-ui);
}
.sub {
  font-size: 12.5px;
  color: var(--muted);
  margin-top: 3px;
}
</style>
