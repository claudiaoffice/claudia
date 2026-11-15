<script setup lang="ts">
// Details… of a document on the front page: its description and tags, changed without opening it. Only an editor or an owner
// may (the server checks, with the person's own password, like Delete); both are public by design (D103), and the
// dialog says so every time. The name is sealed into the file and cannot change here.
import { ref } from 'vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  id: string
  description: string
  tags: string[]
  user: string
  place: string
  counts: { tag: string; count: number }[]
  busy: boolean
  error: string
}>()
const emit = defineEmits<{
  close: []
  save: [values: { user: string; password: string; description: string; tags: string[] }]
}>()

const description = ref(props.description)
const tags = ref([...props.tags])
const user = ref(props.user)
const password = ref('')

function submit() {
  if (props.busy || !password.value) return
  emit('save', { user: user.value.trim(), password: password.value, description: description.value, tags: tags.value })
}
</script>

<template>
  <Modal :title="t('Details of {id}', { id })" :width="560" @close="emit('close')">
    <p class="name">{{ t('Name') }} <code>{{ id }}</code> · {{ t('The name is sealed into the file and cannot change.') }}</p>
    <form class="form" @submit.prevent="submit">
      <DetailsFields v-model:description="description" v-model:tags="tags" :counts="counts" :place="place" id-prefix="edit" />
      <div class="two">
        <label class="field">{{ t('Your name') }}<input v-model="user" name="details-user" autocomplete="username" required ></label>
        <label class="field">{{ t('Your password, to confirm') }}<PasswordInput v-model="password" name="details-password" autocomplete="current-password" required /></label>
      </div>
      <p class="hint">{{ t('Only an editor or an owner of the document can change this.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="submit" :disabled="busy || !password || !user.trim()">{{ t('Save details') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.name {
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 12.5px;
}
.form {
  display: grid;
  gap: 14px;
}
.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.field {
  display: grid;
  gap: 4px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.error {
  margin: 0;
  color: var(--rose);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
