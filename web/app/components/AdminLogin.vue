<script setup lang="ts">
// Signing in to a server that already has administrators (E3.11) — no mockup for this one; the first-admin-setup
// screen's own visual language (dark bar, Fraunces heading, iris primary button), minus the one-time "Keep this
// server local for now" escape, which only ever applies the moment a server is first bound to a real address.
//
// Unlike that screen, this one used to have no way out at all: `FirstAdminSetup.vue` has "Skip for now" and
// `AdminShell.vue` (once signed in) has its `×`, but a person who isn't signing in right now had nothing except
// the browser's own Back button (UX-11). `close`, below, is `AdminShell.vue`'s own `×` affordance, just reached
// one screen earlier.
import { ref } from 'vue'
import type { useAdminSession } from '~/lib/admin-session'
import { useI18n } from '~/lib/i18n'
import { useLoginWait } from '~/lib/login-wait'

const { t } = useI18n()

const props = defineProps<{ label: string; notice?: string; session: ReturnType<typeof useAdminSession> }>()
const emit = defineEmits<{ close: [] }>()

const name = ref('')
const password = ref('')
const formError = ref('')
const wait = useLoginWait() // failed sign-ins make the next one wait (D1266)

async function signIn() {
  formError.value = ''
  if (!name.value.trim() || !password.value) {
    formError.value = t('Fill in your name and password.')
    return
  }
  if (wait.waiting.value) return
  const error = await props.session.login(name.value.trim(), password.value)
  const seconds = props.session.waitAdvice.value
  if (seconds) wait.begin(seconds)
  else wait.clear()
  if (error && !seconds) formError.value = error
}
</script>

<template>
  <div class="login">
    <header class="bar">
      {{ t('Server settings') }}
      <button class="close" type="button" :aria-label="t('Close')" @click="emit('close')">×</button>
    </header>
    <form class="body" @submit.prevent="signIn">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--iris)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="shield">
        <path d="M12 2l8 3.5v5.3c0 5-3.4 8.9-8 10.2-4.6-1.3-8-5.2-8-10.2V5.5L12 2z" /><path d="M9.5 12l1.8 1.8 3.2-3.6" />
      </svg>
      <div role="status">
        <p v-if="notice" class="notice" data-testid="login-notice">{{ notice }}</p>
      </div>
      <h1>{{ t('Sign in to {label}', { label }) }}</h1>
      <p class="lead">{{ t('These settings are for administrators only. Sign in with your name and password to continue.') }}</p>

      <label class="field">{{ t('Your name') }}<input v-model="name" type="text" autocomplete="username" autofocus ></label>
      <label class="field">{{ t('Password') }}<PasswordInput v-model="password" autocomplete="current-password" /></label>

      <p v-if="formError" class="error" role="alert">{{ formError }}</p>
      <div role="status">
        <p v-if="wait.said.value" class="error" data-testid="login-wait">
          {{ wait.said.value }} <span v-if="wait.waiting.value" aria-hidden="true">({{ wait.left.value }} s)</span>
        </p>
      </div>

      <div class="spacer" />
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="session.busy.value || wait.waiting.value">{{ t('Sign in') }}</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.notice {
  margin: 0 0 18px;
  padding: 10px 14px;
  max-width: 520px;
  border-radius: 9px;
  border: 1px solid var(--apricot);
  background: color-mix(in srgb, var(--apricot) 10%, var(--surface));
  font-size: 13px;
  line-height: 1.5;
}
.login {
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
  position: relative;
  background: var(--ink);
  color: var(--paper);
  font: 500 14px var(--font-ui);
}
.close {
  position: absolute;
  right: 10px;
  top: 7px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: none;
  background: transparent;
  color: color-mix(in srgb, var(--paper) 60%, transparent);
  font-size: 16px;
}
.close:hover {
  background: color-mix(in srgb, var(--paper) 12%, transparent);
}
.body {
  flex: 1 1 auto;
  max-width: 440px;
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
.error {
  color: var(--rose);
  margin: 0 0 16px;
}
.spacer {
  flex: 1 1 auto;
}
.buttons {
  display: flex;
  justify-content: flex-end;
}
</style>
