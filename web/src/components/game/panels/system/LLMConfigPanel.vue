<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useLlmConfigPanel } from '@/composables/useLlmConfigPanel'
import LlmHelpModal from './llm-config/LlmHelpModal.vue'
import LlmPresetSection from './llm-config/LlmPresetSection.vue'
import LlmRunModeSection from './llm-config/LlmRunModeSection.vue'
import LlmApiConfigSection from './llm-config/LlmApiConfigSection.vue'
import LlmFastServiceSection from './llm-config/LlmFastServiceSection.vue'
import LlmModelSection from './llm-config/LlmModelSection.vue'
import LlmConfigActions from './llm-config/LlmConfigActions.vue'

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'config-saved'): void
}>()

const {
  loading,
  testing,
  showHelpModal,
  hasSavedApiKey,
  hasSavedFastApiKey,
  apiKeyFocused,
  fastApiKeyFocused,
  showSavedApiKeyMask,
  apiKeyPlaceholder,
  showSavedFastApiKeyMask,
  fastApiKeyPlaceholder,
  llmConfigError,
  config,
  modeOptions,
  apiFormatOptions,
  presets,
  activePresetName,
  applyPreset,
  handleTestAndSave,
  clearSavedApiKey,
  clearSavedFastApiKey,
} = useLlmConfigPanel(() => emit('config-saved'))
</script>

<template>
  <div class="llm-panel">
    <div v-if="loading" class="loading">{{ t('llm.loading') }}</div>
    <div v-else class="config-form">
      <div v-if="llmConfigError" class="error-banner">
        {{ llmConfigError }}
      </div>
      
      <LlmPresetSection
        :title="t('llm.sections.quick_fill')"
        :presets="presets"
        :active-preset-name="activePresetName"
        :badge-label="badge => t(`llm.badges.${badge}`)"
        @apply="applyPreset"
      />

      <LlmApiConfigSection
        :config="config"
        :api-format-options="apiFormatOptions"
        :title="t('llm.sections.api_config')"
        :api-key-label="t('llm.labels.api_key')"
        :api-key-help-label="t('llm.labels.what_is_api')"
        :api-key-placeholder="apiKeyPlaceholder"
        :show-saved-api-key-mask="showSavedApiKeyMask"
        :has-saved-api-key="hasSavedApiKey"
        :saved-api-key-hint="t('llm.api_key_saved_hint')"
        :clear-saved-key-label="t('llm.actions.clear_saved_key')"
        :testing="testing"
        :base-url-label="t('llm.labels.base_url')"
        :base-url-placeholder="t('llm.placeholders.base_url')"
        :api-format-label="t('llm.labels.api_format')"
        :max-concurrent-requests-label="t('llm.labels.max_concurrent_requests')"
        :max-concurrent-requests-desc="t('llm.descs.max_concurrent_requests')"
        :max-concurrent-requests-placeholder="t('llm.placeholders.max_concurrent_requests')"
        @open-help="showHelpModal = true"
        @api-key-focus="apiKeyFocused = true"
        @api-key-blur="apiKeyFocused = false"
        @clear-saved-key="clearSavedApiKey"
      />

      <LlmModelSection
        :config="config"
        :title="t('llm.sections.model_selection')"
        :normal-label="t('llm.labels.normal_model')"
        :normal-desc="t('llm.descs.normal_model')"
        :normal-placeholder="t('llm.placeholders.normal_model')"
        :fast-label="t('llm.labels.fast_model')"
        :fast-desc="t('llm.descs.fast_model')"
        :fast-placeholder="t('llm.placeholders.fast_model')"
        :separate-fast-config-label="t('llm.labels.separate_fast_config')"
        :separate-fast-config-desc="t('llm.descs.separate_fast_config')"
      />

      <LlmFastServiceSection
        v-if="config.use_separate_fast_config"
        :config="config"
        :title="t('llm.sections.api_config')"
        :api-format-options="apiFormatOptions"
        :api-key-label="t('llm.labels.api_key')"
        :api-key-placeholder="fastApiKeyPlaceholder"
        :has-saved-api-key="hasSavedFastApiKey"
        :show-saved-api-key-mask="showSavedFastApiKeyMask"
        :saved-api-key-hint="t('llm.api_key_saved_hint')"
        :clear-saved-key-label="t('llm.actions.clear_saved_key')"
        :base-url-label="t('llm.labels.base_url')"
        :base-url-placeholder="t('llm.placeholders.base_url')"
        :api-format-label="t('llm.labels.api_format')"
        :testing="testing"
        @api-key-focus="fastApiKeyFocused = true"
        @api-key-blur="fastApiKeyFocused = false"
        @clear-saved-key="clearSavedFastApiKey"
      />

      <LlmRunModeSection
        v-model="config.mode"
        :title="t('llm.sections.run_mode')"
        :options="modeOptions"
      />

      <LlmConfigActions
        :testing="testing"
        :label="testing ? t('llm.actions.testing') : t('llm.actions.test_and_save')"
        @save="handleTestAndSave"
      />

    </div>

    <LlmHelpModal v-if="showHelpModal" @close="showHelpModal = false" />
  </div>
</template>

<style scoped>
.llm-panel {
  height: 100%;
  overflow-y: auto;
  padding: 0 0.8em;
}

.loading {
  text-align: center;
  color: #888;
  padding: 3em;
}
.error-banner {
  background: rgba(155, 48, 48, 0.18);
  border: 1px solid rgba(225, 92, 92, 0.42);
  border-radius: 0.35em;
  color: #f0b7b7;
  line-height: 1.45;
  margin-bottom: 1em;
  max-height: 7em;
  overflow: auto;
  padding: 0.75em 0.9em;
  word-break: break-word;
}
/* Modal Styles */
.card {
  flex: 1;
  background: #16181d;
  border: 1px solid #333;
  border-radius: 0.5em;
  padding: 0.8em;
}

.card h5 {
  color: #8a9eff;
  margin: 0 0 0.5em 0;
  font-size: 0.95em;
}

.card p {
  font-size: 0.85em;
  color: #777;
  margin: 0;
}
</style>
