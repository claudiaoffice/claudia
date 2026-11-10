<script setup lang="ts">
// The server settings pages' own small root (E3.11) — reached at `/admin/` on this same bundle (app.vue branches on
// the path; there is no router). Decides, in order: does this server have no administrator at all yet; is nobody
// signed in yet (try the stored token once, then ask); otherwise, which page of the shell to show.
import { onMounted, ref } from 'vue'
import { adminApi, AdminApiError, hasNoAdministrator } from '~/lib/admin-api'
import { useAdminSession } from '~/lib/admin-session'
import { friendlyLabel } from '~/lib/connection'
import { defaultLabel, upsert } from '~/lib/server-bookmarks'

const host = location.host
const origin = location.origin

const loading = ref(true)
const loadError = ref('')
// Whether to offer becoming the first administrator — `administrator === null` (nobody has ever become one), not
// `needs_administrator` (which also requires the server to be exposed beyond loopback): a server that only ever
// runs on loopback is never *forced* through this screen (D152), but someone who navigates here directly can still
// choose to set up an account, e.g. before exposing the server later or just to use these pages from now on.
const noAdministrator = ref(false)
const exposed = ref(false)
// Starts as the bare host (whatever a bookmark from an earlier visit already says, if there is one) and is
// refreshed below once this visit's own `/api/admin/status` call resolves — `friendlyLabel`/`upsert` read and
// write localStorage, which gives Vue nothing to react to on its own.
const label = ref(friendlyLabel(origin, host))
const active = ref<'ai' | 'typeset' | 'access'>('ai')
const session = useAdminSession()

onMounted(async () => {
  try {
    const status = await adminApi.status()
    noAdministrator.value = hasNoAdministrator(status)
    exposed.value = status.exposed
    // Reaching the settings pages directly (not through the Open dialog) is a fine way to arrive here, so this
    // bookmarks the server too — same default-label rule as OpenDialog.vue's own `loadServer`.
    upsert(origin, defaultLabel(origin, status.administrator))
    label.value = friendlyLabel(origin, host)
    if (!noAdministrator.value) await session.refresh()
  } catch (e) {
    loadError.value = e instanceof AdminApiError ? e.message : 'Could not reach this server.'
  } finally {
    loading.value = false
  }
})

function close() {
  location.href = '/'
}
</script>

<template>
  <div class="admin-app">
    <p v-if="loadError" class="load-error" role="alert">{{ loadError }}</p>
    <template v-else-if="!loading">
      <FirstAdminSetup v-if="noAdministrator" :host="host" :exposed="exposed" :session="session" />
      <AdminLogin v-else-if="!session.name.value" :label="label" :session="session" @close="close" />
      <AdminShell v-else :label="label" :host="host" :signed-in-as="session.name.value" :active="active" @navigate="active = $event" @sign-out="session.logout()" @close="close">
        <AdminAiModel v-if="active === 'ai'" :token="session.token.value!" />
        <AdminTypesetting v-else-if="active === 'typeset'" :token="session.token.value!" />
        <AdminAccessDocuments v-else :token="session.token.value!" />
      </AdminShell>
    </template>
    <p v-else class="loading">Loading…</p>
  </div>
</template>

<style scoped>
.admin-app {
  height: 100%;
  background: var(--page);
  color: var(--text);
}
.load-error {
  margin: 40px auto;
  max-width: 480px;
  text-align: center;
  color: var(--rose);
}
.loading {
  margin: 40px auto;
  text-align: center;
  color: var(--muted);
}
</style>
