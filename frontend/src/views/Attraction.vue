<template>
  <div class="attraction-container">
    <PageHeader title="景点推荐" />

    <div class="keyword-bar">
      <van-icon name="fire-o" color="#ff2442" />
      <span>{{ store.getKeyword() }}</span>
    </div>

    <div class="attraction-list">
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
              v-for="note in store.attractionList"
              :key="note.id"
              :note="note"
              @open-detail="openModal"
            />
          </div>
        </van-list>

        <EmptyState
          v-if="!listLoading && !store.attractionList.length"
          description="暂无相关笔记"
          actionText="刷新"
          @action="refreshData"
        />
      </van-pull-refresh>
    </div>

    <XiaohongshuModal
      :visible="modalVisible"
      :note="selectedNote"
      :category="2"
      @close="modalVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAttractionStore } from '@/stores/attraction'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import XiaohongshuCard from '@/components/XiaohongshuCard.vue'
import XiaohongshuModal from '@/components/XiaohongshuModal.vue'

const store = useAttractionStore()

const refreshing = ref(false)
const listLoading = ref(false)
const modalVisible = ref(false)
const selectedNote = ref({})
const ready = ref(false)

function openModal(note) {
  selectedNote.value = note
  modalVisible.value = true
}

onMounted(() => {
  listLoading.value = true
  store.searchAttraction().then(() => {
    ready.value = true
    listLoading.value = false
  })
})

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
  await store.searchAttraction()
  ready.value = true
  refreshing.value = false
}

function refreshData() {
  ready.value = false
  store.noMore = false
  store.pagination.page = 1
  store.searchAttraction().then(() => { ready.value = true })
}
</script>

<style scoped>
.attraction-container {
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
.attraction-list {
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
