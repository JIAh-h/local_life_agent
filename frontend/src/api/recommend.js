import api from './index'

export const recommendApi = {
  // 获取今日推荐
  async getTodayRecommendations(params) {
    return api.get('/recommend/today', { params })
  },

  // 提交反馈
  async submitFeedback(feedbackData) {
    return api.post('/recommend/feedback', feedbackData)
  },

  // 刷新推荐
  async refreshRecommendations(params) {
    return api.post('/recommend/refresh', null, { params })
  }
}
