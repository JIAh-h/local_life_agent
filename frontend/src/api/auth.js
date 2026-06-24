import api from './index'

/**
 * 认证API模块
 */
export const authApi = {
  /**
   * 用户注册
   * @param {Object} userData - 用户数据
   * @param {string} userData.username - 用户名
   * @param {string} userData.password - 密码
   * @param {string} userData.confirm_password - 确认密码
   * @param {string} userData.phone - 手机号
   * @param {string} [userData.email] - 邮箱
   * @param {string} [userData.nickname] - 用户昵称
   * @param {string} userData.captcha_key - 验证码key
   * @param {string} userData.captcha_code - 验证码
   * @returns {Promise<Object>} 用户信息
   */
  register(userData) {
    return api.post('/auth/register', userData)
  },

  /**
   * 用户登录
   * @param {Object} loginData - 登录数据
   * @param {string} loginData.login_type - 登录类型：password/wechat/qq
   * @param {string} [loginData.username] - 用户名/手机号/邮箱
   * @param {string} [loginData.password] - 密码
   * @param {string} loginData.captcha_key - 验证码key
   * @param {string} loginData.captcha_code - 验证码
   * @param {string} [loginData.openid] - 微信openid
   * @param {string} [loginData.qq_openid] - QQ openid
   * @param {string} [loginData.device_info] - 设备信息
   * @param {boolean} [loginData.remember_me] - 记住我
   * @returns {Promise<Object>} Token信息
   */
  login(loginData) {
    return api.post('/auth/login', loginData)
  },

  /**
   * 微信登录
   * @param {Object} loginData - 登录数据
   * @param {string} loginData.code - 微信登录code
   * @param {string} [loginData.device_info] - 设备信息
   * @param {boolean} [loginData.remember_me] - 记住我
   * @returns {Promise<Object>} Token信息
   */
  loginByWechat(loginData) {
    return api.post('/auth/login/wechat', loginData)
  },

  /**
   * QQ登录
   * @param {Object} loginData - 登录数据
   * @param {string} loginData.code - QQ登录code
   * @param {string} [loginData.device_info] - 设备信息
   * @param {boolean} [loginData.remember_me] - 记住我
   * @returns {Promise<Object>} Token信息
   */
  loginByQQ(loginData) {
    return api.post('/auth/login/qq', loginData)
  },

  /**
   * 忘记密码
   * @param {Object} data - 数据
   * @param {string} data.phone - 手机号
   * @param {string} data.captcha_key - 验证码key
   * @param {string} data.captcha_code - 验证码
   * @returns {Promise<Object>} 发送结果
   */
  forgotPassword(data) {
    return api.post('/auth/forgot-password', data)
  },

  /**
   * 重置密码
   * @param {Object} data - 数据
   * @param {string} data.phone - 手机号
   * @param {string} data.new_password - 新密码
   * @param {string} data.confirm_password - 确认密码
   * @param {string} data.captcha_key - 验证码key
   * @param {string} data.captcha_code - 验证码
   * @param {string} data.reset_token - 重置令牌
   * @returns {Promise<Object>} 重置结果
   */
  resetPassword(data) {
    return api.post('/auth/reset-password', data)
  },

  /**
   * 修改密码
   * @param {Object} data - 数据
   * @param {string} data.old_password - 原密码
   * @param {string} data.new_password - 新密码
   * @param {string} data.confirm_password - 确认密码
   * @returns {Promise<Object>} 修改结果
   */
  changePassword(data) {
    return api.post('/auth/change-password', data)
  },

  /**
   * 刷新Token
   * @param {string} refreshToken - 刷新令牌
   * @returns {Promise<Object>} 新的Token信息
   */
  refreshToken(refreshToken) {
    return api.post('/auth/refresh', { refresh_token: refreshToken })
  },

  /**
   * 用户登出
   * @returns {Promise<Object>} 登出结果
   */
  logout() {
    return api.post('/auth/logout')
  },

  /**
   * 登出所有设备
   * @returns {Promise<Object>} 登出结果
   */
  logoutAll() {
    return api.post('/auth/logout-all')
  },

  /**
   * 获取当前用户信息
   * @returns {Promise<Object>} 用户信息
   */
  getCurrentUser() {
    return api.get('/auth/me')
  },

  /**
   * 更新当前用户信息
   * @param {Object} userData - 用户数据
   * @param {string} [userData.nickname] - 用户昵称
   * @param {string} [userData.avatar_url] - 头像URL
   * @param {string} [userData.email] - 邮箱
   * @returns {Promise<Object>} 用户信息
   */
  updateCurrentUser(userData) {
    return api.put('/auth/me', userData)
  },

  /**
   * 验证Token有效性
   * @returns {Promise<Object>} 验证结果
   */
  verifyToken() {
    return api.get('/auth/verify-token')
  },

  /**
   * 获取验证码
   * @returns {Promise<Object>} 验证码信息
   */
  getCaptcha() {
    return api.get('/auth/captcha')
  },

  /**
   * 验证验证码
   * @param {string} captchaKey - 验证码key
   * @param {string} captchaCode - 验证码
   * @returns {Promise<Object>} 验证结果
   */
  verifyCaptcha(captchaKey, captchaCode) {
    return api.post('/auth/verify-captcha', null, {
      params: { captcha_key: captchaKey, captcha_code: captchaCode }
    })
  },

  /**
   * 发送短信验证码
   * @param {Object} data - 数据
   * @param {string} data.phone - 手机号
   * @param {string} data.purpose - 用途：register/login/reset_password
   * @returns {Promise<Object>} 发送结果
   */
  sendSmsCode(data) {
    return api.post('/auth/send-sms-code', data)
  },

  /**
   * 验证短信验证码
   * @param {Object} data - 数据
   * @param {string} data.phone - 手机号
   * @param {string} data.code - 验证码
   * @param {string} data.purpose - 用途：register/login/reset_password
   * @returns {Promise<Object>} 验证结果
   */
  verifySmsCode(data) {
    return api.post('/auth/verify-sms-code', data)
  },

  /**
   * 获取用户状态
   * @returns {Promise<Object>} 用户状态
   */
  getUserStatus() {
    return api.get('/auth/status')
  },

  /**
   * 检查密码强度
   * @param {string} password - 密码
   * @returns {Promise<Object>} 密码强度信息
   */
  checkPasswordStrength(password) {
    return api.get('/auth/password-strength', { params: { password } })
  }
}

export default authApi