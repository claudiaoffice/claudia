<script setup lang="ts">
import { ref, shallowRef, watchEffect } from 'vue'
import { isSlides, isText, type AnySession } from '~/lib/open'
import { tabTitle } from '~/lib/shell-bridge'
import type { SlideSession } from '~/lib/slide-session'
import type { TextSession } from '~/lib/text-session'
import type { Session } from '~/lib/session'

// The server settings pages (E3.11) live at `/admin/` on this same bundle: there is no router anywhere in this
// app, so this is the one branch on the URL path, checked once since the path never changes without a real
// navigation (switching servers, and leaving the admin pages, are both full page loads — see server-bookmarks.ts).
const isAdmin = location.pathname === '/admin' || location.pathname.startsWith('/admin/')

const session = shallowRef<AnySession | null>(null)
/** File ▸ New asks to land on a blank document name, not the one just closed (File ▸ Open / Close document do not). */
const startFresh = ref(false)

function leave(opts?: { startFresh?: boolean }) {
  session.value?.close()
  session.value = null
  startFresh.value = !!opts?.startFresh
}

// Each app has its colour (tokens.css); the open dialog sets it for the app of the documents it lists. The tab
// title follows the same switch, so a person with several documents open in different tabs can tell them apart
// (previously every tab read "claudia computes", nuxt.config.ts's default, whichever app was actually open).
watchEffect(() => {
  if (session.value) document.documentElement.dataset.app = session.value.state.app
  document.title = tabTitle(session.value?.state.app)
})
</script>

<template>
  <AdminApp v-if="isAdmin" />
  <TextWorkspace v-else-if="session && isText(session)" :session="session as TextSession" @leave="leave" />
  <SlideWorkspace v-else-if="session && isSlides(session)" :session="session as SlideSession" @leave="leave" />
  <Workspace v-else-if="session" :session="session as Session" @leave="leave" />
  <OpenDialog v-else :start-fresh="startFresh" @opened="(s: AnySession) => (session = s)" />
</template>
