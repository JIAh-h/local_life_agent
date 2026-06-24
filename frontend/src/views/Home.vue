<template>
  <div class="home-page">
    <!-- ========== 统计栏 ========== -->
    <section class="stats-bar">
      <div class="stats-inner">
        <div class="stat-item" v-for="s in stats" :key="s.label">
          <span class="stat-icon" :style="{ color: s.color }">{{ s.icon }}</span>
          <div class="stat-body">
            <span class="stat-value">{{ s.value }}</span>
            <span class="stat-label">{{ s.label }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- ========== 主内容区（双栏） ========== -->
    <div class="main-layout">
      <!-- 左栏：功能入口 -->
      <section class="col-features">
        <h2 class="section-heading">功能导航</h2>
        <div class="feature-grid">
          <div
            v-for="feat in features"
            :key="feat.path"
            class="feature-card"
            @click="goTo(feat.path)"
          >
            <div class="fc-icon" :style="{ background: feat.gradient }">
              <van-icon :name="feat.icon" />
            </div>
            <div class="fc-body">
              <span class="fc-name">{{ feat.name }}</span>
              <span class="fc-desc">{{ feat.desc }}</span>
            </div>
            <van-icon name="arrow" class="fc-arrow" />
          </div>
        </div>
      </section>

      <!-- 右栏：今日推荐 -->
      <section class="col-recommend">
        <div class="section-header">
          <h2 class="section-heading">
            <van-icon name="fire-o" color="#ff6b6b" />
            今日推荐
          </h2>
          <span class="section-more" @click="goTo('/recommend')">
            全部推荐 <van-icon name="arrow" />
          </span>
        </div>

        <LoadingState
          v-if="recommendStore.loading"
          text="正在智能推荐..."
          height="140px"
        />

        <div v-else-if="recommendStore.recommendations.length" class="rec-grid">
          <div
            v-for="item in recommendStore.recommendations.slice(0, 4)"
            :key="item.id"
            class="rec-card"
            @click="goToDetail(item)"
          >
            <div class="rec-img">
              <img :src="item.image || '/placeholder.png'" :alt="item.name" loading="lazy" />
              <span class="rec-badge">{{ item.recommend_type === 'merchant' ? '美食' : '景点' }}</span>
            </div>
            <div class="rec-body">
              <h3 class="rec-name">{{ item.name }}</h3>
              <p class="rec-reason">{{ item.recommend_reason }}</p>
              <div class="rec-meta">
                <span class="rec-rating">
                  <van-icon name="star" color="#ff6b6b" size="12" />
                  {{ item.rating }}
                </span>
                <span class="rec-dist">{{ formatDistance(item.distance) }}</span>
              </div>
            </div>
          </div>
        </div>

        <EmptyState
          v-else
          description="暂无推荐内容"
          actionText="立即获取推荐"
          @action="fetchRecommendations"
        />
      </section>
    </div>

    <!-- ========== 快捷入口底部栏 ========== -->
    <section class="quick-bar">
      <div class="quick-bar-inner">
        <div
          v-for="item in quickActions"
          :key="item.path"
          class="quick-chip"
          @click="goTo(item.path)"
        >
          <van-icon :name="item.icon" />
          <span>{{ item.label }}</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useLocationStore } from '@/stores/location'
import { useRecommendStore } from '@/stores/recommend'
import { useFavoritesStore } from '@/stores/favorites'
import { getCurrentWeather } from '@/api/amap'
import { formatDistance } from '@/utils/format'
import LoadingState from '@/components/LoadingState.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const locationStore = useLocationStore()
const recommendStore = useRecommendStore()
const favoritesStore = useFavoritesStore()

const weather = ref(null)

// ---- 功能入口 ----
const features = [
  { name: '美食推荐', desc: '发现周边美食', path: '/food', icon: 'fire-o', gradient: 'linear-gradient(135deg,#ff6b6b,#ffa502)' },
  { name: '景点玩乐', desc: '探索附近好去处', path: '/attraction', icon: 'gem-o', gradient: 'linear-gradient(135deg,#2ed573,#7bed9f)' },
  { name: '智能助手', desc: '对话式生活服务', path: '/chat', icon: 'chat-o', gradient: 'linear-gradient(135deg,#667eea,#a29bfe)' },
  { name: '今日推荐', desc: '个性化每日推荐', path: '/recommend', icon: 'star-o', gradient: 'linear-gradient(135deg,#f9ca24,#f0932b)' },
  { name: '我的收藏', desc: '管理收藏的商家', path: '/favorites', icon: 'heart-o', gradient: 'linear-gradient(135deg,#e056fd,#be2edd)' },
  { name: '定位服务', desc: '切换搜索位置', path: '/location', icon: 'location-o', gradient: 'linear-gradient(135deg,#54a0ff,#2e86de)' },
  { name: '个人中心', desc: '查看个人资料', path: '/profile', icon: 'user-o', gradient: 'linear-gradient(135deg,#00d2d3,#01a3a4)' }
]

// ---- 快捷入口 ----
const quickActions = [
  { label: '收藏夹', path: '/favorites', icon: 'star-o' },
  { label: '智能助手', path: '/chat', icon: 'chat-o' },
  { label: '个人中心', path: '/profile', icon: 'user-o' },
  { label: '定位服务', path: '/location', icon: 'location-o' }
]

// ---- 统计 ----
const stats = computed(() => [
  {
    icon: '\uD83C\uDF54', label: '周边美食',
    value: favoritesStore.pagination.total > 0 ? favoritesStore.pagination.total : '--',
    color: '#ff6b6b'
  },
  {
    icon: '\uD83C\uDFDE\uFE0F', label: '附近景点',
    value: recommendStore.recommendations.length || '--',
    color: '#2ed573'
  },
  {
    icon: '\uD83D\uDC96', label: '我的收藏',
    value: favoritesStore.pagination.total > 0 ? favoritesStore.pagination.total : '0',
    color: '#e056fd'
  },
  {
    icon: '\uD83C\uDF24\uFE0F', label: '当前天气',
    value: weather.value ? `${weather.value.temperature}\u00B0` : '--',
    color: '#f9ca24'
  }
])

// ---- 天气 ----
async function fetchWeather(city) {
  try {
    const data = await getCurrentWeather(city)
    weather.value = data
  } catch {
    // 静默失败
  }
}

function getCityForWeather() {
  const loc = locationStore.currentLocation
  if (loc?.adcode) return loc.adcode
  if (loc?.city) return loc.city
  return '佛山'
}

// ---- 生命周期 ----
onMounted(async () => {
  fetchWeather(getCityForWeather())

  if (locationStore.hasLocation) {
    fetchRecommendations()
  }

  // 加载收藏数量
  try {
    await favoritesStore.fetchFavorites()
  } catch {
    // 静默
  }
})

// 位置变化时重新获取天气和推荐
watch(
  () => locationStore.currentLocation?.city,
  (newCity) => {
    if (newCity) {
      fetchWeather(getCityForWeather())
      fetchRecommendations()
    }
  }
)

function fetchRecommendations() {
  recommendStore.fetchTodayRecommendations()
}

function goTo(path) {
  router.push(path)
}

function goToDetail(item) {
  const route = item.recommend_type === 'merchant' ? '/food/' : '/attraction/'
  router.push(route + item.recommend_id)
}
</script>

<style scoped>
/* ========== GLOBAL ========== */
.home-page {
  min-height: 100vh;
  background: #f0f2f5;
  padding: 24px 0 32px;
}

/* ========== 统计栏 ========== */
.stats-bar {
  max-width: 1200px;
  margin: 0 auto;
  position: relative;
  padding: 0 32px;
}
.stats-inner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  background: #fff;
  border-radius: 16px;
  padding: 20px 24px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
}
.stat-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stat-icon { font-size: 24px; line-height: 1; }
.stat-body {
  display: flex;
  flex-direction: column;
}
.stat-value { font-size: 20px; font-weight: 700; color: #333; line-height: 1.2; }
.stat-label { font-size: 12px; color: #999; }

/* ========== 双栏主布局 ========== */
.main-layout {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 24px;
  max-width: 1200px;
  margin: 24px auto 0;
  padding: 0 32px;
}

.section-heading {
  font-size: 18px;
  font-weight: 600;
  color: #333;
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.section-more {
  font-size: 13px;
  color: #667eea;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 16px;
  transition: background 0.2s;
}
.section-more:hover { background: rgba(102,126,234,0.06); }

/* ========== 左栏：功能导航 ========== */
.col-features { min-width: 0; }

.feature-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.feature-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border-radius: 14px;
  padding: 16px 18px;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
}
.fc-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #fff;
  flex-shrink: 0;
}
.fc-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.fc-name {
  font-size: 15px;
  font-weight: 600;
  color: #333;
}
.fc-desc {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}
.fc-arrow {
  color: #ccc;
  font-size: 14px;
  transition: transform 0.2s;
}
.feature-card:hover .fc-arrow {
  transform: translateX(4px);
  color: #667eea;
}

/* ========== 右栏：今日推荐 ========== */
.col-recommend { min-width: 0; }

.rec-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}
.rec-card {
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.rec-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.10);
}
.rec-img {
  position: relative;
  width: 100%;
  height: 110px;
  background: #e8e8e8;
  overflow: hidden;
}
.rec-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}
.rec-card:hover .rec-img img { transform: scale(1.08); }
.rec-badge {
  position: absolute;
  top: 8px;
  left: 8px;
  font-size: 11px;
  color: #fff;
  background: rgba(0,0,0,0.55);
  padding: 2px 8px;
  border-radius: 10px;
  backdrop-filter: blur(2px);
}
.rec-body {
  padding: 10px 12px 12px;
}
.rec-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rec-reason {
  font-size: 11px;
  color: #999;
  margin: 0 0 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.4;
}
.rec-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}
.rec-rating {
  color: #ff6b6b;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 2px;
}
.rec-dist { color: #999; }

/* ========== 快捷入口底部栏 ========== */
.quick-bar {
  max-width: 1200px;
  margin: 32px auto 0;
  padding: 0 32px;
}
.quick-bar-inner {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}
.quick-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 22px;
  background: #fff;
  border-radius: 24px;
  font-size: 14px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}
.quick-chip:hover {
  color: #667eea;
  box-shadow: 0 4px 14px rgba(102,126,234,0.15);
  transform: translateY(-1px);
}

/* ========== 响应式 ========== */

/* 平板 */
@media (max-width: 960px) {
  .main-layout {
    grid-template-columns: 1fr;
  }
  .rec-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 手机 */
@media (max-width: 640px) {
  .stats-bar { padding: 0 16px; }
  .stats-inner {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    padding: 16px;
  }

  .main-layout {
    padding: 0 16px;
    gap: 16px;
    margin-top: 16px;
  }

  .rec-grid {
    grid-template-columns: 1fr;
  }

  .quick-bar { padding: 0 16px; }
  .quick-chip { padding: 8px 16px; font-size: 13px; }
}

/* 超大屏额外优化 */
@media (min-width: 1600px) {
  .main-layout,
  .stats-bar,
  .quick-bar {
    max-width: 1400px;
  }
  .rec-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
