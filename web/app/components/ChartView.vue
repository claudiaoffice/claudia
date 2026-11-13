<script setup lang="ts">
// Draws one chart's Plotly figure (E6.6) — used both for a chart tab (fills its space, responsive) and for a
// floating diagram object on a sheet (a fixed pixel frame, matching the object's own `w`/`h`). The figure
// itself is never built here: the server computes it from the definition plus its sheet's live cells
// (`chart_figure`), so every client draws the same picture (`e0-3-web-surface-notes.md`). Plotly is bundled
// offline (D33/D42) and loaded lazily, so a document with no chart in sight never pays for it.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Session } from '~/lib/session'

const props = defineProps<{
  session: Session
  diagramId: string
  /** A fixed pixel frame (a floating object's own size); omitted for a tab, which fills its container and
   * redraws on resize instead. */
  width?: number
  height?: number
}>()

const el = ref<HTMLDivElement | null>(null)
let plotly: typeof import('plotly.js-dist-min') | null = null
let drawn = false
let drawing = false
let redrawPending = false
let resizeObserver: ResizeObserver | null = null

const CONFIG = { displayModeBar: false, responsive: props.width === undefined }

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
      const layout = {
        ...figure.layout,
        ...(props.width === undefined ? {} : { width: props.width, height: props.height }),
        margin: { t: 32, r: 16, b: 36, l: 48 },
        autosize: props.width === undefined,
      }
      await plotly.default.react(el.value, figure.data as Parameters<typeof plotly.default.react>[1], layout, CONFIG)
      drawn = true
    }
  } while (redrawPending)
  drawing = false
}

watch(() => [props.diagramId, props.width, props.height, props.session.figureOf(props.diagramId)] as const, draw)

onMounted(async () => {
  await draw()
  if (props.width === undefined && el.value) {
    resizeObserver = new ResizeObserver(() => {
      if (drawn && el.value && plotly) void plotly.default.Plots.resize(el.value)
    })
    resizeObserver.observe(el.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (drawn && el.value && plotly) plotly.default.purge(el.value)
})
</script>

<template>
  <div ref="el" class="chart-view" :class="{ fixed: width !== undefined }" :style="width !== undefined ? { width: `${width}px`, height: `${height}px` } : {}" />
</template>

<style scoped>
.chart-view {
  width: 100%;
  height: 100%;
  min-height: 0;
}
.chart-view.fixed {
  pointer-events: none; /* the floating object's own `.object` div handles drag/select; Plotly's hover stays visual only */
}
</style>
