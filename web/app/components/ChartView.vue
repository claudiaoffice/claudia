<script setup lang="ts">
// Draws one chart's Plotly figure (E6.6) in the frame of the chart object that holds it, on a sheet or on a slide
// (E6.31). The figure itself is never built here: the server computes it from the definition plus its sheet's live
// cells (`chart_figure`), so every client draws the same picture (`e0-3-web-surface-notes.md`). Plotly is bundled
// offline (D33/D42) and loaded lazily, so a document with no chart in sight never pays for it. The object that holds
// the view names it for a screen reader and takes the pointer; the view itself is only the picture.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ChartFigures } from '~/lib/charts'

const props = defineProps<{
  session: ChartFigures
  diagramId: string
  /** the chart object's own frame, in pixels */
  width: number
  height: number
}>()

const el = ref<HTMLDivElement | null>(null)
let plotly: typeof import('plotly.js-dist-min') | null = null
let drawn = false
let drawing = false
let redrawPending = false

const CONFIG = { displayModeBar: false, responsive: false }

async function draw() {
  if (drawing) {
    redrawPending = true
    return
  }
  drawing = true
  do {
    redrawPending = false
    await props.session.ensureFigure(props.diagramId)
    const figure = props.session.figureOf(props.diagramId)
    if (el.value && figure) {
      plotly ??= await import('plotly.js-dist-min')
      const target = el.value // (the chart may have gone while the chart library was loading)
      if (!target) break
      const layout = { ...figure.layout, width: props.width, height: props.height, margin: { t: 32, r: 16, b: 36, l: 48 }, autosize: false }
      await plotly.default.react(target, figure.data as Parameters<typeof plotly.default.react>[1], layout, CONFIG)
      drawn = true
    }
  } while (redrawPending)
  drawing = false
}

watch(() => [props.diagramId, props.width, props.height, props.session.figureOf(props.diagramId)] as const, draw)

onMounted(draw)

onBeforeUnmount(() => {
  if (drawn && el.value && plotly) plotly.default.purge(el.value)
})
</script>

<template>
  <div ref="el" class="chart-view" :style="{ width: `${width}px`, height: `${height}px` }" />
</template>

<style scoped>
.chart-view {
  pointer-events: none; /* the object's own frame handles drag/select; Plotly's hover stays visual only */
}
</style>
