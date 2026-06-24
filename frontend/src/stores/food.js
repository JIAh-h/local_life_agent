import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useLocationStore } from './location'

const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'

export const useFoodStore = defineStore('food', () => {
  const foodList = ref([])
  const currentFood = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const noMore = ref(false)  // 是否已无更多数据
  const pagination = ref({
    page: 1,
    pageSize: 20,
  })

  function getKeyword() {
    const loc = useLocationStore().currentLocation
    if (!loc) return '美食'
    return (loc.city || loc.address || loc.district || '') + ' 美食'
  }

  /** 首次搜索/刷新 */
  async function searchFood(params = {}) {
    loading.value = true
    error.value = null
    noMore.value = false
    pagination.value.page = 1

    try {
      const keyword = params.keyword || getKeyword()
      const page = params.page || pagination.value.page
      const pageSize = params.page_size || pagination.value.pageSize

      const response = await fetch(
        `${baseURL}/food/list?keyword=${encodeURIComponent(keyword)}&page=${page}&page_size=${pageSize}`
      )
      if (!response.ok) throw new Error('搜索美食失败')
      const result = await response.json()
      foodList.value = result.notes || []
      // 返回数量 < pageSize 说明没有更多数据了
      if ((result.notes || []).length < pageSize) {
        noMore.value = true
      }
    } catch (err) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  /** 加载下一页（追加到列表末尾） */
  async function loadMore() {
    if (loading.value || noMore.value) return
    loading.value = true
    try {
      pagination.value.page++
      const result = await fetch(
        `${baseURL}/food/list?keyword=${encodeURIComponent(getKeyword())}&page=${pagination.value.page}&page_size=${pagination.value.pageSize}`
      ).then(r => r.json())
      const newNotes = result.notes || []
      foodList.value.push(...newNotes)
      // 返回数量 < pageSize 说明没有更多了
      if (newNotes.length < pagination.value.pageSize) {
        noMore.value = true
      }
    } catch (err) {
      pagination.value.page--
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  return {
    foodList, currentFood, loading, error, pagination, noMore,
    searchFood, loadMore, getKeyword,
    // 兼容旧方法
    fetchFoodDetail: async () => ({ desc: '', image_urls: [] }),
    updateFilters: () => {},
    resetFilters: () => {},
  }
})
