<template>
  <header class="page-header" :class="{ transparent, fixed }">
    <div class="header-content">
      <div class="header-left">
        <slot name="left">
          <van-icon
            v-if="showBack"
            name="arrow-left"
            size="20"
            class="back-icon"
            @click="handleBack"
          />
        </slot>
      </div>
      <div class="header-center">
        <slot>
          <h1 class="header-title">{{ title }}</h1>
        </slot>
      </div>
      <div class="header-right">
        <slot name="right" />
      </div>
    </div>
  </header>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

defineProps({
  title: { type: String, default: '' },
  showBack: { type: Boolean, default: true },
  transparent: { type: Boolean, default: false },
  fixed: { type: Boolean, default: true },
  placeholderHeight: { type: String, default: '46px' }
})

const emit = defineEmits(['back'])

function handleBack() {
  emit('back')
  router.back()
}
</script>

<style scoped>
.page-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  z-index: 100;
}

.page-header.fixed {
  position: sticky;
  top: 0;
}

.page-header.transparent {
  background: transparent;
  box-shadow: none;
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 46px;
  padding: 0 16px;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  min-width: 40px;
}

.header-right {
  justify-content: flex-end;
}

.back-icon {
  color: white;
  cursor: pointer;
  padding: 4px;
}

.header-center {
  flex: 1;
  text-align: center;
}

.header-title {
  font-size: 17px;
  font-weight: 600;
  color: white;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

</style>
