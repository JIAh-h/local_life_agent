import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useLocationStore } from './location'
import { useAuthStore } from './auth'

const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'

export const useAgentStore = defineStore('agent', () => {
  // ─── 状态 ───
  const messages = ref([])
  const sessionId = ref(null)
  const loading = ref(false)
  const streaming = ref(false)
  const error = ref(null)
  const currentReply = ref('')
  const currentSuggestions = ref([])
  const currentResults = ref(null)
  const historyLoaded = ref(false)
  const sessions = ref([])
  const toolStatus = ref('')  // 工具调用状态文本（如 "正在搜索周边美食..."）

  // ─── 模型配置 ───
  const modelProviders = ref([])
  const activeProvider = ref('xiaomi')
  const activeModel = ref('mimo-v2.5-pro')

  // ─── 上下文追踪 ───
  // 用户在对话中提到的“地方”（用于“附近”判断基准）
  const mentionedPlace = ref(null) // { name: string, latitude: number, longitude: number, ... }

  const modelLabel = computed(() => {
    for (const p of modelProviders.value) {
      if (p.key === activeProvider.value) {
        const m = p.models.find(m => m.key === activeModel.value)
        if (m) return m.label
      }
    }
    return '选择模型'
  })

  // ─── 计算属性 ───
  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1])
  const isThinking = computed(() => loading.value && !streaming.value)

  // ─── 获取当前用户ID（UUID格式）───
  function getCurrentUserId() {
    const authStore = useAuthStore()
    const userId = authStore.user?.id
    
    // 如果用户已登录且ID有效
    if (userId) {
      // 检查是否为有效的UUID格式
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
      if (uuidRegex.test(String(userId))) {
        return String(userId)
      }
      // 如果不是UUID格式（如整数ID），使用固定的映射UUID
      const storageKey = `user_uuid_${userId}`
      let mappedUuid = localStorage.getItem(storageKey)
      if (!mappedUuid) {
        mappedUuid = generateUUID()
        localStorage.setItem(storageKey, mappedUuid)
      }
      return mappedUuid
    }
    
    // 用户未登录，从localStorage获取或生成匿名UUID
    let anonymousId = localStorage.getItem('anonymous_user_id')
    if (!anonymousId) {
      anonymousId = generateUUID()
      localStorage.setItem('anonymous_user_id', anonymousId)
    }
    return anonymousId
  }

  // ─── 生成UUID ───
  function generateUUID() {
    // 使用crypto.randomUUID()（现代浏览器支持）
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID()
    }
    // 降级方案：手动生成UUID v4
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0
      const v = c === 'x' ? r : (r & 0x3 | 0x8)
      return v.toString(16)
    })
  }

  // ─── 构建位置上下文 ───
  function buildLocationContext() {
    const locationStore = useLocationStore()
    const ctx = {
      latitude: locationStore.currentLocation?.latitude ?? null,
      longitude: locationStore.currentLocation?.longitude ?? null,
      location_source: locationStore.locationSource || null,
      search_location_name: locationStore.searchLocationName || null,
      mentioned_place: mentionedPlace.value,
    }
    return ctx
  }

  // ─── 行动 ───

  /**
   * 加载对话历史
   */
  async function loadHistory(targetSessionId = null) {
    const userId = getCurrentUserId()
    if (!userId) {
      console.warn('用户未登录，无法加载对话历史')
      return
    }

    try {
      const params = new URLSearchParams({ user_id: userId })
      if (targetSessionId) {
        params.append('session_id', targetSessionId)
      }

      const response = await fetch(`${baseURL}/agent/history?${params}`)
      if (response.ok) {
        const data = await response.json()
        const historyMessages = data.messages || []
        
        // 转换为前端格式
        messages.value = historyMessages.map(msg => ({
          id: msg.id?.toString() || Date.now().toString(),
          role: msg.message_type === 'user' ? 'user' : 'assistant',
          content: msg.content,
          timestamp: msg.created_at,
          intent: msg.message_metadata?.intent,
          entities: msg.message_metadata?.entities,
          actions: msg.message_metadata?.actions || [],
          round_id: msg.round_id || null,
          version: msg.version || 1,
          is_latest: msg.is_latest !== false
        }))
        
        // 设置 session_id
        if (targetSessionId) {
          sessionId.value = targetSessionId
        } else if (historyMessages.length > 0) {
          sessionId.value = historyMessages[0].session_id
        }
        
        historyLoaded.value = true
        console.log(`已加载 ${messages.value.length} 条对话历史`)
      }
    } catch (err) {
      console.error('加载对话历史失败:', err)
    }
  }

  /**
   * 获取用户的会话列表
   */
  async function loadSessions() {
    const userId = getCurrentUserId()
    if (!userId) return

    try {
      const response = await fetch(`${baseURL}/agent/sessions?user_id=${userId}`)
      if (response.ok) {
        const data = await response.json()
        sessions.value = data.sessions || []
      }
    } catch (err) {
      console.error('获取会话列表失败:', err)
    }
  }

  /**
   * 切换到指定会话
   */
  async function switchSession(targetSessionId) {
    await loadHistory(targetSessionId)
  }

  /**
   * 发送消息（非流式）
   */
  async function sendMessage(message) {
    if (!message.trim()) return

    const locationStore = useLocationStore()
    const userId = getCurrentUserId()
    loading.value = true
    error.value = null

    // 添加用户消息到列表
    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    })

    const locationCtx = buildLocationContext()
    const payload = {
      message,
      user_id: userId,
      session_id: sessionId.value,
      latitude: locationCtx.latitude,
      longitude: locationCtx.longitude,
      location_source: locationCtx.location_source,
      search_location_name: locationCtx.search_location_name,
      mentioned_place: locationCtx.mentioned_place,
      stream: false,
      model_config: { provider: activeProvider.value, model: activeModel.value }
    }
    // 补充地址/城市信息
    if (locationCtx.latitude && locationCtx.longitude) {
      const loc = locationStore.currentLocation
      if (loc) {
        if (loc.address) payload.address = loc.address
        if (loc.city) payload.city = loc.city
        if (loc.district) payload.district = loc.district
      }
    }

    try {
      const response = await fetch(`${baseURL}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || '请求失败')
      }

      const data = await response.json()

      // 保存 session_id
      if (data.session_id) {
        sessionId.value = data.session_id
      }

      // 添加 AI 回复
      messages.value.push({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.reply,
        intent: data.intent,
        entities: data.entities,
        actions: data.actions,
        timestamp: new Date().toISOString()
      })

      currentSuggestions.value = data.suggestions || []
      currentResults.value = data.results

    } catch (err) {
      error.value = err.message
      // 添加错误消息
      messages.value.push({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `抱歉，出了点问题：${err.message}`,
        timestamp: new Date().toISOString()
      })
    } finally {
      loading.value = false
    }
  }

  /**
   * 发送消息（SSE 流式）
   */
  async function sendMessageStream(message) {
    if (!message.trim()) return

    const locationStore = useLocationStore()
    const userId = getCurrentUserId()
    streaming.value = true
    error.value = null
    currentReply.value = ''

    // 添加用户消息
    messages.value.push({
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    })

    const locationCtx = buildLocationContext()
    const payload = {
      message,
      user_id: userId,
      session_id: sessionId.value,
      latitude: locationCtx.latitude,
      longitude: locationCtx.longitude,
      location_source: locationCtx.location_source,
      search_location_name: locationCtx.search_location_name,
      mentioned_place: locationCtx.mentioned_place,
      stream: true,
      model_config: { provider: activeProvider.value, model: activeModel.value }
    }
    // 补充地址/城市信息（从 locationStore 读取，供后端注入系统提示词）
    if (locationCtx.latitude && locationCtx.longitude) {
      const loc = locationStore.currentLocation
      if (loc) {
        if (loc.address) payload.address = loc.address
        if (loc.city) payload.city = loc.city
        if (loc.district) payload.district = loc.district
      }
    }

    try {
      const response = await fetch(`${baseURL}/agent/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const events = text.split('\n\n').filter(Boolean)

        for (const eventStr of events) {
          const lines = eventStr.split('\n')
          let eventName = 'content'
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventName = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6).trim()
            }
          }

          if (eventData) {
            try {
              const data = JSON.parse(eventData)
              handleStreamEvent(eventName, data)
            } catch {
              // 非 JSON 数据，忽略
            }
          }
        }
      }
    } catch (err) {
      error.value = err.message
      messages.value.push({
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `流式响应中断：${err.message}`,
        timestamp: new Date().toISOString()
      })
    } finally {
      streaming.value = false
    }
  }

  function handleStreamEvent(eventName, data) {
    switch (eventName) {
      case 'intent':
        // 意图识别结果
        break
      case 'thinking':
        // 思考/工具调用中 → 显示进度文本
        if (data.message) {
          toolStatus.value = data.message
        }
        break
      case 'content':
        // AI 回复文本（仅在最终轮次才会收到）
        if (data.text) {
          // 收到第一条 content 时清除 toolStatus
          if (toolStatus.value) {
            toolStatus.value = ''
          }
          currentReply.value += data.text
        }
        break
      case 'tool_call':
        // 工具调用事件 → 更新进度
        if (data && data.function && data.function.name) {
          const nameMap = {
            'amap.place_around': '搜索周边',
            'amap.regeocode': '定位',
            'amap.direction_walking': '步行路线',
            'amap.direction_bicycling': '骑行路线',
            'amap.direction_driving': '驾车路线',
            'amap.direction_transit_integrated': '公交路线',
            'amap.weather': '查询天气',
          }
          const displayName = nameMap[data.function.name] || data.function.name
          toolStatus.value = `正在${displayName}...`
        }
        break
      case 'tool_result':
        // 工具执行完成
        break
      case 'results':
        currentResults.value = data
        break
      case 'suggestions':
        currentSuggestions.value = data
        break
      case 'done':
        // 流式完成，将累积回复加入消息列表
        if (data.session_id) {
          sessionId.value = data.session_id
        }
        if (currentReply.value) {
          messages.value.push({
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: currentReply.value,
            timestamp: new Date().toISOString(),
            round_id: data.round_id || null,
            version: data.version || 1,
            is_latest: true
          })
          currentReply.value = ''
        }
        // 若后端返回了提及的地点，保存为上下文
        if (data.mentioned_place) {
          mentionedPlace.value = data.mentioned_place
        }
        toolStatus.value = ''
        break
      case 'error':
        error.value = data.error || '未知错误'
        toolStatus.value = ''
        break
    }
  }

  /**
   * 发送建议指令
   */
  function sendSuggestion(text) {
    sendMessage(text)
  }

  /**
   * 新建会话（仅重置本地状态，不删除服务端历史）
   */
  function newSession() {
    messages.value = []
    sessionId.value = null
    currentReply.value = ''
    currentSuggestions.value = []
    currentResults.value = null
    error.value = null
    historyLoaded.value = false
    mentionedPlace.value = null
  }

  /**
   * 清空对话（删除服务端记录并重置本地状态）
   */
  async function clearChat() {
    const userId = getCurrentUserId()
    
    // 如果有 session_id，删除服务器端的历史记录
    if (userId && sessionId.value) {
      try {
        await fetch(`${baseURL}/agent/history/${sessionId.value}?user_id=${userId}`, {
          method: 'DELETE'
        })
        // 从本地会话列表中移除已删除的会话
        sessions.value = sessions.value.filter(s => s.session_id !== sessionId.value)
      } catch (err) {
        console.error('删除服务器端对话历史失败:', err)
      }
    }
    
    // 清空本地状态
    newSession()
  }

  /**
   * 重试最后一条消息
   */
  function retryLast() {
    const userMessages = messages.value.filter(m => m.role === 'user')
    if (userMessages.length > 0) {
      // 移除最后一条 AI 回复
      const lastAISentIdx = [...messages.value].reverse().findIndex(m => m.role === 'assistant')
      if (lastAISentIdx >= 0) {
        messages.value.splice(messages.value.length - 1 - lastAISentIdx, 1)
      }
      const lastUserMsg = userMessages[userMessages.length - 1]
      sendMessage(lastUserMsg.content)
    }
  }

  /**
   * 获取指定轮次的所有版本
   */
  async function getVersions(roundId) {
    const userId = getCurrentUserId()
    if (!userId || !roundId) return []

    try {
      const response = await fetch(`${baseURL}/agent/versions/${roundId}?user_id=${userId}`)
      if (response.ok) {
        const data = await response.json()
        return data.versions || []
      }
    } catch (err) {
      console.error('获取版本列表失败:', err)
    }
    return []
  }

  /**
   * 重新生成AI回复（流式）
   * @param {string} roundId - 要重新生成的轮次ID
   * @param {Function} onContent - 内容回调
   * @param {Function} onDone - 完成回调
   * @param {Function} onError - 错误回调
   */
  async function regenerateMessage(roundId, { onContent, onDone, onError }) {
    const userId = getCurrentUserId()
    if (!userId || !roundId) return

    const locationStore = useLocationStore()
    const locationCtx = buildLocationContext()

    const payload = {
      user_id: userId,
      session_id: sessionId.value,
      round_id: roundId,
      latitude: locationCtx.latitude,
      longitude: locationCtx.longitude,
      stream: true,
      model_config: { provider: activeProvider.value, model: activeModel.value }
    }

    // 补充地址信息
    if (locationCtx.latitude && locationCtx.longitude) {
      const loc = locationStore.currentLocation
      if (loc) {
        if (loc.address) payload.address = loc.address
        if (loc.city) payload.city = loc.city
        if (loc.district) payload.district = loc.district
      }
    }

    try {
      const response = await fetch(`${baseURL}/agent/regenerate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value, { stream: true })
        const events = text.split('\n\n').filter(Boolean)

        for (const eventStr of events) {
          const lines = eventStr.split('\n')
          let eventName = 'content'
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventName = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6).trim()
            }
          }

          if (eventData) {
            try {
              const data = JSON.parse(eventData)
              if (eventName === 'content' && data.text) {
                onContent?.(data.text)
              } else if (eventName === 'done') {
                onDone?.(data)
              } else if (eventName === 'error') {
                onError?.(data.error || '重新生成失败')
              }
            } catch {
              // 非 JSON 数据，忽略
            }
          }
        }
      }
    } catch (err) {
      onError?.(err.message)
    }
  }

  /**
   * 获取可用模型列表
   */
  async function fetchModels() {
    try {
      const response = await fetch(`${baseURL}/agent/models`)
      if (response.ok) {
        const data = await response.json()
        modelProviders.value = data.providers || []
      }
    } catch (err) {
      console.error('获取模型列表失败:', err)
    }
  }

  /**
   * 切换对话模型
   */
  function switchModel(provider, model) {
    activeProvider.value = provider
    activeModel.value = model
  }

  return {
    messages,
    sessionId,
    loading,
    streaming,
    error,
    currentReply,
    currentSuggestions,
    currentResults,
    historyLoaded,
    sessions,
    hasMessages,
    lastMessage,
    isThinking,
    toolStatus,
    modelProviders,
    activeProvider,
    activeModel,
    modelLabel,
    mentionedPlace,
    sendMessage,
    sendMessageStream,
    sendSuggestion,
    newSession,
    clearChat,
    getCurrentUserId,
    retryLast,
    fetchModels,
    switchModel,
    loadHistory,
    loadSessions,
    switchSession,
    getVersions,
    regenerateMessage,
  }
})
