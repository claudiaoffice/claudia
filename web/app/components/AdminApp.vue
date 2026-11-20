<script setup lang="ts">
// The server settings pages' own small root (E3.11) — reached at `/admin/` on this same bundle (app.vue branches on
// the path; there is no router). Decides, with `adminScreen`: somebody signed in sees the settings; otherwise, does this
// server have no administrator at all yet, or is it to ask who signs in (after trying the stored token once).
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { adminApi, AdminApiError, adminScreen, hasNoAdministrator } from '~/lib/admin-api'
import { useAdminSession } from '~/lib/admin-session'
import { friendlyLabel } from '~/lib/connection'
import { defaultLabel, upsert } from '~/lib/server-bookmarks'
import { forgetSetupCode } from '~/lib/setup-code'
import { createShellBridge } from '~/lib/shell-bridge'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

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
/** Does `setup` ask for a setup code (D1370)? */
const setupCode = ref(false)
/** A line on top of the sign-in, after somebody else named the first administrator meanwhile (409). */
const notice = ref('')
// Starts as the bare host (whatever a bookmark from an earlier visit already says, if there is one) and is
// refreshed below once this visit's own `/api/admin/status` call resolves — `friendlyLabel`/`upsert` read and
// write localStorage, which gives Vue nothing to react to on its own.
const label = ref(friendlyLabel(origin, host))
// `/admin/#fonts` opens on the fonts page: where the banner of a document that lacks a font sends an administrator.
const active = ref<'ai' | 'typeset' | 'fonts' | 'security' | 'access'>(location.hash === '#fonts' ? 'fonts' : 'ai')
const session = useAdminSession()
const screen = computed(() => adminScreen(noAdministrator.value, session.name.value))
// Once somebody is signed in, the server has an administrator: signing out later asks who signs in, rather than
// offering to become the first one again.
watch(session.name, (name) => {
  if (name) {
    noAdministrator.value = false
    forgetSetupCode() // an administrator exists: the code is spent
  }
})

function taken() {
  noAdministrator.value = false
  forgetSetupCode() // somebody else spent it
  notice.value = t("Someone has named this server's first administrator in the meantime. Sign in, or ask them to add you.")
}

// In a desktop app, the page says hello like the front page does, so that the app's welcome hands over its own
// server's setup code (D1373); in a browser tab there is nobody to talk to and this does nothing.
const shell = createShellBridge(undefined, undefined, undefined, 'start')
onUnmounted(() => shell.detach())

onMounted(async () => {
  try {
    const status = await adminApi.status()
    noAdministrator.value = hasNoAdministrator(status)
    exposed.value = status.exposed
    setupCode.value = status.setup_code === true
    // Reaching the settings pages directly (not through the Open dialog) is a fine way to arrive here, so this
    // bookmarks the server too — same default-label rule as OpenDialog.vue's own `loadServer`.
    upsert(origin, defaultLabel(origin, status.administrator))
    label.value = friendlyLabel(origin, host)
    if (!noAdministrator.value) await session.refresh()
  } catch (e) {
    loadError.value = e instanceof AdminApiError ? e.message : t('Could not reach this server.')
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
      <FirstAdminSetup v-if="screen === 'setup'" :host="host" :exposed="exposed" :setup-code="setupCode" :session="session" @taken="taken" />
      <AdminLogin v-else-if="screen === 'sign-in'" :label="label" :notice="notice" :session="session" @close="close" />
      <AdminShell v-else-if="session.name.value" :label="label" :host="host" :signed-in-as="session.name.value" :active="active" @navigate="active = $event" @sign-out="session.logout()" @close="close">
        <AdminAiModel v-if="active === 'ai'" :token="session.token.value!" />
        <AdminTypesetting v-else-if="active === 'typeset'" :token="session.token.value!" />
        <AdminFonts v-else-if="active === 'fonts'" :token="session.token.value!" :server="label" />
        <AdminSecurity v-else-if="active === 'security'" :token="session.token.value!" />
        <AdminAccessDocuments v-else :token="session.token.value!" />
      </AdminShell>
    </template>
    <p v-else class="loading">{{ t('Loading…') }}</p>
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
