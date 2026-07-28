import { defineStore } from 'pinia';
import { computed, ref, type WritableComputedRef } from 'vue';

import i18n from '../locales';
import { defaultLocale, getHtmlLang, isEnabledLocale, type AppLocale } from '../locales/registry';
import { systemApi } from '../api/modules/system';
import { worldApi } from '../api/modules/world';
import type { AppSettingsDTO, RunConfigDTO } from '../types/api';
import { logWarn } from '../utils/appError';
import { useEventStore } from './event';
import { useMapStore } from './map';
import { useSectStore } from './sect';
import { useWorldStore } from './world';

function applyUiLocale(lang: string) {
  const localeRef = i18n.global.locale;
  if (typeof localeRef !== 'string') {
    (localeRef as WritableComputedRef<string>).value = lang;
  }

  document.documentElement.lang = getHtmlLang(lang);
}

function getFallbackWorldSecretOptions() {
  return [{ id: 'none', title: i18n.global.t('game.world_secret.option_none') }];
}

function getFallbackMapPresets() {
  return [{
    id: 'classic',
    name: i18n.global.t('game_start.fallback_map.name'),
    desc: i18n.global.t('game_start.fallback_map.desc'),
    size_label: '',
  }];
}

export const useSettingStore = defineStore('setting', () => {
  const eventStore = useEventStore();
  const mapStore = useMapStore();
  const sectStore = useSectStore();
  const worldStore = useWorldStore();

  const hydrated = ref(false);
  const loading = ref(false);

  const locale = ref<AppLocale>(defaultLocale);
  const sfxVolume = ref(0.5);
  const bgmVolume = ref(0.5);
  const isAutoSave = ref(false);
  const maxAutoSaves = ref(5);
  const mapPresets = ref<Array<{ id: string; name: string; desc: string; size_label?: string }>>([]);
  const worldSecretOptions = ref<Array<{ id: string; title: string }>>(getFallbackWorldSecretOptions());
  const newGameDraft = ref<RunConfigDTO>({
    content_locale: defaultLocale,
    map_id: 'classic',
    init_npc_num: 9,
    sect_num: 3,
    npc_awakening_rate_per_month: 0.01,
    world_lore: '',
    world_secret_id: 'none',
    test_mode: false,
  });

  const isReady = computed(() => hydrated.value && !loading.value);

  function applySettings(settings: AppSettingsDTO) {
    locale.value = settings.ui.locale;
    bgmVolume.value = settings.ui.audio.bgm_volume;
    sfxVolume.value = settings.ui.audio.sfx_volume;
    isAutoSave.value = settings.simulation.auto_save_enabled;
    maxAutoSaves.value = settings.simulation.max_auto_saves;
    newGameDraft.value = {
      ...settings.new_game_defaults,
      map_id: settings.new_game_defaults.map_id ?? 'classic',
      world_secret_id: settings.new_game_defaults.world_secret_id ?? 'none',
      test_mode: settings.new_game_defaults.test_mode ?? false,
    };
    applyUiLocale(locale.value);
  }

  async function loadMapPresets() {
    try {
      const presets = await worldApi.fetchMapPresets(locale.value);
      mapPresets.value = presets.length > 0
        ? presets
        : getFallbackMapPresets();
    } catch (e) {
      mapPresets.value = getFallbackMapPresets();
      logWarn('SettingStore load map presets', e);
    }
  }

  async function loadWorldSecretOptions() {
    try {
      const options = await worldApi.fetchWorldSecretOptions();
      worldSecretOptions.value = options.length > 0
        ? options
        : getFallbackWorldSecretOptions();
    } catch (e) {
      worldSecretOptions.value = getFallbackWorldSecretOptions();
      logWarn('SettingStore load world secret options', e);
    }
  }

  async function refreshLocalizedRuntimeData() {
    const currentFilter = { ...eventStore.eventsFilter };

    try {
      await mapStore.preloadMap();
    } catch (e) {
      logWarn('SettingStore refresh localized map', e);
    }

    if (!worldStore.isLoaded) {
      return;
    }

    try {
      await worldStore.fetchState();
      await eventStore.resetEvents(currentFilter);
      await sectStore.refreshTerritories();
    } catch (e) {
      logWarn('SettingStore refresh localized runtime data', e);
    }
  }

  async function hydrate() {
    if (loading.value) return;

    loading.value = true;
    try {
      const settings = await systemApi.fetchSettings();
      applySettings(settings);
      await loadMapPresets();
      await loadWorldSecretOptions();
    } catch (e) {
      logWarn('SettingStore hydrate', e);
      applyUiLocale(locale.value);
    } finally {
      hydrated.value = true;
      loading.value = false;
    }
  }

  async function setLocale(lang: string) {
    const nextLocale = isEnabledLocale(lang) ? lang : defaultLocale
    const previous = locale.value;
    const previousContentLocale = newGameDraft.value.content_locale;
    locale.value = nextLocale;
    newGameDraft.value = {
      ...newGameDraft.value,
      content_locale: nextLocale,
    };
    applyUiLocale(nextLocale);

    try {
      const settings = await systemApi.patchSettings({
        ui: { locale: nextLocale },
        new_game_defaults: { content_locale: nextLocale },
      });
      applySettings(settings);
      await loadMapPresets();
      await loadWorldSecretOptions();
      await refreshLocalizedRuntimeData();
    } catch (e) {
      locale.value = previous;
      newGameDraft.value = {
        ...newGameDraft.value,
        content_locale: previousContentLocale,
      };
      applyUiLocale(previous);
      logWarn('SettingStore set locale', e);
    }
  }

  async function setSfxVolume(volume: number) {
    const previous = sfxVolume.value;
    sfxVolume.value = volume;

    try {
      const settings = await systemApi.patchSettings({ ui: { audio: { sfx_volume: volume } } });
      applySettings(settings);
    } catch (e) {
      sfxVolume.value = previous;
      logWarn('SettingStore set sfx volume', e);
    }
  }

  async function setBgmVolume(volume: number) {
    const previous = bgmVolume.value;
    bgmVolume.value = volume;

    try {
      const settings = await systemApi.patchSettings({ ui: { audio: { bgm_volume: volume } } });
      applySettings(settings);
    } catch (e) {
      bgmVolume.value = previous;
      logWarn('SettingStore set bgm volume', e);
    }
  }

  async function setAutoSave(enabled: boolean) {
    const previous = isAutoSave.value;
    isAutoSave.value = enabled;

    try {
      const settings = await systemApi.patchSettings({ simulation: { auto_save_enabled: enabled } });
      applySettings(settings);
    } catch (e) {
      isAutoSave.value = previous;
      logWarn('SettingStore set auto save', e);
    }
  }

  function updateNewGameDraft(patch: Partial<RunConfigDTO>) {
    newGameDraft.value = {
      ...newGameDraft.value,
      ...patch,
    };
  }

  async function saveNewGameDefaults() {
    const payload = { ...newGameDraft.value };
    newGameDraft.value = payload;
    try {
      const settings = await systemApi.patchSettings({
        new_game_defaults: payload,
      });
      applySettings(settings);
      return true;
    } catch (e) {
      logWarn('SettingStore save new game defaults', e);
      return false;
    }
  }

  async function startGameWithDraft() {
    const saved = await saveNewGameDefaults();
    if (!saved) {
      throw new Error(i18n.global.t('ui.new_game_defaults_save_failed'));
    }
    return systemApi.startGame({ ...newGameDraft.value });
  }

  return {
    hydrated,
    loading,
    isReady,
    locale,
    sfxVolume,
    bgmVolume,
    isAutoSave,
    maxAutoSaves,
    newGameDraft,
    mapPresets,
    worldSecretOptions,
    hydrate,
    loadMapPresets,
    loadWorldSecretOptions,
    setLocale,
    setSfxVolume,
    setBgmVolume,
    setAutoSave,
    updateNewGameDraft,
    saveNewGameDefaults,
    startGameWithDraft,
  };
});
