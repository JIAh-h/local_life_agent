<template>
  <div class="nav-weather" v-if="weather" :title="`${weather.city} · ${weather.weather} ${weather.temperature}°C`">
    <span class="weather-icon">{{ weatherIcon }}</span>
    <span class="weather-temp">{{ weather.temperature }}°</span>
    <span class="weather-text">{{ weather.weather }}</span>
    <span class="weather-date">{{ dateText }}</span>
  </div>
  <div class="nav-weather" v-else>
    <span class="weather-icon-placeholder" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useLocationStore } from '@/stores/location'
import { getCurrentWeather } from '@/api/amap'

const locationStore = useLocationStore()

const weather = ref(null)

const weekdayText = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

const dateText = computed(() => {
  const now = new Date()
  return `${now.getMonth() + 1}月${now.getDate()}日 ${weekdayText[now.getDay()]}`
})

const iconMap = {
  '晴': '\u2600\uFE0F',
  '少云': '\u26C5',
  '晴间多云': '\u26C5',
  '多云': '\u26C5',
  '阴': '\u2601\uFE0F',
  '有霾': '\uD83C\uDF2B\uFE0F',
  '霾': '\uD83C\uDF2B\uFE0F',
  '轻雾': '\uD83C\uDF2B\uFE0F',
  '雾': '\uD83C\uDF2B\uFE0F',
  '毛毛雨': '\uD83C\uDF26\uFE0F',
  '小雨': '\uD83C\uDF26\uFE0F',
  '小雨-中雨': '\uD83C\uDF27\uFE0F',
  '中雨': '\uD83C\uDF27\uFE0F',
  '中雨-大雨': '\uD83C\uDF27\uFE0F',
  '大雨': '\uD83C\uDF27\uFE0F',
  '大雨-暴雨': '\uD83C\uDF27\uFE0F',
  '暴雨': '\uD83C\uDF27\uFE0F',
  '雷阵雨': '\u26C8\uFE0F',
  '雷阵雨伴有冰雹': '\u26C8\uFE0F',
  '冻雨': '\uD83C\uDF27\uFE0F',
  '雨夹雪': '\uD83C\uDF28\uFE0F',
  '小雪': '\u2744\uFE0F',
  '小雪-中雪': '\u2744\uFE0F',
  '中雪': '\u2744\uFE0F',
  '中雪-大雪': '\u2744\uFE0F',
  '大雪': '\u2744\uFE0F',
  '阵雨': '\uD83C\uDF26\uFE0F',
  '阵雪': '\u2744\uFE0F',
  '强沙尘暴': '\uD83C\uDF2B\uFE0F',
  '浮尘': '\uD83C\uDF2B\uFE0F',
  '扬沙': '\uD83C\uDF2B\uFE0F',
  '大风': '\uD83D\uDCA8',
  '飑': '\uD83D\uDCA8',
  '龙卷风': '\uD83C\uDF2A\uFE0F',
  '热': '\uD83E\uDD75',
  '冷': '\uD83E\uDD76',
  '未知': '\u2753'
}

const weatherIcon = computed(() => {
  if (!weather.value) return '\u2753'
  const desc = weather.value.weather || ''
  for (const [key, icon] of Object.entries(iconMap)) {
    if (desc.includes(key)) return icon
  }
  return iconMap['\u672A\u77E5']
})

function getCityForWeather() {
  const loc = locationStore.currentLocation
  if (loc?.adcode) return loc.adcode
  if (loc?.city) return loc.city
  return '\u4F5B\u5C71'
}

async function fetchWeather(city) {
  try {
    const data = await getCurrentWeather(city)
    weather.value = data
  } catch {
    // 静默失败，保持上次有效数据
  }
}

watch(
  () => locationStore.currentLocation?.city,
  (newCity) => {
    if (newCity) {
      fetchWeather(getCityForWeather())
    }
  }
)

onMounted(() => {
  fetchWeather(getCityForWeather())
})
</script>

<style scoped>
.nav-weather {
  display: flex;
  align-items: center;
  gap: 4px;
  color: rgba(255, 255, 255, 0.95);
  font-size: 13px;
  white-space: nowrap;
  padding: 4px 10px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.12);
  min-width: 110px;
  justify-content: center;
  line-height: 1;
}

.weather-icon {
  font-size: 16px;
  line-height: 1;
}

.weather-icon-placeholder {
  display: inline-block;
  width: 16px;
  height: 16px;
}

.weather-temp {
  font-weight: 600;
  font-size: 14px;
  min-width: 24px;
  text-align: right;
}

.weather-text {
  opacity: 0.85;
}

.weather-date {
  opacity: 0.7;
  font-size: 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.2);
  padding-left: 6px;
}
</style>
