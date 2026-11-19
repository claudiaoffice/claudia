<script setup lang="ts">
// Server settings — Security (D1267). How slow password hashing should be for the documents this server makes from now
// on. The server measures what that means for its own machine, in the background; "Apply" asks it to measure again,
// so it is also the way to do so after the hardware changed. Documents made before keep the cost they were made with:
// each person's key is sealed under their own password, so nobody can raise it for them (said on the page).
//
// BITV: the sentence about the cost is a polite live region and changes when it is measured, not while it waits; the
// field has a visible label and its hint and any error are tied to it.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { adminApi, AdminApiError, type ServerSettingsView } from '~/lib/admin-api'
import { useI18n } from '~/lib/i18n'
import { costSentence, parseTarget } from '~/lib/security-settings'

const { t } = useI18n()

const props = defineProps<{ token: string }>()

const POLL_MS = 2000
const settings = ref<ServerSettingsView | null>(null)
const target = ref('')
const busy = ref(false)
const loading = ref(true)
const error = ref('')
let poll: ReturnType<typeof setTimeout> | null = null

const cost = computed(() => costSentence(settings.value?.kdf ?? null))

function sync(s: ServerSettingsView) {
  settings.value = s
  target.value = String(s.security.kdf_target_seconds)
}

// A server that has not finished measuring is asked again until it has, so the sentence says what came out.
function watchMeasuring() {
  if (poll !== null) clearTimeout(poll)
  poll = null
  if (!settings.value?.kdf || settings.value.kdf.measured) return
  poll = setTimeout(async () => {
    try {
      const fresh = await adminApi.getSettings(props.token)
      settings.value = fresh
    } catch {
      // the next try, or the person's own Apply, says what is wrong
    }
    watchMeasuring()
  }, POLL_MS)
}

onMounted(async () => {
  try {
    sync(await adminApi.getSettings(props.token))
    watchMeasuring()
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  if (poll !== null) clearTimeout(poll)
})

function cancel() {
  if (settings.value) sync(settings.value)
  error.value = ''
}

async function apply() {
  const parsed = parseTarget(target.value)
  if (!parsed.ok) {
    error.value = parsed.message
    return
  }
  busy.value = true
  error.value = ''
  try {
    sync(await adminApi.setSecurity(props.token, { kdf_target_seconds: parsed.value }))
    watchMeasuring()
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="!loading && settings">
    <h1>{{ t('Security') }}</h1>
    <p class="lead">{{ t('How passwords protect the documents on this server.') }}</p>

    <h2>{{ t('Password hashing') }}</h2>
    <label class="field" for="kdf-target">{{ t('Time to check one password, in seconds') }}</label>
    <input id="kdf-target" v-model="target" class="mono" inputmode="decimal" aria-describedby="kdf-hint" >
    <p id="kdf-hint" class="hint">
      {{ t('Longer is safer against someone who steals a document file and guesses its passwords, and makes a login take that long. The server measures what this means for its machine at start; Apply measures again.') }}
    </p>
    <div class="card" role="status">
      <template v-if="settings.kdf">{{ cost }}</template>
      <template v-else>{{ t('This server keeps no sealed documents, so there is nothing to set here.') }}</template>
    </div>
    <p class="hint">{{ t('A document keeps the cost it was made with: each person’s key is sealed under their own password, so nobody can make it harder for them afterwards.') }}</p>

    <AdminPageFooter :changed="settings.changed.security ?? null" :busy="busy" :error="error" @cancel="cancel" @apply="apply" />
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
  color: var(--muted);
}
input {
  display: block;
  width: 100%;
  max-width: 160px;
  margin: 6px 0 10px;
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 12.5px var(--font-mono);
}
.hint {
  margin: 0 0 16px;
  font-size: 12px;
  color: var(--muted);
}
.card {
  border: 1px solid var(--line-field);
  border-radius: 12px;
  background: var(--surface);
  padding: 12px 18px;
  margin-bottom: 10px;
  font-size: 13px;
}
</style>
