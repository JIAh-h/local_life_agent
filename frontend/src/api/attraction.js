import api from './index'

export const attractionApi = {
  // 获取景点列表
  async getAttractionList(params) {
    return api.get('/attraction/list', { params })
  },

  // 获取景点详情
  async getAttractionDetail(attractionId) {
    return api.get(`/attraction/${attractionId}`)
  }
}
