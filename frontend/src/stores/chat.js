import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { chatApi } from '@/api/chat'
import { useLocationStore } from './location'

export const useChatStore = defineStore('chat', () => {
  // 状态
  const messages = ref([])
  const sessionId = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const suggestions = ref([])

  // 计算属性
  const hasMessages = computed(() => messages.value.length > 0)

  // 发送消息
  async function sendMessage(content) {
    const locationStore = useLocationStore()
    if (!locationStore.hasLocation) {
      error.value = '请先定位'
      return
    }

    // 添加用户消息
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content,
      timestamp: new Date()
    }
    messages.value.push(userMessage)

    loading.value = true
    error.value = null

    try {
      const response = await chatApi.sendMessage({
        message: content,
        session_id: sessionId.value,
        latitude: locationStore.currentLocation.latitude,
        longitude: locationStore.currentLocation.longitude
      })

      // 更新会话ID
      sessionId.value = response.session_id

      // 添加AI回复
      const aiMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: response.message,
        recommendations: response.recommendations,
        timestamp: new Date()
      }
      messages.value.push(aiMessage)

      // 更新建议
      suggestions.value = response.suggestions || []

      return response
    } catch (err) {
      error.value = err.message
      console.error('发送消息失败:', err)
      
      // 添加错误消息
      const errorMessage = {
        id: Date.now() + 1,
        type: 'ai',
        content: '抱歉，处理您的消息时出现错误，请稍后重试。',
        timestamp: new Date()
      }
      messages.value.push(errorMessage)
    } finally {
      loading.value = false
    }
  }

  // 获取历史记录
  async function fetchHistory() {
    try {
      const history = await chatApi.getHistory({
        session_id: sessionId.value
      })
      messages.value = history
    } catch (err) {
      console.error('获取历史记录失败:', err)
    }
  }

  // 清空历史记录
  async function clearHistory() {
    if (sessionId.value) {
      try {
        await chatApi.deleteHistory(sessionId.value)
      } catch (err) {
        console.error('删除历史记录失败:', err)
      }
    }
    messages.value = []
    sessionId.value = null
    suggestions.value = []
  }

  // 发送建议消息
  function sendSuggestion(suggestion) {
    sendMessage(suggestion)
  }

  return {
    messages,
    sessionId,
    loading,
    error,
    suggestions,
    hasMessages,
    sendMessage,
    fetchHistory,
    clearHistory,
    sendSuggestion
  }
})
