<script setup lang="ts">
import { shallowRef } from 'vue'
import type { Session } from '~/lib/session'

const session = shallowRef<Session | null>(null)

function leave() {
  session.value?.close()
  session.value = null
}
</script>

<template>
  <Workspace v-if="session" :session="session" @leave="leave" />
  <OpenDialog v-else @opened="(s: Session) => (session = s)" />
</template>
