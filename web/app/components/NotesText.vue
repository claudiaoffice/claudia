<script setup lang="ts">
// The speaker notes of a slide, drawn from the Markdown (`lib/notes-markdown.ts`): lines of spans, never HTML. A link is
// shown with its address after it and is not something to click on during a talk.
import { computed } from 'vue'
import { parseNotes, type NoteLine } from '~/lib/notes-markdown'

const props = defineProps<{ notes: string }>()

interface Token {
  text: string
  bold: boolean
  italic: boolean
  code: boolean
  link: boolean
  /** The address of a link, after its last span. */
  url?: string
}

/** The spans of a line as tokens, the address of each link after the last span of it. */
function tokens(line: NoteLine): Token[] {
  const out: Token[] = []
  line.spans.forEach((span, i) => {
    const token: Token = { text: span.text, bold: span.bold, italic: span.italic, code: !!span.code, link: !!span.href }
    if (span.href && line.spans[i + 1]?.href !== span.href) token.url = span.href
    out.push(token)
  })
  return out
}

/** Emphasis is said in the element, not only drawn: a screen reader reads <strong> and <em> as such (BITV). */
const tagOf = (token: Token) => (token.bold ? 'strong' : token.italic ? 'em' : token.code ? 'code' : 'span')

const lines = computed(() => parseNotes(props.notes).map((line) => ({ line, tokens: tokens(line) })))
</script>

<template>
  <div class="notes-text" data-testid="notes-text">
    <template v-for="(row, i) in lines" :key="i">
      <p v-if="row.line.blank" class="gap" aria-hidden="true" />
      <p
        v-else
        :class="{ heading: row.line.heading, quote: row.line.quote, fenced: row.line.fenced, item: !!row.line.marker }"
        :style="row.line.level ? { marginInlineStart: `${row.line.level * 1.4}em` } : undefined"
      >
        <span v-if="row.line.marker" class="mark">{{ row.line.marker }}</span>
        <template v-for="(token, j) in row.tokens" :key="j">
          <component :is="tagOf(token)" :class="{ b: token.bold, i: token.italic, c: token.code, l: token.link }">{{ token.text }}</component
          ><span v-if="token.url" class="url"> ({{ token.url }})</span>
        </template>
      </p>
    </template>
  </div>
</template>

<style scoped>
.notes-text p {
  margin: 0;
  line-height: 1.45;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.gap {
  height: 0.7em;
}
.b {
  font-weight: 650;
}
.i {
  font-style: italic;
}
.c {
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.92em;
}
.l {
  text-decoration: underline;
  text-underline-offset: 2px;
}
.url {
  opacity: 0.7;
  font-size: 0.88em;
}
.mark {
  display: inline-block;
  min-width: 1.3em;
}
.heading {
  margin-top: 0.3em;
}
.quote {
  border-inline-start: 3px solid currentcolor;
  padding-inline-start: 0.7em;
  opacity: 0.85;
}
.fenced {
  font-family: var(--mono, ui-monospace, monospace);
  font-size: 0.92em;
}
</style>
