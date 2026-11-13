<script setup lang="ts">
// File ▸ Print… (D906, D918): the main window shows the pages instead of the document. The pages are laid out here,
// in this browser, by the layout library (D901), and drawn from the very display list the PDF is written from: Print
// hands that PDF to the browser's print dialog, Download PDF saves it. How a document prints belongs to it (D904,
// D917): changing it is a step in the history, for everybody. One component for every app that prints: what it
// prints and what it offers comes from a `PrintSource` (`lib/print/source.ts`), so the bar reads the same everywhere.
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import type { PageSetupData, SlideLayout } from '@claudia/layout'
import { printAssets, type PrintAssets } from '~/lib/print/assets'
import { facesOf, pageSvg, registerFaces } from '~/lib/print/paint'
import { marginPreset, mm, withCustomSize, withPaper } from '~/lib/print/setup'
import { fromBase64 } from '~/lib/print/document'
import { pdfOfPages, type PrintPages, type PrintSource } from '~/lib/print/source'

const props = defineProps<{ source: PrintSource }>()
const emit = defineEmits<{ close: [] }>()
const source = props.source

const page = computed<PageSetupData>(() => source.page())
const canChange = computed(() => source.canChange())
const assets = shallowRef<PrintAssets | null>(null)
const result = shallowRef<PrintPages | null>(null)
/** The page setup `result` was laid out on (the one shown; `page` may be newer while a layout runs). */
const laidOn = shallowRef<PageSetupData | null>(null)
const svgs = ref<string[]>([])
const problem = ref<string | null>(null)
const busy = ref(true)
const images = new Map<string, Uint8Array>()
const imageUrls = new Map<string, string>()
const zoom = ref<'two' | 'width' | number>('two')
const canvas = ref<HTMLElement | null>(null)
const width = ref(1000)
const customOpen = ref(false)
const custom = ref({ w: mm(page.value.width), h: mm(page.value.height) })

/** The type of a picture's bytes, for showing it. */
const mimeOf = (b: Uint8Array) =>
  b[0] === 0x89 ? 'image/png' : b[0] === 0xff ? 'image/jpeg' : b[0] === 0x47 ? 'image/gif' : b[0] === 0x42 ? 'image/bmp' : 'application/octet-stream'
/** The document's pictures as bytes (for the PDF) and as URLs (for the screen); each is decoded once. */
function takeImages() {
  for (const img of source.images()) {
    if (images.has(img.id)) continue
    const bytes = fromBase64(img.data)
    images.set(img.id, bytes)
    imageUrls.set(img.id, URL.createObjectURL(new Blob([bytes as BlobPart], { type: img.format === 'svg' ? 'image/svg+xml' : `image/${img.format}` })))
  }
}

// ------------------------------------------------------------------------------ laying out
let run = 0
let current: Promise<void> = Promise.resolve()
async function relayout() {
  const mine = ++run
  try {
    const a = (assets.value ??= await printAssets())
    const setup = page.value
    takeImages()
    const laid = await source.layOut(a)
    // the pictures SVG pictures carry inside them, for the screen
    for (const [id, bytes] of laid.embedded) if (!imageUrls.has(id)) imageUrls.set(id, URL.createObjectURL(new Blob([bytes as BlobPart], { type: mimeOf(bytes) })))
    await registerFaces(a.fonts, facesOf(laid.list.pages))
    if (mine !== run) return
    result.value = laid
    laidOn.value = setup
    svgs.value = laid.list.pages.map((p, i) => pageSvg(p, (id) => imageUrls.get(id), `pg${i}`))
    problem.value = null
  } catch (e) {
    if (mine === run) problem.value = (e as Error).message
  } finally {
    if (mine === run) busy.value = false
  }
}
let timer: ReturnType<typeof setTimeout> | null = null
function soon() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    timer = null
    current = relayout()
  }, 120)
}
/** The pages as the document and its print setup are now: a layout that is waiting runs at once. */
async function settled(): Promise<PrintPages | null> {
  if (timer) {
    clearTimeout(timer)
    timer = null
    current = relayout()
  }
  let seen: Promise<void>
  do {
    seen = current
    await seen
  } while (seen !== current)
  return result.value
}
watch(() => source.watched(), soon, { deep: true })

onMounted(async () => {
  window.addEventListener('keydown', onKey, true)
  const observer = new ResizeObserver(() => (width.value = canvas.value?.clientWidth ?? 1000))
  if (canvas.value) observer.observe(canvas.value)
  onBeforeUnmount(() => observer.disconnect())
  await source.prepare()
  current = relayout()
  await current
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey, true)
  for (const url of imageUrls.values()) URL.revokeObjectURL(url)
  frame?.remove()
  if (timer) clearTimeout(timer)
})

// ------------------------------------------------------------------------------ the bar
function change(next: PageSetupData) {
  if (canChange.value) source.setPage(next)
}
function chooseLayout(layout: string) {
  if (canChange.value) source.setLayout(layout as SlideLayout)
}
function choosePaper(id: string) {
  if (id === 'custom') {
    custom.value = { w: mm(page.value.width), h: mm(page.value.height) }
    customOpen.value = true
    return
  }
  customOpen.value = false
  change(source.withPaper?.(page.value, id) ?? withPaper(page.value, id))
}
function applyCustom() {
  customOpen.value = false
  const { w, h } = custom.value
  if (w >= 25 && h >= 25 && w <= 1200 && h <= 1200) change(withCustomSize(page.value, w, h))
}
// ------------------------------------------------------------------------------ the language (D915)
/** The languages offered: those the server can hyphenate, and the document's own if it is another one. */
const languages = computed(() => {
  // short names for a narrow bar: "German", and the region where one language comes twice: "English (GB)"
  const all = assets.value?.languages ?? []
  const base = (name: string) => name.replace(/\s*\(.*\)$/, '')
  const listed = all.map((l) => {
    const twice = all.filter((o) => base(o.name) === base(l.name)).length > 1
    const region = l.tag.split('-')[1]
    return { tag: l.tag, name: twice && region ? `${base(l.name)} (${region})` : base(l.name), title: l.name }
  })
  const own = source.language()
  if (own && !listed.some((l) => l.tag.toLowerCase() === own.toLowerCase())) listed.push({ tag: own, name: own, title: `${own}: no hyphenation patterns on this server` })
  return listed.sort((a, b) => a.name.localeCompare(b.name))
})
const canSetLanguage = computed(() => source.canSetLanguage())
function chooseLanguage(tag: string) {
  if (canSetLanguage.value) source.setLanguage(tag || null)
}

function chooseMargins(id: string) {
  const m = source.margins.find((x) => x.id === id)
  if (m) change({ ...page.value, margins: [m.mpt, m.mpt, m.mpt, m.mpt] })
}

// ------------------------------------------------------------------------------ zoom
const PX_PER_MPT = 96 / 72 / 1000
const scale = computed(() => {
  const w = page.value.orientation === 'landscape' ? page.value.height : page.value.width
  if (zoom.value === 'two') return Math.max(0.2, (width.value - 120) / 2 / (w * PX_PER_MPT))
  if (zoom.value === 'width') return Math.max(0.2, (width.value - 80) / (w * PX_PER_MPT))
  return zoom.value
})
const zoomLabel = computed(() => (zoom.value === 'two' ? 'Two pages' : zoom.value === 'width' ? 'Fit width' : `${Math.round(scale.value * 100)} %`))
const zoomBy = (f: number) => (zoom.value = Math.min(4, Math.max(0.25, Math.round(scale.value * f * 100) / 100)))
const pageStyle = computed(() => {
  const g = result.value?.geometry
  return g ? { width: `${g.width * PX_PER_MPT * scale.value}px`, height: `${g.height * PX_PER_MPT * scale.value}px` } : {}
})

// ------------------------------------------------------------------------------ out
async function pdf(): Promise<Uint8Array | null> {
  const r = await settled()
  const a = assets.value
  return a && r ? pdfOfPages(a, r, images, source) : null
}
async function download() {
  const bytes = await pdf()
  if (!bytes) return
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/pdf' }))
  a.download = `${source.title()}.pdf`
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 60_000)
}
let frame: HTMLIFrameElement | null = null
/** The PDF goes to the browser's own print dialog, in a frame of its own; where a browser cannot print a PDF in a
 * frame, it opens in a tab, from where it prints the same. */
async function print() {
  const bytes = await pdf()
  if (!bytes) return
  // Automated tests cannot answer a print dialog (headless Chrome's PDF viewer stops the page instead): they put a
  // function here that receives the PDF that would have been printed.
  const instead = (globalThis as { __claudiaPrintDialog?: (pdf: Uint8Array) => void }).__claudiaPrintDialog
  if (instead) {
    instead(bytes)
    return
  }
  const url = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/pdf' }))
  frame?.remove()
  frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.dataset.testid = 'print-frame'
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0'
  frame.src = url
  frame.onload = () => {
    try {
      frame?.contentWindow?.focus()
      frame?.contentWindow?.print()
    } catch {
      window.open(url, '_blank', 'noopener')
    }
  }
  document.body.appendChild(frame)
}

// Ctrl+P is the window's shortcut (the workspaces' `PRINT`): it opens this preview and, once open, prints.
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && !customOpen.value) {
    event.preventDefault()
    emit('close')
  }
}

const noteText = computed(() => [
  ...new Set(
    (result.value?.notes ?? []).map((n) =>
      n.kind === 'font'
        ? `“${n.requested}” is not on this server; the preview and the PDF use ${n.used} for it.`
        : n.kind === 'hyphenation'
          ? `Not hyphenated: ${n.reason?.replace(/, so words are not hyphenated$/, '')}.`
          : n.partial
            ? `A picture is printed without some of it: ${n.reason}.`
            : `An object cannot be printed: ${n.reason}.`,
    ),
  ),
])
const status = computed(() => (result.value && laidOn.value ? source.status(result.value, laidOn.value) : ''))
const paperListed = computed(() => source.papers.some((p) => p.id === page.value.paper))
const margin = computed(() => marginPreset(page.value, source.margins))
defineExpose({ print, download, status })
</script>

<template>
  <section class="preview" data-testid="print-preview" aria-label="Print preview">
    <div class="bar" role="toolbar" aria-label="Print">
      <button class="back" type="button" :title="`Back to ${source.back} (Esc)`" data-testid="print-close" @click="emit('close')"><span aria-hidden="true">←</span> Print preview</button>
      <span class="sep" />
      <label v-if="source.layouts.length" class="lbl" title="How many slides go on a page">Layout
        <select data-testid="print-layout" :value="source.layout() ?? ''" :disabled="!canChange" @change="chooseLayout(($event.target as HTMLSelectElement).value)">
          <option v-for="l in source.layouts.filter((x) => x.value === 'slides')" :key="l.value" :value="l.value">{{ l.label }}</option>
          <optgroup label="Handouts">
            <option v-for="l in source.layouts.filter((x) => x.value !== 'slides')" :key="l.value" :value="l.value">{{ l.label }}</option>
          </optgroup>
        </select>
      </label>
      <label class="lbl">Paper
        <select data-testid="print-paper" :value="paperListed ? page.paper : 'custom'" :disabled="!canChange" @change="choosePaper(($event.target as HTMLSelectElement).value)">
          <option v-for="p in source.papers" :key="p.id" :value="p.id">{{ p.name }} · {{ p.label }}</option>
          <option value="custom">{{ page.paper === 'custom' ? `${mm(page.width)} × ${mm(page.height)} mm` : 'Custom…' }}</option>
        </select>
      </label>
      <span v-if="customOpen" class="custom" data-testid="print-custom">
        <input v-model.number="custom.w" type="number" min="25" max="1200" aria-label="width in millimetres" > ×
        <input v-model.number="custom.h" type="number" min="25" max="1200" aria-label="height in millimetres" > mm
        <button class="btn small" type="button" @click="applyCustom">Use</button>
      </span>
      <div class="segmented" role="group" aria-label="Orientation">
        <button type="button" :aria-pressed="page.orientation === 'portrait'" :disabled="!canChange" data-testid="print-portrait" @click="change({ ...page, orientation: 'portrait' })">Portrait</button>
        <button type="button" :aria-pressed="page.orientation === 'landscape'" :disabled="!canChange" data-testid="print-landscape" @click="change({ ...page, orientation: 'landscape' })">Landscape</button>
      </div>
      <label class="lbl">Margins
        <select data-testid="print-margins" :value="margin ?? 'own'" :disabled="!canChange" @change="chooseMargins(($event.target as HTMLSelectElement).value)">
          <option v-for="m in source.margins" :key="m.id" :value="m.id">{{ m.label }}</option>
          <option v-if="!margin" value="own" disabled>the document's own</option>
        </select>
      </label>
      <label class="lbl" title="The language of the document: its words are hyphenated by it">Language
        <select class="narrow" data-testid="print-language" :value="source.language() ?? ''" :disabled="!canSetLanguage" @change="chooseLanguage(($event.target as HTMLSelectElement).value)">
          <option value="">Not set</option>
          <option v-for="l in languages" :key="l.tag" :value="l.tag" :title="l.title">{{ l.name }}</option>
        </select>
      </label>
      <label class="check"><input type="checkbox" data-testid="print-numbers" :checked="page.page_numbers" :disabled="!canChange" @change="change({ ...page, page_numbers: ($event.target as HTMLInputElement).checked })" > Page numbers</label>
      <span class="grow" />
      <button class="btn" type="button" :disabled="!result" data-testid="print-download" @click="void download()">Download PDF</button>
      <button class="btn primary" type="button" :disabled="!result" data-testid="print-print" @click="void print()">Print…</button>
    </div>
    <div ref="canvas" class="canvas">
      <div class="over">
        <p v-for="(n, i) in noteText" :key="i" class="note" data-testid="print-note"><span aria-hidden="true">ⓘ</span> {{ n }}</p>
        <p v-if="problem" class="note bad" role="alert" data-testid="print-problem">{{ problem }}</p>
        <span class="grow" />
        <div class="zoom" role="group" aria-label="Zoom">
          <button type="button" title="Smaller" @click="zoomBy(0.8)">−</button>
          <button type="button" class="mode" title="Two pages side by side" @click="zoom = 'two'">{{ zoomLabel }}</button>
          <button type="button" title="Larger" @click="zoomBy(1.25)">+</button>
          <button type="button" title="Fit the width" @click="zoom = 'width'">⤢</button>
        </div>
      </div>
      <p v-if="busy" class="busy">Laying out the pages…</p>
      <div class="pages" :class="{ two: zoom === 'two' }" data-testid="print-pages">
        <!-- eslint-disable-next-line vue/no-v-html -- markup made by lib/print/paint.ts from the display list, every text escaped -->
        <div v-for="(svg, i) in svgs" :key="i" class="page" :style="pageStyle" :aria-label="`page ${i + 1}`" v-html="svg" />
      </div>
    </div>
    <footer class="foot mono" data-testid="print-status">{{ status }}</footer>
  </section>
</template>

<style scoped>
.preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.bar {
  display: flex;
  flex-wrap: wrap; /* in a narrow window the controls take a second line; Print… is never out of sight */
  align-items: center;
  gap: 6px 8px;
  min-height: 46px;
  padding: 7px 12px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.bar > * {
  flex-shrink: 0;
}
.back {
  border: 0;
  background: none;
  font-weight: 600;
}
.sep {
  width: 1px;
  height: 24px;
  background: var(--line);
}
.lbl {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--muted);
}
.lbl select {
  height: 30px;
  max-width: 184px; /* "A4 · 210 × 297 mm", "Slide size · 16:9 · …", "3 per page, with lines" */
  font-size: 13px;
  border: 1px solid var(--line-field);
  border-radius: 7px;
  background: var(--surface);
  color: var(--text);
  padding: 0 8px;
}
.lbl select.narrow {
  max-width: 118px;
}
.custom input {
  width: 64px;
  height: 28px;
  border: 1px solid var(--line-field);
  border-radius: 6px;
  background: var(--surface);
  padding: 0 6px;
}
.bar .btn {
  padding: 5px 13px;
  font-size: 13.5px;
}
.btn.small {
  padding: 3px 10px;
}
.check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.check input {
  accent-color: var(--app);
}
.btn.primary {
  background: var(--app);
  border-color: var(--app);
  color: #fff;
}
.btn.primary:hover:not(:disabled) {
  background: var(--app-dark, var(--app));
  border-color: var(--app-dark, var(--app));
}
.segmented {
  display: inline-flex;
  padding: 2px;
  border-radius: 9px;
  background: var(--mist);
}
.segmented button {
  height: 26px;
  padding: 0 10px;
  font-size: 13px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--ink);
  font-weight: 500;
}
.segmented button[aria-pressed='true'] {
  background: #fff;
  box-shadow: 0 1px 3px color-mix(in srgb, var(--ink) 20%, transparent);
}
.segmented button:disabled {
  opacity: 0.6;
}
.grow {
  flex: 1;
}
.canvas {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: color-mix(in srgb, var(--paper) 70%, var(--ink) 8%);
  padding: 0 24px 32px;
}
.over {
  position: sticky;
  top: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 0;
}
.note {
  margin: 0;
  padding: 5px 14px;
  border: 1px solid #f2c999;
  border-radius: 999px;
  background: #fff6e8;
  color: var(--ink);
  font-size: 12.5px;
}
.note.bad {
  border-color: var(--rose);
  background: color-mix(in srgb, var(--rose) 10%, #fff);
}
.zoom {
  display: inline-flex;
  border: 1px solid var(--line-field);
  border-radius: 7px;
  background: var(--surface);
  overflow: hidden;
}
.zoom button {
  min-width: 30px;
  height: 28px;
  border: 0;
  border-left: 1px solid var(--line);
  background: none;
}
.zoom button:first-child {
  border-left: 0;
}
.zoom .mode {
  min-width: 84px;
  font-size: 13px;
}
.busy {
  color: var(--muted);
  font-size: 13px;
}
.pages {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}
.pages.two {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: center;
  align-items: flex-start;
}
.page {
  flex: none;
  background: #fff;
  box-shadow: 0 3px 12px color-mix(in srgb, var(--ink) 18%, transparent);
}
.page :deep(svg) {
  display: block;
}
.foot {
  height: 32px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border-top: 1px solid var(--line);
  background: var(--surface);
  font-size: 12px;
  color: var(--muted);
}
</style>
