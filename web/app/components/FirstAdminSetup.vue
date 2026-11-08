<script setup lang="ts">
// Naming the first administrator (E3.11; canvas note s7). Shown once: the moment a server is bound to a real
// address instead of staying loopback-only, `needs_administrator` turns true until somebody becomes one.
import { ref } from 'vue'
import type { useAdminSession } from '~/lib/admin-session'

const props = defineProps<{ host: string; session: ReturnType<typeof useAdminSession> }>()

const name = ref('')
const password = ref('')
const confirmPassword = ref('')
const formError = ref('')

async function create() {
  formError.value = ''
  if (!name.value.trim() || !password.value) {
    formError.value = 'Fill in your name and a password.'
    return
  }
  if (password.value !== confirmPassword.value) {
    formError.value = 'The passwords do not match.'
    return
  }
  const error = await props.session.setup(name.value.trim(), password.value)
  if (error) formError.value = error
}

function keepLocal() {
  location.href = '/'
}
</script>

<template>
  <div class="setup">
    <header class="bar">Server settings</header>
    <form class="body" @submit.prevent="create">
      <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="var(--iris)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="shield">
        <path d="M12 2l8 3.5v5.3c0 5-3.4 8.9-8 10.2-4.6-1.3-8-5.2-8-10.2V5.5L12 2z" /><path d="M9.5 12l1.8 1.8 3.2-3.6" />
      </svg>
      <h1>Name yourself as this server's administrator</h1>
      <p class="lead">{{ host }} can now be reached from outside this computer. Before anyone else can reach it, set a name and password for yourself — you'll use them to sign in here from now on.</p>

      <label class="field">Your name<input v-model="name" type="text" autocomplete="username" placeholder="tobi" /></label>
      <label class="field">Password<input v-model="password" type="password" autocomplete="new-password" placeholder="••••••••••" /></label>
      <label class="field">Confirm password<input v-model="confirmPassword" type="password" autocomplete="new-password" placeholder="••••••••••" /></label>

      <div class="note">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <rect x="3" y="11" width="18" height="10" rx="2" /><path d="M7 11V7a5 5 0 0110 0v4" />
        </svg>
        <span>The access secret you set earlier stays as a recovery key — only needed if every administrator is ever locked out.</span>
      </div>

      <p v-if="formError" class="error" role="alert">{{ formError }}</p>

      <div class="spacer" />
      <div class="buttons">
        <button class="btn" type="button" :disabled="session.busy.value" @click="keepLocal">Keep this server local for now</button>
        <button class="btn primary" type="submit" :disabled="session.busy.value">Create administrator</button>
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
