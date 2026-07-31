import { describe, expect, it } from 'vitest'
import { POI_ICON_URLS, resolvePoiIcon } from '@/utils/poiIcons'

describe('poiIcons', () => {
  const graveIconKeys = [
    'grave_01',
    'grave_02',
    'grave_03',
    'grave_04',
    'grave_05',
    'grave_06',
    'grave_07',
    'grave_08',
    'grave_09',
  ]
  const treasureIconKeys = [
    'treasure_01', 'treasure_02', 'treasure_03',
    'treasure_04', 'treasure_05', 'treasure_06',
    'treasure_07', 'treasure_08', 'treasure_09',
  ]

  it('registers all Phase 1 grave icon assets and fallback', () => {
    for (const key of graveIconKeys) {
      expect(POI_ICON_URLS[key]).toContain(`${key}.png`)
    }
    expect(POI_ICON_URLS.fallback_poi).toContain('fallback_poi.png')
    for (const key of treasureIconKeys) {
      expect(POI_ICON_URLS[key]).toContain(`${key}.png`)
    }
  })

  it('resolves known POI icons and falls back for missing keys', () => {
    expect(resolvePoiIcon('grave_03')).toBe(POI_ICON_URLS.grave_03)
    expect(resolvePoiIcon('unknown_grave')).toBe(POI_ICON_URLS.fallback_poi)
    expect(resolvePoiIcon()).toBe(POI_ICON_URLS.fallback_poi)
    expect(resolvePoiIcon('treasure_03')).toBe(POI_ICON_URLS.treasure_03)
  })
})
