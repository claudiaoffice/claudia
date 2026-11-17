<script setup lang="ts">
// The words of one paragraph as every view draws them: the slide being edited, its thumbnail and the presenter's
// slide (E9.22, step A of claudiaoffice-log/notes/text-structure-across-apps.md). One component, so that what one view
// shows — what a search found today, a list item's marker and the references in the text next (E9.30) — no view can
// be left without. The pieces come from `paragraph-pieces.ts`.
//
// A list item's marker or a numbered title's number (E9.21, E9.22) is drawn before the words, a marker gap away (the
// layout library's MARKER_GAP_EM, as composes and the printed pages have it); an item's level moves the words in. The
// marker is text a screen reader reads with the words, and never part of them: search marks count from the words.
//
// An agenda (E9.31) has no words of its own: `entries` are its lines, derived by the server from the slide titles, drawn
// as a list, each with its number, the title and, a dot leader away, its slide number.
import { computed } from 'vue'
import { leaderCss, MARKER_GAP_EM } from '@claudia/layout'
import { piecesOf, type Mark } from '~/lib/paragraph-pieces'
import type { ContentsEntry, Leader } from '~/lib/contents'
import { partsOf, type Shown } from '~/lib/references'
import { useI18n } from '~/lib/i18n'

const props = withDefaults(
  defineProps<{
    text: string
    marks?: readonly Mark[]
    marker?: string | null
    indent?: number
    entries?: readonly ContentsEntry[] | null
    leader?: Leader
    shown?: readonly Shown[] | null
  }>(),
  {
    marks: () => [],
    marker: null,
    indent: 0,
    entries: null,
    leader: 'dots',
    shown: null,
  },
)
const { t } = useI18n()
/** The pieces of the words, each cut at its references (step H): a reference reads as what the server derived. */
const pieces = computed(() => {
  let fields = 0
  return piecesOf(props.text, props.marks).map((piece) => {
    const parts = partsOf(piece.text, 0, fields)
    fields += parts.filter((p) => p.kind === 'field').length
    return { ...piece, parts }
  })
})
const referenceText = (index: number) => {
  const s = props.shown?.[index]
  return !s ? '#' : s.state === 'broken' ? `⚠ ${t('missing reference')}` : s.text || '#'
}
const gap = `${MARKER_GAP_EM}em`
</script>

<template>
  <span v-if="entries" class="agenda" role="list" data-agenda>
    <span v-for="entry in entries" :key="entry.target" class="line" role="listitem"
      ><span v-if="entry.number" class="marker" :style="{ marginRight: gap }">{{ entry.number }}</span><span class="title">{{ entry.text }}</span
      ><span v-if="entry.place" class="leader" :style="leaderCss(leader)" aria-hidden="true" /><span v-if="entry.place" class="place">{{ entry.place }}</span></span
    >
  </span>
  <span v-else class="text" :style="indent ? { display: 'block', paddingLeft: `${indent}em` } : undefined"><span v-if="marker" class="marker" data-marker :style="{ marginRight: gap }">{{ marker }}</span><template v-for="(piece, i) in pieces" :key="i"
      ><span v-if="piece.found" class="found" :class="{ now: piece.found === 'current' }" :data-found="piece.found"
        ><template v-for="(part, j) in piece.parts" :key="j"
          ><span v-if="part.kind === 'field'" class="ref" :class="shown?.[part.index]?.state" data-atom>{{ referenceText(part.index) }}</span
          ><template v-else>{{ part.text }}</template></template
        ></span
      ><template v-else
        ><template v-for="(part, j) in piece.parts" :key="j"
          ><span v-if="part.kind === 'field'" class="ref" :class="shown?.[part.index]?.state" data-atom>{{ referenceText(part.index) }}</span
          ><template v-else>{{ part.text }}</template></template
        ></template
      ></template
    ></span>
</template>

<style scoped>
.marker {
  user-select: none;
}
/* a reference (step H): a quiet iris underline; a broken one dashed, with its sign */
.ref {
  border-bottom: 0.08em solid var(--iris);
}
.ref.broken {
  color: var(--danger);
  border-bottom-style: dashed;
}
.agenda {
  display: block;
}
.line {
  display: flex;
  align-items: baseline;
}
.title {
  min-width: 0;
}
.place {
  font-variant-numeric: tabular-nums;
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
