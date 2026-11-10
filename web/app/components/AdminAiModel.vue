<script setup lang="ts">
// Server settings — AI model (E3.11, canvas's "Server settings — AI model"). The model that answers @ai in every
// document on this server. The mockup also sketched an engine choice (OpenVINO/Ollama/Remote API) and a
// remote-model toggle; neither exists in the backend yet (`AiSettings` is `model_dir`, `device`, `max_tokens`,
// `timeout` — admin_api.py, server_settings.py), so this page sticks to what `PUT /settings/ai` can actually do
// rather than drawing controls that would silently do nothing.
import { onMounted, ref } from 'vue'
import { adminApi, AdminApiError, type ServerSettingsView } from '~/lib/admin-api'

const props = defineProps<{ token: string }>()

const DEVICES = ['CPU', 'GPU', 'NPU', 'AUTO'] as const

const settings = ref<ServerSettingsView | null>(null)
const modelDir = ref('')
const device = ref<string>('GPU')
const maxTokens = ref(512)
const timeout = ref(180)
const busy = ref(false)
const loading = ref(true)
const error = ref('')

function sync(s: ServerSettingsView) {
  settings.value = s
  modelDir.value = s.ai.model_dir ?? ''
  device.value = s.ai.device
  maxTokens.value = s.ai.max_tokens
  timeout.value = s.ai.timeout
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
    sync(
      await adminApi.setAi(props.token, {
        model_dir: modelDir.value.trim() || null,
        device: device.value,
        max_tokens: maxTokens.value,
        timeout: timeout.value,
      }),
    )
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="!loading">
    <h1>AI model</h1>
    <p class="lead">The model that answers @ai in every document on this server.</p>

    <label class="field">
      Model folder
      <div class="row">
        <input v-model="modelDir" class="mono" placeholder="(none — @ai gets the scripted stand-in)" />
      </div>
    </label>

    <h2>Device</h2>
    <div role="group" aria-label="Device" class="segmented">
      <button v-for="d in DEVICES" :key="d" type="button" :aria-pressed="device === d" @click="device = d">{{ d === 'AUTO' ? 'Auto' : d }}</button>
    </div>

    <div class="pair">
      <label class="field">
        Max answer length (tokens)
        <input v-model.number="maxTokens" type="number" min="1" class="mono narrow" />
      </label>
      <label class="field">
        Timeout (seconds)
        <input v-model.number="timeout" type="number" min="1" class="mono narrow" />
      </label>
    </div>

    <AdminPageFooter :changed="settings?.changed.ai ?? null" :busy="busy" :error="error" @cancel="cancel" @apply="apply" />
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
.field {
  display: block;
  font: 500 12.5px var(--font-ui);
  margin-bottom: 6px;
  color: var(--muted);
}
.field input {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 14px var(--font-ui);
}
.field input.mono {
  font: 12.5px var(--font-mono);
}
.field input.narrow {
  max-width: 140px;
}
.row {
  display: flex;
  gap: 8px;
}
.segmented {
  display: flex;
  border: 1px solid var(--line-field);
  border-radius: 9px;
  overflow: hidden;
  margin-bottom: 20px;
  width: 320px;
}
.segmented button {
  flex: 1;
  padding: 9px 4px;
  border: none;
  border-left: 1px solid var(--line-field);
  background: transparent;
  color: var(--text);
  font: 500 13px var(--font-ui);
}
.segmented button:first-child {
  border-left: none;
}
.segmented button[aria-pressed='true'] {
  background: var(--iris);
  color: var(--paper);
}
.pair {
  display: flex;
  gap: 24px;
  margin-bottom: 20px;
}
</style>
