<template>
  <div class="forgot-password-container">
    <div class="forgot-password-card">
      <div class="forgot-password-header">
        <h1>找回密码</h1>
        <p>通过手机号重置您的密码</p>
      </div>
      
      <!-- 步骤1：输入手机号 -->
      <div v-if="currentStep === 1" class="step-content">
        <form @submit.prevent="handleSendSmsCode" class="forgot-password-form">
          <div class="form-group">
            <label for="phone">手机号</label>
            <div class="phone-input">
              <input
                id="phone"
                v-model="form.phone"
                type="tel"
                placeholder="请输入注册时使用的手机号"
                required
                :disabled="loading"
                maxlength="11"
                @blur="validatePhone"
              />
              <button 
                type="button" 
                class="sms-button"
                :disabled="smsCooldown > 0 || loading"
                @click="handleSendSmsCode"
              >
                {{ smsCooldown > 0 ? `${smsCooldown}秒后重试` : '获取验证码' }}
              </button>
            </div>
            <span v-if="errors.phone" class="field-error">{{ errors.phone }}</span>
          </div>
          
          <div class="form-group">
            <label for="captcha">图形验证码</label>
            <div class="captcha-input">
              <input
                id="captcha"
                v-model="form.captcha_code"
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
          
          <div v-if="error" class="error-message">
            {{ error }}
          </div>
          
          <button type="submit" class="next-button" :disabled="!isStep1Valid || loading">
            下一步
          </button>
        </form>
      </div>
      
      <!-- 步骤2：输入验证码和新密码 -->
      <div v-if="currentStep === 2" class="step-content">
        <form @submit.prevent="handleResetPassword" class="forgot-password-form">
          <div class="form-group">
            <label for="smsCode">短信验证码</label>
            <input
              id="smsCode"
              v-model="form.sms_code"
              type="text"
              placeholder="请输入短信验证码"
              required
              :disabled="loading"
              maxlength="6"
            />
          </div>
          
          <div class="form-group">
            <label for="newPassword">新密码</label>
            <div class="password-input">
              <input
                id="newPassword"
                v-model="form.new_password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="至少6位字符"
                required
                :disabled="loading"
                @input="checkPasswordStrength"
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
            <div v-if="passwordStrength" class="password-strength">
              <div class="strength-bar">
                <div 
                  class="strength-fill" 
                  :class="passwordStrength.level"
                  :style="{ width: passwordStrength.score + '%' }"
                ></div>
              </div>
              <span class="strength-text">{{ passwordStrengthText }}</span>
            </div>
            <span v-if="errors.new_password" class="field-error">{{ errors.new_password }}</span>
          </div>
          
          <div class="form-group">
            <label for="confirmPassword">确认新密码</label>
            <div class="password-input">
              <input
                id="confirmPassword"
                v-model="form.confirm_password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="请再次输入新密码"
                required
                :disabled="loading"
                @blur="validateConfirmPassword"
              />
            </div>
            <span v-if="errors.confirm_password" class="field-error">{{ errors.confirm_password }}</span>
          </div>
          
          <div v-if="error" class="error-message">
            {{ error }}
          </div>
          
          <div class="button-group">
            <button type="button" class="back-button" @click="currentStep = 1" :disabled="loading">
              返回
            </button>
            <button type="submit" class="reset-button" :disabled="!isStep2Valid || loading">
              <span v-if="loading" class="loading-spinner"></span>
              {{ loading ? '重置中...' : '重置密码' }}
            </button>
          </div>
        </form>
      </div>
      
      <!-- 步骤3：重置成功 -->
      <div v-if="currentStep === 3" class="step-content success-content">
        <div class="success-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <h2>密码重置成功</h2>
        <p>您的密码已成功重置，请使用新密码登录。</p>
        <button class="login-button" @click="goToLogin">
          前往登录
        </button>
      </div>
      
      <div class="forgot-password-footer">
        <p>想起密码了？ <router-link to="/login">返回登录</router-link></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 当前步骤
const currentStep = ref(1)

// 表单数据
const form = reactive({
  phone: '',
  captcha_key: '',
  captcha_code: '',
  sms_code: '',
  new_password: '',
  confirm_password: '',
  reset_token: ''
})

// 验证码相关
const captchaImage = ref('')
const captchaKey = ref('')
const captchaLoading = ref(false)

// 状态
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)
const smsCooldown = ref(0)

// 密码强度
const passwordStrength = ref(null)

// 表单验证错误
const errors = reactive({
  phone: '',
  new_password: '',
  confirm_password: ''
})

// 密码强度文本
const passwordStrengthText = computed(() => {
  if (!passwordStrength.value) return ''
  const levelMap = {
    weak: '弱',
    medium: '中',
    strong: '强',
    very_strong: '非常强'
  }
  return levelMap[passwordStrength.value.level] || ''
})

// 步骤1验证
const isStep1Valid = computed(() => {
  return form.phone && form.captcha_code && !errors.phone
})

// 步骤2验证
const isStep2Valid = computed(() => {
  return (
    form.sms_code &&
    form.new_password &&
    form.confirm_password &&
    !errors.new_password &&
    !errors.confirm_password
  )
})

// 验证手机号
function validatePhone() {
  const phone = form.phone
  if (!phone) {
    errors.phone = '请输入手机号'
  } else if (!/^1[3-9]\d{9}$/.test(phone)) {
    errors.phone = '请输入有效的手机号'
  } else {
    errors.phone = ''
  }
}

// 验证密码强度
function checkPasswordStrength() {
  const password = form.new_password
  if (!password) {
    passwordStrength.value = null
    errors.new_password = ''
    return
  }
  
  let score = 0
  const suggestions = []
  
  if (password.length >= 6) score += 20
  else suggestions.push('密码长度至少6位')
  
  if (/[a-z]/.test(password)) score += 20
  else suggestions.push('建议包含小写字母')
  
  if (/[A-Z]/.test(password)) score += 20
  else suggestions.push('建议包含大写字母')
  
  if (/\d/.test(password)) score += 20
  else suggestions.push('建议包含数字')
  
  if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score += 20
  else suggestions.push('建议包含特殊字符')
  
  let level = 'weak'
  if (score >= 80) level = 'very_strong'
  else if (score >= 60) level = 'strong'
  else if (score >= 40) level = 'medium'
  
  passwordStrength.value = { score, level, suggestions }
  
  if (password.length < 6) {
    errors.new_password = '密码长度至少6位'
  } else {
    errors.new_password = ''
  }
  
  // 如果确认密码已填写，验证确认密码
  if (form.confirm_password) {
    validateConfirmPassword()
  }
}

// 验证确认密码
function validateConfirmPassword() {
  if (!form.confirm_password) {
    errors.confirm_password = '请再次输入密码'
  } else if (form.new_password !== form.confirm_password) {
    errors.confirm_password = '两次输入的密码不一致'
  } else {
    errors.confirm_password = ''
  }
}

// 获取验证码
async function refreshCaptcha() {
  if (captchaLoading.value) return
  captchaLoading.value = true
  try {
    const response = await authStore.getCaptcha()
    captchaImage.value = response.captcha_image
    captchaKey.value = response.captcha_key
    form.captcha_key = response.captcha_key
  } catch (err) {
    console.error('获取验证码失败:', err)
  } finally {
    captchaLoading.value = false
  }
}

// 验证码图片加载失败时自动重试
function onCaptchaImageError() {
  captchaImage.value = ''
  captchaKey.value = ''
  refreshCaptcha()
}

// 发送短信验证码
async function handleSendSmsCode() {
  validatePhone()
  if (errors.phone) return
  
  if (!form.captcha_code) {
    error.value = '请输入图形验证码'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    await authStore.forgotPassword({
      phone: form.phone,
      captcha_key: form.captcha_key,
      captcha_code: form.captcha_code
    })
    
    // 开始倒计时
    smsCooldown.value = 60
    const timer = setInterval(() => {
      smsCooldown.value--
      if (smsCooldown.value <= 0) {
        clearInterval(timer)
      }
    }, 1000)
    
    // 进入下一步
    currentStep.value = 2
  } catch (err) {
    error.value = err.message || '发送验证码失败'
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}

// 重置密码
async function handleResetPassword() {
  checkPasswordStrength()
  validateConfirmPassword()
  
  if (!isStep2Valid.value) {
    error.value = '请填写完整的信息'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    await authStore.resetPassword({
      phone: form.phone,
      new_password: form.new_password,
      confirm_password: form.confirm_password,
      captcha_key: form.captcha_key,
      captcha_code: form.captcha_code,
      reset_token: form.reset_token
    })
    
    // 重置成功
    currentStep.value = 3
  } catch (err) {
    error.value = err.message || '重置密码失败'
  } finally {
    loading.value = false
  }
}

// 前往登录
function goToLogin() {
  router.push('/login')
}

// 组件挂载时获取验证码
onMounted(() => {
  refreshCaptcha()
})
</script>

<style scoped>
.forgot-password-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.forgot-password-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 100%;
  max-width: 450px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

@media (max-width: 480px) {
  .forgot-password-container {
    padding: 16px;
    align-items: flex-start;
    padding-top: 10vh;
  }
  .forgot-password-card {
    padding: 28px 20px;
    border-radius: 12px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  }
  .forgot-password-header h1 {
    font-size: 22px;
  }
  .captcha-image {
    width: 100px;
    height: 40px;
  }
  .button-group {
    flex-direction: column;
    gap: 8px;
  }
}

.forgot-password-header {
  text-align: center;
  margin-bottom: 30px;
}

.forgot-password-header h1 {
  color: #333;
  margin: 0 0 10px 0;
  font-size: 28px;
}

.forgot-password-header p {
  color: #666;
  margin: 0;
  font-size: 16px;
}

.step-content {
  margin-bottom: 20px;
}

.forgot-password-form {
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

.phone-input {
  display: flex;
  gap: 10px;
}

.phone-input input {
  flex: 1;
}

.sms-button {
  padding: 12px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: background-color 0.3s;
}

.sms-button:hover:not(:disabled) {
  background: #5a6fd6;
}

.sms-button:disabled {
  background: #ccc;
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

.password-strength {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 5px;
}

.strength-bar {
  flex: 1;
  height: 6px;
  background: #e1e5e9;
  border-radius: 3px;
  overflow: hidden;
}

.strength-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s, background-color 0.3s;
}

.strength-fill.weak {
  background-color: #ff4757;
}

.strength-fill.medium {
  background-color: #ffa502;
}

.strength-fill.strong {
  background-color: #2ed573;
}

.strength-fill.very_strong {
  background-color: #1e90ff;
}

.strength-text {
  font-size: 12px;
  color: #666;
  min-width: 40px;
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

.field-error {
  color: #ff4757;
  font-size: 12px;
  margin-top: 4px;
}

.error-message {
  background: #fee;
  color: #c00;
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
}

.button-group {
  display: flex;
  gap: 10px;
}

.back-button {
  flex: 1;
  padding: 14px;
  background: #f5f5f5;
  color: #333;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.3s;
}

.back-button:hover:not(:disabled) {
  background: #e1e5e9;
}

.back-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.next-button,
.reset-button {
  flex: 2;
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

.next-button:hover:not(:disabled),
.reset-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
}

.next-button:disabled,
.reset-button:disabled {
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

.success-content {
  text-align: center;
  padding: 40px 0;
}

.success-icon {
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  color: #2ed573;
}

.success-icon svg {
  width: 100%;
  height: 100%;
}

.success-content h2 {
  color: #333;
  margin: 0 0 10px 0;
  font-size: 24px;
}

.success-content p {
  color: #666;
  margin: 0 0 30px 0;
  font-size: 16px;
}

.login-button {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 14px 40px;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.login-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
}

.forgot-password-footer {
  text-align: center;
  margin-top: 24px;
  color: #666;
}

.forgot-password-footer a {
  color: #667eea;
  text-decoration: none;
  font-weight: 500;
}

.forgot-password-footer a:hover {
  text-decoration: underline;
}
</style>