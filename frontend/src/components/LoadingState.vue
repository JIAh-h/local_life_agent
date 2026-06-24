<template>
  <div class="loading-state" :style="{ minHeight: height }">
    <van-loading :size="size" :color="color" />
    <p v-if="text" class="loading-text">{{ text }}</p>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '加载中...' },
  size: { type: [String, Number], default: 36 },
  color: { type: String, default: '#667eea' },
  height: { type: String, default: '200px' }
})
</script>

<style scoped>
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.loading-text {
  font-size: 14px;
  color: #999;
  margin: 0;
}
</style>
