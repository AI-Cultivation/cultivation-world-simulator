import grave01 from '@/assets/icons/pois/grave_01.png'
import grave02 from '@/assets/icons/pois/grave_02.png'
import grave03 from '@/assets/icons/pois/grave_03.png'
import grave04 from '@/assets/icons/pois/grave_04.png'
import grave05 from '@/assets/icons/pois/grave_05.png'
import grave06 from '@/assets/icons/pois/grave_06.png'
import grave07 from '@/assets/icons/pois/grave_07.png'
import grave08 from '@/assets/icons/pois/grave_08.png'
import grave09 from '@/assets/icons/pois/grave_09.png'
import fallbackPoi from '@/assets/icons/pois/fallback_poi.png'
import treasure01 from '@/assets/icons/pois/treasure_01.png'
import treasure02 from '@/assets/icons/pois/treasure_02.png'
import treasure03 from '@/assets/icons/pois/treasure_03.png'
import treasure04 from '@/assets/icons/pois/treasure_04.png'
import treasure05 from '@/assets/icons/pois/treasure_05.png'
import treasure06 from '@/assets/icons/pois/treasure_06.png'
import treasure07 from '@/assets/icons/pois/treasure_07.png'
import treasure08 from '@/assets/icons/pois/treasure_08.png'
import treasure09 from '@/assets/icons/pois/treasure_09.png'

export const POI_ICON_URLS: Record<string, string> = {
  grave_01: grave01,
  grave_02: grave02,
  grave_03: grave03,
  grave_04: grave04,
  grave_05: grave05,
  grave_06: grave06,
  grave_07: grave07,
  grave_08: grave08,
  grave_09: grave09,
  treasure_01: treasure01,
  treasure_02: treasure02,
  treasure_03: treasure03,
  treasure_04: treasure04,
  treasure_05: treasure05,
  treasure_06: treasure06,
  treasure_07: treasure07,
  treasure_08: treasure08,
  treasure_09: treasure09,
  fallback_poi: fallbackPoi,
}

export function resolvePoiIcon(iconKey?: string): string {
  if (iconKey && POI_ICON_URLS[iconKey]) return POI_ICON_URLS[iconKey]
  return fallbackPoi
}
