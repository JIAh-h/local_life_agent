<template>
  <div class="recommend-container">
    <PageHeader title="今日推荐" :showBack="true">
      <template #right>
        <van-icon name="replay" size="20" color="white" @click="refreshRecommendations" />
      </template>
    </PageHeader>

    <LoadingState v-if="loading" text="正在获取推荐..." />

    <template v-else>
      <!-- 天气卡片 -->
      <div class="weather-card" v-if="recommendStore.weatherInfo">
        <div class="weather-main">
          <van-icon :name="weatherIcon" size="48" />
          <div class="weather-info">
            <span class="temperature">{{ recommendStore.weatherInfo.temperature }}°C</span>
            <span class="description">{{ recommendStore.weatherInfo.description }}</span>
          </div>
        </div>
        <div class="weather-details">
          <span>湿度: {{ recommendStore.weatherInfo.humidity }}%</span>
          <span>风力: {{ recommendStore.weatherInfo.wind }}</span>
        </div>
      </div>

      <!-- 推荐理由 -->
      <div class="recommend-reason" v-if="recommendStore.recommendations.length">
        <van-icon name="bulb-o" color="#667eea" />
        <span>{{ recommendReason }}</span>
      </div>

      <!-- 推荐列表 -->
      <div class="recommend-list" v-if="recommendStore.recommendations.length">
        <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
          <div
            v-for="item in recommendStore.recommendations"
            :key="item.id"
            class="recommend-card"
            @click="goToDetail(item)"
          >
            <div class="card-image">
              <img :src="item.image || '/placeholder.png'" :alt="item.name" />
            </div>
            <div class="card-info">
              <h3 class="card-title">{{ item.name }}</h3>
              <p class="card-reason">{{ item.recommend_reason }}</p>
              <div class="card-meta">
                <span class="rating">{{ item.rating }}分</span>
                <span class="distance">{{ formatDistance(item.distance) }}</span>
              </div>
            </div>
            <div class="card-feedback">
              <van-button size="mini" :type="item.feedback === 1 ? 'primary' : 'default'" @click.stop="submitFeedback(item.id, 1)">喜欢</van-button>
              <van-button size="mini" :type="item.feedback === -1 ? 'danger' : 'default'" @click.stop="submitFeedback(item.id, -1)">不喜欢</van-button>
            </div>
          </div>
        </van-pull-refresh>
      </div>

      <!-- 换一批 -->
      <div class="refresh-button" v-if="recommendStore.recommendations.length">
        <van-button block type="primary" @click="refreshRecommendations" icon="replay">换一批推荐</van-button>
      </div>

      <!-- 空状态 -->
      <EmptyState
        v-if="!recommendStore.recommendations.length && !loading"
        description="暂无推荐内容"
        actionText="获取推荐"
        @action="refreshRecommendations"
      />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRecommendStore } from '@/stores/recommend'
import { formatDistance } from '@/utils/format'
import { showToast } from 'vant'
import PageHeader from '@/components/PageHeader.vue'
import LoadingState from '@/components/LoadingState.vue'
import EmptyState from '@/components/EmptyState.vue'

const router = useRouter()
const recommendStore = useRecommendStore()
const refreshing = ref(false)
const loading = ref(false)

const weatherIcon = computed(() => {
  if (!recommendStore.weatherInfo) return 'weather-o'
  const d = recommendStore.weatherInfo.description
  if (d.includes('晴')) return 'sun-o'
  if (d.includes('云')) return 'cloud-o'
  if (d.includes('雨')) return 'rain-o'
  if (d.includes('雪')) return 'snow-o'
  return 'weather-o'
})

const recommendReason = computed(() => {
  if (!recommendStore.recommendations.length) return ''
  const hour = new Date().getHours()
  if (hour < 10) return '早上好！为您推荐今日好去处'
  if (hour < 14) return '午餐时间到了，为您推荐附近美食'
  if (hour < 18) return '下午时光，为您推荐休闲好去处'
  return '晚上好！为您推荐夜间娱乐场所'
})

onMounted(() => {
  if (!recommendStore.recommendations.length) {
    recommendStore.fetchTodayRecommendations()
  }
})

async function onRefresh() {
  await recommendStore.refreshRecommendations()
  refreshing.value = false
}

async function refreshRecommendations() {
  loading.value = true
  await recommendStore.refreshRecommendations()
  loading.value = false
}

async function submitFeedback(id, feedback) {
  try {
    await recommendStore.submitFeedback(id, feedback)
    showToast(feedback === 1 ? '已标记喜欢' : '已标记不喜欢')
  } catch { showToast('提交失败') }
}

function goToDetail(item) {
  const prefix = item.recommend_type === 'merchant' ? '/food/' : '/attraction/'
  router.push(prefix + item.recommend_id)
}
</script>

<style scoped>
.recommend-container {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 80px;
}
.weather-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  margin: 12px 16px;
  border-radius: 12px;
}
.weather-main { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.weather-info { display: flex; flex-direction: column; }
.temperature { font-size: 32px; font-weight: 600; }
.description { font-size: 14px; opacity: 0.9; }
.weather-details { display: flex; gap: 24px; font-size: 14px; opacity: 0.9; }
.recommend-reason {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; margin: 0 16px 12px;
  background: white; border-radius: 8px; font-size: 14px; color: #333;
}
.recommend-list { padding: 0 16px; }
.recommend-card {
  display: flex; gap: 12px; padding: 14px;
  background: white; border-radius: 12px; margin-bottom: 10px;
  cursor: pointer; transition: transform 0.2s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.recommend-card:active { transform: scale(0.98); }
.card-image { width: 80px; height: 80px; border-radius: 8px; overflow: hidden; flex-shrink: 0; }
.card-image img { width: 100%; height: 100%; object-fit: cover; }
.card-info { flex: 1; min-width: 0; }
.card-title { font-size: 15px; font-weight: 600; color: #333; margin: 0 0 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-reason { font-size: 12px; color: #666; margin: 0 0 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-meta { display: flex; gap: 12px; font-size: 13px; }
.rating { color: #ff6b6b; font-weight: 600; }
.distance { color: #999; }
.card-feedback { display: flex; flex-direction: column; gap: 6px; justify-content: center; }
.refresh-button {
  position: fixed; bottom: 0; left: 0; right: 0;
  padding: 16px; background: white;
  box-shadow: 0 -2px 10px rgba(0,0,0,0.06);
  padding-bottom: calc(16px + env(safe-area-inset-bottom, 0));
}
@media (max-width: 480px) {
  .recommend-list { padding: 0 12px; }
  .recommend-card { padding: 12px; }
  .card-image { width: 68px; height: 68px; }
}
</style>
