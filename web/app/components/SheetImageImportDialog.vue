<script setup lang="ts">
// Edit ▸ Image… (E6.17): choose a picture from disk, describe it, anchor it to the current cell. Only the
// "browse a file" path, same as creates' own `ImageImportDialog.vue` — clipboard and drag-and-drop import are not
// built yet. A plain web browser cannot tell us a chosen file's full path (only its name), so `sourcePath` is
// always null from here; a desktop client that can read the real path would pass it instead, and the server
// would mask it the same way for everyone but the importer (`hub.py`'s per-viewer `to_data_for`).
import { computed, onBeforeUnmount, ref } from 'vue'
import { IMAGE_FILE_ACCEPT, MAX_IMAGE_BYTES, fileToBase64 } from '~/lib/images'
import type { Session } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  session: Session
  /** Where the new object's anchor cell and pixel size go, given the picture's own aspect (width / height) — the
   * current selection's top-left cell, sized so it keeps that aspect (the server rejects any other size for an
   * image, within one pixel). */
  anchorFor: (aspect: number) => { row: number; col: number; w: number; h: number }
}>()
const emit = defineEmits<{ close: []; inserted: [id: string] }>()

const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const previewUrl = ref('')
const naturalSize = ref<{ width: number; height: number } | null>(null)
const alt = ref('')
/** A picture that only decorates needs no words; a screen reader skips it (BITV 1.1.1). */
const decorative = ref(false)
const fileError = ref('')
const busy = ref(false)

const canSubmit = computed(() => file.value !== null && naturalSize.value !== null && (decorative.value || alt.value.trim() !== '') && !busy.value)

function reset() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  naturalSize.value = null
  file.value = null
}
onBeforeUnmount(reset)

function choose() {
  fileInput.value?.click()
}

function onFileChange(event: Event) {
  const picked = (event.target as HTMLInputElement).files?.[0] ?? null
  reset()
  fileError.value = ''
  if (!picked) return
  if (picked.size > MAX_IMAGE_BYTES) {
    fileError.value = t('That file is too big (at most {mb} MB).', { mb: Math.floor(MAX_IMAGE_BYTES / (1024 * 1024)) })
    return
  }
  file.value = picked
  previewUrl.value = URL.createObjectURL(picked)
}

/** The browser decoded the preview, so this is in fact a picture it can show — and now we know its aspect, without
 * this module reading any image format itself. */
function onPreviewLoad(event: Event) {
  const img = event.target as HTMLImageElement
  naturalSize.value = { width: img.naturalWidth, height: img.naturalHeight }
}

function onPreviewError() {
  fileError.value = t('This does not look like a picture the browser can show.')
  reset()
}

async function submit() {
  if (!canSubmit.value || !file.value || !naturalSize.value) return
  busy.value = true
  const data = await fileToBase64(file.value)
  const aspect = naturalSize.value.width / naturalSize.value.height
  const id = await props.session.addImage({ data, alt: decorative.value ? '' : alt.value.trim(), decorative: decorative.value, sourceName: file.value.name, sourcePath: null }, props.anchorFor(aspect))
  busy.value = false
  if (id) emit('inserted', id) // a failure already told the person why, via the session's own notice
}
</script>

<template>
  <Modal :title="t('Insert image')" :width="440" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <input ref="fileInput" type="file" :accept="IMAGE_FILE_ACCEPT" class="hidden-input" @change="onFileChange" >
      <div class="picker">
        <button type="button" class="btn" @click="choose">{{ file ? t('Choose a different file…') : t('Choose a file…') }}</button>
        <span v-if="file" class="filename">{{ file.name }}</span>
      </div>
      <p v-if="fileError" class="error" role="alert">{{ fileError }}</p>
      <div v-if="previewUrl" class="preview">
        <img :src="previewUrl" alt="" @load="onPreviewLoad" @error="onPreviewError" >
      </div>
      <label class="field">{{ t('Description (read aloud to someone who cannot see it)') }}<input v-model="alt" autocomplete="off" maxlength="300" :disabled="decorative" ></label>
      <label class="check"><input v-model="decorative" type="checkbox" > {{ t('Decorative: only for looks, a screen reader skips it') }}</label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!canSubmit">{{ busy ? t('Inserting…') : t('Insert') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.check {
  display: flex;
  gap: 8px;
  align-items: center;
}
.form {
  display: grid;
  gap: 14px;
}
.hidden-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}
.picker {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.filename {
  color: var(--muted);
  font-size: 13px;
  overflow-wrap: anywhere;
}
.error {
  margin: 0;
  color: var(--rose);
  font-size: 13px;
}
.preview {
  display: grid;
  place-items: center;
  max-height: 220px;
  overflow: hidden;
  border-radius: 10px;
  background: color-mix(in srgb, var(--ink) 6%, var(--paper));
}
.preview img {
  max-width: 100%;
  max-height: 220px;
  object-fit: contain;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
