<script setup lang="ts">
// One slide of a frozen deck (`lib/frozen.ts`), drawn to fit the box it is in and not to be touched: the audience
// view, the presenter view's current and next slide, and the overview's thumbnails. It draws from the same style
// helpers as the editor (`SlideCanvas.vue`), so a slide looks in the show as it did on the page; it takes no
// pointer, holds no selection and has no hint text for an empty box. The page of a slide is white whatever the theme
// of the app is, so the default ink is not swapped for the theme's (`withDisplayInk`): that is for the editor's
// surround, not the slide.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { FrozenDeck } from '~/lib/frozen'
import { SLIDE_H, SLIDE_W, fitScale } from '~/lib/geometry'
import { imageDataUrl } from '~/lib/images'
import { cssOf as computedCss, slideFrame, wordsCssOf, wordsOf } from '~/lib/objects'
import { facetCss, scaleCss } from '~/lib/slide-style'
import type { SlideObject } from '~/lib/slide-session'

const props = withDefaults(defineProps<{ deck: FrozenDeck; slide: string; margin?: number }>(), { margin: 0 })

const box = ref<HTMLElement | null>(null)
const size = ref({ w: SLIDE_W, h: SLIDE_H })
const scale = computed(() => fitScale(size.value, props.margin))
let watcher: ResizeObserver | null = null
onMounted(() => {
  if (!box.value) return
  const measure = () => (size.value = { w: box.value!.clientWidth, h: box.value!.clientHeight })
  measure()
  watcher = new ResizeObserver(measure)
  watcher.observe(box.value)
})
onBeforeUnmount(() => watcher?.disconnect())

const objects = computed(() => props.deck.objects[props.slide] ?? [])
const facets = computed(() => props.deck.styleModel?.facets)
const px = (units: number) => `${Math.round(units * scale.value * 100) / 100}px`

function boxStyle(o: SlideObject) {
  const f = slideFrame(o)
  return { left: px(f.x), top: px(f.y), width: px(f.w), height: px(f.h) }
}
const outline = (o: SlideObject) => (o.shape ? (props.deck.shapes[o.shape] ?? null) : null)
function textBox(o: SlideObject) {
  const area = outline(o)?.text_area ?? { x: 0, y: 0, w: 100, h: 100 }
  const pad = o.kind === 'text' ? 0 : 8 // a shape's text is not written right up to its edge
  const f = slideFrame(o)
  return {
    left: `calc(${(area.x / 100) * f.w * scale.value}px + ${pad * scale.value}px)`,
    top: `calc(${(area.y / 100) * f.h * scale.value}px + ${pad * scale.value}px)`,
    width: `calc(${(area.w / 100) * f.w * scale.value}px - ${2 * pad * scale.value}px)`,
    height: `calc(${(area.h / 100) * f.h * scale.value}px - ${2 * pad * scale.value}px)`,
  }
}
function wordsStyle(o: SlideObject): Record<string, string> {
  const words = facetCss(scaleCss(wordsCssOf(props.deck.styles, o), scale.value), facets.value, ['text', 'paragraph'])
  const frame = o.kind === 'text' ? { ...facetCss(scaleCss(computedCss(props.deck.styles, o), scale.value), facets.value, ['box']), 'box-sizing': 'border-box' } : {}
  return { ...words, ...frame, display: 'flex', 'flex-direction': 'column', 'justify-content': o.kind === 'shape' ? 'center' : 'flex-start', ...textBox(o) }
}
const paintStyle = (o: SlideObject) => facetCss(scaleCss(computedCss(props.deck.styles, o), scale.value), facets.value, ['outline'])
function pictureSrc(o: SlideObject): string {
  const asset = o.image ? props.deck.images[o.image] : undefined
  return asset ? imageDataUrl(asset) : ''
}
</script>

<template>
  <div ref="box" class="fit">
    <div class="page" data-testid="show-slide" :data-slide="slide" :style="{ width: px(SLIDE_W), height: px(SLIDE_H) }">
      <div v-for="o in objects" :key="o.id" class="obj" :class="o.kind" :style="boxStyle(o)">
        <img v-if="o.kind === 'image'" class="picture" :src="pictureSrc(o)" alt="" draggable="false" >
        <template v-else>
          <svg v-if="outline(o)" class="shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <path :d="outline(o)!.path" vector-effect="non-scaling-stroke" :style="paintStyle(o)" />
          </svg>
          <div class="words" :style="wordsStyle(o)">
            <span v-if="wordsOf(o)" class="text">{{ wordsOf(o) }}</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fit {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}
.page {
  position: relative;
  background: #fff;
  overflow: hidden;
  user-select: none;
  pointer-events: none;
}
.obj {
  position: absolute;
}
.shape {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}
.picture {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.words {
  position: absolute;
  overflow: hidden;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
</style>
