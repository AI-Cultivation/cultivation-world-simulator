import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { getExpectedHtmlLang, testDefaultLocale, testFallbackLocale } from '@/__tests__/utils/i18n'

const {
  mockFetchSettings,
  mockPatchSettings,
  mockStartGame,
  mockFetchMapPresets,
  mockFetchWorldSecretOptions,
  mockMapPreload,
  mockWorldFetchState,
  mockSectRefreshTerritories,
  mockEventResetEvents,
} = vi.hoisted(() => ({
  mockFetchSettings: vi.fn(),
  mockPatchSettings: vi.fn(),
  mockStartGame: vi.fn(),
  mockFetchMapPresets: vi.fn(),
  mockFetchWorldSecretOptions: vi.fn(),
  mockMapPreload: vi.fn(),
  mockWorldFetchState: vi.fn(),
  mockSectRefreshTerritories: vi.fn(),
  mockEventResetEvents: vi.fn(),
}))

let mockI18nLocale: { value: string } | string = { value: testDefaultLocale }
let mockI18nMode = 'composition'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value))
}

const baseSettings = {
  schema_version: 2,
  ui: {
    locale: testDefaultLocale,
    audio: {
      bgm_volume: 0.5,
      sfx_volume: 0.5,
    },
  },
  simulation: {
    auto_save_enabled: false,
    max_auto_saves: 5,
  },
  llm: {
    profile: {
      base_url: '',
      model_name: '',
      fast_model_name: '',
      mode: 'default',
      max_concurrent_requests: 10,
      has_api_key: false,
    },
  },
  new_game_defaults: {
    content_locale: testDefaultLocale,
    init_npc_num: 9,
    sect_num: 3,
    npc_awakening_rate_per_month: 0.01,
    world_lore: '',
    world_secret_id: 'none',
  },
}

vi.mock('@/locales', () => ({
  default: {
    get mode() {
      return mockI18nMode
    },
    global: {
      get locale() {
        return mockI18nLocale
      },
      set locale(val) {
        mockI18nLocale = val
      },
      t(key: string) {
        if (key === 'game.world_secret.option_none') return 'None'
        if (key === 'game_start.fallback_map.name') return 'Central Nine Provinces'
        if (key === 'game_start.fallback_map.desc') return ''
        return key
      },
    },
  },
}))

vi.mock('@/api/modules/system', () => ({
  systemApi: {
    fetchSettings: mockFetchSettings,
    patchSettings: mockPatchSettings,
    startGame: mockStartGame,
  },
}))

vi.mock('@/api/modules/world', () => ({
  worldApi: {
    fetchMapPresets: mockFetchMapPresets,
    fetchWorldSecretOptions: mockFetchWorldSecretOptions,
  },
}))

vi.mock('@/stores/map', () => ({
  useMapStore: () => ({
    preloadMap: mockMapPreload,
  }),
}))

vi.mock('@/stores/world', () => ({
  useWorldStore: () => ({
    isLoaded: true,
    fetchState: mockWorldFetchState,
  }),
}))

vi.mock('@/stores/sect', () => ({
  useSectStore: () => ({
    refreshTerritories: mockSectRefreshTerritories,
  }),
}))

vi.mock('@/stores/event', () => ({
  useEventStore: () => ({
    eventsFilter: {},
    resetEvents: mockEventResetEvents,
  }),
}))

import { useSettingStore } from '@/stores/setting'

describe('useSettingStore', () => {
  let store: ReturnType<typeof useSettingStore>
  let currentSettings: typeof baseSettings

  beforeEach(() => {
    vi.clearAllMocks()
    mockI18nLocale = { value: testDefaultLocale }
    mockI18nMode = 'composition'
    currentSettings = clone(baseSettings)
    mockMapPreload.mockResolvedValue(undefined)
    mockFetchMapPresets.mockResolvedValue([
      { id: 'classic', name: '九州中土', desc: '地貌均衡，适合默认体验。', size_label: '中型' },
    ])
    mockFetchWorldSecretOptions.mockResolvedValue([
      { id: 'none', title: '无' },
      { id: 'random', title: '随机' },
    ])
    mockWorldFetchState.mockResolvedValue(undefined)
    mockSectRefreshTerritories.mockResolvedValue(undefined)
    mockEventResetEvents.mockResolvedValue(undefined)
    mockFetchSettings.mockImplementation(async () => clone(currentSettings))
    mockPatchSettings.mockImplementation(async (patch: any) => {
      currentSettings = {
        ...clone(currentSettings),
        ui: {
          ...clone(currentSettings.ui),
          ...(patch.ui || {}),
          audio: {
            ...clone(currentSettings.ui.audio),
            ...(patch.ui?.audio || {}),
          },
        },
        simulation: {
          ...clone(currentSettings.simulation),
          ...(patch.simulation || {}),
        },
        new_game_defaults: {
          ...clone(currentSettings.new_game_defaults),
          ...(patch.new_game_defaults || {}),
        },
      }
      return clone(currentSettings)
    })
    mockStartGame.mockResolvedValue({ status: 'ok', message: 'started' })

    setActivePinia(createPinia())
    store = useSettingStore()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('hydrates settings from backend', async () => {
    await store.hydrate()

    expect(mockFetchSettings).toHaveBeenCalled()
    expect(store.hydrated).toBe(true)
    expect(store.locale).toBe(testDefaultLocale)
    expect(store.bgmVolume).toBe(0.5)
    expect(store.newGameDraft.init_npc_num).toBe(9)
    expect(mockFetchMapPresets).toHaveBeenCalledWith(testDefaultLocale)
  })

  it('uses localized fallback world secret option when meta loading fails', async () => {
    mockFetchWorldSecretOptions.mockRejectedValueOnce(new Error('network'))

    await store.hydrate()

    expect(store.worldSecretOptions).toEqual([{ id: 'none', title: 'None' }])
  })

  it('uses localized fallback map preset when map preset loading fails', async () => {
    mockFetchMapPresets.mockRejectedValueOnce(new Error('network'))

    await store.hydrate()

    expect(store.mapPresets).toEqual([{ id: 'classic', name: 'Central Nine Provinces', desc: '', size_label: '' }])
  })

  it('updates i18n locale after hydrate', async () => {
    mockFetchSettings.mockResolvedValueOnce({
      ...clone(baseSettings),
      ui: {
        ...clone(baseSettings.ui),
        locale: testFallbackLocale,
      },
    })

    await store.hydrate()

    expect((mockI18nLocale as { value: string }).value).toBe(testFallbackLocale)
    expect(document.documentElement.lang).toBe(getExpectedHtmlLang(testFallbackLocale))
  })

  it('saves locale through patchSettings', async () => {
    await store.setLocale('zh-TW')

    expect(mockPatchSettings).toHaveBeenCalledWith({
      ui: { locale: 'zh-TW' },
      new_game_defaults: { content_locale: 'zh-TW' },
    })
    expect(store.locale).toBe('zh-TW')
    expect(store.newGameDraft.content_locale).toBe('zh-TW')
    expect(document.documentElement.lang).toBe(getExpectedHtmlLang('zh-TW'))
    expect(mockFetchMapPresets).toHaveBeenCalledWith('zh-TW')
    expect(mockMapPreload).toHaveBeenCalled()
    expect(mockWorldFetchState).toHaveBeenCalled()
    expect(mockEventResetEvents).toHaveBeenCalledWith({})
    expect(mockSectRefreshTerritories).toHaveBeenCalled()
  })

  it('saves bgm volume through patchSettings', async () => {
    await store.setBgmVolume(0.8)

    expect(mockPatchSettings).toHaveBeenCalledWith({ ui: { audio: { bgm_volume: 0.8 } } })
    expect(store.bgmVolume).toBe(0.8)
  })

  it('saves auto save through patchSettings', async () => {
    await store.setAutoSave(true)

    expect(mockPatchSettings).toHaveBeenCalledWith({ simulation: { auto_save_enabled: true } })
    expect(store.isAutoSave).toBe(true)
  })

  it('allows manual content locale edits in draft before start game', () => {
    store.updateNewGameDraft({ init_npc_num: 20, content_locale: testFallbackLocale })

    expect(store.newGameDraft.init_npc_num).toBe(20)
    expect(store.newGameDraft.content_locale).toBe(testFallbackLocale)
  })

  it('persists manually adjusted content locale before starting game', async () => {
    await store.setLocale(testFallbackLocale)
    store.updateNewGameDraft({ init_npc_num: 20, content_locale: testDefaultLocale })

    await store.startGameWithDraft()

    expect(mockPatchSettings).toHaveBeenCalledWith({
      new_game_defaults: {
        content_locale: testDefaultLocale,
        init_npc_num: 20,
        sect_num: 3,
        map_id: 'classic',
        npc_awakening_rate_per_month: 0.01,
        world_lore: '',
        world_secret_id: 'none',
        test_mode: false,
      },
    })
    expect(mockStartGame).toHaveBeenCalledWith({
      content_locale: testDefaultLocale,
      init_npc_num: 20,
      sect_num: 3,
      map_id: 'classic',
      npc_awakening_rate_per_month: 0.01,
      world_lore: '',
      world_secret_id: 'none',
      test_mode: false,
    })
  })

  it('sends test mode as part of the run configuration', async () => {
    store.updateNewGameDraft({ test_mode: true })

    await store.startGameWithDraft()

    expect(mockStartGame).toHaveBeenCalledWith(expect.objectContaining({ test_mode: true }))
  })

  it('hydrates content locale from backend as saved by settings service', async () => {
    currentSettings = {
      ...clone(baseSettings),
      ui: {
        ...clone(baseSettings.ui),
        locale: testFallbackLocale,
      },
      new_game_defaults: {
        ...clone(baseSettings.new_game_defaults),
        content_locale: testDefaultLocale,
      },
    }
    mockFetchSettings.mockResolvedValueOnce(clone(currentSettings))

    await store.hydrate()

    expect(store.locale).toBe(testFallbackLocale)
    expect(store.newGameDraft.content_locale).toBe(testDefaultLocale)
  })

  it('marks store hydrated even when fetch fails', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mockFetchSettings.mockRejectedValueOnce(new Error('network'))

    await store.hydrate()

    expect(store.hydrated).toBe(true)
    expect(consoleSpy).toHaveBeenCalledWith('[SettingStore hydrate]', expect.any(Error))
    consoleSpy.mockRestore()
  })
})

