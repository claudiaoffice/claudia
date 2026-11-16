<script setup lang="ts">
// The words of one paragraph as every view draws them: the slide being edited, its thumbnail and the presenter's
// slide (E9.22, step A of claudiaoffice-log/notes/text-structure-across-apps.md). One component, so that what one view
// shows — what a search found today, a list item's marker and the references in the text next (E9.30) — no view can
// be left without. The pieces come from `paragraph-pieces.ts`.
//
// A list item's marker or a numbered title's number (E9.21, E9.22) is drawn before the words, a marker gap away (the
// layout library's MARKER_GAP_EM, as composes and the printed pages have it); an item's level moves the words in. The
// marker is text a screen reader reads with the words, and never part of them: search marks count from the words.
import { computed } from 'vue'
import { MARKER_GAP_EM } from '@claudia/layout'
import { piecesOf, type Mark } from '~/lib/paragraph-pieces'

const props = withDefaults(defineProps<{ text: string; marks?: readonly Mark[]; marker?: string | null; indent?: number }>(), {
  marks: () => [],
  marker: null,
  indent: 0,
})
const pieces = computed(() => piecesOf(props.text, props.marks))
const gap = `${MARKER_GAP_EM}em`
</script>

<template>
  <span class="text" :style="indent ? { display: 'block', paddingLeft: `${indent}em` } : undefined"><span v-if="marker" class="marker" data-marker :style="{ marginRight: gap }">{{ marker }}</span><template v-for="(piece, i) in pieces" :key="i"><span v-if="piece.found" class="found" :class="{ now: piece.found === 'current' }" :data-found="piece.found">{{ piece.text }}</span><template v-else>{{ piece.text }}</template></template></span>
</template>

<style scoped>
.marker {
  user-select: none;
}
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
