import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDialog, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { llmApi } from '@/api'
import type { LLMConfigDTO } from '@/types/api'
import { useUiStore } from '@/stores/ui'

export interface LlmPreset {
  name: string
  base_url: string
  model_name: string
  fast_model_name: string
  api_format: LLMConfigDTO['api_format']
  badge?: 'recommended' | 'free' | 'local'
  isLocal?: boolean
}

const createEmptyConfig = (): LLMConfigDTO => ({
  base_url: '',
  api_key: '',
  model_name: '',
  fast_model_name: '',
  mode: 'default',
  max_concurrent_requests: 10,
  api_format: 'openai',
  use_separate_fast_config: false,
  fast_base_url: '',
  fast_api_key: '',
  fast_api_format: 'openai',
})

const LOCAL_LLM_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '0.0.0.0'])

function getCredentialScope(baseUrl: string): string {
  const raw = baseUrl.trim()
  if (!raw) {
    return ''
  }

  try {
    const url = new URL(raw)
    return url.host.toLowerCase()
  } catch {
    return raw.toLowerCase()
  }
}

function isLocalOpenAiEndpoint(config: LLMConfigDTO): boolean {
  if ((config.api_format || 'openai') !== 'openai') {
    return false
  }

  try {
    const url = new URL(config.base_url.trim())
    return LOCAL_LLM_HOSTS.has(url.hostname.toLowerCase())
  } catch {
    return false
  }
}

export function useLlmConfigPanel(onConfigSaved: () => void) {
  const { t } = useI18n()
  const message = useMessage()
  const dialog = useDialog()
  const uiStore = useUiStore()
  const { llmConfigError } = storeToRefs(uiStore)
  const loading = ref(false)
  const testing = ref(false)
  const showHelpModal = ref(false)
  const hasSavedApiKey = ref(false)
  const hasSavedFastApiKey = ref(false)
  const apiKeyFocused = ref(false)
  const fastApiKeyFocused = ref(false)
  const savedCredentialScope = ref('')
  const savedFastCredentialScope = ref('')
  const config = ref<LLMConfigDTO>(createEmptyConfig())

  const hasDraftApiKey = computed(() => Boolean(config.value.api_key))
  const showSavedApiKeyMask = computed(
    () => hasSavedApiKey.value && !hasDraftApiKey.value && !apiKeyFocused.value,
  )
  const apiKeyPlaceholder = computed(() => (
    hasSavedApiKey.value
      ? t('llm.placeholders.api_key_saved')
      : t('llm.placeholders.api_key')
  ))
  const showSavedFastApiKeyMask = computed(
    () => hasSavedFastApiKey.value && !config.value.fast_api_key && !fastApiKeyFocused.value,
  )
  const fastApiKeyPlaceholder = computed(() => (
    hasSavedFastApiKey.value
      ? t('llm.placeholders.api_key_saved')
      : t('llm.placeholders.api_key')
  ))

  const modeOptions = computed(() => [
    { label: t('llm.modes.default'), value: 'default', desc: t('llm.modes.default_desc') },
    { label: t('llm.modes.normal'), value: 'normal', desc: t('llm.modes.normal_desc') },
    { label: t('llm.modes.fast'), value: 'fast', desc: t('llm.modes.fast_desc') },
  ])

  const apiFormatOptions = computed(() => [
    { label: t('llm.formats.openai'), value: 'openai', desc: t('llm.formats.openai_desc') },
    { label: t('llm.formats.anthropic'), value: 'anthropic', desc: t('llm.formats.anthropic_desc') },
  ])

  const presets = computed<LlmPreset[]>(() => [
    {
      name: t('llm.presets.qwen'),
      base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      model_name: 'qwen3.7-plus',
      fast_model_name: 'qwen3.5-flash',
      api_format: 'openai',
      badge: 'recommended',
    },
    {
      name: t('llm.presets.gemini'),
      base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
      model_name: 'gemini-3.1-pro-preview',
      fast_model_name: 'gemini-3.5-flash',
      api_format: 'openai',
      badge: 'recommended',
    },
    {
      name: t('llm.presets.openai'),
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-5.6-terra',
      fast_model_name: 'gpt-5.6-luna',
      api_format: 'openai',
    },
    {
      name: t('llm.presets.anthropic'),
      base_url: 'https://api.anthropic.com',
      model_name: 'claude-sonnet-5',
      fast_model_name: 'claude-haiku-4-5',
      api_format: 'anthropic',
    },
    {
      name: t('llm.presets.kimi'),
      base_url: 'https://api.moonshot.cn/v1',
      model_name: 'kimi-k3',
      fast_model_name: 'kimi-k2.6',
      api_format: 'openai',
    },
    {
      name: t('llm.presets.deepseek'),
      base_url: 'https://api.deepseek.com',
      model_name: 'deepseek-v4-pro',
      fast_model_name: 'deepseek-v4-flash',
      api_format: 'openai',
      badge: 'free',
    },
    {
      name: t('llm.presets.groq'),
      base_url: 'https://api.groq.com/openai/v1',
      model_name: 'openai/gpt-oss-120b',
      fast_model_name: 'openai/gpt-oss-20b',
      api_format: 'openai',
      badge: 'free',
    },
    {
      name: t('llm.presets.minimax'),
      base_url: 'https://api.minimax.io/v1',
      model_name: 'MiniMax-M3',
      fast_model_name: 'MiniMax-M2.7-highspeed',
      api_format: 'openai',
    },
    {
      name: t('llm.presets.longcat'),
      base_url: 'https://api.longcat.chat/openai',
      model_name: 'LongCat-2.0',
      fast_model_name: 'LongCat-2.0',
      api_format: 'openai',
      badge: 'free',
    },
    {
      name: t('llm.presets.siliconflow'),
      base_url: 'https://api.siliconflow.cn/v1',
      model_name: 'Qwen/Qwen3.6-27B',
      fast_model_name: 'Qwen/Qwen3-8B',
      api_format: 'openai',
    },
    {
      name: t('llm.presets.openrouter'),
      base_url: 'https://openrouter.ai/api/v1',
      model_name: 'anthropic/claude-sonnet-5',
      fast_model_name: 'google/gemini-3.5-flash',
      api_format: 'openai',
    },
    {
      name: t('llm.presets.ollama'),
      base_url: 'http://localhost:11434/v1',
      model_name: 'qwen3.5:9b',
      fast_model_name: 'qwen3:8b',
      api_format: 'openai',
      badge: 'local',
      isLocal: true,
    },
  ])

  const activePresetName = computed(() => {
    const matched = presets.value.find(preset => (
      config.value.base_url === preset.base_url
      && config.value.model_name === preset.model_name
      && config.value.fast_model_name === preset.fast_model_name
      && config.value.api_format === preset.api_format
    ))
    return matched?.name ?? ''
  })

  async function fetchConfig() {
    loading.value = true
    try {
      const result = await llmApi.fetchConfig()
      hasSavedApiKey.value = result.has_api_key
      hasSavedFastApiKey.value = result.has_fast_api_key
      savedCredentialScope.value = getCredentialScope(result.base_url)
      savedFastCredentialScope.value = getCredentialScope(result.fast_base_url)
      config.value = {
        base_url: result.base_url,
        api_key: '',
        model_name: result.model_name,
        fast_model_name: result.fast_model_name,
        mode: result.mode,
        max_concurrent_requests: result.max_concurrent_requests,
        api_format: result.api_format || 'openai',
        use_separate_fast_config: result.use_separate_fast_config,
        fast_base_url: result.fast_base_url,
        fast_api_key: '',
        fast_api_format: result.fast_api_format || 'openai',
      }
    } catch {
      message.error(t('llm.fetch_failed'))
    } finally {
      loading.value = false
    }
  }

  function applyPreset(preset: LlmPreset) {
    config.value.base_url = preset.base_url
    config.value.model_name = preset.model_name
    config.value.fast_model_name = preset.fast_model_name
    config.value.api_format = preset.api_format || 'openai'

    if (preset.isLocal) {
      message.info(t('llm.preset_applied', { name: preset.name, extra: t('llm.preset_extra_local') }))
    } else if (hasDraftApiKey.value) {
      message.info(t('llm.preset_applied', { name: preset.name, extra: t('llm.preset_extra_keep_draft_key') }))
    } else if (hasSavedApiKey.value) {
      message.info(t('llm.preset_applied', { name: preset.name, extra: t('llm.preset_extra_keep_saved_key') }))
    } else {
      message.info(t('llm.preset_applied', { name: preset.name, extra: t('llm.preset_extra_key') }))
    }
  }

  async function handleTestAndSave() {
    if (!config.value.base_url) {
      message.warning(t('llm.base_url_required'))
      return
    }

    testing.value = true
    try {
      const payload = { ...config.value }
      const shouldClearOldKey = hasSavedApiKey.value
        && !payload.api_key
        && (
          isLocalOpenAiEndpoint(payload)
          || getCredentialScope(payload.base_url) !== savedCredentialScope.value
        )
      if (shouldClearOldKey) {
        payload.clear_api_key = true
      }
      const shouldClearOldFastKey = payload.use_separate_fast_config
        && hasSavedFastApiKey.value
        && !payload.fast_api_key
        && (
          isLocalOpenAiEndpoint({ ...payload, base_url: payload.fast_base_url, api_format: payload.fast_api_format })
          || getCredentialScope(payload.fast_base_url) !== savedFastCredentialScope.value
        )
      if (shouldClearOldFastKey) {
        payload.clear_fast_api_key = true
      }

      await llmApi.testConnection(payload)
      message.success(t('llm.test_success'))
      const saved = await llmApi.saveConfig(payload)
      hasSavedApiKey.value = saved.config?.has_api_key ?? Boolean(config.value.api_key || hasSavedApiKey.value)
      hasSavedFastApiKey.value = saved.config?.has_fast_api_key ?? Boolean(config.value.fast_api_key || hasSavedFastApiKey.value)
      savedCredentialScope.value = getCredentialScope(saved.config?.base_url ?? payload.base_url)
      savedFastCredentialScope.value = getCredentialScope(saved.config?.fast_base_url ?? payload.fast_base_url)
      config.value.api_key = ''
      config.value.fast_api_key = ''
      message.success(t('llm.save_success'))
      uiStore.clearLlmConfigError()
      onConfigSaved()
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : t('llm.test_save_failed_title')
      dialog.error({
        title: t('llm.test_save_failed_title'),
        content: errorMsg,
        positiveText: t('common.confirm'),
      })
    } finally {
      testing.value = false
    }
  }

  function clearSavedApiKey() {
    if (!hasSavedApiKey.value || testing.value) {
      return
    }

    dialog.warning({
      title: t('llm.clear_key.title'),
      content: t('llm.clear_key.content'),
      positiveText: t('llm.clear_key.confirm'),
      negativeText: t('common.cancel'),
      onPositiveClick: async () => {
        testing.value = true
        try {
          const saved = await llmApi.saveConfig({
            ...config.value,
            api_key: '',
            clear_api_key: true,
          })
          hasSavedApiKey.value = saved.config?.has_api_key ?? false
          config.value.api_key = ''
          message.success(t('llm.clear_key.success'))
        } catch (error) {
          const errorMsg = error instanceof Error ? error.message : t('llm.clear_key.failed')
          dialog.error({
            title: t('llm.clear_key.failed'),
            content: errorMsg,
            positiveText: t('common.confirm'),
          })
        } finally {
          testing.value = false
        }
      },
    })
  }

  function clearSavedFastApiKey() {
    if (!hasSavedFastApiKey.value || testing.value) return
    dialog.warning({
      title: t('llm.clear_key.title'),
      content: t('llm.clear_key.content'),
      positiveText: t('llm.clear_key.confirm'),
      negativeText: t('common.cancel'),
      onPositiveClick: async () => {
        testing.value = true
        try {
          const saved = await llmApi.saveConfig({ ...config.value, fast_api_key: '', clear_fast_api_key: true })
          hasSavedFastApiKey.value = saved.config?.has_fast_api_key ?? false
          config.value.fast_api_key = ''
          message.success(t('llm.clear_key.success'))
        } finally {
          testing.value = false
        }
      },
    })
  }

  onMounted(() => {
    void fetchConfig()
  })

  return {
    loading,
    testing,
    showHelpModal,
    hasSavedApiKey,
    hasSavedFastApiKey,
    apiKeyFocused,
    fastApiKeyFocused,
    hasDraftApiKey,
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
    fetchConfig,
    applyPreset,
    handleTestAndSave,
    clearSavedApiKey,
    clearSavedFastApiKey,
  }
}
