<script setup lang="ts">
// The menu of a floating object or a table in a text, and what its entries open (D1225, D1224): the context menu, the
// description dialog, the Rotate By… popover, the style menu of the object and the gap of the wrap. The list is
// `lib/object-menu.ts`'s, the one all three apps use; this is only composes' callbacks for it. It stays mounted, so a
// dialog goes on after the menu has closed, and the parent only says where a menu is to open.
import { computed, ref, watch } from 'vue'
import { pictureAlt } from '~/lib/descriptions'
import { contextMenuItems } from '~/lib/object-menu'
import { objectStyleHost, type ObjectStyling } from '~/lib/object-style-host'
import { tableContextItems, type TableMenuHost } from '~/lib/table-menu'
import type { TextSession } from '~/lib/text-session'
import { pointer } from '~/lib/objects'
import { wrapOf, MAX_WRAP_GAP, DEFAULT_WRAP_GAP, type Wrap } from '~/lib/wrap'
import { useI18n } from '~/lib/i18n'
import type { MenuItem } from './MenuBar.vue'

const { t } = useI18n()
const props = defineProps<{ session: TextSession; menu: { id: string; x: number; y: number } | null; tableHost: TableMenuHost; clipboard: { cut: () => unknown; copy: () => unknown } }>()
const emit = defineEmits<{
  close: []
  /** A turn being tried from Rotate By… (`null`: none), for the page to draw. */
  turning: [at: { id: string; turn: number } | null]
  /** The all-styles dialog, which the workspace owns. */
  styles: []
}>()
const session = props.session
const state = session.state
const readonly = computed(() => session.readOnly)

const shown = ref(props.menu)
watch(() => props.menu, (menu) => (shown.value = menu))
const closeMenu = () => {
  shown.value = null
  emit('close')
}

const objectOf = (id: string) => state.objects[id] ?? null

// ------------------------------------------------------------------------------ the entries
const items = computed<MenuItem[]>(() => {
  const at = shown.value
  const o = at ? objectOf(at.id) : null
  if (!at || !o) return []
  const describe = () => {
    shown.value = null
    describing.value = o.id
  }
  if (o.kind === 'table') {
    const id = pointer(o, 'table')
    const table = id ? state.tables[id] : undefined
    return tableContextItems({ t }, props.tableHost, { describe, remove: () => void (table && session.removeTable(table.id)) })
  }
  const wrap = wrapOf(o.anchor).wrap
  return contextMenuItems(
    o,
    readonly.value,
    {
      describe,
      edit: () => {
        session.selectObject(o.id)
        state.editingObject = o.id
      },
      style: () => {
        shown.value = null
        styling.value = { x: at.x, y: at.y }
      },
      rotateBy: () => {
        shown.value = null
        rotating.value = { id: o.id, from: o.rotation, x: at.x, y: at.y }
      },
      remove: () => void session.removeObject(o.id),
      cut: () => void props.clipboard.cut(),
      copy: () => void props.clipboard.copy(),
      setSnap: () => undefined, // composes has no grid
      setWrap: (mode: Wrap) => void session.setWrap(o.id, mode),
      setGap: () => {
        shown.value = null
        gapping.value = o.id
      },
    },
    // only a rendered container is written in, here (the server has no step for the words of a box or a shape in a text)
    { wrap, edit: o.kind === 'rendered' },
  )
})

// ------------------------------------------------------------------------------ describing (BITV 1.1.1)
const describing = ref<string | null>(null)
const describingObject = computed(() => (describing.value ? objectOf(describing.value) : null))
async function saveDescription(params: { description: string; decorative: boolean }) {
  const id = describing.value
  describing.value = null
  if (id) await session.describeObject(id, params.description, params.decorative)
}

// ------------------------------------------------------------------------------ Rotate By… (D1024)
const rotating = ref<{ id: string; from: number; x: number; y: number } | null>(null)
function preview(angle: number) {
  if (rotating.value) emit('turning', { id: rotating.value.id, turn: angle })
}
async function doneRotate(angle: number) {
  const r = rotating.value
  rotating.value = null
  if (r && angle !== r.from) await session.rotateObject(r.id, angle)
  emit('turning', null)
}
function cancelRotate() {
  rotating.value = null
  emit('turning', null)
}

// ------------------------------------------------------------------------------ the style of the object (E9.7, D203)
const styling = ref<{ x: number; y: number } | null>(null)
const objectStyling: ObjectStyling = {
  get readOnly() {
    return session.readOnly
  },
  get styles() {
    return session.styleViews()
  },
  get roles() {
    return state.palette?.roles ?? []
  },
  get readings() {
    return state.palette?.readings ?? []
  },
  get model() {
    return state.styleModel
  },
  get selected() {
    return state.selectedObject ? (state.objects[state.selectedObject] ?? null) : null
  },
  get bodies() {
    return session.bodies()
  },
  applyStyle: (targets, style, slot) => session.applyObjectStyle(targets, style, slot),
  changeStyle: (style, edit) => session.changeStyle(style, edit),
  deviateStyle: (parent, targets, slot, edit) => session.deviateObjectStyle(parent, targets, slot, edit),
  renameStyle: (style, name) => session.renameStyle(style, name),
  checkCss: (text) => session.checkCss(text),
  setRole: (role, colour) => session.setRole(role, colour),
}
const styleHost = objectStyleHost(objectStyling)

// ------------------------------------------------------------------------------ the gap of the wrap
const gapping = ref<string | null>(null)
const gapOf = computed(() => (gapping.value && objectOf(gapping.value) ? String(wrapOf(objectOf(gapping.value)!.anchor).gap) : String(DEFAULT_WRAP_GAP)))
async function setGap(text: string) {
  const id = gapping.value
  gapping.value = null
  const o = id ? objectOf(id) : null
  const gap = Number.parseInt(text, 10)
  if (!o || Number.isNaN(gap)) return
  await session.setWrap(o.id, wrapOf(o.anchor).wrap, gap)
}
</script>

<template>
  <div class="object-menu-host">
    <ContextMenu v-if="shown" :x="shown.x" :y="shown.y" :items="items" :label="state.objects[shown.id]?.kind === 'table' ? t('Table menu') : t('Object menu')" @close="closeMenu" />
    <ObjectDescriptionDialog v-if="describingObject" :object="describingObject" :current="pictureAlt(describingObject)" @save="saveDescription" @close="describing = null" />
    <RotatePopover v-if="rotating" :x="rotating.x" :y="rotating.y" :rotation="rotating.from" @preview="preview" @done="doneRotate" @cancel="cancelRotate" />
    <StyleMenu v-if="styling" :host="styleHost" :x="styling.x" :y="styling.y" @close="styling = null" @styles="((styling = null), emit('styles'))" />
    <PromptDialog
      v-if="gapping"
      :title="t('Gap…')"
      :label="t('How far the words keep from the object, in pixels (0 to {max})', { max: MAX_WRAP_GAP })"
      :ok="t('Save')"
      required
      :initial="gapOf"
      @ok="setGap"
      @close="gapping = null"
    />
  </div>
</template>
