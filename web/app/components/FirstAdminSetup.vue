<script setup lang="ts">
// Naming the first administrator (E3.11; canvas note s7; SEC-12). Shown whenever no administrator exists yet: forced
// the moment a server is reached from other computers (`exposed`), offered but skippable while it stays on this
// computer — a person can still choose to set one up early, e.g. before exposing the server later.
//
// Every server asks for its setup code here (D1370; mock-up notes/mockups/sec12-first-administrator-setup-code.svg):
// typed from the server's log, filled in from a link of the log (panel 3), or handed over by the desktop app, in
// which case there is no field at all (panel 5). A code the page was given is checked first; if the server refuses
// it, the field appears. On the computer's shared service, the app of a person who may not read its code says so, and
// the field's hint tells her to ask an administrator of this computer (E8.5, D1624).
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { adminApi, AdminApiError } from '~/lib/admin-api'
import type { SetupRefusal, useAdminSession } from '~/lib/admin-session'
import { useI18n } from '~/lib/i18n'
import {
  codeField,
  forgetSetupCode,
  mustAskAdministrator,
  onAskAdministrator,
  onSetupCode,
  rememberedSetupCode,
  type CodeCheck,
  type GivenCode,
} from '~/lib/setup-code'

const { t } = useI18n()

const props = defineProps<{ host: string; exposed: boolean; setupCode: boolean; session: ReturnType<typeof useAdminSession> }>()
/** Somebody else named the first administrator meanwhile (409): the page turns to the sign-in. */
const emit = defineEmits<{ taken: [] }>()

const name = ref('')
const password = ref('')
const confirmPassword = ref('')
const formError = ref('')
const typedCode = ref('')
const codeError = ref('')

const given = ref<GivenCode | null>(rememberedSetupCode())
const check = ref<CodeCheck>('unchecked')
const askAdministrator = ref(mustAskAdministrator())
const field = computed(() => codeField(props.setupCode, given.value, check.value))

function wrongCode(): string {
  return t("That is not this server's setup code. Check the log of its last start: a restart makes a new code.")
}

function tooSoon(seconds: number | undefined): string {
  return t('Too many tries from this address. Try again in {seconds} seconds.', { seconds: seconds ?? 30 })
}

let asked = 0 // the newest check: an answer to an older one, for a code replaced meanwhile, is not used

/** Is the code the page was given this run's? Refused, it goes to the field (a link's) or away (the app's). */
async function verify(code: GivenCode) {
  const mine = ++asked
  given.value = code
  check.value = 'unchecked'
  if (!props.setupCode) return
  try {
    await adminApi.checkSetupCode(code.code)
    if (mine === asked) check.value = 'ok'
  } catch (error) {
    if (mine !== asked) return
    const status = error instanceof AdminApiError ? error.status : 0
    if (status === 409) return emit('taken')
    check.value = 'refused'
    typedCode.value = code.from === 'link' ? code.code : ''
    if (status === 403 && code.from === 'link') codeError.value = wrongCode()
    if (status === 429) codeError.value = tooSoon(error instanceof AdminApiError ? error.retryAfter : undefined)
  }
}

function useAnotherCode() {
  asked++
  forgetSetupCode()
  given.value = null
  check.value = 'unchecked'
  typedCode.value = ''
  codeError.value = ''
}

const stopListening: Array<() => void> = []
onMounted(() => {
  if (given.value) void verify(given.value)
  // the desktop app's welcome may come after the page drew
  stopListening.push(onSetupCode((code) => void verify(code)), onAskAdministrator((ask) => (askAdministrator.value = ask)))
})
onUnmounted(() => stopListening.forEach((stop) => stop()))

function refused(refusal: SetupRefusal) {
  if (refusal.kind === 'taken') return emit('taken')
  if (refusal.kind === 'wrong-code') {
    codeError.value = wrongCode()
    if (given.value) {
      typedCode.value = given.value.from === 'link' ? given.value.code : ''
      check.value = 'refused'
    }
  } else if (refusal.kind === 'too-soon') codeError.value = tooSoon(refusal.retryAfter)
  else formError.value = refusal.message
}

async function create() {
  formError.value = ''
  codeError.value = ''
  const code = field.value === 'typed' ? typedCode.value : (given.value?.code ?? '')
  if (props.setupCode && !code.trim()) {
    codeError.value = t('Fill in the setup code.')
    return
  }
  if (!name.value.trim() || !password.value) {
    formError.value = t('Fill in your name and a password.')
    return
  }
  if (password.value !== confirmPassword.value) {
    formError.value = t('The passwords do not match.')
    return
  }
  const refusal = await props.session.setup(name.value.trim(), password.value, code)
  if (refusal) refused(refusal)
  else forgetSetupCode()
}

function keepLocal() {
  location.href = '/'
}
</script>

<template>
  <div class="setup">
    <header class="bar">{{ t('Server settings') }}</header>
    <form class="body" @submit.prevent="create">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--iris)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="shield">
        <path d="M12 2l8 3.5v5.3c0 5-3.4 8.9-8 10.2-4.6-1.3-8-5.2-8-10.2V5.5L12 2z" /><path d="M9.5 12l1.8 1.8 3.2-3.6" />
      </svg>
      <h1>{{ t('Name yourself as this server\'s administrator') }}</h1>
      <p v-if="exposed" class="lead">{{ t('{host} can be reached from other computers. To show that you run it, give the setup code from the server\'s log, then a name and a password for yourself. You will use them to sign in here from now on.', { host }) }}</p>
      <p v-else class="lead">{{ t('{host} isn\'t reachable beyond this computer yet, so this isn\'t required — but set a name and password now if you\'d like to manage its settings, or before you open it up to others later.', { host }) }}</p>

      <div v-if="field !== 'none'" class="field code" data-testid="setup-code">
        <label for="setup-code">{{ t('Setup code') }}</label>
        <div class="code-line">
          <input
            v-if="field === 'typed'"
            id="setup-code"
            v-model="typedCode"
            type="text"
            autocomplete="one-time-code"
            autocapitalize="characters"
            spellcheck="false"
            placeholder="XXXX-XXXX-XXXX"
            :aria-invalid="codeError ? 'true' : undefined"
            aria-describedby="setup-code-hint"
          >
          <input v-else id="setup-code" class="from-link" :value="given?.code" type="text" readonly aria-describedby="setup-code-hint" >
          <svg v-if="field === 'from-link' && check === 'ok'" class="checked" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--teal)" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
        </div>
        <p v-if="codeError" class="error code-error" role="alert">{{ codeError }}</p>
        <p v-if="field === 'from-link'" id="setup-code-hint" class="hint">
          {{ t('From the link you opened.') }}
          <button class="link" type="button" @click="useAnotherCode">{{ t('Use another code') }}</button>
        </p>
        <p v-else-if="askAdministrator" id="setup-code-hint" class="hint">{{ t('Only an administrator of this computer can name this server\'s first administrator. Ask one.') }}</p>
        <p v-else id="setup-code-hint" class="hint">{{ t('In the server\'s log where it started, or in admin/setup-code in its state folder. A restart of the server makes a new code.') }}</p>
      </div>

      <label class="field">{{ t('Your name') }}<input v-model="name" type="text" autocomplete="username" :placeholder="t('tobi')" ></label>
      <label class="field">{{ t('Password') }}<PasswordInput v-model="password" autocomplete="new-password" placeholder="••••••••••" /></label>
      <label class="field">{{ t('Confirm password') }}<PasswordInput v-model="confirmPassword" autocomplete="new-password" placeholder="••••••••••" /></label>

      <div class="note">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="11" width="18" height="10" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" />
        </svg>
        <span>{{ t('Keep this password safe. If every administrator is ever locked out, only someone with access to the computer the server runs on can name a new first administrator.') }}</span>
      </div>

      <p v-if="formError" class="error" role="alert">{{ formError }}</p>

      <div class="spacer" />
      <div class="buttons">
        <button class="btn" type="button" :disabled="session.busy.value" @click="keepLocal">{{ exposed ? t('Keep this server local for now') : t('Skip for now') }}</button>
        <button class="btn primary" type="submit" :disabled="session.busy.value">{{ t('Create administrator') }}</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.setup {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--page);
}
.bar {
  height: 46px;
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ink);
  color: var(--paper);
  font: 500 14px var(--font-ui);
}
.body {
  flex: 1 1 auto;
  max-width: 680px;
  width: 100%;
  margin: 0 auto;
  padding: 40px 24px;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.shield {
  margin-bottom: 16px;
}
h1 {
  margin: 0 0 10px;
  font: 500 24px/1.35 var(--font-display);
}
.lead {
  margin: 0 0 26px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--muted);
  max-width: 520px;
}
.field {
  display: block;
  font: 500 12.5px var(--font-ui);
  margin-bottom: 16px;
  color: var(--muted);
}
.field input {
  display: block;
  width: 100%;
  max-width: 340px;
  margin-top: 6px;
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 14px var(--font-ui);
}
/* the password field (PasswordInput): the box is the wrapper, so the eye sits at the end of the input */
.field .password {
  margin-top: 6px;
  max-width: 340px;
}
.field .password :deep(input) {
  display: block;
  padding: 10px 12px;
  border-radius: 9px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 14px var(--font-ui);
}
.code label {
  display: block;
}
.code-line {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 340px;
}
.code input {
  max-width: 230px;
  font: 500 14.5px var(--font-mono);
  letter-spacing: 0.04em;
}
.code input.from-link {
  border-color: var(--teal);
  background: color-mix(in srgb, var(--teal) 8%, var(--surface));
}
.code input[aria-invalid='true'] {
  border-color: var(--rose);
}
.checked {
  flex: none;
  margin-top: 6px;
}
.hint {
  margin: 6px 0 0;
  max-width: 420px;
  font: 400 11.5px/1.5 var(--font-ui);
  color: var(--muted);
}
.code-error {
  margin: 6px 0 0;
  font-size: 12px;
}
.link {
  border: 0;
  padding: 0;
  margin-left: 6px;
  background: none;
  color: var(--iris);
  font: 500 11.5px var(--font-ui);
  cursor: pointer;
}
.note {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-bottom: 20px;
  max-width: 480px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--muted);
}
.note svg {
  flex: none;
  margin-top: 2px;
}
.error {
  color: var(--rose);
  margin: 0 0 16px;
}
.spacer {
  flex: 1 1 auto;
}
.buttons {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
</style>
