<template>
  <div class="food-container">
    <PageHeader title="美食推荐" />

    <div class="keyword-bar">
      <van-icon name="fire-o" color="#ff2442" />
      <span>{{ store.getKeyword() }}</span>
    </div>

    <div class="food-list">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh" success-text="刷新成功">
        <van-list
          v-model:loading="listLoading"
          :finished="store.noMore"
          finished-text="—— THE END ——"
          offset="100"
          @load="onLoad"
        >
          <div class="xhs-grid">
            <XiaohongshuCard
              v-for="note in store.foodList"
              :key="note.id"
              :note="note"
              @open-detail="openModal"
            />
          </div>
        </van-list>

        <EmptyState
          v-if="!listLoading && !store.foodList.length"
          description="暂无相关笔记"
          actionText="刷新"
          @action="refreshData"
        />
      </van-pull-refresh>
    </div>

    <XiaohongshuModal
      :visible="modalVisible"
      :note="selectedNote"
      :category="1"
      @close="modalVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useFoodStore } from '@/stores/food'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import XiaohongshuCard from '@/components/XiaohongshuCard.vue'
import XiaohongshuModal from '@/components/XiaohongshuModal.vue'

const store = useFoodStore()

const refreshing = ref(false)
const listLoading = ref(false)
const modalVisible = ref(false)
const selectedNote = ref({})
const ready = ref(false) // page=1 加载完成后为 true

function openModal(note) {
  selectedNote.value = note
  modalVisible.value = true
}

onMounted(() => {
  listLoading.value = true
  store.searchFood().then(() => {
    ready.value = true
    listLoading.value = false
  })
})

// van-list 挂载触发时 ready=false（跳过并释放），滚动到底时 ready=true（执行分页）
async function onLoad() {
  if (!ready.value) {
    listLoading.value = false
    return
  }
  if (store.noMore) {
    listLoading.value = false
    return
  }
  await store.loadMore()
  listLoading.value = false
}

async function onRefresh() {
  ready.value = false
  store.noMore = false
  store.pagination.page = 1
  await store.searchFood()
  ready.value = true
  refreshing.value = false
}

function refreshData() {
  ready.value = false
  store.noMore = false
  store.pagination.page = 1
  store.searchFood().then(() => { ready.value = true })
}
</script>

<style scoped>
.food-container {
  min-height: 100vh;
  background-color: #f5f5f5;
}
.keyword-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  font-size: 13px;
  color: #666;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
}
.food-list {
  padding: 12px;
  max-width: 1100px;
  margin: 0 auto;
}
.xhs-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}
@media (max-width: 1100px) { .xhs-grid { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 900px) { .xhs-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 640px) { .xhs-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; } }
@media (max-width: 375px) { .xhs-grid { grid-template-columns: repeat(1, 1fr); } }
</style>
