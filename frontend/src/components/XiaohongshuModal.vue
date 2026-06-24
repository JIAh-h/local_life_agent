<template>
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="visible" class="xhs-modal-mask" @click.self="close" @wheel.self.prevent>
        <div class="xhs-modal-container" @click.stop>
          <!-- 加载状态 -->
          <LoadingState v-if="loading" text="加载笔记详情..." height="100%" />

          <!-- 错误状态 -->
          <div v-else-if="loadError" class="modal-error">
            <p>{{ loadError }}</p>
            <van-button size="small" type="primary" plain @click="loadData">重试</van-button>
          </div>

          <!-- 主内容：左右布局 -->
          <div v-else class="xhs-modal-body">
            <!-- 左侧：图片展示区 -->
            <div
              class="modal-image-area"
              ref="imageAreaRef"
              @wheel.prevent="onImageWheel"
            >
              <div class="modal-image-wrap">
                <img
                  v-for="(url, i) in detail.image_urls"
                  :key="i"
                  :src="url"
                  :alt="`图片${i + 1}`"
                  :class="{ active: currentImgIdx === i }"
                  @error="onImgError"
                />
              </div>

              <!-- 左切换按钮 -->
              <button
                v-if="detail.image_urls.length > 1"
                class="modal-img-nav modal-img-prev"
                @click="prevImage"
              >
                <van-icon name="arrow-left" size="20" color="#fff" />
              </button>
              <!-- 右切换按钮 -->
              <button
                v-if="detail.image_urls.length > 1"
                class="modal-img-nav modal-img-next"
                @click="nextImage"
              >
                <van-icon name="arrow" size="20" color="#fff" />
              </button>

              <!-- 图片分页指示 -->
              <div v-if="detail.image_urls.length > 1" class="modal-img-pagination">
                <span
                  v-for="(_, i) in detail.image_urls"
                  :key="i"
                  :class="{ active: currentImgIdx === i }"
                  class="pagination-dot"
                ></span>
              </div>
            </div>

            <!-- 右侧：信息区 -->
            <div class="modal-info-area">
              <!-- 用户信息栏 -->
              <div class="modal-user-bar">
                <img
                  :src="displayUser.avatar"
                  class="modal-user-avatar"
                  @error="onAvatarErr"
                  v-if="displayUser.avatar"
                />
                <div class="modal-user-avatar-placeholder" v-else>
                  <van-icon name="contact" size="20" color="#999" />
                </div>
                <div class="modal-user-info">
                  <span class="modal-user-name">{{ displayUser.nickname || '用户' }}</span>
                  <span class="modal-user-time">{{ displayTime }}</span>
                </div>
                <button
                  class="modal-favorite-btn"
                  :class="{ favorited: isFav }"
                  @click="toggleFavorite"
                >
                  <van-icon :name="isFav ? 'star' : 'star-o'" size="13" />
                  {{ isFav ? '已收藏' : '收藏' }}
                </button>
              </div>

              <!-- 标题 + 文案（滚动区域） -->
              <div class="modal-content-scroll" @scroll="onScroll">
                <h2 class="modal-title">{{ displayTitle || '笔记' }}</h2>
                <p class="modal-desc" v-if="detail.desc" v-html="formatDesc(detail.desc)"></p>

                <!-- 互动数据 -->
                <div class="modal-stats">
                  <span class="stat-item">
                    <van-icon name="like-o" size="14" /> {{ likedCount }}
                  </span>
                  <span class="stat-item">
                    <van-icon name="chat-o" size="14" /> {{ commentTotal }}
                  </span>
                  <span class="stat-item" v-if="collectedCount > 0">
                    <van-icon name="star-o" size="14" /> {{ collectedCount }}
                  </span>
                </div>

                <!-- 评论区域 -->
                <div class="modal-comments">
                  <div class="modal-comment-header">
                    <span class="modal-comment-title">评论</span>
                    <span class="modal-comment-count">{{ commentTotal }} 条</span>
                  </div>

                  <!-- 首次加载（无评论时居中显示） -->
                  <LoadingState v-if="!comments.length && commentsLoading" text="加载评论..." height="60px" />

                  <!-- 空状态 -->
                  <div v-else-if="!comments.length" class="modal-comment-empty">
                    <van-icon name="chat-o" size="24" color="#ddd" />
                    <p>暂无评论</p>
                  </div>

                  <!-- 评论列表 -->
                  <div v-else class="modal-comment-list">
                    <div v-for="c in comments" :key="c.id" class="modal-comment-item">
                      <img
                        :src="c.user_image"
                        class="modal-comment-avatar"
                        @error="onAvatarErr"
                        v-if="c.user_image"
                      />
                      <div class="modal-comment-avatar-placeholder" v-else>
                        <van-icon name="contact" size="14" color="#999" />
                      </div>
                      <div class="modal-comment-body">
                        <div class="modal-comment-top">
                          <span class="modal-comment-nickname">{{ c.user_nickname }}</span>
                          <span class="modal-comment-time">{{ c.create_time }}</span>
                        </div>
                        <p class="modal-comment-content">{{ c.content }}</p>
                        <div class="modal-comment-meta">
                          <span v-if="c.ip_location" class="modal-comment-location">{{ c.ip_location }}</span>
                          <span v-if="c.like_count > 0" class="modal-comment-like">
                            <van-icon name="like-o" size="11" /> {{ c.like_count }}
                          </span>
                        </div>
                        <!-- 子评论 -->
                        <div v-if="c.sub_comments && c.sub_comments.length" class="modal-sub-comments">
                          <div v-for="sub in c.sub_comments" :key="sub.id" class="modal-sub-item">
                            <span class="modal-sub-nickname">{{ sub.user_nickname }}</span>
                            <span class="modal-sub-content">：{{ sub.content }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                    <!-- 加载更多：在评论列表底部 -->
                    <div v-if="commentsLoading" class="modal-loading-more">
                      <van-loading type="spinner" size="14" color="#ccc" />
                      <span>加载更多...</span>
                    </div>
                    <!-- 已到底 -->
                    <div v-if="!hasMoreComments && comments.length > 0" class="modal-end-line">
                      —— THE END ——
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
import { ref, watch, computed, nextTick } from 'vue'
import { showToast } from 'vant'
import { getNoteDetail, getNoteComments } from '@/api/xiaohongshu'
import { useFavoritesStore } from '@/stores/favorites'
import LoadingState from '@/components/LoadingState.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  note: { type: Object, required: true },
  category: { type: Number, default: 1 },  // 1=美食 2=景点
  localDetail: { type: Object, default: null },  // 本地数据（跳过外部API）
})

const emit = defineEmits(['close'])

const favStore = useFavoritesStore()
const isFav = ref(false)
const favId = ref(null)

const loading = ref(false)
const loadError = ref('')
const detail = ref({ desc: '', image_urls: [], display_title: '', liked_count: 0, collected_count: 0, comment_count: 0, user: {}, publish_time: '' })
const comments = ref([])
const commentsLoading = ref(false)
const hasMoreComments = ref(false)
const commentCursor = ref('')
const commentTotal = ref(0)
const likedCount = ref(0)
const collectedCount = ref(0)
const currentImgIdx = ref(0)
const imageAreaRef = ref(null)
const scrollRef = ref(null)

const noteData = computed(() => props.note || {})
const displayTitle = computed(() => detail.value.display_title || noteData.value.display_title || '')
const displayUser = computed(() => {
  const backendUser = detail.value.user || {}
  const noteUser = noteData.value.user || {}
  return {
    nickname: backendUser.nickname || noteUser.nickname || '',
    avatar: backendUser.avatar || noteUser.avatar || '',
  }
})
const displayTime = computed(() => detail.value.publish_time || noteData.value.publish_time || '')

// ─── 弹窗打开/关闭 ───
watch(() => props.visible, async (val) => {
  if (val) {
    currentImgIdx.value = 0

    // 判断是否使用本地数据（收藏页）还是调用外部API（搜索页）
    if (props.localDetail) {
      useLocalDetail(props.localDetail)
    } else {
      loadData()
    }

    // 检查收藏状态
    const noteId = noteData.value.id
    if (noteId) {
      const r = await favStore.checkFavorited(noteId)
      isFav.value = r.favorited
      favId.value = r.id
    }
  } else {
    isFav.value = false
    favId.value = null
    detail.value = { desc: '', image_urls: [], display_title: '', liked_count: 0, collected_count: 0, comment_count: 0, user: {}, publish_time: '' }
    comments.value = []
    loadError.value = ''
  }
})

// ─── 左右图片切换 ───
function prevImage() {
  if (currentImgIdx.value > 0) {
    currentImgIdx.value--
  } else {
    currentImgIdx.value = detail.value.image_urls.length - 1
  }
}

function nextImage() {
  if (currentImgIdx.value < detail.value.image_urls.length - 1) {
    currentImgIdx.value++
  } else {
    currentImgIdx.value = 0
  }
}

// ─── 鼠标滚轮切换图片 ───
function onImageWheel(e) {
  if (detail.value.image_urls.length <= 1) return
  if (e.deltaY > 0) {
    nextImage()
  } else {
    prevImage()
  }
}

// ─── 关闭 ───
function close() {
  emit('close')
}

// ─── 使用本地数据（收藏页：不调用外部 API） ───
function useLocalDetail(d) {
  detail.value = {
    desc: d.note_desc || '',
    image_urls: d.note_image_urls || [],
    display_title: d.note_title || '',
    publish_time: d.note_publish_time || '',
    liked_count: d.note_like_count || 0,
    collected_count: d.note_collect_count || 0,
    comment_count: d.note_comment_count || 0,
    user: {
      nickname: d.note_author || '',
      avatar: d.note_author_avatar || '',
    },
  }
  likedCount.value = d.note_like_count || 0
  collectedCount.value = d.note_collect_count || 0
  commentTotal.value = d.note_comment_count || (d.comments ? d.comments.length : 0)
  hasMoreComments.value = false
  comments.value = d.comments || []
}

// ─── 收藏 / 取消收藏 ───
async function toggleFavorite() {
  if (isFav.value) {
    // 取消收藏
    try {
      await favStore.removeFavorite(favId.value)
      isFav.value = false
      favId.value = null
      showToast({ message: '已取消收藏', zIndex: 3000 })
    } catch (e) {
      showToast({ message: '取消收藏失败', zIndex: 3000 })
    }
  } else {
    // 收藏：将当前笔记数据写入
    try {
      const d = detail.value
      const data = {
        id: noteData.value.id,
        xsec_token: noteData.value.xsec_token || '',
        display_title: d.display_title || noteData.value.display_title || '',
        cover_url: (d.image_urls && d.image_urls[0]) || noteData.value.cover_url || '',
        image_urls: d.image_urls || [],
        desc: d.desc || '',
        user: d.user || noteData.value.user || {},
        publish_time: d.publish_time || noteData.value.publish_time || '',
        liked_count: d.liked_count || 0,
        collected_count: d.collected_count || 0,
        comment_count: d.comment_count || 0,
      }
      const result = await favStore.addFavorite(data, props.category, comments.value)
      isFav.value = true
      favId.value = result.id
      showToast({ message: '收藏成功', zIndex: 3000 })
    } catch (e) {
      showToast({ message: e.message || '收藏失败', zIndex: 3000 })
    }
  }
}

// ─── 滚动到底部自动加载更多评论 ───
function onScroll(e) {
  if (!hasMoreComments.value || commentsLoading.value) return
  const el = e.target
  // 距离底部 50px 以内触发加载
  if (el.scrollHeight - el.scrollTop - el.clientHeight < 50) {
    loadMoreComments()
  }
}

// ─── 数据加载 ───
async function loadData() {
  const noteId = noteData.value.id
  const xsecToken = noteData.value.xsec_token
  if (!noteId || !xsecToken) {
    loadError.value = '笔记参数不完整'
    loading.value = false
    return
  }

  loading.value = true
  loadError.value = ''

  try {
    const [detailResult, commentResult] = await Promise.all([
      getNoteDetail(noteId, xsecToken),
      getNoteComments(noteId, xsecToken),
    ])

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
  const noteId = noteData.value.id
  const xsecToken = noteData.value.xsec_token
  commentsLoading.value = true

  // 保存当前滚动位置
  const scrollEl = document.querySelector('.modal-content-scroll')
  const savedScrollTop = scrollEl ? scrollEl.scrollTop : 0

  try {
    const result = await getNoteComments(noteId, xsecToken, commentCursor.value)
    comments.value = [...comments.value, ...(result.comments || [])]
    commentCursor.value = result.cursor || ''
    hasMoreComments.value = result.has_more || false

    // 等待 DOM 更新后再恢复滚动位置，防止新内容导致 scrollTop 回弹
    await nextTick()
    if (scrollEl) {
      scrollEl.scrollTop = savedScrollTop
    }
  } catch (err) {
    showToast({ message: '加载更多评论失败', zIndex: 3000 })
  } finally {
    commentsLoading.value = false
  }
}

function formatDesc(text) {
  if (!text) return ''
  return text.replace(/\n/g, '<br />')
}

function onImgError(e) {
  e.target.style.objectFit = 'contain'
  e.target.style.background = '#f0f0f0'
}

function onAvatarErr(e) {
  e.target.style.display = 'none'
}
</script>

<style scoped>
/* ─── 遮罩层（透明，保留点击关闭） ─── */
.xhs-modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 2000;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}
.xhs-modal-container {
  position: relative;
  width: 90vw;
  max-width: 960px;
  height: 85vh;
  max-height: 680px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

/* ─── 关闭按钮 ─── */
.modal-close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.45);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}
.modal-close-btn:hover {
  background: rgba(0, 0, 0, 0.65);
}

/* ─── 加载 / 错误 ─── */
.modal-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: #999;
  font-size: 14px;
  padding: 40px;
}

/* ─── 左右布局主体 ─── */
.xhs-modal-body {
  display: flex;
  flex: 1;
  min-height: 0;
}

/* ─── 左侧：图片展示区 ─── */
.modal-image-area {
  position: relative;
  flex: 0 0 55%;
  background: #000;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.modal-image-wrap {
  position: relative;
  width: 100%;
  height: 100%;
}
.modal-image-wrap img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  opacity: 0;
  transition: opacity 0.35s ease;
}
.modal-image-wrap img.active {
  opacity: 1;
}

/* 左右导航按钮 */
.modal-img-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px;
  height: 64px;
  background: rgba(255, 255, 255, 0.12);
  border: none;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
  z-index: 2;
}
.modal-img-nav:hover {
  background: rgba(255, 255, 255, 0.25);
}
.modal-img-prev {
  left: 8px;
}
.modal-img-next {
  right: 8px;
}

/* 分页指示器 */
.modal-img-pagination {
  position: absolute;
  bottom: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  z-index: 2;
}
.pagination-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.4);
  transition: all 0.2s;
}
.pagination-dot.active {
  width: 18px;
  border-radius: 3px;
  background: #fff;
}

/* ─── 右侧：信息区 ─── */
.modal-info-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #fff;
}

/* 用户栏 */
.modal-user-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f0;
  flex-shrink: 0;
}
.modal-user-avatar,
.modal-user-avatar-placeholder {
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
.modal-user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.modal-user-name {
  font-size: 14px;
  font-weight: 600;
  color: #222;
}
.modal-user-time {
  font-size: 11px;
  color: #999;
}
.modal-favorite-btn {
  height: 26px;
  padding: 0 12px;
  border-radius: 13px;
  border: 1px solid #ff2442;
  background: transparent;
  color: #ff2442;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
  transition: 0.2s;
  display: flex;
  align-items: center;
  gap: 3px;
}
.modal-favorite-btn:hover {
  background: #fff0f3;
}
.modal-favorite-btn.favorited {
  background: #ff2442;
  color: #fff;
}

/* 内容滚动区（隐藏滚动条，保留滚轮/触摸滚动） */
.modal-content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.modal-content-scroll::-webkit-scrollbar {
  display: none;
}

/* 标题 */
.modal-title {
  font-size: 16px;
  font-weight: 700;
  color: #222;
  margin: 0 0 8px;
  line-height: 1.4;
}

/* 描述 */
.modal-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #444;
  margin: 0 0 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 互动数据行 */
.modal-stats {
  display: flex;
  gap: 20px;
  padding: 10px 0;
  border-top: 1px solid #f5f5f5;
  border-bottom: 1px solid #f5f5f5;
  margin-bottom: 12px;
}
.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #666;
}

/* ─── 评论区 ─── */
.modal-comment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.modal-comment-title {
  font-size: 14px;
  font-weight: 600;
  color: #222;
}
.modal-comment-count {
  font-size: 12px;
  color: #999;
}
.modal-comment-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 20px 0;
  color: #ccc;
  font-size: 13px;
}
.modal-comment-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal-comment-item {
  display: flex;
  gap: 8px;
}
.modal-comment-avatar,
.modal-comment-avatar-placeholder {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-comment-body {
  flex: 1;
  min-width: 0;
}
.modal-comment-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}
.modal-comment-nickname {
  font-size: 12px;
  font-weight: 600;
  color: #222;
}
.modal-comment-time {
  font-size: 11px;
  color: #999;
}
.modal-comment-content {
  font-size: 13px;
  color: #333;
  margin: 3px 0;
  line-height: 1.5;
}
.modal-comment-meta {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: #999;
}
.modal-comment-location { color: #999; }
.modal-comment-like { display: flex; align-items: center; gap: 2px; }

/* 子评论 */
.modal-sub-comments {
  margin-top: 5px;
  padding: 6px 8px;
  background: #f8f8f8;
  border-radius: 6px;
}
.modal-sub-item {
  font-size: 12px;
  line-height: 1.5;
  padding: 2px 0;
}
.modal-sub-nickname { font-weight: 600; color: #222; }
.modal-sub-content { color: #444; }

/* 滚动加载更多指示器（小尺寸，在评论列表底部） */
.modal-loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 10px 0;
  font-size: 11px;
  color: #bbb;
}
/* 到底提示 */
.modal-end-line {
  text-align: center;
  padding: 12px 0;
  font-size: 11px;
  color: #ccc;
  letter-spacing: 2px;
}

/* ─── 过渡动画 ─── */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.25s ease;
}
.modal-fade-enter-active .xhs-modal-container,
.modal-fade-leave-active .xhs-modal-container {
  transition: transform 0.25s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
.modal-fade-enter-from .xhs-modal-container {
  transform: scale(0.92);
}
.modal-fade-leave-to .xhs-modal-container {
  transform: scale(0.92);
}

/* ─── 响应式 ─── */
@media (max-width: 640px) {
  .xhs-modal-container {
    width: 100vw;
    height: 100vh;
    max-width: none;
    max-height: none;
    border-radius: 0;
  }
  .xhs-modal-body {
    flex-direction: column;
  }
  .modal-image-area {
    flex: 0 0 50%;
  }
  .modal-close-btn {
    top: 8px;
    right: 8px;
  }
}
</style>
