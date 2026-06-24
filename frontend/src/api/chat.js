import api from './index'

export const chatApi = {
  // 发送消息
  async sendMessage(messageData) {
    return api.post('/chat/send', messageData)
  },

  // 获取历史记录
  async getHistory(params) {
    return api.get('/chat/history', { params })
  },

  // 删除历史记录
  async deleteHistory(sessionId) {
    return api.delete(`/chat/history/${sessionId}`)
  }
}
