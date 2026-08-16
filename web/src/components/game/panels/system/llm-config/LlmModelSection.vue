<script setup lang="ts">
import type { LLMConfigDTO } from '@/types/api'

defineProps<{
  title: string
  config: LLMConfigDTO
  normalLabel: string
  normalDesc: string
  normalPlaceholder: string
  fastLabel: string
  fastDesc: string
  fastPlaceholder: string
  separateFastConfigLabel: string
  separateFastConfigDesc: string
}>()
</script>

<template>
  <div class="section">
    <div class="section-title">{{ title }}</div>

    <div class="form-item">
      <label class="toggle-label">
        <input v-model="config.use_separate_fast_config" type="checkbox" />
        {{ separateFastConfigLabel }}
      </label>
      <div class="desc">{{ separateFastConfigDesc }}</div>
    </div>

    <div class="form-item">
      <label>{{ normalLabel }}</label>
      <div class="desc">{{ normalDesc }}</div>
      <input
        v-model="config.model_name"
        type="text"
        :placeholder="normalPlaceholder"
        class="input-field"
      />
    </div>

    <div class="form-item">
      <label>{{ fastLabel }}</label>
      <div class="desc">{{ fastDesc }}</div>
      <input
        v-model="config.fast_model_name"
        type="text"
        :placeholder="fastPlaceholder"
        class="input-field"
      />
    </div>
  </div>
</template>

<style scoped>
.section {
  margin-bottom: 1.5em;
}

.section-title {
  font-size: 1em;
  font-weight: bold;
  color: #ddd;
  margin-bottom: 0.8em;
  border-left: 0.2em solid #4a9eff;
  padding-left: 0.5em;
}

.form-item {
  margin-bottom: 1.2em;
}

.form-item label {
  display: block;
  font-size: 0.9em;
  color: #bbb;
  margin-bottom: 0.4em;
}

.desc {
  font-size: 0.8em;
  color: #666;
  margin-bottom: 0.4em;
}

.input-field {
  width: 100%;
  background: #222;
  border: 1px solid #444;
  color: #ddd;
  padding: 0.6em 0.8em;
  border-radius: 0.3em;
  font-family: monospace;
  font-size: 0.9em;
}

.input-field:focus {
  outline: none;
  border-color: #4a9eff;
  background: #1a1a1a;
}
.toggle-label { align-items: center; display: flex !important; gap: .55em; }
</style>
