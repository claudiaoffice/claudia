<script setup lang="ts">
// The words of one paragraph as every view draws them: the slide being edited, its thumbnail and the presenter's
// slide (E9.22, step A of claudiaoffice-log/notes/text-structure-across-apps.md). One component, so that what one view
// shows — what a search found today, a list item's marker and the references in the text next (E9.30) — no view can
// be left without. The pieces come from `paragraph-pieces.ts`.
import { computed } from 'vue'
import { piecesOf, type Mark } from '~/lib/paragraph-pieces'

const props = withDefaults(defineProps<{ text: string; marks?: readonly Mark[] }>(), { marks: () => [] })
const pieces = computed(() => piecesOf(props.text, props.marks))
</script>

<template>
  <span class="text"><template v-for="(piece, i) in pieces" :key="i"><span v-if="piece.found" class="found" :class="{ now: piece.found === 'current' }" :data-found="piece.found">{{ piece.text }}</span><template v-else>{{ piece.text }}</template></template></span>
</template>

<style scoped>
/* what a search found (E10.19, E9.28): a band and an underline, never colour alone; the one being looked at has an
   outline too */
.found {
  background: color-mix(in srgb, var(--purpose-input) 55%, transparent);
  border-bottom: 3px solid var(--app);
}
.found.now {
  outline: 2px solid var(--ink);
  outline-offset: 1px;
  background: color-mix(in srgb, var(--purpose-input) 80%, transparent);
}
</style>
