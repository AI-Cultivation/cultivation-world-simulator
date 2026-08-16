<script setup lang="ts">
import type { LLMConfigDTO } from '@/types/api'

type ApiFormatOption = { label: string; desc: string; value: LLMConfigDTO['api_format'] }

defineProps<{
  config: LLMConfigDTO
  title: string
  apiFormatOptions: ApiFormatOption[]
  apiKeyLabel: string
  apiKeyPlaceholder: string
  hasSavedApiKey: boolean
  showSavedApiKeyMask: boolean
  savedApiKeyHint: string
  clearSavedKeyLabel: string
  baseUrlLabel: string
  baseUrlPlaceholder: string
  apiFormatLabel: string
  testing: boolean
}>()

const emit = defineEmits<{
  (e: 'api-key-focus'): void
  (e: 'api-key-blur'): void
  (e: 'clear-saved-key'): void
}>()
</script>

<template>
  <div class="section">
    <div class="section-title">{{ title }}</div>
    <div class="form-item">
      <label>{{ baseUrlLabel }}</label>
      <input v-model="config.fast_base_url" type="text" :placeholder="baseUrlPlaceholder" class="input-field" />
    </div>
    <div class="form-item">
      <label>{{ apiKeyLabel }}</label>
      <div class="api-key-input-wrap">
        <input v-model="config.fast_api_key" type="password" :placeholder="apiKeyPlaceholder" class="input-field" @focus="emit('api-key-focus')" @blur="emit('api-key-blur')" />
        <div v-if="showSavedApiKeyMask" class="saved-key-mask">********************</div>
      </div>
      <div v-if="hasSavedApiKey" class="secret-status-row">
        <span>{{ savedApiKeyHint }}</span>
        <button type="button" class="clear-secret-btn" :disabled="testing" @click="emit('clear-saved-key')">{{ clearSavedKeyLabel }}</button>
      </div>
    </div>
    <div class="form-item">
      <label>{{ apiFormatLabel }}</label>
      <div class="format-options">
        <label v-for="opt in apiFormatOptions" :key="opt.value" class="format-radio" :class="{ active: config.fast_api_format === opt.value }">
          <input v-model="config.fast_api_format" type="radio" :value="opt.value" class="hidden-radio" />
          <div><div class="radio-label">{{ opt.label }}</div><div class="radio-desc">{{ opt.desc }}</div></div>
        </label>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section { margin-bottom: 1.5em; }
.section-title { font-size: 1em; font-weight: bold; color: #ddd; margin-bottom: .8em; border-left: .2em solid #4a9eff; padding-left: .5em; }
.form-item { margin-bottom: 1.2em; }
.form-item label { display: block; font-size: .9em; color: #bbb; margin-bottom: .4em; }
.input-field { width: 100%; background: #222; border: 1px solid #444; color: #ddd; padding: .6em .8em; border-radius: .3em; font-family: monospace; font-size: .9em; }
.api-key-input-wrap { position: relative; }
.saved-key-mask { position: absolute; inset: 1px auto 1px .8em; display: flex; align-items: center; color: #b9c0c8; pointer-events: none; font-family: monospace; font-size: .9em; }
.secret-status-row { display: flex; justify-content: space-between; gap: .8em; margin-top: .45em; color: #7f98ad; font-size: .78em; }
.clear-secret-btn { background: transparent; border: 1px solid #4c3b3b; border-radius: .3em; color: #d49b9b; cursor: pointer; font-size: .78em; padding: .25em .65em; }
.format-options { display: flex; gap: .5em; }
.format-radio { display: flex; background: #222; border: 1px solid #333; padding: .35em .65em; border-radius: .3em; cursor: pointer; text-align: center; }
.format-radio.active { border-color: #4a9eff; background: rgba(74, 158, 255, .1); }
.hidden-radio { display: none; }
.radio-label { color: #eee; font-weight: bold; margin-bottom: .3em; }
.radio-desc { color: #888; font-size: .85em; line-height: 1.4; }
</style>
