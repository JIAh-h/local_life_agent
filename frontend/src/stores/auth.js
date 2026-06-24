import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  // 状态
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')
  const loading = ref(false)
  const error = ref(null)

  // 计算属性
  const isAuthenticated = computed(() => !!accessToken.value)
  const currentUser = computed(() => user.value)

  // 设置Token
  function setTokens(access, refresh, rememberMe = false) {
    accessToken.value = access
    refreshToken.value = refresh
    
    if (rememberMe) {
      // 记住我：使用localStorage持久化
      localStorage.setItem('access_token', access)
      localStorage.setItem('refresh_token', refresh)
      localStorage.setItem('remember_me', 'true')
    } else {
      // 不记住我：使用sessionStorage，关闭浏览器后清除
      sessionStorage.setItem('access_token', access)
      sessionStorage.setItem('refresh_token', refresh)
      localStorage.removeItem('remember_me')
      // 清除之前的localStorage
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }

  // 清除Token
  function clearTokens() {
    accessToken.value = ''
    refreshToken.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('remember_me')
    sessionStorage.removeItem('access_token')
    sessionStorage.removeItem('refresh_token')
  }

  // 初始化Token（从存储中恢复）
  function initializeTokens() {
    // 优先从localStorage恢复（记住我）
    let access = localStorage.getItem('access_token')
    let refresh = localStorage.getItem('refresh_token')
    
    if (!access || !refresh) {
      // 如果localStorage没有，从sessionStorage恢复
      access = sessionStorage.getItem('access_token')
      refresh = sessionStorage.getItem('refresh_token')
    }
    
    if (access && refresh) {
      accessToken.value = access
      refreshToken.value = refresh
    }
  }

  // 用户注册
  async function register(userData) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.register(userData)
      return response
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 用户登录
  async function login(loginData) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.login(loginData)
      setTokens(response.access_token, response.refresh_token, loginData.remember_me)
      // 获取用户信息
      await fetchCurrentUser()
      return response
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 微信登录
  async function loginByWechat(loginData) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.loginByWechat(loginData)
      setTokens(response.access_token, response.refresh_token, loginData.remember_me)
      // 获取用户信息
      await fetchCurrentUser()
      return response
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // QQ登录
  async function loginByQQ(loginData) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.loginByQQ(loginData)
      setTokens(response.access_token, response.refresh_token, loginData.remember_me)
      // 获取用户信息
      await fetchCurrentUser()
      return response
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 刷新Token
  async function refreshAccessToken() {
    if (!refreshToken.value) {
      throw new Error('No refresh token available')
    }
    try {
      const response = await authApi.refreshToken(refreshToken.value)
      setTokens(response.access_token, response.refresh_token)
      return response
    } catch (err) {
      // 刷新失败，清除Token并跳转到登录页
      clearTokens()
      user.value = null
      router.push('/login')
      throw err
    }
  }

  // 获取当前用户信息
  async function fetchCurrentUser() {
    if (!accessToken.value) return null
    try {
      const response = await authApi.getCurrentUser()
      user.value = response
      return response
    } catch (err) {
      // 如果获取用户信息失败，可能是Token过期
      if (err.message.includes('401') || err.message.includes('Unauthorized')) {
        try {
          await refreshAccessToken()
          // 重新获取用户信息
          const response = await authApi.getCurrentUser()
          user.value = response
          return response
        } catch (refreshError) {
          clearTokens()
          user.value = null
          throw refreshError
        }
      }
      throw err
    }
  }

  // 更新用户信息
  async function updateCurrentUser(userData) {
    loading.value = true
    error.value = null
    try {
      const response = await authApi.updateCurrentUser(userData)
      user.value = response
      return response
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 用户登出
  async function logout() {
    try {
      await authApi.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      clearTokens()
      user.value = null
      router.push('/login')
    }
  }

  // 登出所有设备
  async function logoutAll() {
    try {
      await authApi.logoutAll()
    } catch (err) {
      console.error('Logout all error:', err)
    } finally {
      clearTokens()
      user.value = null
      router.push('/login')
    }
  }

  // 验证Token
  async function verifyToken() {
    if (!accessToken.value) return false
    try {
      await authApi.verifyToken()
      return true
    } catch (err) {
      return false
    }
  }

  // 获取验证码
  async function getCaptcha() {
    try {
      return await authApi.getCaptcha()
    } catch (err) {
      console.error('Get captcha error:', err)
      throw err
    }
  }

  // 发送短信验证码
  async function sendSmsCode(phone, purpose = 'register') {
    try {
      return await authApi.sendSmsCode({ phone, purpose })
    } catch (err) {
      console.error('Send SMS code error:', err)
      throw err
    }
  }

  // 忘记密码
  async function forgotPassword(data) {
    loading.value = true
    error.value = null
    try {
      return await authApi.forgotPassword(data)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 重置密码
  async function resetPassword(data) {
    loading.value = true
    error.value = null
    try {
      return await authApi.resetPassword(data)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 修改密码
  async function changePassword(data) {
    loading.value = true
    error.value = null
    try {
      return await authApi.changePassword(data)
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  // 初始化：检查Token并获取用户信息
  async function initialize() {
    initializeTokens()
    if (accessToken.value) {
      try {
        await fetchCurrentUser()
      } catch (err) {
        console.error('Failed to initialize auth:', err)
        clearTokens()
      }
    }
  }

  return {
    // 状态
    user,
    accessToken,
    refreshToken,
    loading,
    error,
    // 计算属性
    isAuthenticated,
    currentUser,
    // 方法
    register,
    login,
    loginByWechat,
    loginByQQ,
    refreshAccessToken,
    fetchCurrentUser,
    updateCurrentUser,
    logout,
    logoutAll,
    verifyToken,
    getCaptcha,
    sendSmsCode,
    forgotPassword,
    resetPassword,
    changePassword,
    initialize,
    setTokens,
    clearTokens,
    initializeTokens
  }
})