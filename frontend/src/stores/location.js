import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { locationApi } from '@/api/location'

export const useLocationStore = defineStore('location', () => {
  // 状态
  const currentLocation = ref(null)
  const favoriteLocations = ref([])
  const loading = ref(false)
  const error = ref(null)
  const lastLocateResult = ref('') // 'success' | 'failed' | ''
  const locationSource = ref(null)   // 'search' | 'gps' | 'saved' | null
  const searchLocationName = ref('') // 用户搜索的地点名称

  // 计算属性
  const hasLocation = computed(() => !!currentLocation.value)
  const locationText = computed(() => {
    if (!currentLocation.value) return '未定位'
    return currentLocation.value.address || '未知位置'
  })

  // 设置定位（由定位服务组件/MCP调用）
  function setLocation(location, source = 'gps') {
    currentLocation.value = location
    locationSource.value = source
    lastLocateResult.value = 'success'
    error.value = null
    // 如果不是搜索来源，清除搜索地点名
    if (source !== 'search') {
      searchLocationName.value = ''
    }
  }

  // 设置搜索定位（用户搜索了特定地点）
  function setSearchLocation(location, searchName) {
    currentLocation.value = location
    locationSource.value = 'search'
    searchLocationName.value = searchName || ''
    lastLocateResult.value = 'success'
    error.value = null
  }

  // 清除定位
  function clearLocation() {
    currentLocation.value = null
    locationSource.value = null
    searchLocationName.value = ''
    lastLocateResult.value = ''
    error.value = null
  }

  // 设置定位失败
  function setLocationError(errMsg) {
    error.value = errMsg
    lastLocateResult.value = 'failed'
    currentLocation.value = null
  }

  // 获取常用位置列表
  async function fetchFavoriteLocations() {
    try {
      const locations = await locationApi.getFavoriteLocations()
      favoriteLocations.value = locations
    } catch (err) {
      console.error('获取常用位置失败:', err)
    }
  }

  // 切换位置
  async function switchLocation(locationId) {
    try {
      const location = await locationApi.switchLocation(locationId)
      currentLocation.value = location
    } catch (err) {
      console.error('切换位置失败:', err)
      throw err
    }
  }

  // 添加常用位置
  async function addFavoriteLocation(locationData) {
    try {
      const location = await locationApi.addFavoriteLocation(locationData)
      favoriteLocations.value.push(location)
      return location
    } catch (err) {
      console.error('添加常用位置失败:', err)
      throw err
    }
  }

  // 更新常用位置
  async function updateFavoriteLocation(locationId, locationData) {
    try {
      const location = await locationApi.updateFavoriteLocation(locationId, locationData)
      const index = favoriteLocations.value.findIndex(loc => loc.id === locationId)
      if (index !== -1) {
        favoriteLocations.value[index] = location
      }
      return location
    } catch (err) {
      console.error('更新常用位置失败:', err)
      throw err
    }
  }

  // 删除常用位置
  async function removeFavoriteLocation(locationId) {
    try {
      await locationApi.removeFavoriteLocation(locationId)
      favoriteLocations.value = favoriteLocations.value.filter(
        (loc) => loc.id !== locationId
      )
    } catch (err) {
      console.error('删除常用位置失败:', err)
      throw err
    }
  }

  return {
    currentLocation,
    favoriteLocations,
    loading,
    error,
    hasLocation,
    locationText,
    lastLocateResult,
    locationSource,
    searchLocationName,
    setLocation,
    setSearchLocation,
    clearLocation,
    setLocationError,
    fetchFavoriteLocations,
    switchLocation,
    addFavoriteLocation,
    updateFavoriteLocation,
    removeFavoriteLocation
  }
})
