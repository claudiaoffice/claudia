<script setup lang="ts">
// What a document says about itself in a list: one line of its description and its tags as chips (D103: plain in the
// file, so everybody who may list the server reads it). The description is never HTML (`summaryOf`); a chip is a
// button that narrows the list to that tag, and says so (`aria-pressed`) for a screen reader (BITV). Where a search
// word was found is marked, and a document with nothing to say keeps the height of its neighbours.
import { computed } from 'vue'
import { summaryOf } from '~/lib/open'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{
    description?: string
    tags?: string[]
    /** The tag the list is narrowed to, if any. */
    active?: string
    /** The words being searched for. */
    words?: string[]
    /** How many chips fit on a line or two; the rest fold into "+N". */
    most?: number
    /** Show "No description yet" for a document that has none (a place's list, not Mine). */
    hint?: boolean
  }>(),
  { description: '', tags: () => [], active: '', words: () => [], most: 5, hint: true },
)
const emit = defineEmits<{ tag: [tag: string] }>()

const spans = computed(() => summaryOf(props.description))
const shownTags = computed(() => props.tags.slice(0, props.most))
const hidden = computed(() => Math.max(0, props.tags.length - props.most))
const found = (tag: string) => props.words.some((w) => w && tag.includes(w.toLowerCase()))
const tagOf = (s: { bold: boolean; italic: boolean; code?: boolean }) => (s.bold ? 'strong' : s.italic ? 'em' : s.code ? 'code' : 'span')
</script>

<template>
  <div v-if="spans.length || tags.length || hint" class="details">
    <p v-if="spans.length" class="summary">
      <component :is="tagOf(s)" v-for="(s, i) in spans" :key="i">{{ s.text }}</component>
    </p>
    <p v-else-if="hint && !tags.length" class="summary none">{{ t('No description yet') }}</p>
    <ul v-if="tags.length" class="chips" :aria-label="t('Tags')">
      <li v-for="tag in shownTags" :key="tag">
        <button type="button" class="chip" :class="{ on: active === tag, hit: found(tag) }" :aria-pressed="active === tag" @click="emit('tag', tag)">{{ tag }}</button>
      </li>
      <li v-if="hidden" class="more" :title="tags.slice(most).join(', ')">+{{ hidden }}</li>
    </ul>
  </div>
</template>

<style scoped>
.details {
  flex: 1 0 100%;
  margin: 0 0 4px;
  padding: 0 12px;
  min-width: 0;
}
.summary {
  margin: 2px 0;
  font-size: 12.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary.none {
  color: var(--muted);
  font-style: italic;
}
.summary strong {
  font-weight: 650;
}
.summary code {
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.92em;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  max-height: 3.4em;
  overflow: hidden;
  padding: 0;
  margin: 2px 0 0;
  list-style: none;
}
.chip {
  border: 1px solid transparent;
  border-radius: 999px;
  background: var(--app-soft);
  color: var(--text);
  font: 12px var(--font-ui);
  padding: 1px 9px;
  cursor: pointer;
}
.chip:hover,
.chip:focus-visible,
.chip.on {
  border-color: var(--app);
}
.chip.on {
  background: var(--app);
  color: #fff;
}
.chip.hit {
  outline: 2px solid var(--amber, #e6a23c);
  outline-offset: 0;
}
.more {
  color: var(--muted);
  font-size: 12px;
  align-self: center;
}
</style>
