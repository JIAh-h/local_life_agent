<template>
  <div class="chat-wrapper">
    <!-- 左侧边栏 -->
    <aside :class="['chat-sidebar', { open: sidebarOpen }]">
      <div class="sidebar-header">
        <div class="sidebar-brand">
          <van-icon name="chat-o" size="20" color="#667eea" />
          <span>智能助手</span>
        </div>
        <div class="sidebar-actions">
          <div class="sidebar-action-btn" @click="createNewSession" title="新建会话">
            <van-icon name="plus" size="16" />
          </div>
          <div class="sidebar-action-btn mobile-close" @click="sidebarOpen = false" title="收起侧边栏">
            <van-icon name="arrow-left" size="16" />
          </div>
        </div>
      </div>

      <div class="sidebar-search">
        <van-icon name="search" size="14" color="#999" />
        <input type="text" v-model="searchKeyword" placeholder="搜索历史对话..." class="search-input" />
      </div>

      <div class="sidebar-sessions">
        <div class="sessions-title">历史对话</div>
        <div
          v-for="session in filteredSessions"
          :key="session.session_id"
          :class="['session-item', { active: session.session_id === agentStore.sessionId }]"
          @click="switchSession(session.session_id)"
          @mouseenter="hoveredSessionId = session.session_id"
          @mouseleave="hoveredSessionId = null"
        >
          <div class="session-info">
            <div class="session-preview">
              <van-icon v-if="pinnedSessions.includes(session.session_id)" name="flag-o" size="12" class="pin-icon" />
              {{ session.first_question || session.last_message || '新会话' }}
            </div>
            <div class="session-time">{{ formatSessionTime(session.last_message_time) }}</div>
          </div>
          <div
            v-show="hoveredSessionId === session.session_id || menuSessionId === session.session_id"
            class="session-more-btn"
            @click.stop="toggleSessionMenu(session.session_id)"
            title="更多操作"
          >
            <van-icon name="ellipsis" size="16" />
          </div>
          <!-- 弹出菜单 -->
          <div v-if="menuSessionId === session.session_id" class="session-menu" @click.stop>
            <div class="menu-item" @click="pinSession(session.session_id)">
              {{ pinnedSessions.includes(session.session_id) ? '取消置顶' : '置顶' }}
            </div>
            <div class="menu-item danger" @click="deleteSessionFromList(session.session_id)">删除</div>
          </div>
        </div>
        <div v-if="filteredSessions.length === 0" class="sessions-empty">
          <template v-if="!sessionsLoaded">
            <van-loading size="24" color="#667eea" />
            <p>加载中...</p>
          </template>
          <template v-else>
            <van-icon name="info-o" size="32" color="#ddd" />
            <p>{{ searchKeyword ? '没有匹配的对话' : '暂无历史对话' }}</p>
            <button v-if="!searchKeyword" class="retry-btn" @click="reloadSessions">重新加载</button>
          </template>
        </div>
      </div>
    </aside>

    <!-- 侧边栏遮罩（移动端） -->
    <div v-if="sidebarOpen" class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <!-- 右侧主对话区 -->
    <div class="chat-main">
      <!-- 顶部栏 -->
      <div class="chat-topbar">
        <div class="topbar-left">
          <div class="sidebar-toggle" @click="sidebarOpen = !sidebarOpen" title="切换侧边栏">
            <van-icon name="bars" size="18" color="#666" />
          </div>
          <van-popover
            v-model:show="showModelMenu"
            :actions="modelActions"
            placement="bottom-start"
            @select="onModelSelect"
            trigger="click"
          >
            <template #reference>
              <div class="model-btn">
                <van-icon name="aim" size="14" color="#667eea" />
                <span class="model-label">{{ agentStore.modelLabel }}</span>
                <van-icon name="arrow-down" size="12" color="#999" />
              </div>
            </template>
          </van-popover>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="message-list" ref="messageListRef">
        <!-- 欢迎屏幕 -->
        <div v-if="!agentStore.hasMessages && !agentStore.loading && !agentStore.streaming" class="welcome-screen">
          <div class="welcome-icon">
            <van-icon name="chat-o" size="48" color="#667eea" />
          </div>
          <h2 class="welcome-title">智能生活助手</h2>
          <p class="welcome-desc">您好！我是您的生活助手，可以帮您推荐美食、景点，规划出行方案。</p>
          <div class="quick-actions">
            <div
              v-for="action in quickActions"
              :key="action.text"
              class="quick-action-item"
              @click="sendMessage(action.text)"
            >
              <van-icon :name="action.icon" color="#667eea" size="20" />
              <span>{{ action.text }}</span>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div
          v-for="(message, index) in agentStore.messages"
          :key="message.id"
          :class="['message-item', message.role]"
          @mouseenter="hoveredMsgId = message.id"
          @mouseleave="hoveredMsgId = null"
          @click="hoveredMsgId = message.id"
        >
          <div class="message-avatar">
            <van-icon :name="message.role === 'user' ? 'user-o' : 'chat-o'" size="20" />
          </div>
          <div class="message-content">
            <div class="message-bubble">
              <!-- 编辑模式 -->
              <div v-if="editingMsgId === message.id" class="message-edit-bar">
                <div class="edit-input-wrap">
                  <input
                    v-model="editContent"
                    class="edit-input"
                    placeholder="修改提问..."
                    @keydown.enter="submitEdit(message)"
                    @keydown.escape="cancelEdit"
                    ref="editInputRef"
                  />
                  <div class="edit-buttons">
                    <div class="edit-btn cancel" @click.stop="cancelEdit" title="取消编辑">
                      <van-icon name="cross" size="16" />
                    </div>
                    <div class="edit-btn send" @click.stop="submitEdit(message)" title="重新发送">
                      <van-icon name="arrow-up" size="16" />
                    </div>
                  </div>
                </div>
              </div>
              <!-- 正常显示（用户消息直接显示，AI消息支持版本切换） -->
              <div v-else-if="message.role === 'user'" class="message-text markdown-body" v-html="renderMarkdown(message.content)"></div>
              <!-- AI 回复内容（支持多版本切换） -->
              <template v-else-if="message.role === 'assistant'">
                <div class="message-text markdown-body" v-html="renderMarkdown(getAssistantDisplayText(message))"></div>
              </template>
              <!-- 推荐结果卡片 -->
              <div v-if="message.role === 'assistant' && agentStore.currentResults?.pois?.length && message === agentStore.lastMessage" class="recommendations">
                <div
                  v-for="rec in agentStore.currentResults.pois.slice(0, 3)"
                  :key="rec.id"
                  class="recommendation-card"
                  @click="goToDetail(rec)"
                >
                  <div class="card-image">
                    <van-icon name="location-o" size="24" color="#667eea" />
                  </div>
                  <div class="card-info">
                    <h4 class="card-title">{{ rec.name }}</h4>
                    <p class="card-meta">{{ rec.rating }}分 · {{ rec.distance }}m</p>
                  </div>
                  <van-icon name="arrow" color="#999" />
                </div>
              </div>
            </div>
            <!-- 悬浮操作按钮（固定占位30px，visibility切换避免位移） -->
            <div :class="['message-actions', message.role, { visible: hoveredMsgId === message.id && editingMsgId !== message.id }]">
              <div class="action-btn" @click.stop="copyMessage(getAssistantDisplayText(message))" title="复制">
                <van-icon name="description-o" size="14" />
              </div>
              <div v-if="message.role === 'user' && isLatestUserMessage(message)" class="action-btn" @click.stop="startEdit(message)" title="编辑">
                <van-icon name="edit" size="14" />
              </div>
              <div v-if="message.role === 'assistant' && !message._regenerating && isLatestAssistantMessage(message)" class="action-btn" @click.stop="regenerateAssistantReply(message)" title="重新生成">
                <van-icon name="replay" size="14" />
              </div>
              <!-- 版本翻页（助理消息有多版本时显示，放在重新生成和删除之间） -->
              <div v-if="message.role === 'assistant' && hasMultipleVersions(message)" class="action-btn version-pager-btn" title="上一个版本" @click.stop="prevVersion(message)" :class="{ disabled: versionIsFirst(message) }">
                <van-icon name="arrow-left" size="14" />
              </div>
              <div v-if="message.role === 'assistant' && hasMultipleVersions(message)" class="action-btn version-indicator-btn" title="版本切换">
                <template v-if="message._regenerating">生成中...</template>
                <template v-else>{{ getVersionIndex(message) + 1 }}/{{ getVersionTotal(message) }}</template>
              </div>
              <div v-if="message.role === 'assistant' && hasMultipleVersions(message)" class="action-btn version-pager-btn" title="下一个版本" @click.stop="nextVersion(message)" :class="{ disabled: versionIsLast(message) }">
                <van-icon name="arrow" size="14" />
              </div>
              <div class="action-btn danger" @click.stop="openDeleteDialog(message, index)" title="删除">
                <van-icon name="delete-o" size="14" />
              </div>
            </div>
          </div>
        </div>

        <!-- 删除确认弹窗 -->
        <van-dialog
          v-model:show="showDeleteDialog"
          title="确定要删除历史记录吗？"
          :show-confirm-button="true"
          :show-cancel-button="true"
          confirm-button-text="删除"
          confirm-button-color="#ff4757"
          cancel-button-text="取消"
          @confirm="confirmDelete"
          @cancel="showDeleteDialog = false"
        >
          <div class="delete-dialog-body">
            <p class="delete-dialog-tip">以下对话记录将从历史列表中删除，不可恢复：</p>
            <div class="delete-rounds-list">
              <div
                v-for="(round, idx) in deleteRounds"
                :key="idx"
                class="delete-round-item"
              >
                <van-checkbox v-model="round.selected" :name="idx">
                  <div class="round-preview">
                    <span class="round-user-msg">{{ truncateText(round.userMsg) }}</span>
                    <span v-if="round.aiMsg" class="round-ai-msg">{{ truncateText(round.aiMsg) }}</span>
                  </div>
                </van-checkbox>
              </div>
            </div>
            <p class="delete-dialog-count">已选择 {{ selectedDeleteCount }} 组对话</p>
          </div>
        </van-dialog>

        <!-- 工具调用进度（ReAct 中间轮次：只显示进度，不显示 LLM 思考过程） -->
        <div v-if="agentStore.streaming && agentStore.toolStatus && !agentStore.currentReply" class="message-item assistant">
          <div class="message-avatar">
            <van-icon name="chat-o" size="20" />
          </div>
          <div class="message-content">
            <div class="message-bubble tool-status-bubble">
              <van-loading size="14" style="margin-right: 8px; vertical-align: middle;" />
              <span class="tool-status-text">{{ agentStore.toolStatus }}</span>
            </div>
          </div>
        </div>

        <!-- 流式回复（仅在最终轮次显示） -->
        <div v-if="agentStore.streaming && agentStore.currentReply" class="message-item assistant">
          <div class="message-avatar">
            <van-icon name="chat-o" size="20" />
          </div>
          <div class="message-content">
            <div class="message-bubble">
              <div class="message-text markdown-body" v-html="renderMarkdown(agentStore.currentReply) + '<span class=\'cursor-blink\'>|</span>'"></div>
            </div>
          </div>
        </div>

        <!-- 加载状态 -->
        <div v-if="agentStore.isThinking" class="message-item assistant">
          <div class="message-avatar">
            <van-icon name="chat-o" size="20" />
          </div>
          <div class="message-content">
            <div class="message-bubble typing-bubble">
              <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 建议区域 -->
      <div class="suggestions" v-if="agentStore.currentSuggestions.length">
        <div
          v-for="suggestion in agentStore.currentSuggestions"
          :key="suggestion"
          class="suggestion-item"
          @click="sendMessage(suggestion)"
        >
          {{ suggestion }}
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <van-field
          v-model="inputMessage"
          placeholder="输入您的问题..."
          @keyup.enter="handleSend"
          :disabled="agentStore.loading || agentStore.streaming"
          clearable
          class="input-field"
        >
          <template #button>
            <van-button
              size="small"
              type="primary"
              @click="handleSend"
              :loading="agentStore.loading || agentStore.streaming"
              :disabled="!inputMessage.trim()"
              class="send-btn"
            >
              发送
            </van-button>
          </template>
        </van-field>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'
import { showConfirmDialog, showToast } from 'vant'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'

const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'

// 配置 marked 使用 highlight.js
marked.setOptions({
  highlight: function (code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
  breaks: true,
  gfm: true
})

// 将 Markdown 渲染为 HTML
function renderMarkdown(content) {
  if (!content) return ''
  return marked.parse(content)
}

const router = useRouter()
const route = useRoute()
const agentStore = useAgentStore()
const authStore = useAuthStore()

const quickActions = [
  { icon: 'food-o', text: '推荐美食' },
  { icon: 'guide-o', text: '推荐景点' },
  { icon: 'location-o', text: '附近有什么' },
  { icon: 'weather-o', text: '今天天气' },
]

const inputMessage = ref('')
const messageListRef = ref(null)
const showModelMenu = ref(false)
const sidebarOpen = ref(false)
const searchKeyword = ref('')
const hoveredSessionId = ref(null)
const menuSessionId = ref(null)

// 置顶会话列表（localStorage持久化）
const pinnedSessions = ref(JSON.parse(localStorage.getItem('pinned_sessions') || '[]'))

// 消息悬浮操作
const hoveredMsgId = ref(null)
const editingMsgId = ref(null)
const editContent = ref('')
const editInputRef = ref(null)

/** 判断是否为最新一轮的用户消息（仅此可编辑） */
function isLatestUserMessage(message) {
  if (message.role !== 'user') return false
  const msgs = agentStore.messages
  // 最后一条用户消息（排除可能的末尾AI回复）
  let lastUserIdx = -1
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') {
      lastUserIdx = i
      break
    }
  }
  if (lastUserIdx === -1) return false
  
  // 只允许编辑最后一条用户消息
  return msgs[lastUserIdx]?.id === message.id
}

/** 判断是否为最新一轮 AI 回复（仅此可重新生成） */
function isLatestAssistantMessage(message) {
  if (message.role !== 'assistant') return false
  const msgs = agentStore.messages
  // 最后一条 assistant 消息
  let lastAiIdx = -1
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'assistant') {
      lastAiIdx = i
      break
    }
  }
  if (lastAiIdx === -1) return false
  
  // 只允许重新生成最后一条 AI 回复
  return msgs[lastAiIdx]?.id === message.id
}

// 删除确认弹窗
const showDeleteDialog = ref(false)
const deleteRounds = ref([])       // [{ selected: true, userMsg: "...", aiMsg: "...", userIdx: 0, aiIdx: 1 }]
const deleteTargetMsg = ref(null)   // 触发删除的那条消息
const deleteTargetIndex = ref(-1)

const filteredSessions = computed(() => {
  let list = [...agentStore.sessions]
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    list = list.filter(s => (s.first_question || s.last_message || '').toLowerCase().includes(kw))
  }
  // 排序：置顶优先（按置顶顺序），非置顶按时间倒序
  list.sort((a, b) => {
    const aPinned = pinnedSessions.value.includes(a.session_id)
    const bPinned = pinnedSessions.value.includes(b.session_id)
    if (aPinned && !bPinned) return -1
    if (!aPinned && bPinned) return 1
    // 都在置顶列表，按置顶顺序排
    if (aPinned && bPinned) {
      return pinnedSessions.value.indexOf(a.session_id) - pinnedSessions.value.indexOf(b.session_id)
    }
    // 都不置顶，按时间倒序
    const aTime = a.last_message_time || ''
    const bTime = b.last_message_time || ''
    return bTime.localeCompare(aTime)
  })
  return list
})

function toggleSessionMenu(sessionId) {
  menuSessionId.value = menuSessionId.value === sessionId ? null : sessionId
}

function pinSession(sessionId) {
  const idx = pinnedSessions.value.indexOf(sessionId)
  if (idx > -1) {
    pinnedSessions.value.splice(idx, 1)
  } else {
    pinnedSessions.value.unshift(sessionId)
  }
  localStorage.setItem('pinned_sessions', JSON.stringify(pinnedSessions.value))
  menuSessionId.value = null
}

// ─── 消息操作 ───

/** 截断文本用于预览 */
function truncateText(text, maxLen = 40) {
  if (!text) return ''
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

/** 复制消息内容 */
async function copyMessage(message) {
  try {
    await navigator.clipboard.writeText(message.content)
    showToast('已复制')
  } catch {
    showToast('复制失败')
  }
}

/** 开始编辑消息 - 仅最新一轮用户消息可编辑 */
function startEdit(message) {
  if (!isLatestUserMessage(message)) return
  editingMsgId.value = message.id
  editContent.value = message.content
  // 自动聚焦输入框
  nextTick(() => {
    editInputRef.value?.focus()
  })
}

/** 取消编辑 */
function cancelEdit() {
  editingMsgId.value = null
  editContent.value = ''
}

/** 提交编辑：替换原提问并重新生成AI回复 */
async function submitEdit(message) {
  const newContent = editContent.value.trim()
  if (!newContent) return
  
  cancelEdit()
  
  // 找到该消息在列表中的位置
  const msgIndex = agentStore.messages.findIndex(m => m.id === message.id)
  if (msgIndex === -1) return
  
  // 替换原用户提问内容
  agentStore.messages[msgIndex].content = newContent
  agentStore.messages[msgIndex].timestamp = new Date().toISOString()
  
  // 如果后面紧跟着AI回复，替换为占位"生成中..."
  const aiMsgIdx = msgIndex + 1
  const hasAiMsg = aiMsgIdx < agentStore.messages.length && 
                   agentStore.messages[aiMsgIdx].role === 'assistant'
  if (hasAiMsg) {
    agentStore.messages[aiMsgIdx].content = '正在重新生成回复...'
    agentStore.messages[aiMsgIdx].timestamp = new Date().toISOString()
  }
  
  // 直接调后端流式接口（不经过 agentStore.sendMessageStream，避免重复添加用户消息）
  const userId = agentStore.getCurrentUserId ? agentStore.getCurrentUserId() : ''
  agentStore.loading = true
  agentStore.streaming = true
  agentStore.error = null
  agentStore.currentReply = ''
  
  const locationStore = (await import('@/stores/location')).useLocationStore()
  const payload = {
    message: newContent,
    user_id: userId,
    session_id: agentStore.sessionId,
    latitude: locationStore.currentLocation?.latitude ?? null,
    longitude: locationStore.currentLocation?.longitude ?? null,
    stream: true,
    model_config: { provider: agentStore.activeProvider, model: agentStore.activeModel }
  }
  
  try {
    const response = await fetch(`${baseURL}/agent/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let fullReply = ''
    
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
          if (line.startsWith('event: ')) eventName = line.slice(7).trim()
          else if (line.startsWith('data: ')) eventData = line.slice(6).trim()
        }
        
        if (eventData) {
          try {
            const data = JSON.parse(eventData)
            if (eventName === 'content' && data.text) {
              fullReply += data.text
              // 实时更新AI回复内容
              if (hasAiMsg) {
                agentStore.messages[aiMsgIdx].content = fullReply
              }
            } else if (eventName === 'done') {
              if (data.session_id) agentStore.sessionId = data.session_id
              // 最终更新
              if (hasAiMsg) {
                agentStore.messages[aiMsgIdx].content = fullReply
              }
            } else if (eventName === 'error') {
              throw new Error(data.error || '流式错误')
            }
          } catch { /* ignore parse errors */ }
        }
      }
    }
  } catch (err) {
    agentStore.error = err.message
    if (hasAiMsg) {
      agentStore.messages[aiMsgIdx].content = `重新生成失败: ${err.message}`
    }
  } finally {
    agentStore.loading = false
    agentStore.streaming = false
    agentStore.currentReply = ''
    nextTick(() => scrollToBottom())
    await reloadSessions()
  }
}

/** ─── AI 回复版本管理与翻页（后端持久化） ─── */

// 版本数据缓存：{ roundId: { versions: [...], currentIdx: number } }
const versionCache = ref({})

/** 获取 AI 回复当前显示的文字（支持版本切换） */
function getAssistantDisplayText(message) {
  if (message.role !== 'assistant') return message.content
  // 如果正在重新生成，显示"生成中..."
  if (message._regenerating) return '正在重新生成回复...'
  
  const roundId = message.round_id
  if (!roundId) return message.content
  
  const cache = versionCache.value[roundId]
  if (!cache || !cache.versions.length) return message.content
  
  const idx = cache.currentIdx
  if (idx >= 0 && idx < cache.versions.length) {
    return cache.versions[idx].content
  }
  return message.content
}

/** 获取当前版本索引（从0开始） */
function getVersionIndex(message) {
  const roundId = message.round_id
  if (!roundId) return 0
  
  const cache = versionCache.value[roundId]
  if (!cache) return 0
  
  return cache.currentIdx >= 0 ? cache.currentIdx : (cache.versions.length - 1)
}

/** 获取版本总数 */
function getVersionTotal(message) {
  const roundId = message.round_id
  if (!roundId) return 1
  
  const cache = versionCache.value[roundId]
  if (!cache) return 1
  
  return cache.versions.length || 1
}

/** 是否为第一个版本（禁用左箭头） */
function versionIsFirst(message) {
  return getVersionIndex(message) <= 0
}

/** 是否为最后一个版本（禁用右箭头） */
function versionIsLast(message) {
  const roundId = message.round_id
  if (!roundId) return true
  
  const cache = versionCache.value[roundId]
  if (!cache) return true
  
  return getVersionIndex(message) >= (cache.versions.length - 1)
}

/** 切换到上一个版本 */
function prevVersion(message) {
  if (message._regenerating) return
  
  const roundId = message.round_id
  if (!roundId) return
  
  const cache = versionCache.value[roundId]
  if (!cache || cache.versions.length <= 1) return
  
  if (cache.currentIdx > 0) {
    cache.currentIdx--
  }
}

/** 切换到下一个版本 */
function nextVersion(message) {
  if (message._regenerating) return
  
  const roundId = message.round_id
  if (!roundId) return
  
  const cache = versionCache.value[roundId]
  if (!cache || cache.versions.length <= 1) return
  
  if (cache.currentIdx < cache.versions.length - 1) {
    cache.currentIdx++
  }
}

/** 判断是否有多个版本（用于显示翻页栏） */
function hasMultipleVersions(message) {
  const roundId = message.round_id
  if (!roundId) return false
  
  const cache = versionCache.value[roundId]
  return cache && cache.versions.length > 1
}

/** 加载指定轮次的版本列表 */
async function loadVersions(roundId) {
  if (!roundId || versionCache.value[roundId]) return
  
  const versions = await agentStore.getVersions(roundId)
  if (versions.length > 0) {
    versionCache.value[roundId] = {
      versions: versions,
      currentIdx: versions.length - 1  // 默认显示最新版本
    }
  }
}

/** 重新生成AI回复（后端持久化版本管理） */
async function regenerateAssistantReply(message) {
  // 权限检查：仅最新 AI 回复可重新生成
  if (!isLatestAssistantMessage(message)) return
  
  const roundId = message.round_id
  if (!roundId) {
    showToast('该消息不支持重新生成')
    return
  }
  
  // 确保版本数据已加载
  await loadVersions(roundId)
  
  // 标记为"正在重新生成"
  message._regenerating = true
  
  agentStore.loading = true
  agentStore.streaming = true
  agentStore.error = null
  agentStore.currentReply = ''
  
  let newContent = ''
  
  await agentStore.regenerateMessage(roundId, {
    onContent: (text) => {
      newContent += text
      message.content = newContent
    },
    onDone: async (data) => {
      // 更新版本缓存
      const cache = versionCache.value[roundId]
      if (cache) {
        cache.versions.push({
          version: data.version || cache.versions.length + 1,
          content: newContent,
          is_latest: true
        })
        // 将旧版本标记为非最新
        if (cache.versions.length > 1) {
          cache.versions[cache.versions.length - 2].is_latest = false
        }
        cache.currentIdx = cache.versions.length - 1
      } else {
        // 首次加载
        versionCache.value[roundId] = {
          versions: [{
            version: data.version || 2,
            content: newContent,
            is_latest: true
          }],
          currentIdx: 0
        }
      }
      
      // 更新消息的 version
      message.version = data.version || (cache ? cache.versions.length : 2)
    },
    onError: (error) => {
      agentStore.error = error
      showToast(`重新生成失败: ${error}`)
    }
  })
  
  agentStore.loading = false
  agentStore.streaming = false
  agentStore.currentReply = ''
  message._regenerating = false
  nextTick(() => scrollToBottom())
  await reloadSessions()
}

/** 打开删除确认弹窗 */
function openDeleteDialog(message, index) {
  deleteTargetMsg.value = message
  deleteTargetIndex.value = index
  
  // 构建轮次列表（每对 user + assistant 为一轮）
  const rounds = []
  const msgs = agentStore.messages
  for (let i = 0; i < msgs.length; i += 2) {
    const userMsg = msgs[i]
    const aiMsg = (i + 1 < msgs.length && msgs[i + 1].role === 'assistant') ? msgs[i + 1] : null
    rounds.push({
      selected: false,
      userMsg: userMsg.content,
      aiMsg: aiMsg ? aiMsg.content : '',
      userIdx: i,
      aiIdx: aiMsg ? i + 1 : -1,
    })
  }
  
  // 默认勾选当前轮次
  const currentRoundIdx = Math.floor(index / 2)
  if (currentRoundIdx < rounds.length) {
    rounds[currentRoundIdx].selected = true
  }
  
  deleteRounds.value = rounds
  showDeleteDialog.value = true
}

/** 计算已选中的删除数量 */
const selectedDeleteCount = computed(() => {
  return deleteRounds.value.filter(r => r.selected).length
})

/** 确认删除 */
async function confirmDelete() {
  const selectedRoundIndices = []
  deleteRounds.value.forEach((round, idx) => {
    if (round.selected) selectedRoundIndices.push(idx)
  })
  
  if (selectedRoundIndices.length === 0) {
    showDeleteDialog.value = false
    return
  }
  
  // 收集所有要删除的消息ID
  const msgIdsToRemove = new Set()
  selectedRoundIndices.forEach(roundIdx => {
    const round = deleteRounds.value[roundIdx]
    if (round.userIdx >= 0) msgIdsToRemove.add(agentStore.messages[round.userIdx].id)
    if (round.aiIdx >= 0 && round.aiIdx < agentStore.messages.length) {
      msgIdsToRemove.add(agentStore.messages[round.aiIdx].id)
    }
  })
  
  // 从列表中移除
  agentStore.messages = agentStore.messages.filter(m => !msgIdsToRemove.has(m.id))
  
  // 如果全部删除，调用后端删除该 session
  if (agentStore.messages.length === 0 && agentStore.sessionId) {
    const userId = agentStore.getCurrentUserId ? agentStore.getCurrentUserId() : ''
    try {
      await fetch(`${baseURL}/agent/history/${agentStore.sessionId}?user_id=${userId}`, {
        method: 'DELETE'
      })
    } catch (err) {
      console.error('删除后端记录失败:', err)
    }
    agentStore.newSession()
  }
  
  // 刷新会话列表
  await reloadSessions()
  
  showDeleteDialog.value = false
  deleteRounds.value = []
  deleteTargetMsg.value = null
  deleteTargetIndex.value = -1
}

async function deleteSessionFromList(sessionId) {
  menuSessionId.value = null
  try {
    await showConfirmDialog({ title: '删除会话', message: '确定要删除这条历史记录吗？删除后无法恢复。' })
  } catch { return }
  
  // 调用服务端删除（MySQL + Redis 双清）
  if (agentStore.getCurrentUserId) {
    const userId = agentStore.getCurrentUserId()
    try {
      const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'
      const resp = await fetch(`${baseURL}/agent/history/${sessionId}?user_id=${userId}`, {
        method: 'DELETE'
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      console.log(`删除会话成功: ${data.deleted_count || 0} 条记录`)
    } catch (err) {
      console.error('删除会话失败:', err)
    }
  }
  
  // 从本地列表中移除
  const sessions = agentStore.sessions
  const idx = sessions.findIndex(s => s.session_id === sessionId)
  if (idx > -1) sessions.splice(idx, 1)
  
  // 如果删除的是当前会话，重置到新会话
  if (agentStore.sessionId === sessionId) {
    agentStore.newSession()
  }
  
  // 清除置顶记录
  const pinIdx = pinnedSessions.value.indexOf(sessionId)
  if (pinIdx > -1) {
    pinnedSessions.value.splice(pinIdx, 1)
    localStorage.setItem('pinned_sessions', JSON.stringify(pinnedSessions.value))
  }
}

// 模型选择器 actions
const modelActions = computed(() => {
  const actions = []
  for (const provider of agentStore.modelProviders) {
    for (const model of provider.models) {
      actions.push({
        text: model.label,
        provider: provider.key,
        model: model.key,
      })
    }
  }
  return actions
})

onMounted(async () => {
  await agentStore.fetchModels()
  
  // 加载历史对话和会话列表
  await loadUserData()
  
  // 点击空白处关闭菜单
  document.addEventListener('click', onDocumentClick)
  
  if (route.query.q) {
    inputMessage.value = route.query.q
    handleSend()
  }
})

function onDocumentClick() {
  menuSessionId.value = null
}

// 监听：当用户数据就绪且之前未加载时，补充加载
let sessionsLoaded = false
watch(() => authStore.user, async (user) => {
  if (user?.id && !sessionsLoaded) {
    await loadUserData()
  }
}, { immediate: false })

async function loadUserData() {
  // 如果已登录，加载对话历史与会话列表
  if (authStore.isAuthenticated && authStore.currentUser?.id) {
    await agentStore.loadHistory()
    await agentStore.loadSessions()
    sessionsLoaded = true
  }
}

async function reloadSessions() {
  if (authStore.isAuthenticated && authStore.currentUser?.id) {
    await agentStore.loadSessions()
    sessionsLoaded = true
  }
}

function onModelSelect(action) {
  if (action.provider && action.model) {
    agentStore.switchModel(action.provider, action.model)
  }
}

async function switchSession(sessionId) {
  sidebarOpen.value = false
  await agentStore.switchSession(sessionId)
  nextTick(() => scrollToBottom())
}

function formatSessionTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${date.getMonth() + 1}/${date.getDate()}`
}

// 监听消息变化自动滚动，并加载版本数据
watch(() => agentStore.messages.length, async () => {
  nextTick(() => scrollToBottom())
  // 为有 round_id 的 assistant 消息加载版本数据
  for (const msg of agentStore.messages) {
    if (msg.role === 'assistant' && msg.round_id && !versionCache.value[msg.round_id]) {
      await loadVersions(msg.round_id)
    }
  }
})

// 监听流式回复自动滚动
watch(() => agentStore.currentReply, () => {
  nextTick(() => scrollToBottom())
})

async function handleSend() {
  const message = inputMessage.value.trim()
  if (!message || agentStore.loading || agentStore.streaming) return
  inputMessage.value = ''
  await sendMessage(message)
}

async function sendMessage(message) {
  if (agentStore.loading || agentStore.streaming) return
  // 使用流式接口以获得实时回显效果
  agentStore.sendMessageStream(message)
  // 轮询等待流式完成，完成后自动刷新会话列表
  const poll = setInterval(async () => {
    if (!agentStore.streaming && !agentStore.loading) {
      clearInterval(poll)
      nextTick(() => scrollToBottom())
      // 自动刷新左侧历史对话列表
      await reloadSessions()
    }
  }, 100)
}

function scrollToBottom() {
  if (messageListRef.value) {
    messageListRef.value.scrollTo({ top: messageListRef.value.scrollHeight, behavior: 'smooth' })
  }
}

function formatTime(timestamp) {
  return formatDateTime(timestamp, 'HH:mm')
}

function goToDetail(recommendation) {
  const route = recommendation.type === 'merchant' ? '/food/' : '/attraction/'
  router.push(route + recommendation.id)
}

function createNewSession() {
  // 如果正在加载或流式响应中，不允许创建新会话
  if (agentStore.loading || agentStore.streaming) return
  
  // 如果当前没有消息，不需要创建新会话
  if (!agentStore.hasMessages) return
  
  // 开启新会话（仅重置本地状态，历史会话保留）
  agentStore.newSession()
  
  // 滚动到顶部
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = 0
    }
  })
}
</script>

<style scoped>
/* ─── 全局布局 ─── */
.chat-wrapper {
  display: flex;
  height: calc(100vh - 60px);
  background: #f5f5f5;
}
:global(html), :global(body) {
  overflow: hidden;
  height: 100%;
}

/* ─── 左侧边栏 ─── */
.chat-sidebar {
  width: 280px;
  min-width: 280px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
  z-index: 10;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}
.sidebar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.sidebar-action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #666;
  cursor: pointer;
  transition: background 0.2s;
}
.sidebar-action-btn:hover {
  background: #f0f0f0;
}
.sidebar-action-btn:active {
  background: #e0e0e0;
}
.mobile-close {
  display: none;
}

.sidebar-search {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 16px;
  padding: 8px 12px;
  background: #f5f5f5;
  border-radius: 8px;
}
.search-input {
  flex: 1;
  border: none;
  background: transparent;
  outline: none;
  font-size: 13px;
  color: #333;
}
.search-input::placeholder {
  color: #999;
}

.sidebar-sessions {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 8px;
}
.sessions-title {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 8px 6px;
}
.session-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 2px;
  position: relative;
}
.session-item:hover {
  background: #f5f5f5;
}
.session-item.active {
  background: #eef1ff;
}
.session-item.active .session-preview {
  color: #667eea;
  font-weight: 500;
}
.session-info {
  flex: 1;
  min-width: 0;
}
.session-preview {
  font-size: 13px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 2px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.pin-icon {
  color: #667eea;
  flex-shrink: 0;
}
.session-time {
  font-size: 11px;
  color: #999;
}

.session-more-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
  position: relative;
  z-index: 1;
}
.session-more-btn:hover {
  background: #e8e8e8;
  color: #333;
}

.session-menu {
  position: absolute;
  right: 12px;
  top: 100%;
  margin-top: 2px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.12);
  z-index: 100;
  min-width: 80px;
  overflow: hidden;
}
.menu-item {
  padding: 8px 16px;
  font-size: 13px;
  color: #333;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
}
.menu-item:hover {
  background: #f5f5f5;
}
.menu-item.danger {
  color: #ff4757;
}
.menu-item.danger:hover {
  background: #fff0f0;
}
.sessions-empty {
  padding: 40px 20px;
  text-align: center;
  color: #999;
  font-size: 13px;
}
.sessions-empty p {
  margin-top: 8px;
}
.retry-btn {
  margin-top: 12px;
  padding: 6px 16px;
  border: 1px solid #667eea;
  border-radius: 6px;
  background: #fff;
  color: #667eea;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.retry-btn:hover {
  background: #667eea;
  color: #fff;
}

/* 侧边栏遮罩（移动端） */
.sidebar-overlay {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4);
  z-index: 9;
}

/* ─── 右侧主对话区 ─── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #f5f5f5;
}

/* 顶部栏 */
.chat-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #f0f0f0;
  min-height: 48px;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.sidebar-toggle {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
}
.sidebar-toggle:hover {
  background: #f0f0f0;
}

.model-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: #f5f5f5;
  border-radius: 8px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  transition: background 0.2s;
  user-select: none;
}
.model-btn:active {
  background: #e8e8e8;
}
.model-label {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #333;
  font-weight: 500;
}

/* ─── 消息列表 ─── */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  -webkit-overflow-scrolling: touch;
}

/* 欢迎屏幕 */
.welcome-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}
.welcome-icon {
  width: 80px;
  height: 80px;
  border-radius: 20px;
  background: rgba(102, 126, 234, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.welcome-title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  margin: 0 0 8px;
}
.welcome-desc {
  font-size: 14px;
  color: #666;
  margin: 0 0 24px;
  line-height: 1.6;
}
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  max-width: 400px;
}
.quick-action-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: white;
  border-radius: 20px;
  font-size: 13px;
  color: #333;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s, box-shadow 0.2s;
}
.quick-action-item:active {
  transform: scale(0.95);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

/* ─── 消息项 ─── */
.message-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  animation: fadeInUp 0.3s ease;
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.message-item.user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #667eea;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}
.message-item.user .message-avatar {
  background: #4ecdc4;
}
.message-content {
  max-width: 75%;
  min-width: 60px;
}
.message-bubble {
  background: white;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.message-item.assistant .message-bubble {
  background: linear-gradient(135deg, #fff5f5 0%, #fff 100%);
  border: 1px solid #ffe0e0;
}
.message-item.user .message-bubble {
  background: #667eea;
  color: white;
}
.message-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

/* Markdown 样式 */
.markdown-body { font-size: 14px; line-height: 1.8; word-break: break-word; }
.markdown-body h1, .markdown-body h2, .markdown-body h3, .markdown-body h4 {
  font-weight: 600; margin: 12px 0 8px; color: #333;
}
.markdown-body h1 { font-size: 18px; }
.markdown-body h2 { font-size: 16px; }
.markdown-body h3 { font-size: 15px; }
.markdown-body p { margin: 6px 0; }
.markdown-body strong { color: #333; font-weight: 600; }
.markdown-body em { font-style: italic; color: #666; }
.markdown-body ul, .markdown-body ol { padding-left: 20px; margin: 8px 0; }
.markdown-body li { margin: 4px 0; }
.markdown-body code {
  background: #f5f5f5; padding: 2px 6px; border-radius: 4px;
  font-size: 13px; font-family: 'Courier New', Courier, monospace; color: #e74c3c;
}
.markdown-body pre {
  background: #282c34; border-radius: 8px; padding: 12px;
  margin: 10px 0; overflow-x: auto;
}
.markdown-body pre code { background: transparent; color: #abb2bf; padding: 0; font-size: 13px; }
.markdown-body blockquote {
  border-left: 3px solid #667eea; padding: 8px 12px;
  margin: 10px 0; background: #f9f9f9; color: #666;
}
.markdown-body hr { border: none; border-top: 1px solid #eee; margin: 12px 0; }
.markdown-body a { color: #667eea; text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body table { border-collapse: collapse; width: 100%; margin: 10px 0; }
.markdown-body th, .markdown-body td { border: 1px solid #eee; padding: 8px; text-align: left; }
.markdown-body th { background: #f5f5f5; font-weight: 600; }
.message-item.user .markdown-body strong { color: white; }
.message-item.user .markdown-body a { color: #b3d9ff; }
.hljs { background: #282c34 !important; border-radius: 8px; }

/* 悬浮操作按钮（固定占位30px，避免悬停时文本位移） */
.message-actions {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  height: 26px;               /* 固定占位高度 */
  align-items: center;
  visibility: hidden;          /* 默认隐藏但占据空间 */
  opacity: 0;
  transition: opacity 0.15s ease;
}
.message-actions.visible {
  visibility: visible;
  opacity: 1;
}
.message-actions.user {
  justify-content: flex-end;
}
.message-actions.assistant {
  justify-content: flex-start;
}
.action-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  color: #666;
  cursor: pointer;
  transition: all 0.15s;
}
.action-btn:hover {
  background: #e8e8e8;
  color: #333;
}
.action-btn.danger:hover {
  background: #ffeded;
  color: #ff4757;
}

/* ─── 操作栏版本翻页按钮 ─── */
.version-pager-btn {
  font-size: 13px;
}
.version-pager-btn.disabled {
  opacity: 0.3;
  cursor: not-allowed;
  pointer-events: none;
}
.version-indicator-btn {
  font-size: 12px;
  color: #667eea;
  min-width: 32px;
  text-align: center;
  font-weight: 500;
  cursor: default;
}

/* 编辑栏 */
.message-edit-bar {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.edit-input-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #fff;
  border: 1px solid #667eea;
  border-radius: 8px;
  padding: 4px 6px;
  transition: border-color 0.2s;
}
.edit-input-wrap:focus-within {
  border-color: #4a5fd9;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.15);
}
.edit-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  line-height: 1.5;
  padding: 4px 8px;
  min-width: 0;
  color: #333;
  font-family: inherit;
}
.edit-input::placeholder {
  color: #bbb;
}
.edit-buttons {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}
.edit-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}
.edit-btn.cancel {
  color: #999;
  background: #f5f5f5;
}
.edit-btn.cancel:hover {
  background: #eee;
  color: #666;
}
.edit-btn.send {
  color: #fff;
  background: #667eea;
}
.edit-btn.send:hover {
  background: #5a6fd6;
}
.edit-btn.send:active {
  background: #4a5fd9;
}

/* 删除弹窗 */
.delete-dialog-body {
  padding: 16px 24px;
  max-height: 50vh;
  overflow-y: auto;
}
.delete-dialog-tip {
  font-size: 13px;
  color: #999;
  margin: 0 0 12px;
  line-height: 1.5;
}
.delete-rounds-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.delete-round-item {
  padding: 8px 12px;
  background: #f9f9f9;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.delete-round-item:hover {
  background: #f0f0f0;
}
.delete-round-item :deep(.van-checkbox__label) {
  flex: 1;
  min-width: 0;
}
.round-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-left: 4px;
}
.round-user-msg {
  font-size: 13px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.round-ai-msg {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.delete-dialog-count {
  font-size: 12px;
  color: #ff4757;
  margin: 12px 0 0;
  text-align: right;
  font-weight: 500;
}

/* 打字指示器 */
.typing-bubble {
  display: flex; align-items: center; justify-content: center;
  min-width: 60px; min-height: 36px;
}
.typing-indicator { display: flex; gap: 4px; }
.typing-indicator span {
  width: 8px; height: 8px; border-radius: 50%;
  background: #667eea;
  animation: typing 1.4s infinite ease-in-out;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* 工具调用进度气泡 */
.tool-status-bubble {
  display: flex; align-items: center;
  padding: 10px 14px; background: #f0f4ff;
  border: 1px solid #d4dffe; border-radius: 14px; color: #667eea; font-size: 13px;
}
.tool-status-text { color: #5b6abf; }

/* 推荐卡片 */
.recommendations { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }
.recommendation-card {
  display: flex; align-items: center; gap: 10px;
  padding: 10px; background: #f9f9f9; border-radius: 8px; cursor: pointer;
}
.recommendation-card:active { background: #f0f0f0; }
.card-image {
  width: 44px; height: 44px; border-radius: 6px;
  overflow: hidden; flex-shrink: 0;
}
.card-image img { width: 100%; height: 100%; object-fit: cover; }
.card-info { flex: 1; min-width: 0; }
.card-title {
  font-size: 13px; font-weight: 600; color: #333;
  margin: 0 0 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.card-meta { font-size: 11px; color: #666; margin: 0; }

/* 建议区域 */
.suggestions {
  display: flex; gap: 8px; padding: 10px 16px;
  overflow-x: auto; background: white; border-top: 1px solid #f0f0f0;
  -webkit-overflow-scrolling: touch;
}
.suggestions::-webkit-scrollbar { display: none; }
.suggestion-item {
  padding: 6px 14px; background: #f0f0f0; border-radius: 16px;
  font-size: 13px; color: #333; white-space: nowrap;
  cursor: pointer; flex-shrink: 0;
}
.suggestion-item:active { background: #e0e0e0; }

/* 输入区域 */
.input-area {
  background: white;
  padding: 10px 16px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom, 0));
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.06);
}
.input-field { border-radius: 20px; overflow: hidden; }
.send-btn { border-radius: 16px; padding: 0 16px; }

/* 流式光标动画 */
.cursor-blink {
  animation: cursorBlink 1s infinite; color: #667eea; font-weight: bold;
}
@keyframes cursorBlink { 0%, 50% { opacity: 1; } 51%, 100% { opacity: 0; } }

/* ─── 响应式：移动端 ─── */
@media (max-width: 768px) {
  .chat-sidebar {
    position: fixed;
    left: -280px;
    top: 0;
    bottom: 0;
    transition: left 0.3s ease;
    z-index: 1000;
    box-shadow: 4px 0 20px rgba(0,0,0,0.15);
  }
  .chat-sidebar.open {
    left: 0;
  }
  .sidebar-overlay {
    display: block;
  }
  .mobile-close {
    display: flex !important;
  }
  .sidebar-toggle {
    display: flex !important;
  }
  .chat-topbar {
    padding: 8px 12px;
  }
  .message-list {
    padding: 12px;
  }
  .message-content {
    max-width: 85%;
  }
  .welcome-screen {
    padding: 40px 16px;
  }
  .quick-actions {
    max-width: 100%;
  }
  .quick-action-item {
    font-size: 12px;
    padding: 8px 12px;
  }
}
</style>
