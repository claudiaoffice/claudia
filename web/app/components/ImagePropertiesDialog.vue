<script setup lang="ts">
// Right-click an image ▸ Properties (follow-up to the context-menu fix, 2026-11-07): everything already known
// about one imported picture, read-only — the asset's own `format`/`width`/`height`/`data` (`creates.images`) and
// the object's own `imported` record (who, when, from where; `claudia_core.ImageImport`). `source_path` is simply
// absent here when the server has masked it (`hub.py`'s per-viewer `to_data_for`) — there is nothing to tell that
// case apart from a browser that could not supply a path to begin with, and that is by design (D141): the person
// reading this dialog is told the same thing either way. Nothing here is editable yet; "Replace Image…" and a few
// other actions sat in the design mockup for this dialog but are not built (undecided, like most of the context
// menu's own next steps) — this shows what the picture already carries, and closes.
import { computed } from 'vue'
import { formatByteSize, imageByteSize, imageDataUrl } from '~/lib/images'
import { ago, colorOf, inkOn, initial } from '~/lib/people'
import type { SlideObject, SlideSession } from '~/lib/slide-session'

const props = defineProps<{ session: SlideSession; object: SlideObject }>()
const emit = defineEmits<{ close: [] }>()

const state = props.session.state
const asset = computed(() => (props.object.image ? state.images[props.object.image] : undefined))
const imported = computed(() => props.object.imported)

const thumbSrc = computed(() => (asset.value ? imageDataUrl(asset.value) : ''))
const formatLabel = computed(() => {
  const a = asset.value
  if (!a) return ''
  if (a.format === 'svg') return 'SVG (vector)'
  if (a.format === 'gif') return a.animated ? 'GIF (animated)' : 'GIF'
  if (a.format === 'png') return a.animated ? 'PNG (animated)' : 'PNG'
  return a.format.toUpperCase()
})
const byteSize = computed(() => (asset.value ? formatByteSize(imageByteSize(asset.value.data)) : ''))
const importedByColor = computed(() => (imported.value ? colorOf(state, imported.value.imported_by) : ''))
</script>

<template>
  <Modal title="Image properties" :width="480" @close="emit('close')">
    <div v-if="asset && imported" class="props">
      <div class="head">
        <img class="thumb" :src="thumbSrc" alt="" />
        <div class="names">
          <div class="filename">{{ imported.source_name }}</div>
          <div class="alt">“{{ imported.alt }}”</div>
        </div>
      </div>

      <dl class="facts">
        <div class="row">
          <dt>Format</dt>
          <dd>{{ formatLabel }}</dd>
        </div>
        <div class="row">
          <dt>Dimensions</dt>
          <dd>{{ asset.width }} × {{ asset.height }} px</dd>
        </div>
        <div class="row">
          <dt>File size</dt>
          <dd>{{ byteSize }}</dd>
        </div>
      </dl>

      <div class="divider" />

      <dl class="facts">
        <div class="row">
          <dt>Imported by</dt>
          <dd class="person">
            <span class="avatar" :style="{ background: importedByColor, color: inkOn(importedByColor) }">{{ initial(imported.imported_by) }}</span>
            {{ imported.imported_by }}
          </dd>
        </div>
        <div class="row">
          <dt>Imported</dt>
          <dd>{{ ago(imported.imported_at) }}</dd>
        </div>
        <div class="row">
          <dt>Source</dt>
          <dd>
            Imported from disk
            <div v-if="imported.source_path" class="path">{{ imported.source_path }}</div>
          </dd>
        </div>
      </dl>
    </div>

    <div class="buttons">
      <button class="btn primary" type="button" @click="emit('close')">Close</button>
    </div>
  </Modal>
</template>

<style scoped>
.props {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.head {
  display: flex;
  gap: 14px;
  align-items: center;
}
.thumb {
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border-radius: 8px;
  object-fit: contain;
  background: var(--mist);
  box-shadow: var(--shadow);
}
.names {
  min-width: 0;
}
.filename {
  font: 600 14px var(--font-ui);
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.alt {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.divider {
  height: 1px;
  background: var(--line);
}
.facts {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}
.row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
dt {
  font-size: 12px;
  color: var(--muted);
  flex-shrink: 0;
}
dd {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  text-align: right;
}
.person {
  display: flex;
  align-items: center;
  gap: 6px;
}
.avatar {
  width: 16px;
  height: 16px;
  border-radius: 999px;
  font-size: 9px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.path {
  color: var(--muted);
  font-weight: 400;
  word-break: break-all;
  max-width: 280px;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}
</style>
