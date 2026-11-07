<script setup lang="ts">
// Insert ▸ Image (E10.8): choose a picture from disk, describe it, put it on the slide. Only the "browse a file"
// path — clipboard and drag-and-drop import are not built yet, by the same decision that kept `add_image` to just
// that. A plain web browser cannot tell us a chosen file's full path (only its name), so `sourcePath` is always
// null from here; a desktop client that can read the real path would pass it instead, and the server would mask it
// the same way for everyone but the importer (`hub.py`'s per-viewer `to_data_for`).
import { computed, onBeforeUnmount, ref } from 'vue'
import type { Frame } from '~/lib/geometry'
import { IMAGE_FILE_ACCEPT, MAX_IMAGE_BYTES, fileToBase64 } from '~/lib/images'
import type { SlideSession } from '~/lib/slide-session'

const props = defineProps<{
  session: SlideSession
  /** Where the new object goes, given the picture's own aspect (width / height) — mirrors how `SlideWorkspace`
   * already places a shape, so a picture is shifted the same way among whatever else was just added. */
  frameFor: (aspect: number) => Frame
}>()
const emit = defineEmits<{ close: []; inserted: [id: string] }>()

const fileInput = ref<HTMLInputElement | null>(null)
const file = ref<File | null>(null)
const previewUrl = ref('')
const naturalSize = ref<{ width: number; height: number } | null>(null)
const alt = ref('')
const fileError = ref('')
const busy = ref(false)

const canSubmit = computed(() => file.value !== null && naturalSize.value !== null && alt.value.trim() !== '' && !busy.value)

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
    fileError.value = `That file is too big (at most ${Math.floor(MAX_IMAGE_BYTES / (1024 * 1024))} MB).`
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
  fileError.value = 'This does not look like a picture the browser can show.'
  reset()
}

async function submit() {
  if (!canSubmit.value || !file.value || !naturalSize.value) return
  busy.value = true
  const data = await fileToBase64(file.value)
  const aspect = naturalSize.value.width / naturalSize.value.height
  const id = await props.session.addImage(
    { data, alt: alt.value.trim(), sourceName: file.value.name, sourcePath: null },
    props.frameFor(aspect),
  )
  busy.value = false
  if (id) emit('inserted', id) // a failure already told the person why, via the session's own notice
}
</script>

<template>
  <Modal title="Insert image" :width="440" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <input ref="fileInput" type="file" :accept="IMAGE_FILE_ACCEPT" class="hidden-input" @change="onFileChange" />
      <div class="picker">
        <button type="button" class="btn" @click="choose">{{ file ? 'Choose a different file…' : 'Choose a file…' }}</button>
        <span v-if="file" class="filename">{{ file.name }}</span>
      </div>
      <p v-if="fileError" class="error" role="alert">{{ fileError }}</p>
      <div v-if="previewUrl" class="preview">
        <img :src="previewUrl" alt="" @load="onPreviewLoad" @error="onPreviewError" />
      </div>
      <label class="field">Description (read aloud to someone who cannot see it)<input v-model="alt" autocomplete="off" maxlength="300" /></label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!canSubmit">{{ busy ? 'Inserting…' : 'Insert' }}</button>
        <button class="btn" type="button" @click="emit('close')">Cancel</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
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
