<script setup lang="ts">
import { shallowRef, watchEffect } from 'vue'
import { isSlides, isText, type AnySession } from '~/lib/open'
import type { SlideSession } from '~/lib/slide-session'
import type { TextSession } from '~/lib/text-session'
import type { Session } from '~/lib/session'

const session = shallowRef<AnySession | null>(null)

function leave() {
  session.value?.close()
  session.value = null
}

// Each app has its colour (tokens.css); the open dialog sets it for the app of the documents it lists.
watchEffect(() => {
  if (session.value) document.documentElement.dataset.app = session.value.state.app
})
</script>

<template>
  <TextWorkspace v-if="session && isText(session)" :session="session as TextSession" @leave="leave" />
  <SlideWorkspace v-else-if="session && isSlides(session)" :session="session as SlideSession" @leave="leave" />
  <Workspace v-else-if="session" :session="session as Session" @leave="leave" />
  <OpenDialog v-else @opened="(s: AnySession) => (session = s)" />
</template>
