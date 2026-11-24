<script setup lang="ts">
// Server settings — AI (E3.11, E7.11, mockups ai-provider-1 and -2). Which provider answers @ai in every document on this
// server: the scripted stand-in, the local model, or Claude. Says in words what answers now (with "remote" for Claude),
// the last error and since when, and never shows the provider key again: only its last four characters.
import { computed, onMounted, ref } from 'vue'
import { adminApi, AdminApiError, type ServerSettingsView } from '~/lib/admin-api'
import { answerLength, applyState, approxWords, claudePayload, failureHint, failureSentence, lengthIsValid, lengthToSend, PROVIDERS, setAnswerLength, type AiForm, type Provider } from '~/lib/admin-ai'
import { ago, clock } from '~/lib/people'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ token: string }>()

const DEVICES = ['CPU', 'GPU', 'NPU', 'AUTO'] as const
const APPROVAL = t('Document content is sent to Anthropic when someone asks @ai.')

const settings = ref<ServerSettingsView | null>(null)
const form = ref<AiForm>({ provider: 'stand-in', modelDir: '', device: 'GPU', maxTokens: 512, claudeMaxTokens: 4096, timeout: 180, model: '', key: '', removeKey: false, confirmed: false })
const busy = ref(false)
const loading = ref(true)
const error = ref('')
const refusal = ref<{ sentence: string; reason: string } | null>(null)
const removing = ref(false)
/** Applying Claude asks it one test question first, so a page that was applied has had it answered. */
const tested = ref(false)

const ai = computed(() => settings.value?.ai ?? null)
/** The field edits the answer length of the provider that is chosen: Claude's own, or the local model's. */
const length = computed({
  get: () => answerLength(form.value),
  set: (tokens: number) => setAnswerLength(form.value, tokens),
})
const apply_ = computed(() => (ai.value ? applyState(form.value, { provider: ai.value.provider, key_set: ai.value.claude.key_set }) : null))

function sync(s: ServerSettingsView) {
  settings.value = s
  form.value = {
    provider: PROVIDERS.includes(s.ai.provider as Provider) ? (s.ai.provider as Provider) : 'stand-in',
    modelDir: s.ai.model_dir ?? '',
    device: s.ai.device,
    maxTokens: s.ai.max_tokens,
    claudeMaxTokens: s.ai.claude.max_tokens,
    timeout: s.ai.timeout,
    model: s.ai.claude.model,
    key: '',
    removeKey: false,
    confirmed: false,
  }
  removing.value = false
}

const providerNames: Record<Provider, () => string> = {
  'stand-in': () => t('Scripted stand-in'),
  local: () => t('Local model'),
  claude: () => t('Claude'),
}

/** Why the server refused, in the language of the page; the server's own sentence where the cause has none. */
function refused(e: AdminApiError): string {
  return e.reason ? failureSentence(e.reason, { model: form.value.model, seconds: form.value.timeout }, e.message) : e.message
}

onMounted(async () => {
  try {
    sync(await adminApi.getSettings(props.token))
  } catch (e) {
    error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
  } finally {
    loading.value = false
  }
})

function cancel() {
  if (settings.value) sync(settings.value)
  error.value = ''
  refusal.value = null
}

async function apply() {
  busy.value = true
  error.value = ''
  refusal.value = null
  tested.value = false
  const f = form.value
  try {
    sync(
      await adminApi.setAi(props.token, {
        provider: f.provider,
        model_dir: f.modelDir.trim() || null,
        device: f.device,
        max_tokens: lengthToSend(f.maxTokens, ai.value?.max_tokens ?? 512),
        timeout: f.timeout,
        claude: claudePayload(f, ai.value?.claude ?? { max_tokens: 4096 }),
      }),
    )
    tested.value = f.provider === 'claude'
  } catch (e) {
    if (e instanceof AdminApiError && e.reason) refusal.value = { sentence: refused(e), reason: e.reason }
    else error.value = e instanceof AdminApiError ? e.message : t('Could not reach the server.')
  } finally {
    busy.value = false
  }
}

/** Removing the key while Claude answers would leave no way to answer: the page asks first, then goes to the local model. */
function removeKey() {
  if (form.value.provider === 'claude' && !removing.value) {
    removing.value = true
    return
  }
  form.value.removeKey = true
  form.value.key = ''
  if (form.value.provider === 'claude') form.value.provider = form.value.modelDir.trim() ? 'local' : 'stand-in'
  removing.value = false
}

function replaceKey() {
  form.value.removeKey = true
}

const lastError = computed(() => {
  const e = ai.value?.last_error
  return e ? { ...e, text: failureSentence(e.reason, { model: ai.value!.claude.model, seconds: ai.value!.timeout }, e.sentence) } : null
})
</script>

<template>
  <div v-if="!loading && ai && apply_">
    <h1>{{ t('AI') }}</h1>
    <p class="lead">{{ t('What answers @ai in every document on this server.') }}</p>

    <p class="now" data-testid="ai-now">
      <span>{{ t('Answering now:') }}</span>
      <strong>{{ ai.answering.label }}</strong>
      <span v-if="ai.answering.remote" class="remote">{{ t('remote') }}</span>
    </p>
    <p v-if="lastError" class="lastError" role="alert" data-testid="ai-last-error">
      <strong>{{ t('Last error') }} · {{ clock(lastError.when) }}</strong>
      <span>{{ lastError.text }}</span>
      <span class="hint">{{ failureHint(lastError.reason) }}</span>
      <span class="hint">{{ t('The administrator decides: add credit, or choose another provider.') }}</span>
    </p>
    <p v-else class="lead" data-testid="ai-last-error">{{ t('Last error: none') }}</p>

    <h2>{{ t('AI provider') }}</h2>
    <div role="group" :aria-label="t('AI provider')" class="segmented">
      <button v-for="p in PROVIDERS" :key="p" type="button" :aria-pressed="form.provider === p" @click="form.provider = p">{{ providerNames[p]() }}</button>
    </div>

    <template v-if="form.provider === 'local'">
      <label class="field">
        {{ t('Model folder') }}
        <div class="row">
          <input v-model="form.modelDir" class="mono" :placeholder="t('(none — @ai gets the scripted stand-in)')" >
        </div>
      </label>

      <h2>{{ t('Device') }}</h2>
      <div role="group" :aria-label="t('Device')" class="segmented">
        <button v-for="d in DEVICES" :key="d" type="button" :aria-pressed="form.device === d" @click="form.device = d">{{ d === 'AUTO' ? t('Auto') : d }}</button>
      </div>
    </template>

    <template v-if="form.provider === 'claude'">
      <div class="field">
        <span id="key-label">{{ t('Provider key') }}</span>
        <p v-if="ai.claude.key_from_operator" class="lead" data-testid="ai-key-operator">{{ t('The key is given by the server’s operator.') }}</p>
        <div v-else-if="ai.claude.key_set && !form.removeKey" class="row keyRow">
          <span class="mono" data-testid="ai-key">sk-ant-{{ '•'.repeat(20) }} {{ ai.claude.key_tail }}</span>
          <button type="button" class="btn" @click="replaceKey">{{ t('Replace') }}</button>
          <button type="button" class="btn" @click="removeKey">{{ t('Remove') }}</button>
        </div>
        <input v-else v-model="form.key" class="mono" type="password" autocomplete="off" aria-labelledby="key-label" :placeholder="t('Paste the key of your Anthropic account')" >
        <p v-if="removing" class="lead" role="alert">
          {{ t('Removing the key switches this server to the local model, because nothing else could answer.') }}
          <button type="button" class="btn" @click="removeKey">{{ t('Remove the key') }}</button>
        </p>
        <p class="lead">{{ t('Kept on this server only. It is never shown again, never sent to a client or into a document.') }}</p>
        <p class="lead">{{ t('A key of your Anthropic account. Anthropic bills its use apart from any Claude subscription.') }}</p>
      </div>

      <label class="field">
        {{ t('Model') }}
        <input v-model="form.model" class="mono" list="claude-models" >
        <datalist id="claude-models"><option v-for="m in ['claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-5-5', 'claude-fable-5-2']" :key="m" :value="m" /></datalist>
      </label>
      <p class="lead">{{ t('Type any model id: the list of models changes faster than this app does.') }}</p>
    </template>

    <div class="pair">
      <div class="field">
        <label for="answer-length">{{ t('Max answer length (tokens)') }}</label>
        <input id="answer-length" v-model.number="length" type="number" min="1" class="mono narrow" aria-describedby="answer-words" :aria-invalid="!lengthIsValid(length)" data-testid="ai-max-tokens" >
        <span v-if="!lengthIsValid(length)" id="answer-words" class="hint" role="alert" data-testid="ai-max-words">{{ t('The answer length must be a whole number of at least 1.') }}</span>
        <span v-else-if="approxWords(length) > 0" id="answer-words" class="hint" data-testid="ai-max-words">{{ t('About {words} words', { words: approxWords(length) }) }}</span>
      </div>
      <label class="field">
        {{ t('Timeout (seconds)') }}
        <input v-model.number="form.timeout" type="number" min="1" class="mono narrow" >
      </label>
    </div>

    <section v-if="form.provider === 'claude'" class="approval" data-testid="ai-approval">
      <label class="check">
        <input v-model="form.confirmed" type="checkbox" :disabled="!apply_.needsConfirm && !!ai.claude.confirmed">
        <span><strong>{{ APPROVAL }}</strong></span>
      </label>
      <p class="lead">{{ t('Documents are encrypted on this server; Claude reads what it is shown in plain text.') }}</p>
      <p v-if="ai.claude.confirmed" class="lead" data-testid="ai-confirmed">{{ t('Confirmed by {by}, {when}', { by: ai.claude.confirmed.by, when: ago(ai.claude.confirmed.at) }) }}</p>
      <p class="lead">{{ t('This is not enough on its own: the owner of each document must also allow Claude (Preferences ▸ AI…, off by default). Until it is allowed, @ai in that document uses the local model or the stand-in, and says so.') }}</p>
      <p class="lead">{{ t('Apply asks Claude one test question first.') }}</p>
      <p v-if="apply_.needsKey || (apply_.needsConfirm && !form.confirmed)" class="lead">{{ t('Apply needs a key and the confirmed sentence.') }}</p>
    </section>

    <p v-if="tested" class="lead" role="status" data-testid="ai-tested">{{ t('Test answered') }}</p>

    <section v-if="refusal" class="refused" role="alert" data-testid="ai-refused">
      <strong>{{ refusal.sentence }}</strong>
      <span>{{ t('Nothing was changed: @ai still answers with {who}.', { who: ai.answering.label }) }}</span>
    </section>

    <AdminPageFooter :changed="settings?.changed.ai ?? null" :busy="busy" :error="error" :cannot-apply="!apply_.canApply" @cancel="cancel" @apply="apply" />
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
.now {
  display: flex;
  gap: 8px;
  align-items: baseline;
  margin: 0 0 8px;
}
.remote {
  padding: 1px 8px;
  border: 1px solid currentcolor;
  border-radius: 10px;
  font: 600 12px var(--font-ui);
}
.lastError,
.refused {
  display: grid;
  gap: 2px;
  margin: 0 0 16px;
  padding: 10px 12px;
  border: 1px solid var(--line-field);
  border-left-width: 4px;
  border-radius: 9px;
}
.hint,
.lead + .lead {
  color: var(--muted);
}
.keyRow {
  align-items: center;
}
.approval {
  display: grid;
  gap: 4px;
  margin-bottom: 16px;
}
.check {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
