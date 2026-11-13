<script setup lang="ts">
import { onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{ title: string; label: string; ok: string; placeholder?: string; required?: boolean; initial?: string }>(),
  { placeholder: '', required: false, initial: '' },
)
const emit = defineEmits<{ ok: [value: string]; close: [] }>()

const value = ref(props.initial)
const field = ref<HTMLInputElement | null>(null)
onMounted(() => field.value?.focus())

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
.buttons {
  display: flex;
  gap: 10px;
}
</style>
