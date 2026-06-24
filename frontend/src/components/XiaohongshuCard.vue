<template>
  <div class="xhs-card" @click="goToDetail">
    <!-- 封面图 -->
    <div class="xhs-card-cover">
      <img
        :src="note.cover_url || '/placeholder.png'"
        :alt="note.display_title"
        loading="lazy"
        @error="onImgError"
      />
      <!-- 多图标记 -->
      <span v-if="note.thumbnails && note.thumbnails.length > 1" class="xhs-card-multi">
        <van-icon name="photo-o" size="12" /> {{ note.thumbnails.length }}
      </span>
      <!-- 发布时间角标 -->
      <span v-if="note.publish_time" class="xhs-card-badge">{{ note.publish_time }}</span>
    </div>
    <!-- 标题 -->
    <div class="xhs-card-title">{{ note.display_title || '无标题' }}</div>
    <!-- 底部信息 -->
    <div class="xhs-card-footer">
      <div class="xhs-card-user" v-if="note.user && note.user.nickname">
        <img
          v-if="note.user.avatar"
          :src="note.user.avatar"
          class="xhs-card-avatar"
          @error="onAvatarError"
        />
        <span class="xhs-card-avatar-placeholder" v-else>
          <van-icon name="contact" size="14" color="#999" />
        </span>
        <span class="xhs-card-nickname">{{ note.user.nickname }}</span>
      </div>
      <van-icon name="arrow" color="#ccc" size="14" />
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  note: { type: Object, required: true }
})

const emit = defineEmits(['open-detail'])

function goToDetail() {
  emit('open-detail', props.note)
}

function onImgError(e) {
  e.target.src = '/placeholder.png'
}

function onAvatarError(e) {
  e.target.style.display = 'none'
}
</script>

<style scoped>
.xhs-card {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  break-inside: avoid;
  margin-bottom: 8px;
}
.xhs-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.10);
}

/* 封面 */
.xhs-card-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  background: #f0f0f0;
  overflow: hidden;
}
.xhs-card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.xhs-card-multi {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(0,0,0,0.5);
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 2px;
  backdrop-filter: blur(2px);
}
.xhs-card-badge {
  position: absolute;
  left: 6px;
  bottom: 6px;
  background: rgba(0,0,0,0.55);
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  backdrop-filter: blur(2px);
}

/* 标题 */
.xhs-card-title {
  padding: 8px 8px 0;
  font-size: 13px;
  font-weight: 500;
  color: #222;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 底部 */
.xhs-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px 8px;
}
.xhs-card-user {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  flex: 1;
}
.xhs-card-avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
}
.xhs-card-avatar-placeholder {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #f5f5f5;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.xhs-card-nickname {
  font-size: 11px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
