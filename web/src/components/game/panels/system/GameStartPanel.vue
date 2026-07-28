<script setup lang="ts">
import { computed, ref } from 'vue'
import { NForm, NFormItem, NInputNumber, NButton, NInput, NSelect, NCheckbox, useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'

import { useSettingStore } from '@/stores/setting'
import { logError } from '@/utils/appError'
import MapPresetPreview from './MapPresetPreview.vue'

const { t } = useI18n()
const settingStore = useSettingStore()

defineProps<{
  readonly: boolean
}>()

const message = useMessage()
const loading = ref(false)
const worldSecretSelectOptions = computed(() => settingStore.worldSecretOptions.map(option => ({
  label: option.title,
  value: option.id,
})))

async function startGame() {
  try {
    loading.value = true
    await settingStore.startGameWithDraft()
    message.success(t('game_start.messages.start_success'))
  } catch (e) {
    message.error(t('game_start.messages.start_failed'))
    logError('GameStartPanel start game', e)
    loading.value = false
  }
}
</script>

<template>
  <div class="game-start-panel">
    <div class="panel-header">
      <h3>{{ t('game_start.title') }}</h3>
      <p class="description">{{ t('game_start.description') }}</p>
    </div>

    <n-form
      label-placement="left"
      label-width="160"
      require-mark-placement="right-hanging"
      :disabled="readonly"
    >
      <div class="map-section">
        <div class="map-section-title">{{ t('game_start.labels.map') }}</div>
        <div class="map-options">
          <button
            v-for="preset in settingStore.mapPresets"
            :key="preset.id"
            class="map-option"
            :class="{ active: settingStore.newGameDraft.map_id === preset.id }"
            type="button"
            :disabled="readonly"
            @click="settingStore.updateNewGameDraft({ map_id: preset.id })"
          >
            <MapPresetPreview :preset-id="preset.id" />
            <span class="map-option-body">
              <span class="map-option-title">{{ preset.name }}</span>
              <span class="map-option-desc">{{ preset.desc }}</span>
            </span>
          </button>
        </div>
      </div>

      <n-form-item :label="t('game_start.labels.init_npc_num')" path="init_npc_num">
        <n-input-number
          :value="settingStore.newGameDraft.init_npc_num"
          :min="0"
          :max="100"
          @update:value="(value) => settingStore.updateNewGameDraft({ init_npc_num: value ?? 0 })"
        />
      </n-form-item>

      <n-form-item :label="t('game_start.labels.sect_num')" path="sect_num">
        <n-input-number
          :value="settingStore.newGameDraft.sect_num"
          :min="0"
          :max="10"
          @update:value="(value) => settingStore.updateNewGameDraft({ sect_num: value ?? 0 })"
        />
      </n-form-item>
      <div class="tip-text" style="margin-top: -12px;">
        {{ t('game_start.tips.sect_num') }}
      </div>

      <n-form-item :label="t('game_start.labels.new_npc_rate')" path="npc_awakening_rate_per_month">
        <n-input-number
          :value="settingStore.newGameDraft.npc_awakening_rate_per_month"
          :min="0"
          :max="1"
          :step="0.001"
          :format="(val: number) => `${(val * 100).toFixed(1)}%`"
          :parse="(val: string) => parseFloat(val) / 100"
          @update:value="(value) => settingStore.updateNewGameDraft({ npc_awakening_rate_per_month: value ?? 0 })"
        />
      </n-form-item>

      <n-form-item :label="t('game_start.labels.world_lore')" path="world_lore">
        <n-input
          :value="settingStore.newGameDraft.world_lore"
          type="textarea"
          :placeholder="t('game_start.placeholders.world_lore')"
          :autosize="{ minRows: 4, maxRows: 6 }"
          maxlength="800"
          show-count
          @update:value="(value) => settingStore.updateNewGameDraft({ world_lore: value })"
        />
      </n-form-item>

      <n-form-item :label="t('game_start.labels.world_secret')" path="world_secret_id">
        <n-select
          :value="settingStore.newGameDraft.world_secret_id ?? 'none'"
          :options="worldSecretSelectOptions"
          @update:value="(value) => settingStore.updateNewGameDraft({ world_secret_id: String(value || 'none') })"
        />
      </n-form-item>

      <n-form-item :label="t('game_start.labels.test_mode')" path="test_mode">
        <div>
          <n-checkbox
            :checked="settingStore.newGameDraft.test_mode"
            @update:checked="(value) => settingStore.updateNewGameDraft({ test_mode: value })"
          >
            {{ t('game_start.options.test_mode') }}
          </n-checkbox>
          <div class="tip-text test-mode-tip">{{ t('game_start.tips.test_mode') }}</div>
        </div>
      </n-form-item>

      <div class="actions" v-if="!readonly">
        <n-button type="primary" size="large" @click="startGame" :loading="loading">
          {{ t('game_start.actions.start') }}
        </n-button>
      </div>
    </n-form>
  </div>
</template>

<style scoped>
.game-start-panel {
  color: #eee;
  max-width: 600px;
  margin: 0 auto;
}

.panel-header {
  margin-bottom: 2em;
  text-align: center;
}

.description {
  color: #888;
  font-size: 0.9em;
}

.tip-text {
  margin-left: 160px;
  margin-bottom: 24px;
  color: #aaa;
  font-size: 0.85em;
  line-height: 1.5;
}

.test-mode-tip {
  margin: 6px 0 0;
}

.map-section {
  margin-bottom: 24px;
}

.map-section-title {
  margin-bottom: 10px;
  color: #eee;
  font-size: 0.95rem;
  font-weight: 600;
}

.map-options {
  display: grid;
  width: 100%;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.map-option {
  min-height: 168px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: #eee;
  text-align: left;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: border-color 0.16s ease, background 0.16s ease;
}

.map-option:hover:not(:disabled) {
  border-color: rgba(121, 187, 255, 0.5);
  background: rgba(121, 187, 255, 0.08);
}

.map-option.active {
  border-color: #63b3ff;
  background: rgba(99, 179, 255, 0.14);
}

.map-option.active :deep(.map-preset-preview) {
  filter: brightness(1.08) saturate(1.06);
}

.map-option:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.map-option-title,
.map-option-desc {
  display: block;
}

.map-option-body {
  display: block;
  flex: 1;
  padding: 10px 2px 0;
}

.map-option-title {
  margin-bottom: 5px;
  font-size: 0.95rem;
  font-weight: 600;
}

.map-option-desc {
  color: #aaa;
  font-size: 0.82rem;
  line-height: 1.45;
}

@media (max-width: 760px) {
  .map-options {
    grid-template-columns: 1fr;
  }
}

.actions {
  display: flex;
  justify-content: center;
  margin-top: 2em;
}
</style>
