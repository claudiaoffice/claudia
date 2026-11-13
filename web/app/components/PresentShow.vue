<script setup lang="ts">
// The show (E10.2): the audience view, the presenter view, the overview, a blank screen and the end, in one window
// over the workspace (D345 is open for a second window; this is the one-screen show, `P` swapping the two views).
//
// It runs on a frozen copy of the presentation (D341, `lib/frozen.ts`): a colleague's edit changes nothing on the
// screen; the presenter view says how many steps the document has taken since and offers to take them in between
// slides. Showing is read-only and local (D340): it writes no command, takes no lock and leaves nothing in the
// history. The keys, the order of the slides and the clock are `lib/show.ts`; this draws them.
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { freeze, showSlides, type FrozenDeck } from '~/lib/frozen'
import { wordsOf } from '~/lib/objects'
import { Show, changesSince, showAction } from '~/lib/show'
import { formatTime } from '~/lib/show-time'
import type { SlideSession } from '~/lib/slide-session'
import NotesText from './NotesText.vue'
import SlideView from './SlideView.vue'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string
const props = defineProps<{ session: SlideSession; from: number; view: 'audience' | 'presenter'; t: Translate }>()
const emit = defineEmits<{ close: [] }>()
const { t } = props

const seconds = () => Date.now() / 1000
const deck = ref<FrozenDeck>(freeze(props.session))
const show = reactive(new Show(showSlides(deck.value), { from: props.from, now: seconds(), view: props.view, columns: 4 })) as Show
const now = ref(seconds())
const root = ref<HTMLElement | null>(null)
const idle = ref(false) // the pointer has not moved for a while: no pill, no cursor
const fullscreen = ref(false)
const noteSize = ref(22) // px, the notes' reading size in the presenter view

// ------------------------------------------------------------------------------ what is on the screen
const slideId = computed(() => show.current.id)
const position = computed(() => t('{n} / {total}', { n: show.index + 1, total: show.slides.length }))
const changes = computed(() => changesSince(deck.value.revision, props.session.state.revision))
const next = computed(() => show.next)
/** What a screen reader hears when a slide comes up: its place and its first words (D346). */
const announcement = computed(() => {
  if (show.ended) return t('End of presentation')
  const title = (deck.value.objects[slideId.value] ?? []).map((o) => wordsOf(o)).find((words) => words.trim()) ?? ''
  return title
    ? t('Slide {n} of {total}: {title}', { n: show.index + 1, total: show.slides.length, title: title.split('\n')[0]! })
    : t('Slide {n} of {total}', { n: show.index + 1, total: show.slides.length })
})

const elapsed = computed(() => show.elapsed(now.value))
const onSlide = computed(() => show.onSlide(now.value))
const pace = computed(() => show.pace(now.value))
const paceText = computed(() => {
  const delta = pace.value
  if (delta === null) return ''
  if (Math.abs(delta) < 5) return t('on time')
  return delta > 0 ? t('{time} behind', { time: formatTime(delta) }) : t('{time} ahead', { time: formatTime(-delta) })
})
const clock = computed(() => new Date(now.value * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
const overBudget = computed(() => show.slidePlan !== null && onSlide.value > show.slidePlan)
const thumbs = computed(() => show.slides.map((slide, i) => ({ slide, n: i + 1 })))

// ------------------------------------------------------------------------------ keys and the pointer
function apply(event: KeyboardEvent) {
  // Nothing of the workspace may act while the show runs (undo would change the document under it): the show hears
  // every key first and keeps it. F5 also keeps the browser from reloading the page.
  event.stopImmediatePropagation()
  const action = showAction(event)
  if (action === null) {
    if (event.key === 'F5') event.preventDefault()
    return
  }
  event.preventDefault()
  wake()
  if (typeof action === 'object') return show.digit(action.digit, seconds())
  if (action === 'fullscreen') return void toggleFullscreen()
  if (show.press(action, seconds()) === 'exit') emit('close')
}
let hiding: ReturnType<typeof setTimeout> | undefined
function wake() {
  idle.value = false
  clearTimeout(hiding)
  hiding = setTimeout(() => (idle.value = true), 2000)
}
function go(command: 'next' | 'prev') {
  if (show.press(command, seconds()) === 'exit') emit('close')
}
function pickFromOverview(index: number) {
  show.go(index, seconds())
  show.overview = false
}
function takeInChanges() {
  deck.value = freeze(props.session)
  show.update(showSlides(deck.value))
}

// ------------------------------------------------------------------------------ the window
async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await root.value?.requestFullscreen()
  } catch {
    /* a shell that does not allow it (D345): the show covers the window instead */
  }
}
function fullscreenChanged() {
  fullscreen.value = !!document.fullscreenElement
}
let wakeLock: { release: () => Promise<void> } | null = null
let ticking: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  window.addEventListener('keydown', apply, true)
  document.addEventListener('fullscreenchange', fullscreenChanged)
  ticking = setInterval(() => (now.value = seconds()), 500)
  wake()
  root.value?.focus()
  // Best effort, and only where the browser has them: the whole screen for the audience, and no sleeping screen.
  void root.value?.requestFullscreen?.().catch(() => undefined)
  void (navigator as Navigator & { wakeLock?: { request: (kind: 'screen') => Promise<typeof wakeLock> } }).wakeLock
    ?.request('screen')
    .then((lock) => (wakeLock = lock))
    .catch(() => undefined)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', apply, true)
  document.removeEventListener('fullscreenchange', fullscreenChanged)
  clearInterval(ticking)
  clearTimeout(hiding)
  void wakeLock?.release()
  if (document.fullscreenElement) void document.exitFullscreen().catch(() => undefined)
})
</script>

<template>
  <div
    ref="root"
    class="show"
    :class="[`view-${show.view}`, { idle }]"
    role="dialog"
    aria-modal="true"
    :aria-label="t('Presentation')"
    tabindex="-1"
    data-testid="show"
    :data-view="show.view"
    :data-index="show.index"
    @pointermove="wake"
  >
    <div class="sr" aria-live="polite" data-testid="show-announce">{{ announcement }}</div>

    <!-- ------------------------------------------------------------------ the audience view -->
    <template v-if="show.view === 'audience'">
      <div v-if="show.blank" class="blank" data-testid="show-blank" />
      <div v-else-if="show.ended" class="end" data-testid="show-end">{{ t('End of presentation') }}</div>
      <button v-else type="button" class="stage" :aria-label="t('Next slide')" tabindex="-1" @click="go('next')">
        <SlideView :deck="deck" :slide="slideId" />
      </button>
      <div v-if="!show.overview" class="pill" :class="{ hidden: idle }" role="toolbar" :aria-label="t('Presentation controls')">
        <button type="button" :aria-label="t('Previous slide')" @click="go('prev')">‹</button>
        <span class="mono" data-testid="show-position">{{ position }}</span>
        <button type="button" :aria-label="t('Next slide')" @click="go('next')">›</button>
        <button type="button" :title="t('Presenter view (P)')" :aria-label="t('Presenter view')" @click="show.press('swap', seconds())">P</button>
        <button type="button" :title="t('Overview (G)')" :aria-label="t('Overview')" @click="show.press('overview', seconds())">▦</button>
        <button type="button" :title="t('End the show (Esc)')" :aria-label="t('End the show')" @click="emit('close')">✕</button>
      </div>
    </template>

    <!-- ------------------------------------------------------------------ the presenter view -->
    <div v-else class="presenter" data-testid="presenter">
      <header class="bar">
        <div class="stat" data-testid="show-elapsed">
          <span class="caption">{{ t('Elapsed') }}</span>
          <span class="big mono">{{ formatTime(elapsed) }}</span>
          <span v-if="show.planned.planned" class="of mono">/ {{ formatTime(show.planned.seconds) }}</span>
        </div>
        <div v-if="paceText" class="stat" data-testid="show-pace" :class="{ late: (pace ?? 0) >= 5 }">
          <span class="caption">{{ t('Pace') }}</span>
          <span class="big">{{ paceText }}</span>
        </div>
        <div class="stat" data-testid="show-slide-time" :class="{ late: overBudget }">
          <span class="caption">{{ t('This slide') }}</span>
          <span class="big mono">{{ formatTime(onSlide) }}</span>
          <span v-if="show.slidePlan !== null" class="of mono">/ {{ formatTime(show.slidePlan) }}</span>
        </div>
        <div v-if="show.planned.unplanned && show.planned.planned" class="stat quiet">
          <span class="caption">{{ t('No time planned') }}</span>
          <span class="of">{{ t('{n} of {total} slides', { n: show.planned.unplanned, total: show.slides.length }) }}</span>
        </div>
        <div class="stat right">
          <span class="caption">{{ t('Time') }}</span>
          <span class="big mono">{{ clock }}</span>
        </div>
      </header>
      <div v-if="changes" class="changes" role="status" data-testid="show-changes">
        <span>{{ t('Changes since you started: {n}', { n: changes }) }}</span>
        <button type="button" data-testid="show-take-in" @click="takeInChanges">{{ t('Update now') }}</button>
      </div>
      <div class="views">
        <section class="now" :aria-label="t('Current slide')">
          <div class="frame"><SlideView :deck="deck" :slide="slideId" /></div>
          <span class="count mono" data-testid="show-position">{{ position }}</span>
        </section>
        <section class="after" :aria-label="t('Next slide')">
          <div v-if="next" class="frame small"><SlideView :deck="deck" :slide="next.id" /></div>
          <div v-else class="frame small last">{{ t('End of presentation') }}</div>
          <div class="notes">
            <div class="notes-head">
              <h2>{{ t('Notes') }}</h2>
              <button type="button" :aria-label="t('Smaller notes')" @click="noteSize = Math.max(14, noteSize - 2)">A−</button>
              <button type="button" :aria-label="t('Larger notes')" @click="noteSize = Math.min(48, noteSize + 2)">A+</button>
            </div>
            <div class="notes-body" tabindex="0" :style="{ fontSize: `${noteSize}px` }" :aria-label="t('Speaker notes')">
              <NotesText v-if="show.current.notes" :notes="show.current.notes" />
              <p v-else class="none">{{ t('No notes for this slide.') }}</p>
            </div>
          </div>
        </section>
      </div>
      <footer class="help">
        <span><kbd>←</kbd> <kbd>→</kbd> {{ t('slides') }}</span>
        <span><kbd>G</kbd> {{ t('overview') }}</span>
        <span><kbd>B</kbd> {{ t('blank') }}</span>
        <span><kbd>P</kbd> {{ t('audience view') }}</span>
        <span><kbd>F</kbd> {{ t('full screen') }}</span>
        <span><kbd>Esc</kbd> {{ t('end') }}</span>
      </footer>
    </div>

    <!-- ------------------------------------------------------------------ the overview -->
    <div v-if="show.overview" class="overview" data-testid="show-overview" role="group" :aria-label="t('All slides')">
      <header>
        <h2>{{ t('All slides') }}</h2>
        <span class="mono">{{ t('Planned: {time}', { time: formatTime(show.planned.seconds) }) }}</span>
        <span v-if="show.typed" class="mono typed" data-testid="show-typed">→ {{ show.typed }}</span>
      </header>
      <ol class="grid">
        <li v-for="item in thumbs" :key="item.slide.id">
          <button
            type="button"
            :class="{ cursor: show.cursor === item.n - 1, here: show.index === item.n - 1 }"
            :aria-label="t('Slide {n}', { n: item.n }) + (item.slide.seconds ? `, ${formatTime(item.slide.seconds)}` : '')"
            :aria-current="show.index === item.n - 1 ? 'true' : undefined"
            :data-testid="`show-thumb-${item.n}`"
            @click="pickFromOverview(item.n - 1)"
          >
            <span class="thumb"><SlideView :deck="deck" :slide="item.slide.id" /></span>
            <span class="label"
              ><span class="mono">{{ item.n }}</span
              ><span v-if="item.slide.seconds" class="mono">{{ formatTime(item.slide.seconds) }}</span></span
            >
          </button>
        </li>
      </ol>
    </div>
    <div v-else-if="show.typed" class="typed-badge mono" data-testid="show-typed">→ {{ show.typed }}</div>
  </div>
</template>

<style scoped>
.show {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  grid-template: minmax(0, 1fr) / minmax(0, 1fr);
  background: var(--ink, #1f1a33);
  color: #f4f2fa;
  outline: none;
}
.show.view-audience.idle {
  cursor: none;
}
.sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
.stage {
  display: block;
  width: 100%;
  height: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: inherit;
}
.blank {
  background: #000;
}
.end {
  display: grid;
  place-items: center;
  font-size: 22px;
  opacity: 0.7;
}
.pill {
  position: absolute;
  left: 50%;
  bottom: 22px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  /* dark, not light: the slide behind it is a white page, and a pill that is nearly white on it cannot be read */
  background: rgb(31 26 51 / 78%);
  color: #f4f2fa;
  backdrop-filter: blur(8px);
  transition: opacity 150ms;
}
.pill.hidden {
  opacity: 0;
  pointer-events: none;
}
.pill button {
  min-width: 34px;
  height: 34px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: inherit;
  font-size: 18px;
}
.pill button:hover,
.pill button:focus-visible {
  background: rgb(244 242 250 / 24%);
}
.pill .mono {
  padding: 0 10px;
  font-size: 14px;
}
.presenter {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 18px;
  min-height: 0;
}
.bar {
  display: flex;
  gap: 28px;
  align-items: flex-end;
}
.stat {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: 8px;
}
.stat.right {
  margin-inline-start: auto;
}
.stat.quiet {
  opacity: 0.7;
}
.caption {
  flex-basis: 100%;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.7;
}
.big {
  font-size: 26px;
  font-weight: 600;
}
.of {
  font-size: 16px;
  opacity: 0.75;
}
.late .big {
  color: #ffb27a;
}
.changes {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 6px 12px;
  border-radius: 8px;
  background: rgb(242 160 87 / 18%);
  font-size: 14px;
}
.changes button {
  padding: 3px 12px;
  border: 1px solid currentcolor;
  border-radius: 999px;
  background: transparent;
  color: inherit;
}
.views {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr);
  gap: 18px;
  min-height: 0;
}
.now,
.after {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  min-width: 0;
}
.frame {
  flex: 1;
  min-height: 0;
  background: #000;
  border-radius: 6px;
  overflow: hidden;
}
.frame.small {
  flex: 0 0 auto;
  aspect-ratio: 16 / 9;
}
.frame.last {
  display: grid;
  place-items: center;
  opacity: 0.7;
}
.count {
  align-self: flex-end;
  font-size: 14px;
  opacity: 0.8;
}
.notes {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: rgb(244 242 250 / 7%);
  border-radius: 8px;
}
.notes-head {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px 0;
}
.notes-head h2 {
  flex: 1;
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.7;
}
.notes-head button {
  border: 1px solid rgb(244 242 250 / 30%);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  padding: 1px 8px;
}
.notes-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 14px 14px;
}
.none {
  opacity: 0.6;
  margin: 0;
}
.help {
  display: flex;
  gap: 18px;
  font-size: 12px;
  opacity: 0.7;
}
kbd {
  padding: 0 5px;
  border: 1px solid rgb(244 242 250 / 40%);
  border-radius: 4px;
  font-size: 11px;
}
.overview {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px 24px;
  overflow-y: auto;
  background: rgb(20 16 34 / 96%);
}
.overview header {
  display: flex;
  gap: 18px;
  align-items: baseline;
}
.overview h2 {
  margin: 0;
  font-size: 18px;
}
.typed {
  margin-inline-start: auto;
}
.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 0;
  margin: 0;
  list-style: none;
}
.grid button {
  display: block;
  width: 100%;
  padding: 6px;
  border: 2px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: inherit;
  text-align: start;
}
.grid button.here {
  border-color: rgb(244 242 250 / 35%);
}
.grid button.cursor,
.grid button:focus-visible {
  border-color: var(--apricot, #f2a057);
}
.thumb {
  display: block;
  aspect-ratio: 16 / 9;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}
.label {
  display: flex;
  justify-content: space-between;
  padding-top: 4px;
  font-size: 13px;
}
.typed-badge {
  position: absolute;
  top: 14px;
  right: 18px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgb(244 242 250 / 18%);
}
.mono {
  font-variant-numeric: tabular-nums;
}
@media (prefers-reduced-motion: reduce) {
  .pill {
    transition: none;
  }
}
</style>
