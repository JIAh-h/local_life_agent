import api from './index'

export const foodApi = {
  // 获取美食列表
  async getFoodList(params) {
    return api.get('/food/list', { params })
  },

  // 获取美食详情
  async getFoodDetail(foodId) {
    return api.get(`/food/${foodId}`)
  }
}
