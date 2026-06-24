<template>
  <div class="favorites-container">
    <PageHeader title="我的收藏" :showBack="true" />

    <div class="category-tabs">
      <van-tabs v-model:active="activeTab" @change="onTabChange" sticky :offset-top="46" active-color="#ff2442">
        <van-tab title="全部" name="0" />
        <van-tab title="美食" name="1" />
        <van-tab title="景点" name="2" />
      </van-tabs>
    </div>

    <div class="favorites-list">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh" success-text="刷新成功">
        <van-list
          v-model:loading="listLoading"
          :finished="store.noMore"
          finished-text="—— THE END ——"
          offset="100"
          :immediate-check="false"
          @load="onLoad"
        >
          <div v-for="item in store.favorites" :key="item.id" class="fav-card" @click="openNote(item)">
            <div class="fav-cover">
              <img :src="item.note_cover || '/placeholder.png'" :alt="item.note_title" />
              <van-tag class="fav-cat" :type="item.category === 1 ? 'warning' : 'primary'" size="medium">
                {{ item.category === 1 ? '美食' : '景点' }}
              </van-tag>
            </div>
            <div class="fav-info">
              <h3 class="fav-title">{{ item.note_title || '无标题' }}</h3>
              <p class="fav-author">{{ item.note_author || '小红书用户' }}</p>
              <p class="fav-desc" v-if="item.note_desc">{{ item.note_desc }}</p>
              <div class="fav-meta">
                <span><van-icon name="like-o" size="12" /> {{ item.note_like_count }}</span>
                <span><van-icon name="star-o" size="12" /> {{ item.note_collect_count }}</span>
              </div>
            </div>
            <div class="fav-action">
              <van-button size="small" type="danger" plain @click.stop="removeFav(item.id)">
                取消收藏
              </van-button>
            </div>
          </div>
        </van-list>

        <EmptyState
          v-if="!listLoading && !store.favorites.length"
          description="暂无收藏"
          actionText="去探索"
          @action="$router.push('/food')"
        />
      </van-pull-refresh>
    </div>

    <!-- 小红书笔记详情弹窗（数据来自本地数据库） -->
    <XiaohongshuModal
      :visible="modalVisible"
      :note="modalNote"
      :category="selectedItem.category || 1"
      :local-detail="selectedItem"
      @close="modalVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useFavoritesStore } from '@/stores/favorites'
import { showToast, showConfirmDialog } from 'vant'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import XiaohongshuModal from '@/components/XiaohongshuModal.vue'

const store = useFavoritesStore()

const activeTab = ref(0)
const refreshing = ref(false)
const listLoading = ref(false)

const ready = ref(false)

// 弹窗状态
const modalVisible = ref(false)
const selectedItem = ref({})

/** 转换收藏项为弹窗可用的 note 格式 */
const modalNote = computed(() => {
  const item = selectedItem.value
  if (!item || !item.note_id) return {}
  return {
    id: item.note_id,
    xsec_token: item.xsec_token || '',
    display_title: item.note_title || '',
    cover_url: item.note_cover || '',
    user: { nickname: item.note_author || '', avatar: item.note_author_avatar || '' },
    publish_time: item.note_publish_time || '',
  }
})

function openNote(item) {
  selectedItem.value = item
  modalVisible.value = true
}

onMounted(() => {
  listLoading.value = true
  store.fetchFavorites({ category: activeTab.value || undefined }).then(() => {
    ready.value = true
    listLoading.value = false
  })
})

function onTabChange(tab) {
  ready.value = false
  const c = Number(tab) || undefined
  store.fetchFavorites({ category: c }).then(() => { ready.value = true })
}

function onLoad() {
  listLoading.value = false
}

async function onRefresh() {
  const c = activeTab.value || undefined
  await store.fetchFavorites({ category: c })
  refreshing.value = false
}

async function removeFav(id) {
  try {
    await showConfirmDialog({ title: '确认取消收藏', message: '确定要取消收藏吗？' })
    await store.removeFavorite(id)
    showToast('已取消收藏')
  } catch (e) {
    if (e !== 'cancel') showToast('操作失败')
  }
}
</script>

<style scoped>
.favorites-container { min-height: 100vh; background-color: #f5f5f5; }
.category-tabs { background: #fff; }
.favorites-list { padding: 12px 16px; max-width: 800px; margin: 0 auto; }

.fav-card {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 10px;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.fav-cover {
  width: 90px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
}
.fav-cover img { width: 100%; height: 100%; object-fit: cover; }
.fav-cat { position: absolute; top: 4px; left: 4px; }

.fav-info { flex: 1; min-width: 0; }
.fav-title { font-size: 15px; font-weight: 600; color: #222; margin: 0 0 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fav-author { font-size: 12px; color: #999; margin: 0 0 4px; }
.fav-desc { font-size: 13px; color: #666; margin: 0 0 6px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.fav-meta { display: flex; gap: 12px; font-size: 12px; color: #999; }
.fav-meta span { display: flex; align-items: center; gap: 2px; }
.fav-action { display: flex; align-items: center; flex-shrink: 0; }
</style>
