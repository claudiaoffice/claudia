<script setup lang="ts">
// Server settings — Access & documents. Who may configure this server, who may create or list documents, and how
// many it holds. Administrators, the access secret and the document cap are three independent backend calls
// (admin_api.py has a separate route for each), so each acts the moment its own button is pressed — only the
// document cap behaves like a draft, which is what the shared Cancel/Apply footer governs.
import { computed, onMounted, ref } from 'vue'
import { adminApi, AdminApiError, type AdminAccount, type ServerSettingsView } from '~/lib/admin-api'
import { ago, initial } from '~/lib/people'

const props = defineProps<{ token: string }>()

const settings = ref<ServerSettingsView | null>(null)
const admins = ref<AdminAccount[]>([])
const loading = ref(true)
const loadError = ref('')

const PALETTE = ['--teal', '--rose', '--apricot', '--iris']
function avatarColor(i: number): string {
  return `var(${PALETTE[i % PALETTE.length]})`
}

async function loadAll() {
  try {
    const [s, a] = await Promise.all([adminApi.getSettings(props.token), adminApi.listAdmins(props.token)])
    settings.value = s
    admins.value = a
    maxDocuments.value = s.max_documents
  } catch (e) {
    loadError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    loading.value = false
  }
}
onMounted(loadAll)

// ---- administrators
const adding = ref(false)
const newName = ref('')
const newPassword = ref('')
const addBusy = ref(false)
const addError = ref('')

function startAdd() {
  adding.value = true
  newName.value = ''
  newPassword.value = ''
  addError.value = ''
}
async function confirmAdd() {
  addBusy.value = true
  addError.value = ''
  try {
    admins.value = [...admins.value, await adminApi.addAdmin(props.token, newName.value.trim(), newPassword.value)]
    adding.value = false
  } catch (e) {
    addError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    addBusy.value = false
  }
}

const removing = ref<string | null>(null)
const removeError = ref('')
async function remove(account: AdminAccount) {
  removing.value = account.name
  removeError.value = ''
  try {
    await adminApi.removeAdmin(props.token, account.name)
    admins.value = admins.value.filter((a) => a.name !== account.name)
  } catch (e) {
    removeError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    removing.value = null
  }
}

const changingPasswordFor = ref<string | null>(null)
const newOwnPassword = ref('')
const passwordBusy = ref(false)
const passwordError = ref('')
function startPasswordChange(account: AdminAccount) {
  changingPasswordFor.value = account.name
  newOwnPassword.value = ''
  passwordError.value = ''
}
async function confirmPasswordChange() {
  if (!changingPasswordFor.value) return
  passwordBusy.value = true
  passwordError.value = ''
  try {
    await adminApi.changeAdminPassword(props.token, changingPasswordFor.value, newOwnPassword.value)
    changingPasswordFor.value = null
  } catch (e) {
    passwordError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    passwordBusy.value = false
  }
}

// ---- access secret
const secretBusy = ref(false)
const secretError = ref('')
const secretValue = ref<string | null>(null)
const secretVisible = ref(false)
const secretOn = computed(() => settings.value?.access_secret_set ?? false)

async function toggleSecret(on: boolean) {
  secretBusy.value = true
  secretError.value = ''
  try {
    if (on) {
      const result = await adminApi.rotateAccessSecret(props.token)
      settings.value = result
      secretValue.value = result.access_secret
      secretVisible.value = true
    } else {
      settings.value = await adminApi.putAccessSecret(props.token, null)
      secretValue.value = null
      secretVisible.value = false
    }
  } catch (e) {
    secretError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    secretBusy.value = false
  }
}

async function reveal() {
  if (secretVisible.value) {
    secretVisible.value = false
    return
  }
  secretBusy.value = true
  secretError.value = ''
  try {
    secretValue.value = (await adminApi.revealAccessSecret(props.token)).access_secret
    secretVisible.value = true
  } catch (e) {
    secretError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    secretBusy.value = false
  }
}

async function rotate() {
  if (!confirm('Replace the access secret? Anyone using the old one will need the new one — this never signs an administrator out.')) return
  secretBusy.value = true
  secretError.value = ''
  try {
    const result = await adminApi.rotateAccessSecret(props.token)
    settings.value = result
    secretValue.value = result.access_secret
    secretVisible.value = true
  } catch (e) {
    secretError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    secretBusy.value = false
  }
}

// ---- documents
const maxDocuments = ref(1000)
const docBusy = ref(false)
const docError = ref('')
function cancelDocs() {
  if (settings.value) maxDocuments.value = settings.value.max_documents
  docError.value = ''
}
async function applyDocs() {
  docBusy.value = true
  docError.value = ''
  try {
    settings.value = await adminApi.setMaxDocuments(props.token, maxDocuments.value)
  } catch (e) {
    docError.value = e instanceof AdminApiError ? e.message : 'Could not reach the server.'
  } finally {
    docBusy.value = false
  }
}
</script>

<template>
  <div v-if="!loading && settings">
    <h1>Access &amp; documents</h1>
    <p class="lead">Who may change these settings, who may create or list documents, and how many this server holds.</p>
    <p v-if="loadError" class="error" role="alert">{{ loadError }}</p>

    <h2>Administrators</h2>
    <div class="card">
      <div v-for="(a, i) in admins" :key="a.name" class="admin-row">
        <span class="avatar" :style="{ background: avatarColor(i) }">{{ initial(a.name) }}</span>
        <div class="who">
          <div class="name-line">
            <span class="name">{{ a.name }}</span>
            <span v-if="a.you" class="you">you</span>
          </div>
          <div class="since">{{ a.you ? 'Administrator since' : 'Added' }} {{ ago(a.added) }}</div>
          <template v-if="changingPasswordFor === a.name">
            <form class="inline-form" @submit.prevent="confirmPasswordChange">
              <input v-model="newOwnPassword" type="password" placeholder="New password (at least 8 characters)" autocomplete="new-password" autofocus />
              <button class="btn primary small" type="submit" :disabled="passwordBusy">Save</button>
              <button class="btn small" type="button" :disabled="passwordBusy" @click="changingPasswordFor = null">Cancel</button>
            </form>
            <p v-if="passwordError" class="error">{{ passwordError }}</p>
          </template>
        </div>
        <button class="btn small" type="button" @click="startPasswordChange(a)">Change password</button>
        <button v-if="!a.you" class="btn small" type="button" :disabled="removing === a.name" @click="remove(a)">Remove</button>
      </div>
    </div>
    <p v-if="removeError" class="error">{{ removeError }}</p>

    <template v-if="adding">
      <form class="inline-form add-form" @submit.prevent="confirmAdd">
        <input v-model="newName" placeholder="Name" autocomplete="off" autofocus />
        <input v-model="newPassword" type="password" placeholder="Password (at least 8 characters)" autocomplete="new-password" />
        <button class="btn primary small" type="submit" :disabled="addBusy">Add</button>
        <button class="btn small" type="button" :disabled="addBusy" @click="adding = false">Cancel</button>
      </form>
      <p v-if="addError" class="error">{{ addError }}</p>
    </template>
    <button v-else type="button" class="dashed" @click="startAdd">+ Add administrator…</button>

    <h2>Access secret</h2>
    <div class="card">
      <div class="secret-row">
        <div class="desc">
          <div class="title">Require a secret to create or list documents</div>
          <div class="sub">Without one, only this machine may create documents.</div>
        </div>
        <ToggleSwitch :model-value="secretOn" label="Require a secret to create or list documents" :disabled="secretBusy" @update:model-value="toggleSecret" />
      </div>
      <div v-if="secretOn" class="secret-row reveal-row">
        <div class="reveal">
          <span class="value mono">{{ secretVisible && secretValue ? secretValue : '•••••••••••••••••••••' }}</span>
          <button class="btn small" type="button" :disabled="secretBusy" @click="reveal">{{ secretVisible ? 'Hide' : 'Reveal' }}</button>
        </div>
        <button class="btn danger small" type="button" :disabled="secretBusy" @click="rotate">Rotate secret</button>
      </div>
    </div>
    <p v-if="secretError" class="error">{{ secretError }}</p>
    <p class="hint">A recovery key, not needed day to day — administrators sign in with their own name and password instead. Rotating it doesn't sign anyone out.</p>

    <h2>Documents</h2>
    <div class="card">
      <div class="secret-row">
        <div class="desc">
          <div class="title">Maximum documents</div>
          <div class="sub">A request beyond this number is refused before anything is written.</div>
        </div>
        <input v-model.number="maxDocuments" type="number" min="1" class="mono narrow" />
      </div>
    </div>

    <AdminPageFooter :changed="settings.changed.max_documents ?? null" :busy="docBusy" :error="docError" @cancel="cancelDocs" @apply="applyDocs" />
  </div>
</template>

<style scoped>
h1 {
  margin: 0 0 4px;
  font: 500 23px/1.3 var(--font-display);
}
h2 {
  margin: 20px 0 8px;
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
  margin-bottom: 10px;
}
.admin-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-top: 1px solid var(--line);
}
.admin-row:first-child {
  border-top: none;
}
.avatar {
  width: 26px;
  height: 26px;
  flex: none;
  border-radius: 50%;
  color: var(--paper);
  font: 600 12px var(--font-ui);
  display: flex;
  align-items: center;
  justify-content: center;
}
.who {
  flex: 1;
  min-width: 0;
}
.name-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.name {
  font: 500 14px var(--font-ui);
}
.you {
  padding: 2px 8px;
  border-radius: 20px;
  background: var(--app-soft);
  color: var(--app-text);
  font: 600 10.5px var(--font-ui);
  letter-spacing: 0.02em;
}
.since {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}
.inline-form {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.inline-form input {
  flex: 1;
  min-width: 0;
  padding: 6px 9px;
  border-radius: 7px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  font: 13px var(--font-ui);
}
.add-form {
  margin: 4px 0 0;
}
.dashed {
  margin: 0 0 24px;
  padding: 9px 16px;
  border: 1px dashed var(--line-field);
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font: 500 13px var(--font-ui);
}
.secret-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
}
.reveal-row {
  border-top: 1px solid var(--line);
}
.desc {
  max-width: 420px;
}
.title {
  font: 500 14px var(--font-ui);
}
.sub {
  font-size: 12.5px;
  color: var(--muted);
  margin-top: 3px;
  line-height: 1.5;
}
.reveal {
  display: flex;
  align-items: center;
  gap: 10px;
}
.value.mono {
  font: 13px var(--font-mono);
  letter-spacing: 0.08em;
  color: var(--text);
}
.hint {
  margin: 10px 0 24px;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
}
.mono {
  font-family: var(--font-mono);
}
.narrow {
  width: 84px;
  flex: none;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--line-field);
  background: var(--surface);
  color: var(--text);
  text-align: right;
}
.btn.small {
  padding: 5px 11px;
  font-size: 12px;
}
.error {
  color: var(--rose);
  margin: 6px 0 0;
}
</style>
