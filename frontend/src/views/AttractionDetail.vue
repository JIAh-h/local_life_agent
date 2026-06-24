<template>
  <div class="attraction-detail-container">
    <PageHeader title="景点详情" />

    <!-- 加载状态 -->
    <LoadingState v-if="attractionStore.loading" text="加载详情中..." />

    <!-- 错误状态 -->
    <ErrorState v-else-if="loadError" message="加载失败" @retry="loadData" />

    <!-- 详情内容 -->
    <template v-else-if="attractionStore.currentAttraction">
      <!-- 图片轮播 -->
      <div class="image-carousel" v-if="attractionStore.currentAttraction.images?.length">
        <van-swipe :autoplay="4000" indicator-color="white">
          <van-swipe-item v-for="(image, index) in attractionStore.currentAttraction.images" :key="index">
            <img :src="image" :alt="attractionStore.currentAttraction.name" />
          </van-swipe-item>
        </van-swipe>
      </div>
      <div v-else class="image-placeholder">
        <van-icon name="gem-o" size="64" color="#ddd" />
      </div>

      <!-- 基本信息 -->
      <div class="basic-info">
        <h1 class="title">{{ attractionStore.currentAttraction.name }}</h1>
        <div class="rating-row">
          <van-rate v-model="attractionStore.currentAttraction.rating" readonly size="14" />
          <span class="rating-text">{{ attractionStore.currentAttraction.rating }}分</span>
          <span class="rating-count">{{ attractionStore.currentAttraction.rating_count || 0 }}条评价</span>
        </div>
        <div class="meta-row">
          <span class="price" :class="{ free: attractionStore.currentAttraction.ticket_price === 0 }">
            {{ attractionStore.currentAttraction.ticket_price === 0 ? '免费' : `¥${attractionStore.currentAttraction.ticket_price}` }}
          </span>
          <span class="category" v-if="attractionStore.currentAttraction.category">
            {{ attractionStore.currentAttraction.category }}
          </span>
        </div>
      </div>

      <!-- 详细信息 -->
      <div class="detail-section">
        <div class="info-item">
          <van-icon name="location-o" color="#667eea" />
          <span>{{ attractionStore.currentAttraction.address || '暂无地址信息' }}</span>
        </div>
        <div class="info-item">
          <van-icon name="clock-o" color="#667eea" />
          <span>{{ attractionStore.currentAttraction.opening_hours || '暂无开放时间' }}</span>
        </div>
        <div class="info-item" v-if="attractionStore.currentAttraction.phone">
          <van-icon name="phone-o" color="#667eea" />
          <span>{{ attractionStore.currentAttraction.phone }}</span>
        </div>
      </div>

      <!-- 亮点介绍 -->
      <div class="section" v-if="attractionStore.currentAttraction.highlights?.length">
        <h2 class="section-title">亮点介绍</h2>
        <div class="highlights-list">
          <div v-for="highlight in attractionStore.currentAttraction.highlights" :key="highlight" class="highlight-item">
            <van-icon name="gem-o" color="#667eea" />
            <span>{{ highlight }}</span>
          </div>
        </div>
      </div>

      <!-- 标签 -->
      <div class="section" v-if="attractionStore.currentAttraction.tags?.length">
        <h2 class="section-title">特色标签</h2>
        <div class="tags-list">
          <van-tag v-for="tag in attractionStore.currentAttraction.tags" :key="tag" type="success" size="medium" plain>
            {{ tag }}
          </van-tag>
        </div>
      </div>

      <!-- 小红书笔记 -->
      <div class="section">
        <h2 class="section-title">小红书笔记</h2>
        <LoadingState v-if="notesLoading" text="搜索相关笔记..." height="100px" />
        <div v-else-if="notes.length" class="xhs-notes-grid">
          <XiaohongshuCard
            v-for="note in notes"
            :key="note.id"
            :note="note"
          />
        </div>
        <EmptyState v-else description="暂无相关笔记" />
      </div>

      <!-- 底部操作栏 -->
      <div class="bottom-bar">
        <van-button
          :icon="isFavorited ? 'star' : 'star-o'"
          :type="isFavorited ? 'warning' : 'default'"
          @click="toggleFavorite"
        >
          {{ isFavorited ? '已收藏' : '收藏' }}
        </van-button>
        <van-button icon="share-o" @click="share">分享</van-button>
        <van-button type="primary" icon="guide-o" @click="navigate">导航</van-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAttractionStore } from '@/stores/attraction'
import { useFavoritesStore } from '@/stores/favorites'
import { showToast } from 'vant'
import PageHeader from '@/components/PageHeader.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EmptyState from '@/components/EmptyState.vue'
import XiaohongshuCard from '@/components/XiaohongshuCard.vue'
import { buildAMapURI } from '@/api/amap'
import { searchNotes } from '@/api/xiaohongshu'

const router = useRouter()
const route = useRoute()
const attractionStore = useAttractionStore()
const favoritesStore = useFavoritesStore()

const notes = ref([])
const notesLoading = ref(false)
const loadError = ref(false)
const isFavorited = computed(() => favoritesStore.isFavorited(null, route.params.id))

onMounted(() => {
  loadData()
})

async function loadData() {
  loadError.value = false
  try {
    await attractionStore.fetchAttractionDetail(route.params.id)
    await loadXiaohongshuNotes()
  } catch (err) {
    loadError.value = true
  }
}

async function loadXiaohongshuNotes() {
  const name = attractionStore.currentAttraction?.name
  if (!name) return

  notesLoading.value = true
  try {
    const result = await searchNotes(name, 1, 12)
    notes.value = result.notes || []
  } catch (err) {
    console.warn('[XHS] 搜索笔记失败:', err.message)
  } finally {
    notesLoading.value = false
  }
}

async function toggleFavorite() {
  try {
    if (isFavorited.value) {
      await favoritesStore.removeFavorite(null, route.params.id)
      showToast('已取消收藏')
    } else {
      await favoritesStore.addFavorite({ attraction_id: route.params.id })
      showToast('收藏成功')
    }
  } catch (err) {
    showToast('操作失败')
  }
}

function share() {
  const data = attractionStore.currentAttraction
  if (navigator.share) {
    navigator.share({
      title: data.name,
      text: `${data.name} - ${data.address}`,
      url: window.location.href
    }).catch(() => {})
  } else {
    navigator.clipboard?.writeText(window.location.href)
    showToast('链接已复制')
  }
}

function navigate() {
  const data = attractionStore.currentAttraction
  if (data?.latitude && data?.longitude) {
    const url = buildAMapURI(
      { latitude: data.latitude, longitude: data.longitude },
      data.name,
      'navi'
    )
    window.open(url, '_blank')
  } else {
    showToast('暂无坐标信息')
  }
}
</script>

<style scoped>
.attraction-detail-container {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 70px;
}

.image-carousel {
  height: 250px;
}

.image-carousel img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-placeholder {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f0f0;
}

.basic-info {
  background: white;
  padding: 16px;
  margin-bottom: 12px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
}

.rating-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.rating-text {
  font-size: 16px;
  color: #ff6b6b;
  font-weight: 600;
}

.rating-count {
  font-size: 14px;
  color: #999;
}

.meta-row {
  display: flex;
  gap: 16px;
  font-size: 14px;
}

.price {
  color: #ff6b6b;
  font-weight: 600;
}

.price.free {
  color: #2ed573;
}

.category {
  color: #666;
  padding: 2px 8px;
  background: #f0f0f0;
  border-radius: 4px;
}

.detail-section {
  background: white;
  padding: 16px;
  margin-bottom: 12px;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
  color: #333;
}

.info-item:last-child {
  border-bottom: none;
}

.section {
  background: white;
  padding: 16px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
}

.highlights-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.highlight-item {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #333;
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.notes-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 小红书笔记网格 */
.xhs-notes-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.note-card {
  padding: 12px;
  background: #f9f9f9;
  border-radius: 8px;
}

.note-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px;
}

.note-summary {
  font-size: 12px;
  color: #666;
  margin: 0 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.note-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  background: white;
  padding: 12px 16px;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.1);
  z-index: 100;
}

.bottom-bar .van-button {
  flex: 1;
}

@media (min-width: 768px) {
  .attraction-detail-container {
    max-width: 720px;
    margin: 0 auto;
  }

  .image-carousel {
    height: 350px;
    border-radius: 0 0 16px 16px;
    overflow: hidden;
  }

  .basic-info,
  .detail-section,
  .section {
    border-radius: 12px;
    margin-left: 16px;
    margin-right: 16px;
  }
}
</style>
