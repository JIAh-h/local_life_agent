import { defineStore } from 'pinia'
import { ref } from 'vue'
import { recommendApi } from '@/api/recommend'
import { useLocationStore } from './location'

export const useRecommendStore = defineStore('recommend', () => {
  // 状态
  const recommendations = ref([])
  const weatherInfo = ref(null)
  const loading = ref(false)
  const error = ref(null)

  // 获取今日推荐
  async function fetchTodayRecommendations() {
    const locationStore = useLocationStore()
    if (!locationStore.hasLocation) {
      error.value = '请先定位'
      return
    }

    loading.value = true
    error.value = null

    try {
      const result = await recommendApi.getTodayRecommendations({
        latitude: locationStore.currentLocation.latitude,
        longitude: locationStore.currentLocation.longitude
      })
      recommendations.value = result
      
      // 提取天气信息
      if (result.length > 0 && result[0].weather_info) {
        weatherInfo.value = result[0].weather_info
      }
    } catch (err) {
      error.value = err.message
      console.error('获取今日推荐失败:', err)
    } finally {
      loading.value = false
    }
  }

  // 提交反馈
  async function submitFeedback(recommendationId, feedback) {
    try {
      await recommendApi.submitFeedback({
        recommendation_id: recommendationId,
        feedback
      })
      
      // 更新本地状态
      const index = recommendations.value.findIndex(
        (rec) => rec.id === recommendationId
      )
      if (index !== -1) {
        recommendations.value[index].feedback = feedback
      }
    } catch (err) {
      error.value = err.message
      console.error('提交反馈失败:', err)
      throw err
    }
  }

  // 刷新推荐
  async function refreshRecommendations() {
    const locationStore = useLocationStore()
    if (!locationStore.hasLocation) {
      error.value = '请先定位'
      return
    }

    loading.value = true
    error.value = null

    try {
      const result = await recommendApi.refreshRecommendations({
        latitude: locationStore.currentLocation.latitude,
        longitude: locationStore.currentLocation.longitude
      })
      recommendations.value = result
      
      // 提取天气信息
      if (result.length > 0 && result[0].weather_info) {
        weatherInfo.value = result[0].weather_info
      }
    } catch (err) {
      error.value = err.message
      console.error('刷新推荐失败:', err)
    } finally {
      loading.value = false
    }
  }

  return {
    recommendations,
    weatherInfo,
    loading,
    error,
    fetchTodayRecommendations,
    submitFeedback,
    refreshRecommendations
  }
})
