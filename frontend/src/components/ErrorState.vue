<template>
  <div class="error-state">
    <van-icon name="warning-o" size="48" color="#ff4757" />
    <p class="error-text">{{ message }}</p>
    <van-button
      v-if="showRetry"
      type="primary"
      size="small"
      class="retry-btn"
      @click="$emit('retry')"
    >
      {{ retryText }}
    </van-button>
  </div>
</template>

<script setup>
defineProps({
  message: { type: String, default: '加载失败，请重试' },
  showRetry: { type: Boolean, default: true },
  retryText: { type: String, default: '重试' }
})

defineEmits(['retry'])
</script>

<style scoped>
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 16px;
  gap: 12px;
  min-height: 200px;
}

.error-text {
  font-size: 14px;
  color: #666;
  margin: 0;
  text-align: center;
}

.retry-btn {
  border-radius: 20px;
  padding: 0 24px;
}
</style>
