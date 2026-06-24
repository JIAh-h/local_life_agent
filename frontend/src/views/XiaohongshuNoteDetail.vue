<template>
  <div class="note-detail-page">
    <!-- 顶部导航 -->
    <div class="note-top-bar">
      <van-icon name="arrow-left" size="20" color="#222" @click="goBack" />
      <span class="note-top-title">笔记</span>
      <van-icon name="ellipsis" size="20" color="#222" />
    </div>

    <LoadingState v-if="loading" text="加载笔记详情..." height="60vh" />

    <div v-else-if="loadError" class="note-error">
      <van-icon name="warning-o" size="48" color="#ccc" />
      <p>{{ loadError }}</p>
      <van-button size="small" type="primary" plain @click="loadData">重试</van-button>
    </div>

    <template v-else>
      <!-- 图片轮播 -->
      <div class="note-carousel" v-if="detail.image_urls && detail.image_urls.length">
        <van-swipe
          :autoplay="0"
          indicator-color="white"
          :loop="false"
          :show-indicators="detail.image_urls.length > 1"
          height="100vw"
          @change="onSwipeChange"
        >
          <van-swipe-item v-for="(url, i) in detail.image_urls" :key="i">
            <div class="swipe-img-wrap">
              <img :src="url" :alt="`图片${i + 1}`" @error="onSwipeImgError" />
            </div>
          </van-swipe-item>
        </van-swipe>
        <div class="carousel-index" v-if="detail.image_urls.length > 1">
          <span>{{ currentSwipeIdx + 1 }}/{{ detail.image_urls.length }}</span>
        </div>
      </div>
      <!-- 无图占位 -->
      <div v-else class="note-no-image">
        <van-icon name="photo-o" size="48" color="#ddd" />
        <span>暂无图片</span>
      </div>

      <!-- 用户信息栏 -->
      <div class="note-user-bar">
        <img
          :src="displayUser.avatar"
          class="note-user-avatar"
          @error="onAvatarErr"
          v-if="displayUser.avatar"
        />
        <div class="note-user-avatar-placeholder" v-else>
          <van-icon name="contact" size="24" color="#999" />
        </div>
        <div class="note-user-info">
          <span class="note-user-name">{{ displayUser.nickname || '用户' }}</span>
          <span class="note-user-time">{{ displayTime }}</span>
        </div>
        <van-button size="small" round plain type="danger" class="follow-btn">关注</van-button>
      </div>

      <!-- 笔记标题 -->
      <div class="note-section">
        <h1 class="note-title">{{ displayTitle || '笔记' }}</h1>
      </div>

      <!-- 笔记正文 -->
      <div class="note-section" v-if="detail.desc">
        <p class="note-desc" v-html="formatDesc(detail.desc)"></p>
      </div>

      <!-- 互动栏 -->
      <div class="note-actions">
        <div class="note-action-item">
          <van-icon name="like-o" size="22" color="#444" />
          <span>{{ likedCount }}</span>
        </div>
        <div class="note-action-item">
          <van-icon name="chat-o" size="22" color="#444" />
          <span>{{ commentTotal }}</span>
        </div>
        <div class="note-action-item">
          <van-icon name="star-o" size="22" color="#444" />
          <span>{{ collectedCount }}</span>
        </div>
        <div class="note-action-item">
          <van-icon name="share-o" size="22" color="#444" />
        </div>
      </div>

      <!-- 评论区域 -->
      <div class="note-section comment-section">
        <div class="comment-header">
          <span class="comment-title">评论</span>
          <span class="comment-count">{{ commentTotal }} 条</span>
        </div>

        <LoadingState v-if="commentsLoading" text="加载评论..." height="80px" />

        <div v-else-if="!comments.length" class="comment-empty">
          <van-icon name="chat-o" size="32" color="#ddd" />
          <p>暂无评论</p>
        </div>

        <div v-else class="comment-list">
          <div v-for="c in comments" :key="c.id" class="comment-item">
            <img
              :src="c.user_image"
              class="comment-avatar"
              @error="onAvatarErr"
              v-if="c.user_image"
            />
            <div class="comment-avatar-placeholder" v-else>
              <van-icon name="contact" size="16" color="#999" />
            </div>
            <div class="comment-body">
              <div class="comment-top">
                <span class="comment-nickname">{{ c.user_nickname }}</span>
                <span class="comment-time">{{ c.create_time }}</span>
              </div>
              <p class="comment-content">{{ c.content }}</p>
              <div class="comment-meta">
                <span class="comment-location" v-if="c.ip_location">{{ c.ip_location }}</span>
                <span class="comment-like" v-if="c.like_count > 0">
                  <van-icon name="like-o" size="12" /> {{ c.like_count }}
                </span>
                <span class="comment-reply-btn">回复</span>
              </div>
              <!-- 子评论 -->
              <div v-if="c.sub_comments && c.sub_comments.length" class="sub-comments">
                <div v-for="sub in c.sub_comments" :key="sub.id" class="sub-comment-item">
                  <span class="sub-nickname">{{ sub.user_nickname }}</span>
                  <span class="sub-content">：{{ sub.content }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-if="hasMoreComments" class="load-more-comments" @click="loadMoreComments">
            加载更多评论
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast } from 'vant'
import { getNoteDetail, getNoteComments } from '@/api/xiaohongshu'
import LoadingState from '@/components/LoadingState.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const loadError = ref('')
const detail = ref({ desc: '', image_urls: [], display_title: '', liked_count: 0, collected_count: 0, comment_count: 0, user: {}, publish_time: '' })
const comments = ref([])
const commentsLoading = ref(false)
const hasMoreComments = ref(false)
const commentCursor = ref('')
const commentTotal = ref(0)
const likedCount = ref(0)
const collectedCount = ref(0)
const currentSwipeIdx = ref(0)

// 从路由参数获取笔记ID和令牌
const noteId = computed(() => route.params.id)
const xsecToken = computed(() => route.query.xsec_token || '')

// 使用标题：优先从后端详情数据获取，降级到路由 query 参数
const displayTitle = computed(() => {
  return detail.value.display_title || route.query.title || ''
})

// 使用用户信息：优先从后端详情数据获取，降级到路由 query
const displayUser = computed(() => {
  const backendUser = detail.value.user || {}
  return {
    nickname: backendUser.nickname || route.query.author || '',
    avatar: backendUser.avatar || route.query.avatar || '',
  }
})

// 使用发布时间：优先从后端详情数据获取，降级到路由 query
const displayTime = computed(() => {
  return detail.value.publish_time || route.query.time || ''
})

onMounted(async () => {
  if (!noteId.value || !xsecToken.value) {
    loadError.value = '笔记参数不完整'
    loading.value = false
    return
  }
  await loadData()
})

async function loadData() {
  loading.value = true
  loadError.value = ''
  comments.value = []

  try {
    const [detailResult, commentResult] = await Promise.all([
      getNoteDetail(noteId.value, xsecToken.value),
      getNoteComments(noteId.value, xsecToken.value),
    ])

    // 合并后端返回的详情数据
    detail.value = {
      desc: detailResult.desc || '',
      image_urls: detailResult.image_urls || [],
      display_title: detailResult.display_title || '',
      publish_time: detailResult.publish_time || '',
      liked_count: detailResult.liked_count || 0,
      collected_count: detailResult.collected_count || 0,
      comment_count: detailResult.comment_count || 0,
      user: detailResult.user || {},
    }

    likedCount.value = detailResult.liked_count || 0
    collectedCount.value = detailResult.collected_count || 0

    comments.value = commentResult.comments || []
    commentCursor.value = commentResult.cursor || ''
    hasMoreComments.value = commentResult.has_more || false
    commentTotal.value = detailResult.comment_count > 0
      ? detailResult.comment_count
      : (commentResult.comments?.length || 0)
  } catch (err) {
    loadError.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadMoreComments() {
  commentsLoading.value = true
  try {
    const result = await getNoteComments(noteId.value, xsecToken.value, commentCursor.value)
    comments.value = [...comments.value, ...(result.comments || [])]
    commentCursor.value = result.cursor || ''
    hasMoreComments.value = result.has_more || false
  } catch (err) {
    showToast('加载更多评论失败')
  } finally {
    commentsLoading.value = false
  }
}

function onSwipeChange(index) {
  currentSwipeIdx.value = index
}

function formatDesc(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br />')
}

function goBack() {
  router.back()
}

function onSwipeImgError(e) {
  e.target.style.objectFit = 'contain'
  e.target.style.background = '#f0f0f0'
}

function onAvatarErr(e) {
  e.target.style.display = 'none'
}
</script>

<style scoped>
.note-detail-page {
  min-height: 100vh;
  background: #fff;
  max-width: 500px;
  margin: 0 auto;
  padding-bottom: 24px;
}

/* 顶部导航 */
.note-top-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}
.note-top-title {
  font-size: 16px;
  font-weight: 600;
  color: #222;
}

/* 加载 / 错误 */
.note-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 20px;
  color: #999;
  font-size: 14px;
}

/* 无图占位 */
.note-no-image {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 200px;
  background: #f8f8f8;
  color: #ccc;
  font-size: 13px;
}

/* 轮播 */
.note-carousel {
  position: relative;
  width: 100%;
}
.swipe-img-wrap {
  width: 100%;
  height: 100vw;
  background: #f0f0f0;
}
.swipe-img-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.carousel-index {
  position: absolute;
  right: 12px;
  bottom: 12px;
  background: rgba(0,0,0,0.5);
  color: #fff;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 12px;
  backdrop-filter: blur(2px);
  z-index: 1;
}

/* 用户信息栏 */
.note-user-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid #f5f5f5;
}
.note-user-avatar,
.note-user-avatar-placeholder {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}
.note-user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.note-user-name {
  font-size: 14px;
  font-weight: 600;
  color: #222;
}
.note-user-time {
  font-size: 11px;
  color: #999;
}
.follow-btn {
  height: 28px;
  font-size: 12px;
  padding: 0 14px;
}

/* 通用 Section */
.note-section {
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
}

/* 标题 */
.note-title {
  font-size: 17px;
  font-weight: 700;
  color: #222;
  margin: 0;
  line-height: 1.4;
}

/* 正文 */
.note-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #333;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 互动栏 */
.note-actions {
  display: flex;
  justify-content: space-around;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid #f5f5f5;
}
.note-action-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #444;
  font-size: 12px;
  cursor: pointer;
}

/* 评论区域 */
.comment-section {
  border-bottom: none;
}
.comment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.comment-title {
  font-size: 15px;
  font-weight: 600;
  color: #222;
}
.comment-count {
  font-size: 12px;
  color: #999;
}

.comment-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 24px 0;
  color: #ccc;
  font-size: 13px;
}

.comment-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comment-item {
  display: flex;
  gap: 10px;
}
.comment-avatar,
.comment-avatar-placeholder {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}
.comment-body {
  flex: 1;
  min-width: 0;
}
.comment-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.comment-nickname {
  font-size: 13px;
  font-weight: 600;
  color: #222;
}
.comment-time {
  font-size: 11px;
  color: #999;
}
.comment-content {
  font-size: 14px;
  color: #333;
  margin: 4px 0;
  line-height: 1.5;
}
.comment-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: #999;
}
.comment-location {
  color: #999;
}
.comment-like {
  display: flex;
  align-items: center;
  gap: 2px;
}
.comment-reply-btn {
  color: #667eea;
  cursor: pointer;
}

/* 子评论 */
.sub-comments {
  margin-top: 6px;
  padding: 8px 10px;
  background: #f8f8f8;
  border-radius: 6px;
}
.sub-comment-item {
  font-size: 13px;
  line-height: 1.6;
  padding: 2px 0;
}
.sub-nickname {
  font-weight: 600;
  color: #222;
}
.sub-content {
  color: #333;
}

/* 加载更多 */
.load-more-comments {
  text-align: center;
  padding: 12px 0;
  font-size: 13px;
  color: #667eea;
  cursor: pointer;
}
.load-more-comments:active {
  opacity: 0.7;
}
</style>
