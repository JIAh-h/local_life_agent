<template>
  <div class="empty-state">
    <van-empty :image="image" :description="description" />
    <van-button
      v-if="actionText"
      type="primary"
      size="small"
      class="empty-action"
      @click="$emit('action')"
    >
      {{ actionText }}
    </van-button>
  </div>
</template>

<script setup>
defineProps({
  description: { type: String, default: '暂无数据' },
  image: { type: String, default: 'default' },
  actionText: { type: String, default: '' }
})

defineEmits(['action'])
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px 16px;
  gap: 16px;
}

.empty-action {
  border-radius: 20px;
  padding: 0 24px;
}
</style>
