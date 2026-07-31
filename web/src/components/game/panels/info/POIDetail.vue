<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { POIDetail } from '@/types/core'

const props = defineProps<{
  data: POIDetail
}>()

const { t } = useI18n()
const deceased = computed(() => props.data.deceased)
const goods = computed(() => props.data.grave_goods)
const treasure = computed(() => props.data.treasure)
</script>

<template>
  <div class="poi-detail">
    <div class="section">
      <div class="section-title">{{ t(data.kind === 'treasure' ? 'game.info_panel.poi.sections.treasure' : 'game.info_panel.poi.sections.grave') }}</div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.location') }}</span>
        <strong>({{ data.x }}, {{ data.y }})</strong>
      </div>
      <p v-if="data.desc" class="desc">{{ data.desc }}</p>
    </div>

    <div v-if="deceased" class="section">
      <div class="section-title">{{ t('game.info_panel.poi.sections.deceased') }}</div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.name') }}</span>
        <strong>{{ deceased.name }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.realm') }}</span>
        <strong>{{ deceased.realm_at_death }} {{ deceased.stage_at_death }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.death_reason') }}</span>
        <strong>{{ deceased.death_reason }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.sect') }}</span>
        <strong>{{ deceased.sect_name_at_death || t('game.info_panel.poi.rogue') }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.alignment') }}</span>
        <strong>{{ deceased.alignment_at_death || t('game.info_panel.poi.unknown') }}</strong>
      </div>
    </div>

    <div v-if="treasure" class="section">
      <div class="section-title">{{ t('game.info_panel.poi.sections.treasure_info') }}</div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.source') }}</span>
        <strong>{{ treasure.source_label || treasure.source }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.realm') }}</span>
        <strong>{{ treasure.realm_name || treasure.realm }}</strong>
      </div>
      <div class="kv">
        <span>{{ t('game.info_panel.poi.attempt_count') }}</span>
        <strong>{{ treasure.attempt_count }}</strong>
      </div>
      <div class="kv" v-if="treasure.expires_month != null">
        <span>{{ t('game.info_panel.poi.expires_month') }}</span>
        <strong>{{ treasure.expires_month }}</strong>
      </div>
      <div class="item-row" v-if="treasure.item">
        <span>{{ treasure.item.kind === 'weapon' ? t('game.info_panel.poi.weapon') : t('game.info_panel.poi.auxiliary') }}</span>
        <strong>{{ treasure.item.name }}</strong>
      </div>
      <div v-else class="empty">{{ t('game.info_panel.poi.empty_treasure') }}</div>
    </div>

    <div v-if="goods" class="section">
      <div class="section-title">{{ t('game.info_panel.poi.sections.goods') }}</div>
      <div v-if="goods?.weapon" class="item-row">
        <span>{{ t('game.info_panel.poi.weapon') }}</span>
        <strong>{{ goods.weapon.name }}</strong>
      </div>
      <div v-if="goods?.auxiliary" class="item-row">
        <span>{{ t('game.info_panel.poi.auxiliary') }}</span>
        <strong>{{ goods.auxiliary.name }}</strong>
      </div>
      <div v-if="!goods?.weapon && !goods?.auxiliary" class="empty">{{ t('game.info_panel.poi.empty_goods') }}</div>
    </div>
  </div>
</template>

<style scoped>
.poi-detail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow: auto;
  min-height: 0;
  padding-right: 4px;
}

.section {
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 700;
  color: #e6d8b8;
  margin-bottom: 8px;
}

.kv,
.item-row {
  display: grid;
  grid-template-columns: 76px 1fr;
  gap: 8px;
  align-items: start;
  font-size: 13px;
  line-height: 1.5;
}

.kv span,
.item-row span {
  color: var(--color-text-secondary);
}

.kv strong,
.item-row strong {
  color: #eee;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.desc,
.empty {
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 1.55;
  margin: 6px 0 0;
}
</style>
