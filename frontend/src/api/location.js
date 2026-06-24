import api from './index'

export const locationApi = {
  // 获取当前位置
  async getCurrentLocation(userId) {
    return api.get('/location/current', { params: { user_id: userId } })
  },

  // 设置位置
  async setLocation(locationData) {
    return api.post('/location/set', locationData)
  },

  // 获取常用位置列表
  async getFavoriteLocations(userId) {
    return api.get('/location/favorites', { params: { user_id: userId } })
  },

  // 添加常用位置
  async addFavoriteLocation(locationData) {
    return api.post('/location/favorites', locationData)
  },

  // 更新常用位置
  async updateFavoriteLocation(locationId, locationData) {
    return api.put(`/location/favorites/${locationId}`, locationData)
  },

  // 删除常用位置
  async removeFavoriteLocation(locationId) {
    return api.delete(`/location/favorites/${locationId}`)
  },

  // 切换到常用位置
  async switchLocation(locationId) {
    return api.post(`/location/switch/${locationId}`)
  }
}
