<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1>小紫薯</h1>
        <p>登录您的账户</p>
      </div>
      
      <!-- 登录方式切换 -->
      <div class="login-tabs">
        <button 
          :class="['tab-button', { active: loginType === 'password' }]"
          @click="loginType = 'password'"
        >
          账号密码登录
        </button>
        <button 
          :class="['tab-button', { active: loginType === 'wechat' }]"
          @click="loginType = 'wechat'"
        >
          微信登录
        </button>
        <button 
          :class="['tab-button', { active: loginType === 'qq' }]"
          @click="loginType = 'qq'"
        >
          QQ登录
        </button>
      </div>
      
      <!-- 账号密码登录表单 -->
      <form v-if="loginType === 'password'" @submit.prevent="handlePasswordLogin" class="login-form">
        <div class="form-group">
          <label for="username">用户名/手机号/邮箱</label>
          <div class="username-input-wrapper">
            <input
              id="username"
              v-model="loginForm.username"
              type="text"
              placeholder="请输入用户名、手机号或邮箱"
              required
              :disabled="loading"
              autocomplete="off"
              @focus="showAccountPicker = true"
              @blur="hideAccountPicker"
              @input="showAccountPicker = true"
            />
            <!-- 已保存账号下拉列表 -->
            <div v-if="showAccountPicker && filteredAccounts.length > 0" class="account-picker" @mousedown.prevent>
              <div class="account-picker-header">已保存的账号</div>
              <div
                v-for="account in filteredAccounts"
                :key="account.username"
                class="account-picker-item"
                @mousedown.prevent="selectAccount(account)"
              >
                <div class="account-picker-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                </div>
                <div class="account-picker-info">
                  <div class="account-picker-name">{{ account.username }}</div>
                  <div class="account-picker-pwd">密码已保存</div>
                </div>
                <button
                  type="button"
                  class="account-picker-delete"
                  @mousedown.prevent.stop="deleteAccount(account.username)"
                  title="删除此账号记录"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
        
        <div class="form-group">
          <label for="password">密码</label>
          <div class="password-input">
            <input
              id="password"
              v-model="loginForm.password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              required
              :disabled="loading"
            />
            <button 
              type="button" 
              class="password-toggle"
              @click="showPassword = !showPassword"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            >
              <svg v-if="showPassword" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                <line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
              <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </button>
          </div>
        </div>
        
        <div class="form-group">
          <label for="captcha">验证码</label>
          <div class="captcha-input">
            <input
              id="captcha"
              ref="captchaInputRef"
              v-model="loginForm.captcha_code"
              type="text"
              placeholder="请输入验证码"
              required
              :disabled="loading"
              maxlength="4"
            />
            <div class="captcha-image" @click="refreshCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="验证码" @error="onCaptchaImageError" />
              <span v-else class="captcha-placeholder">
                <span v-if="captchaLoading" class="captcha-loading">加载中...</span>
                <span v-else>点击获取</span>
              </span>
            </div>
          </div>
        </div>
        
        <div class="form-options">
          <label class="remember-me">
            <input
              v-model="loginForm.remember_me"
              type="checkbox"
              :disabled="loading"
            />
            <span>记住我</span>
          </label>
          <router-link to="/forgot-password" class="forgot-password">
            忘记密码？
          </router-link>
        </div>
        
        <div v-if="error" class="error-message">
          {{ error }}
        </div>
        
        <button type="submit" class="login-button" :disabled="loading || !isFormValid">
          <span v-if="loading" class="loading-spinner"></span>
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
      
      <!-- 微信登录表单 -->
      <form v-if="loginType === 'wechat'" @submit.prevent="handleWechatLogin" class="login-form">
        <div class="third-party-login">
          <div class="qr-code-placeholder">
            <div class="qr-code">
              <p>微信扫码登录</p>
              <p class="hint">请使用微信扫描二维码</p>
            </div>
          </div>
          <p class="login-hint">微信登录功能开发中...</p>
        </div>
      </form>
      
      <!-- QQ登录表单 -->
      <form v-if="loginType === 'qq'" @submit.prevent="handleQQLogin" class="login-form">
        <div class="third-party-login">
          <div class="qr-code-placeholder">
            <div class="qr-code">
              <p>QQ扫码登录</p>
              <p class="hint">请使用QQ扫描二维码</p>
            </div>
          </div>
          <p class="login-hint">QQ登录功能开发中...</p>
        </div>
      </form>
      
      <div class="login-footer">
        <p>还没有账户？ <router-link to="/register">立即注册</router-link></p>
      </div>
    </div>

    <!-- 账号信息弹窗 -->
    <transition name="modal-fade">
      <div v-if="showAccountModal" class="account-modal-overlay" @click.self="closeAccountModal">
        <div class="account-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="account-modal-header">
            <h3 id="modal-title">账号信息确认</h3>
            <button type="button" class="modal-close" @click="closeAccountModal" aria-label="关闭">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="account-modal-body">
            <div class="account-info-row">
              <label class="account-info-label">账号</label>
              <div class="account-info-value">{{ selectedAccount?.username }}</div>
            </div>
            <div class="account-info-row">
              <label class="account-info-label">密码</label>
              <div class="account-info-value password-display">
                <span>{{ modalPasswordVisible ? selectedAccount?.password : '••••••••' }}</span>
                <button
                  type="button"
                  class="modal-password-toggle"
                  @click="modalPasswordVisible = !modalPasswordVisible"
                  :aria-label="modalPasswordVisible ? '隐藏密码' : '显示密码'"
                >
                  <svg v-if="modalPasswordVisible" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                  </svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <div class="account-modal-footer">
            <button type="button" class="modal-btn modal-btn-cancel" @click="closeAccountModal">取消</button>
            <button type="button" class="modal-btn modal-btn-confirm" @click="autoFillAccount">一键填充</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// ========== 常量 ==========
const REMEMBERED_USERNAME_KEY = 'remembered_username'
const REMEMBER_ME_CHECKED_KEY = 'remember_me_checked'
// 已保存账号列表的存储 key（含账号+密码，用于一键填充）
// 注意：密码以 Base64 简单编码存储，非真正加密。仅用于本地开发便利，生产环境应避免明文存储密码。
const SAVED_ACCOUNTS_KEY = 'saved_accounts'

// ========== 登录类型 ==========
const loginType = ref('password')

// ========== 登录表单 ==========
const loginForm = reactive({
  username: localStorage.getItem(REMEMBERED_USERNAME_KEY) || '',
  password: '',
  captcha_key: '',
  captcha_code: '',
  remember_me: localStorage.getItem(REMEMBER_ME_CHECKED_KEY) === 'true',
  device_info: navigator.userAgent
})

// ========== 验证码相关 ==========
const captchaImage = ref('')
const captchaKey = ref('')
const captchaLoading = ref(false)

// ========== 状态 ==========
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)

// ========== 账号选择 & 弹窗相关 ==========
const captchaInputRef = ref(null)
const showAccountPicker = ref(false)        // 下拉列表显示
const showAccountModal = ref(false)         // 弹窗显示
const selectedAccount = ref(null)           // 选中的账号
const modalPasswordVisible = ref(false)     // 弹窗中密码是否可见
const savedAccounts = ref([])               // 已保存的账号列表

// ========== 账号列表管理 ==========

// 从 localStorage 加载已保存账号
function loadSavedAccounts() {
  try {
    const raw = localStorage.getItem(SAVED_ACCOUNTS_KEY)
    if (!raw) return
    const accounts = JSON.parse(raw)
    // 解码密码（Base64 -> 明文）
    savedAccounts.value = accounts.map(acc => ({
      username: acc.username,
      password: atob(acc.password)
    }))
  } catch (e) {
    console.error('加载已保存账号失败:', e)
    savedAccounts.value = []
  }
}

// 保存账号列表到 localStorage
function saveAccounts() {
  const encoded = savedAccounts.value.map(acc => ({
    username: acc.username,
    password: btoa(acc.password)  // Base64 编码
  }))
  localStorage.setItem(SAVED_ACCOUNTS_KEY, JSON.stringify(encoded))
}

// 添加或更新账号
function upsertAccount(username, password) {
  if (!username || !password) return
  const idx = savedAccounts.value.findIndex(a => a.username === username)
  if (idx >= 0) {
    savedAccounts.value[idx].password = password
  } else {
    savedAccounts.value.push({ username, password })
    // 最多保留 10 个账号
    if (savedAccounts.value.length > 10) {
      savedAccounts.value = savedAccounts.value.slice(-10)
    }
  }
  saveAccounts()
}

// 删除账号
function deleteAccount(username) {
  savedAccounts.value = savedAccounts.value.filter(a => a.username !== username)
  saveAccounts()
}

// 过滤后的账号列表（根据输入框内容模糊匹配）
const filteredAccounts = computed(() => {
  const keyword = loginForm.username.trim().toLowerCase()
  if (!keyword) return savedAccounts.value
  return savedAccounts.value.filter(a =>
    a.username.toLowerCase().includes(keyword)
  )
})

// 隐藏下拉列表（延迟，避免点击事件丢失）
function hideAccountPicker() {
  setTimeout(() => {
    showAccountPicker.value = false
  }, 200)
}

// 选中账号 -> 弹出弹窗
function selectAccount(account) {
  selectedAccount.value = account
  modalPasswordVisible.value = false
  showAccountPicker.value = false
  loginForm.username = account.username
  showAccountModal.value = true
}

// 关闭弹窗
function closeAccountModal() {
  showAccountModal.value = false
  selectedAccount.value = null
  modalPasswordVisible.value = false
}

// 一键填充：填入账号密码，关闭弹窗，焦点跳转到验证码
async function autoFillAccount() {
  if (!selectedAccount.value) return
  loginForm.username = selectedAccount.value.username
  loginForm.password = selectedAccount.value.password
  showAccountModal.value = false
  modalPasswordVisible.value = false
  // 等待 DOM 更新后聚焦验证码输入框
  await nextTick()
  captchaInputRef.value?.focus()
}

// ========== 表单验证 ==========
const isFormValid = computed(() => {
  return loginForm.username && loginForm.password && loginForm.captcha_code
})

// ========== 验证码 ==========
async function refreshCaptcha() {
  if (captchaLoading.value) return
  captchaLoading.value = true
  try {
    const response = await fetch('/api/v1/auth/captcha')
    const data = await response.json()
    captchaImage.value = data.captcha_image
    captchaKey.value = data.captcha_key
    loginForm.captcha_key = data.captcha_key
  } catch (err) {
    console.error('获取验证码失败:', err)
    error.value = '验证码加载失败，请重试'
  } finally {
    captchaLoading.value = false
  }
}

function onCaptchaImageError() {
  captchaImage.value = ''
  captchaKey.value = ''
  refreshCaptcha()
}

// ========== 登录 ==========
async function handlePasswordLogin() {
  if (!isFormValid.value) {
    error.value = '请填写完整的登录信息'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    await authStore.login({
      login_type: 'password',
      username: loginForm.username,
      password: loginForm.password,
      captcha_key: loginForm.captcha_key,
      captcha_code: loginForm.captcha_code,
      remember_me: loginForm.remember_me,
      device_info: loginForm.device_info
    })
    
    // 记住我：保存用户名和复选框状态
    if (loginForm.remember_me) {
      localStorage.setItem(REMEMBERED_USERNAME_KEY, loginForm.username)
      localStorage.setItem(REMEMBER_ME_CHECKED_KEY, 'true')
      // 保存账号密码到账号列表（供下次一键填充）
      upsertAccount(loginForm.username, loginForm.password)
    } else {
      localStorage.removeItem(REMEMBERED_USERNAME_KEY)
      localStorage.removeItem(REMEMBER_ME_CHECKED_KEY)
    }
    
    // 登录成功，跳转到之前的页面或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (err) {
    error.value = err.message || '登录失败，请重试'
    // 刷新验证码
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

// 微信登录
async function handleWechatLogin() {
  error.value = '微信登录功能暂未开放'
}

// QQ登录
async function handleQQLogin() {
  error.value = 'QQ登录功能暂未开放'
}

// 组件挂载时获取验证码 & 加载已保存账号
onMounted(() => {
  refreshCaptcha()
  loadSavedAccounts()
})
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 100%;
  max-width: 450px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

@media (max-width: 480px) {
  .login-container {
    padding: 16px;
    align-items: flex-start;
    padding-top: 10vh;
  }
  .login-card {
    padding: 28px 20px;
    border-radius: 12px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  }
  .login-header h1 {
    font-size: 22px;
  }
  .captcha-image {
    width: 100px;
    height: 40px;
  }
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  color: #333;
  margin: 0 0 10px 0;
  font-size: 28px;
}

.login-header p {
  color: #666;
  margin: 0;
  font-size: 16px;
}

.login-tabs {
  display: flex;
  margin-bottom: 24px;
  border-bottom: 2px solid #eee;
}

.tab-button {
  flex: 1;
  padding: 12px;
  background: none;
  border: none;
  font-size: 14px;
  font-weight: 500;
  color: #666;
  cursor: pointer;
  transition: all 0.3s;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}

.tab-button:hover {
  color: #667eea;
}

.tab-button.active {
  color: #667eea;
  border-bottom-color: #667eea;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  color: #333;
  font-weight: 500;
  font-size: 14px;
}

.form-group input {
  padding: 12px 16px;
  border: 2px solid #e1e5e9;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 0.3s;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
}

.form-group input:disabled {
  background-color: #f5f5f5;
  cursor: not-allowed;
}

.password-input {
  position: relative;
}

.password-input input {
  width: 100%;
  padding-right: 60px;
}

.password-toggle {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: #667eea;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.password-toggle:hover {
  background: rgba(102, 126, 234, 0.1);
}

.captcha-input {
  display: flex;
  gap: 10px;
}

.captcha-input input {
  flex: 1;
}

.captcha-image {
  width: 120px;
  height: 44px;
  border: 2px solid #e1e5e9;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: #f5f5f5;
  flex-shrink: 0;
}

.captcha-image:hover {
  border-color: #667eea;
}

.captcha-image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.captcha-placeholder {
  color: #667eea;
  font-size: 12px;
  user-select: none;
}

.captcha-loading {
  color: #999;
  font-size: 12px;
}

.captcha-placeholder {
  color: #667eea;
  font-size: 12px;
}

.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.remember-me {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #666;
  font-size: 14px;
  cursor: pointer;
}

.remember-me input {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.forgot-password {
  color: #667eea;
  text-decoration: none;
  font-size: 14px;
}

.forgot-password:hover {
  text-decoration: underline;
}

.error-message {
  background: #fee;
  color: #c00;
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
}

.login-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 14px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
}

.login-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid white;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.third-party-login {
  text-align: center;
  padding: 20px 0;
}

.qr-code-placeholder {
  margin-bottom: 20px;
}

.qr-code {
  width: 200px;
  height: 200px;
  border: 2px dashed #e1e5e9;
  border-radius: 12px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f9f9f9;
}

.qr-code p {
  margin: 5px 0;
  color: #333;
  font-weight: 500;
}

.qr-code .hint {
  font-size: 12px;
  color: #666;
}

.login-hint {
  color: #666;
  font-size: 14px;
}

.login-footer {
  text-align: center;
  margin-top: 24px;
  color: #666;
}

.login-footer a {
  color: #667eea;
  text-decoration: none;
  font-weight: 500;
}

.login-footer a:hover {
  text-decoration: underline;
}

/* ========== 用户名输入框 + 下拉选择 ========== */
.username-input-wrapper {
  position: relative;
}

.username-input-wrapper input {
  width: 100%;
}

/* 已保存账号下拉列表 */
.account-picker {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #e1e5e9;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  z-index: 100;
  max-height: 240px;
  overflow-y: auto;
}

.account-picker-header {
  padding: 8px 14px;
  font-size: 12px;
  color: #999;
  border-bottom: 1px solid #f0f0f0;
  user-select: none;
}

.account-picker-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.account-picker-item:hover {
  background-color: #f5f7ff;
}

.account-picker-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f0f0f5;
  color: #667eea;
  flex-shrink: 0;
}

.account-picker-info {
  flex: 1;
  min-width: 0;
}

.account-picker-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.account-picker-pwd {
  font-size: 12px;
  color: #999;
}

.account-picker-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: none;
  color: #ccc;
  cursor: pointer;
  border-radius: 4px;
  flex-shrink: 0;
  transition: all 0.15s;
}

.account-picker-delete:hover {
  color: #e74c3c;
  background: rgba(231, 76, 60, 0.1);
}

/* ========== 账号信息弹窗 ========== */
.account-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.account-modal {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 380px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  overflow: hidden;
}

.account-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f0f0;
}

.account-modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
  font-weight: 600;
}

.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: none;
  color: #999;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.15s;
}

.modal-close:hover {
  color: #333;
  background: #f5f5f5;
}

.account-modal-body {
  padding: 24px;
}

.account-info-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 16px;
}

.account-info-row:last-child {
  margin-bottom: 0;
}

.account-info-label {
  font-size: 13px;
  color: #999;
  font-weight: 500;
}

.account-info-value {
  font-size: 15px;
  color: #333;
  padding: 10px 14px;
  background: #f8f9fb;
  border-radius: 8px;
  border: 1px solid #eef0f4;
}

.password-display {
  display: flex;
  align-items: center;
  justify-content: space-between;
  letter-spacing: 2px;
  font-family: 'Courier New', monospace;
}

.modal-password-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: none;
  color: #667eea;
  cursor: pointer;
  border-radius: 4px;
  flex-shrink: 0;
  transition: background-color 0.15s;
}

.modal-password-toggle:hover {
  background: rgba(102, 126, 234, 0.1);
}

.account-modal-footer {
  display: flex;
  gap: 12px;
  padding: 16px 24px 24px;
}

.modal-btn {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.modal-btn-cancel {
  background: #f5f5f5;
  color: #666;
}

.modal-btn-cancel:hover {
  background: #ebebeb;
}

.modal-btn-confirm {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.modal-btn-confirm:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

/* 弹窗淡入淡出动画 */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-active .account-modal,
.modal-fade-leave-active .account-modal {
  transition: transform 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .account-modal,
.modal-fade-leave-to .account-modal {
  transform: scale(0.92) translateY(-10px);
}
</style>