<template>
  <div class="poi-card" @click="$emit('click')">
    <div class="poi-card-image">
      <img :src="image || '/placeholder.png'" :alt="name" loading="lazy" />
    </div>
    <div class="poi-card-info">
      <h3 class="poi-card-title">{{ name }}</h3>
      <div class="poi-card-rating">
        <van-rate :model-value="rating" readonly size="12" />
        <span class="rating-text">{{ rating }}分</span>
        <span v-if="ratingCount" class="rating-count">{{ ratingCount }}条评价</span>
      </div>
      <div class="poi-card-meta">
        <span class="price">{{ priceText }}</span>
        <span v-if="distance != null" class="distance">{{ formatDistance(distance) }}</span>
      </div>
      <div v-if="tags?.length" class="poi-card-tags">
        <span v-for="tag in tags.slice(0, 3)" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { formatDistance } from '@/utils/format'

const props = defineProps({
  name: { type: String, required: true },
  image: { type: String, default: '' },
  rating: { type: Number, default: 0 },
  ratingCount: { type: Number, default: 0 },
  price: { type: [Number, String], default: null },
  priceUnit: { type: String, default: '人' },
  distance: { type: Number, default: null },
  tags: { type: Array, default: () => [] },
  isFree: { type: Boolean, default: false }
})

defineEmits(['click'])

const priceText = computed(() => {
  if (props.isFree || props.price === 0) return '免费'
  if (props.price == null) return ''
  return `¥${props.price}/${props.priceUnit}`
})
</script>

<style scoped>
.poi-card {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: white;
  border-radius: 12px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.poi-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.poi-card-image {
  width: 100px;
  height: 100px;
  border-radius: 8px;
  overflow: hidden;
  flex-shrink: 0;
  background: #f0f0f0;
}

.poi-card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.poi-card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
}

.poi-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.poi-card-rating {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.rating-text {
  font-size: 14px;
  color: #ff6b6b;
  font-weight: 600;
}

.rating-count {
  font-size: 12px;
  color: #999;
}

.poi-card-meta {
  display: flex;
  gap: 16px;
  font-size: 14px;
  margin-bottom: 6px;
}

.price {
  color: #ff6b6b;
  font-weight: 600;
}

.distance {
  color: #999;
}

.poi-card-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  padding: 2px 8px;
  background: #f0f0f0;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
}

@media (min-width: 768px) {
  .poi-card-image {
    width: 120px;
    height: 120px;
  }

  .poi-card {
    padding: 20px;
  }
}

@media (max-width: 374px) {
  .poi-card-image {
    width: 80px;
    height: 80px;
  }
}
</style>
