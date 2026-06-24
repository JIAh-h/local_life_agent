<template>
  <div class="register-container">
    <div class="register-card">
      <div class="register-header">
        <h1>小紫薯</h1>
        <p>创建新账户</p>
      </div>
      
      <form @submit.prevent="handleRegister" class="register-form">
        <!-- 必填字段 -->
        <div class="form-section">
          
          <div class="form-group">
            <label for="username">用户名 *</label>
            <input
              id="username"
              v-model="registerForm.username"
              type="text"
              placeholder="3-32位，字母、数字、下划线"
              required
              :disabled="loading"
              @blur="validateUsername"
            />
            <span v-if="errors.username" class="field-error">{{ errors.username }}</span>
          </div>
          
          <div class="form-group">
            <label for="password">密码 *</label>
            <div class="password-input">
              <input
                id="password"
                v-model="registerForm.password"
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
            <span v-if="errors.password" class="field-error">{{ errors.password }}</span>
          </div>
          
          <div class="form-group">
            <label for="confirmPassword">确认密码 *</label>
            <div class="password-input">
              <input
                id="confirmPassword"
                v-model="registerForm.confirm_password"
                :type="showConfirmPassword ? 'text' : 'password'"
                placeholder="请再次输入密码"
                required
                :disabled="loading"
                @blur="validateConfirmPassword"
              />
              <button 
                type="button" 
                class="password-toggle"
                @click="showConfirmPassword = !showConfirmPassword"
                :aria-label="showConfirmPassword ? '隐藏密码' : '显示密码'"
              >
                <svg v-if="showConfirmPassword" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
            <span v-if="errors.confirm_password" class="field-error">{{ errors.confirm_password }}</span>
          </div>
          
          <div class="form-group">
            <label for="phone">手机号 *</label>
            <div class="phone-input">
              <input
                id="phone"
                v-model="registerForm.phone"
                type="tel"
                placeholder="请输入手机号"
                required
                :disabled="loading"
                @blur="validatePhone"
                maxlength="11"
              />
              <button 
                type="button" 
                class="sms-button"
                :disabled="smsCooldown > 0 || loading"
                @click="sendSmsCode"
              >
                {{ smsCooldown > 0 ? `${smsCooldown}秒后重试` : '获取验证码' }}
              </button>
            </div>
            <span v-if="errors.phone" class="field-error">{{ errors.phone }}</span>
          </div>
          
          <div class="form-group">
            <label for="smsCode">短信验证码 *</label>
            <input
              id="smsCode"
              v-model="registerForm.sms_code"
              type="text"
              placeholder="请输入短信验证码"
              required
              :disabled="loading"
              maxlength="6"
            />
          </div>
        </div>
        
        <!-- 用户协议 -->
        <div class="form-group agreement">
          <label class="agreement-label">
            <input
              v-model="agreeToTerms"
              type="checkbox"
              :disabled="loading"
            />
            <span>我已阅读并同意 <a href="#" @click.prevent>《用户协议》</a> 和 <a href="#" @click.prevent>《隐私政策》</a></span>
          </label>
        </div>
        
        <div v-if="error" class="error-message">
          {{ error }}
        </div>
        
        <div v-if="success" class="success-message">
          {{ success }}
        </div>
        
        <button type="submit" class="register-button" :disabled="loading || !isFormValid">
          <span v-if="loading" class="loading-spinner"></span>
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>
      
      <div class="register-footer">
        <p>已有账户？ <router-link to="/login">立即登录</router-link></p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// 注册表单
const registerForm = reactive({
  username: '',
  password: '',
  confirm_password: '',
  phone: '',
  sms_code: '',
  nickname: '',
  email: ''
})

// 状态
const loading = ref(false)
const error = ref('')
const success = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const agreeToTerms = ref(false)
const smsCooldown = ref(0)

// 密码强度
const passwordStrength = ref(null)

// 表单验证错误
const errors = reactive({
  username: '',
  password: '',
  confirm_password: '',
  phone: '',
  email: ''
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

// 表单验证
const isFormValid = computed(() => {
  return (
    registerForm.username &&
    registerForm.password &&
    registerForm.confirm_password &&
    registerForm.phone &&
    registerForm.sms_code &&
    agreeToTerms.value &&
    !Object.values(errors).some(error => error)
  )
})

// 验证用户名
function validateUsername() {
  const username = registerForm.username
  if (!username) {
    errors.username = '请输入用户名'
  } else if (!/^[a-zA-Z0-9_]{3,32}$/.test(username)) {
    errors.username = '用户名必须是3-32位，只能包含字母、数字、下划线'
  } else {
    errors.username = ''
  }
}

// 验证密码强度
function checkPasswordStrength() {
  const password = registerForm.password
  if (!password) {
    passwordStrength.value = null
    errors.password = ''
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
    errors.password = '密码长度至少6位'
  } else {
    errors.password = ''
  }
  
  // 如果确认密码已填写，验证确认密码
  if (registerForm.confirm_password) {
    validateConfirmPassword()
  }
}

// 验证确认密码
function validateConfirmPassword() {
  if (!registerForm.confirm_password) {
    errors.confirm_password = '请再次输入密码'
  } else if (registerForm.password !== registerForm.confirm_password) {
    errors.confirm_password = '两次输入的密码不一致'
  } else {
    errors.confirm_password = ''
  }
}

// 验证手机号
function validatePhone() {
  const phone = registerForm.phone
  if (!phone) {
    errors.phone = '请输入手机号'
  } else if (!/^1[3-9]\d{9}$/.test(phone)) {
    errors.phone = '请输入有效的手机号'
  } else {
    errors.phone = ''
  }
}

// 验证邮箱
function validateEmail() {
  const email = registerForm.email
  if (email && !/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email)) {
    errors.email = '请输入有效的邮箱地址'
  } else {
    errors.email = ''
  }
}

// 发送短信验证码
async function sendSmsCode() {
  validatePhone()
  if (errors.phone) return
  
  try {
    await authStore.sendSmsCode(registerForm.phone, 'register')
    
    // 开始倒计时
    smsCooldown.value = 60
    const timer = setInterval(() => {
      smsCooldown.value--
      if (smsCooldown.value <= 0) {
        clearInterval(timer)
      }
    }, 1000)
    
    success.value = '验证码已发送到您的手机'
    setTimeout(() => {
      success.value = ''
    }, 3000)
  } catch (err) {
    error.value = err.message || '发送验证码失败'
  }
}

// 注册
async function handleRegister() {
  // 验证所有字段
  validateUsername()
  checkPasswordStrength()
  validateConfirmPassword()
  validatePhone()
  validateEmail()
  
  if (!isFormValid.value) {
    error.value = '请填写完整的注册信息'
    return
  }
  
  loading.value = true
  error.value = ''
  success.value = ''
  
  try {
    const userData = {
      username: registerForm.username,
      password: registerForm.password,
      confirm_password: registerForm.confirm_password,
      phone: registerForm.phone
    }
    
    if (registerForm.nickname) {
      userData.nickname = registerForm.nickname
    }
    if (registerForm.email) {
      userData.email = registerForm.email
    }
    
    await authStore.register(userData)
    
    success.value = '注册成功！正在跳转到登录页面...'
    
    // 2秒后跳转到登录页
    setTimeout(() => {
      router.push('/login')
    }, 2000)
  } catch (err) {
    error.value = err.message || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}


</script>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.register-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 100%;
  max-width: 500px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

@media (max-width: 480px) {
  .register-container {
    padding: 16px;
    align-items: flex-start;
    padding-top: 6vh;
  }
  .register-card {
    padding: 28px 20px;
    border-radius: 12px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  }
  .register-header h1 {
    font-size: 22px;
  }
  .form-section {
    padding: 16px;
  }
  .phone-input {
    flex-direction: column;
    gap: 8px;
  }
  .sms-button {
    width: 100%;
  }
}

.register-header {
  text-align: center;
  margin-bottom: 30px;
}

.register-header h1 {
  color: #333;
  margin: 0 0 10px 0;
  font-size: 28px;
}

.register-header p {
  color: #666;
  margin: 0;
  font-size: 16px;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.form-section {
  border: 1px solid #e1e5e9;
  border-radius: 12px;
  padding: 20px;
  background: #f9f9f9;
}

.section-title {
  margin: 0 0 16px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
  padding-bottom: 8px;
  border-bottom: 2px solid #667eea;
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

.field-error {
  color: #ff4757;
  font-size: 12px;
  margin-top: 4px;
}

.agreement {
  margin-top: 10px;
}

.agreement-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: #666;
  font-size: 14px;
  cursor: pointer;
}

.agreement-label input {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  cursor: pointer;
}

.agreement-label a {
  color: #667eea;
  text-decoration: none;
}

.agreement-label a:hover {
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

.success-message {
  background: #efe;
  color: #060;
  padding: 12px;
  border-radius: 8px;
  font-size: 14px;
  text-align: center;
}

.register-button {
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

.register-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
}

.register-button:disabled {
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

.register-footer {
  text-align: center;
  margin-top: 24px;
  color: #666;
}

.register-footer a {
  color: #667eea;
  text-decoration: none;
  font-weight: 500;
}

.register-footer a:hover {
  text-decoration: underline;
}
</style>