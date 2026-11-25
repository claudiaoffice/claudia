<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = withDefaults(
  defineProps<{ title: string; label: string; ok: string; placeholder?: string; required?: boolean; initial?: string }>(),
  { placeholder: '', required: false, initial: '' },
)
const emit = defineEmits<{ ok: [value: string]; close: [] }>()

const value = ref(props.initial)
const field = ref<HTMLInputElement | null>(null)
// what the field starts with is selected, so that Enter takes it and typing replaces it (UX-76)
onMounted(() => {
  field.value?.focus()
  field.value?.select()
})

function submit() {
  const text = value.value.trim()
  if (props.required && !text) return
  emit('ok', text)
}
</script>

<template>
  <Modal :title="title" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <label class="field">{{ label }}<input ref="field" v-model="value" :placeholder="placeholder" autocomplete="off" ></label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="required && !value.trim()">{{ ok }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 14px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
