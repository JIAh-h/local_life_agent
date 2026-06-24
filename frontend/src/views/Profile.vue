<template>
  <div class="profile-container">
    <PageHeader title="个人中心" :showBack="true" />

    <LoadingState v-if="loading" text="加载用户信息..." />

    <div v-else-if="user" class="profile-content">
      <!-- ===== 用户头部（仅展示） ===== -->
      <div class="user-header">
        <div class="user-avatar-wrapper" v-if="user">
          <div class="user-avatar-inner" @click="triggerAvatarUpload" role="button" tabindex="0" @keydown.enter="triggerAvatarUpload" title="点击更换头像">
            <img
              class="user-avatar"
              :src="user.avatar_url || 'https://via.placeholder.com/100'"
              :alt="user.nickname || '用户头像'"
            />
            <div class="avatar-overlay">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                <circle cx="12" cy="13" r="4"/>
              </svg>
            </div>
          </div>
          <input
            ref="avatarFileInputRef"
            type="file"
            accept="image/*"
            class="avatar-file-input"
            @change="handleAvatarChange"
          />
        </div>
        <div class="user-header-name">
          <span class="user-nickname">{{ user.nickname || '未设置昵称' }}</span>
          <span class="user-id">ID: {{ user.id }}</span>
        </div>
      </div>

      <!-- ===== 个人信息卡片（含行内编辑） ===== -->
      <div class="info-card">
        <h3 class="card-title">个人信息</h3>

        <!-- 只读：用户名 -->
        <div class="info-item info-item-readonly">
          <span class="label"><van-icon name="user-o" /> 用户名</span>
          <span class="value">{{ user.username || '未设置' }}</span>
        </div>

        <!-- 编辑：昵称 -->
        <div class="info-item" :class="editingField === 'nickname' ? 'is-editing' : ''">
          <span class="label"><van-icon name="smile-o" /> 昵称</span>
          <template v-if="editingField === 'nickname'">
            <div class="edit-inline">
              <input
                v-model="editForm.nickname"
                type="text"
                maxlength="32"
                class="edit-input"
                placeholder="请输入昵称"
                ref="nicknameInputRef"
                @keydown.escape="cancelEdit"
                @keydown.enter="saveEdit('nickname')"
              />
              <button class="edit-btn save" @click="saveEdit('nickname')" :disabled="savingEdit">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
              <button class="edit-btn cancel" @click="cancelEdit" :disabled="savingEdit">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </template>
          <template v-else>
            <span class="value">{{ user.nickname || '未设置' }}</span>
            <button class="edit-trigger" @click="startEdit('nickname', user.nickname)" aria-label="编辑昵称">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          </template>
        </div>

        <!-- 编辑：邮箱 -->
        <div class="info-item" :class="editingField === 'email' ? 'is-editing' : ''">
          <span class="label"><van-icon name="envelop-o" /> 邮箱</span>
          <template v-if="editingField === 'email'">
            <div class="edit-inline">
              <input
                v-model="editForm.email"
                type="email"
                maxlength="64"
                class="edit-input"
                placeholder="请输入邮箱"
                ref="emailInputRef"
                @keydown.escape="cancelEdit"
                @keydown.enter="saveEdit('email')"
              />
              <button class="edit-btn save" @click="saveEdit('email')" :disabled="savingEdit">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
              <button class="edit-btn cancel" @click="cancelEdit" :disabled="savingEdit">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </template>
          <template v-else>
            <span class="value">{{ user.email || '未设置' }}</span>
            <button class="edit-trigger" @click="startEdit('email', user.email)" aria-label="编辑邮箱">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          </template>
        </div>

        <!-- 编辑：手机号 -->
        <div class="info-item" :class="editingField === 'phone' ? 'is-editing' : ''">
          <span class="label"><van-icon name="phone-o" /> 手机号</span>
          <template v-if="editingField === 'phone'">
            <div class="edit-inline edit-inline-column">
              <input
                v-model="editForm.phone"
                type="tel"
                maxlength="11"
                class="edit-input"
                placeholder="请输入11位手机号"
                ref="phoneInputRef"
                @keydown.escape="cancelEdit"
                @keydown.enter="saveEdit('phone')"
                @input="validatePhoneInput"
              />
              <div class="edit-inline-actions">
                <button class="edit-btn save" @click="saveEdit('phone')" :disabled="savingEdit || !phoneValid">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
                </button>
                <button class="edit-btn cancel" @click="cancelEdit" :disabled="savingEdit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            </div>
            <div v-if="phoneError" class="edit-field-error">{{ phoneError }}</div>
          </template>
          <template v-else>
            <span class="value">{{ user.phone || '未绑定' }}</span>
            <button class="edit-trigger" @click="startEdit('phone', user.phone)" aria-label="编辑手机号">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          </template>
        </div>

        <!-- 只读：注册时间 -->
        <div class="info-item info-item-readonly">
          <span class="label"><van-icon name="clock-o" /> 注册时间</span>
          <span class="value">{{ formatDate(user.created_at) }}</span>
        </div>

        <!-- 只读：最后更新 -->
        <div class="info-item info-item-readonly">
          <span class="label"><van-icon name="upgrade" /> 最后更新</span>
          <span class="value">{{ formatDate(user.updated_at) }}</span>
        </div>

        <!-- 只读：最后登录 -->
        <div class="info-item info-item-readonly" v-if="user.last_login">
          <span class="label"><van-icon name="location-o" /> 最后登录</span>
          <span class="value">{{ formatDate(user.last_login) }}</span>
        </div>
      </div>

      <!-- ===== 修改密码卡片 ===== -->
      <div class="info-card password-card" :class="{ 'is-expanded': passwordExpanded }">
        <h3 class="card-title card-title-clickable"
          @click="togglePasswordSection"
          :aria-expanded="passwordExpanded"
          role="button"
          tabindex="0"
          @keydown.enter="togglePasswordSection"
        >
          <span><van-icon name="lock" /> 修改密码</span>
          <span class="card-arrow" :class="{ rotated: passwordExpanded }">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
          </span>
        </h3>

        <transition name="slide">
          <div v-show="passwordExpanded" class="password-form">
            <div class="form-group">
              <label for="old-password">原密码</label>
              <div class="pwd-input-wrapper">
                <input
                  id="old-password"
                  v-model="passwordForm.old_password"
                  :type="showPwdFields.old ? 'text' : 'password'"
                  placeholder="请输入原密码"
                  :disabled="changingPwd"
                />
                <button type="button" class="pwd-toggle" @click="showPwdFields.old = !showPwdFields.old">
                  <svg v-if="showPwdFields.old" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
            </div>

            <div class="form-group">
              <label for="new-password">新密码</label>
              <div class="pwd-input-wrapper">
                <input
                  id="new-password"
                  v-model="passwordForm.new_password"
                  :type="showPwdFields.newPwd ? 'text' : 'password'"
                  placeholder="至少6位字符"
                  :disabled="changingPwd"
                  @input="checkPasswordMatch"
                />
                <button type="button" class="pwd-toggle" @click="showPwdFields.newPwd = !showPwdFields.newPwd">
                  <svg v-if="showPwdFields.newPwd" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
            </div>

            <div class="form-group">
              <label for="confirm-password">确认新密码</label>
              <div class="pwd-input-wrapper">
                <input
                  id="confirm-password"
                  v-model="passwordForm.confirm_password"
                  :type="showPwdFields.confirm ? 'text' : 'password'"
                  placeholder="请再次输入新密码"
                  :disabled="changingPwd"
                  @input="checkPasswordMatch"
                />
                <button type="button" class="pwd-toggle" @click="showPwdFields.confirm = !showPwdFields.confirm">
                  <svg v-if="showPwdFields.confirm" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                  <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
              </div>
              <div class="password-hint">
                <span v-if="pwdMatchError" class="hint-error">{{ pwdMatchError }}</span>
                <span v-else-if="passwordForm.confirm_password && pwdMatchOk" class="hint-success">✓ 两次密码输入一致</span>
                <span v-else-if="passwordForm.confirm_password" class="hint-error">✗ 两次密码输入不一致</span>
              </div>
            </div>

            <div v-if="pwdError" class="pwd-global-error">{{ pwdError }}</div>

            <button
              class="pwd-submit-btn"
              :disabled="!pwdFormValid || changingPwd"
              @click="handleChangePassword"
            >
              <span v-if="changingPwd" class="inline-spinner"></span>
              {{ changingPwd ? '提交中...' : '确认修改' }}
            </button>
          </div>
        </transition>
      </div>

      <!-- ===== 操作 ===== -->
      <div class="actions">
        <van-button block type="default" @click="handleLogout" class="action-btn">
          退出登录
        </van-button>
        <van-button block plain type="danger" @click="handleLogoutAll" class="action-btn">
          退出所有设备
        </van-button>
      </div>
    </div>

    <ErrorState v-else message="无法加载用户信息" @retry="fetchUser" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { showConfirmDialog, showToast } from 'vant'
import PageHeader from '@/components/PageHeader.vue'
import LoadingState from '@/components/LoadingState.vue'
import ErrorState from '@/components/ErrorState.vue'

const router = useRouter()
const authStore = useAuthStore()
const user = ref(null)
const loading = ref(true)

// ========== 行内编辑 ==========
const editingField = ref('')           // '' | 'nickname' | 'email' | 'phone'
const savingEdit = ref(false)
const editForm = reactive({ nickname: '', email: '', phone: '' })
const nicknameInputRef = ref(null)
const emailInputRef = ref(null)
const phoneInputRef = ref(null)
const phoneValid = ref(false)
const phoneError = ref('')

// 手机号校验
function validatePhoneInput() {
  const phone = editForm.phone.trim()
  if (!phone) {
    phoneValid.value = false
    phoneError.value = ''
    return
  }
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    phoneValid.value = false
    phoneError.value = '请输入有效的11位手机号（如 138xxxx1234）'
  } else {
    phoneValid.value = true
    phoneError.value = ''
  }
}

// 开始编辑某个字段
function startEdit(field, currentValue) {
  editingField.value = field
  editForm[field] = currentValue || ''
  if (field === 'phone') {
    phoneValid.value = false
    phoneError.value = ''
    if (currentValue) validatePhoneInput()
  }
  nextTick(() => {
    if (field === 'nickname') nicknameInputRef.value?.focus()
    else if (field === 'email') emailInputRef.value?.focus()
    else if (field === 'phone') phoneInputRef.value?.focus()
  })
}

// 取消编辑
function cancelEdit() {
  editingField.value = ''
  phoneError.value = ''
  phoneValid.value = false
}

// 保存编辑
async function saveEdit(field) {
  const value = editForm[field].trim()
  // 手机号额外校验
  if (field === 'phone' && value && !/^1[3-9]\d{9}$/.test(value)) {
    phoneError.value = '手机号格式不正确，请输入11位手机号'
    return
  }
  if (value === (user.value[field] || '')) {
    editingField.value = ''
    return
  }
  savingEdit.value = true
  try {
    await authStore.updateCurrentUser({ [field]: value })
    user.value[field] = value
    editingField.value = ''
    showToast({ type: 'success', message: '修改成功', duration: 1500 })
  } catch (err) {
    showToast({ type: 'fail', message: err.message || '修改失败，请重试' })
  } finally {
    savingEdit.value = false
  }
}

// ========== 头像上传 ==========
const avatarFileInputRef = ref(null)
const uploadingAvatar = ref(false)

function triggerAvatarUpload() {
  if (uploadingAvatar.value) return
  avatarFileInputRef.value?.click()
}

async function handleAvatarChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  // 检查文件大小（限制 2MB）
  if (file.size > 2 * 1024 * 1024) {
    showToast({ type: 'fail', message: '图片大小不能超过 2MB' })
    return
  }
  // 检查文件类型
  if (!file.type.startsWith('image/')) {
    showToast({ type: 'fail', message: '请选择图片文件' })
    return
  }
  uploadingAvatar.value = true
  try {
    const base64 = await fileToBase64(file)
    await authStore.updateCurrentUser({ avatar_url: base64 })
    user.value.avatar_url = base64
    showToast({ type: 'success', message: '头像更新成功', duration: 1500 })
  } catch (err) {
    showToast({ type: 'fail', message: err.message || '头像更新失败' })
  } finally {
    uploadingAvatar.value = false
    // 清空 input 以允许重复选择同一文件
    event.target.value = ''
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

// ========== 修改密码 ==========
const passwordExpanded = ref(false)

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const showPwdFields = reactive({
  old: false,
  newPwd: false,
  confirm: false
})

const changingPwd = ref(false)
const pwdError = ref('')
const pwdMatchOk = ref(false)
const pwdMatchError = ref('')

function togglePasswordSection() {
  passwordExpanded.value = !passwordExpanded.value
  if (!passwordExpanded.value) {
    resetPasswordForm()
  }
}

function checkPasswordMatch() {
  const { new_password, confirm_password } = passwordForm
  if (!confirm_password) {
    pwdMatchError.value = ''
    pwdMatchOk.value = false
    return
  }
  if (new_password && confirm_password && new_password !== confirm_password) {
    pwdMatchError.value = '两次密码输入不一致'
    pwdMatchOk.value = false
  } else if (new_password && confirm_password && new_password === confirm_password) {
    pwdMatchError.value = ''
    pwdMatchOk.value = true
  }
}

const pwdFormValid = computed(() => {
  const { old_password, new_password, confirm_password } = passwordForm
  return (
    old_password.length >= 6 &&
    new_password.length >= 6 &&
    confirm_password.length >= 6 &&
    new_password === confirm_password
  )
})

async function handleChangePassword() {
  if (!pwdFormValid.value) return
  changingPwd.value = true
  pwdError.value = ''
  try {
    await authApi.changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
      confirm_password: passwordForm.confirm_password
    })
    showToast({ type: 'success', message: '密码修改成功，请重新登录' })
    resetPasswordForm()
    passwordExpanded.value = false
    // 修改密码后需重新登录
    setTimeout(() => {
      authStore.logout()
    }, 1500)
  } catch (err) {
    pwdError.value = err.message || '密码修改失败'
  } finally {
    changingPwd.value = false
  }
}

function resetPasswordForm() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
  showPwdFields.old = false
  showPwdFields.newPwd = false
  showPwdFields.confirm = false
  pwdMatchOk.value = false
  pwdMatchError.value = ''
  pwdError.value = ''
}

// ========== 工具函数 ==========
function formatDate(dateString) {
  if (!dateString) return '未知'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  })
}

// ========== 数据请求 ==========
async function fetchUser() {
  loading.value = true
  try {
    const userData = await authStore.fetchCurrentUser()
    user.value = userData
  } catch (error) {
    console.error('Failed to fetch user:', error)
    user.value = null
  } finally {
    loading.value = false
  }
}

// ========== 退出 ==========
async function handleLogout() {
  try {
    await showConfirmDialog({ title: '退出登录', message: '确定要退出登录吗？' })
    await authStore.logout()
  } catch { /* 用户取消 */ }
}

async function handleLogoutAll() {
  try {
    await showConfirmDialog({ title: '退出所有设备', message: '确定要退出所有设备吗？这将使您在其他设备上的登录状态失效。' })
    await authStore.logoutAll()
  } catch { /* 用户取消 */ }
}

onMounted(() => { fetchUser() })
</script>

<style scoped>
.profile-container {
  min-height: 100vh;
  background-color: #f5f5f5;
}
.profile-content {
  padding-bottom: 24px;
}

/* ===== 用户头部 ===== */
.user-header {
  position: relative;
  background: white;
  padding: 36px 20px 20px;
  text-align: center;
  margin-bottom: 12px;
}
.user-avatar-wrapper {
  position: relative;
  z-index: 1;
  display: inline-block;
}
.user-avatar-inner {
  position: relative;
  display: inline-block;
  cursor: pointer;
  border-radius: 50%;
  overflow: hidden;
}
.user-avatar-inner:focus-visible {
  outline: 2px solid #667eea;
  outline-offset: 2px;
}
.user-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  object-fit: cover;
  border: 3px solid white;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  display: block;
  transition: filter 0.2s;
}
.user-avatar-inner:hover .user-avatar {
  filter: brightness(0.7);
}
.avatar-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
  border-radius: 50%;
}
.user-avatar-inner:hover .avatar-overlay {
  opacity: 1;
}
.avatar-file-input {
  display: none;
}
.user-header-name {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.user-nickname {
  font-size: 18px;
  font-weight: 600;
  color: #333;
}
.user-id {
  font-size: 13px;
  color: #999;
}

/* ===== 信息卡片 ===== */
.info-card {
  background: white;
  margin: 0 16px 12px;
  padding: 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}
.card-title-clickable {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
  transition: color 0.15s;
}
.card-title-clickable:hover {
  color: #667eea;
}
.card-arrow {
  display: flex;
  align-items: center;
  transition: transform 0.25s ease;
  color: #999;
}
.card-arrow.rotated {
  transform: rotate(180deg);
}

/* 信息行 */
.info-item {
  display: flex;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f5f5f5;
  min-height: 44px;
  gap: 8px;
  transition: background-color 0.15s;
}
.info-item:last-child { border-bottom: none; }
.info-item.is-editing {
  background: #f8f9ff;
  margin: 0 -12px;
  padding: 12px;
  border-radius: 8px;
  border-bottom-color: transparent;
}
.info-item .label {
  color: #666;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 72px;
}
.info-item .value {
  color: #333;
  font-size: 14px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.info-item-readonly .value {
  color: #999;
}

/* 编辑触发按钮 */
.edit-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #ccc;
  cursor: pointer;
  border-radius: 6px;
  flex-shrink: 0;
  transition: all 0.15s;
}
.info-item:not(.info-item-readonly):hover .edit-trigger {
  color: #667eea;
  background: rgba(102, 126, 234, 0.08);
}

/* 行内编辑 */
.edit-inline {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}
.edit-inline-column {
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}
.edit-inline-actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}
.edit-field-error {
  font-size: 12px;
  color: #e74c3c;
  margin-top: -2px;
  flex-basis: 100%;
}
.edit-input {
  flex: 1;
  padding: 8px 12px;
  border: 2px solid #667eea;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  min-width: 0;
}
.edit-input:focus {
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15);
}
.edit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.15s;
}
.edit-btn.save {
  background: #667eea;
  color: white;
}
.edit-btn.save:hover:not(:disabled) {
  background: #5a6fd6;
}
.edit-btn.save:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.edit-btn.cancel {
  background: #f0f0f0;
  color: #999;
}
.edit-btn.cancel:hover:not(:disabled) {
  background: #e8e8e8;
  color: #666;
}
.edit-btn.cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ===== 修改密码 ===== */
.password-card {
  overflow: hidden;
}
.password-card.is-expanded {
  border: 1px solid #eef0f4;
}
.password-form {
  padding-top: 4px;
}
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}
.form-group label {
  font-size: 13px;
  font-weight: 500;
  color: #666;
}
.pwd-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}
.pwd-input-wrapper input {
  flex: 1;
  padding: 10px 42px 10px 14px;
  border: 2px solid #e1e5e9;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.pwd-input-wrapper input:focus {
  border-color: #667eea;
}
.pwd-input-wrapper input:disabled {
  background: #f8f8f8;
  cursor: not-allowed;
}
.pwd-toggle {
  position: absolute;
  right: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  background: none;
  color: #999;
  cursor: pointer;
  border-radius: 4px;
  transition: color 0.15s;
}
.pwd-toggle:hover {
  color: #667eea;
}
.password-hint {
  font-size: 12px;
  min-height: 18px;
}
.hint-error {
  color: #e74c3c;
}
.hint-success {
  color: #27ae60;
}
.pwd-global-error {
  background: #fff0f0;
  color: #e74c3c;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 12px;
}
.pwd-submit-btn {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.2s;
}
.pwd-submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}
.pwd-submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 密码卡片折叠动画 */
.slide-enter-active {
  transition: all 0.25s ease-out;
  overflow: hidden;
}
.slide-leave-active {
  transition: all 0.2s ease-in;
  overflow: hidden;
}
.slide-enter-from {
  max-height: 0;
  opacity: 0;
  margin-top: -8px;
}
.slide-enter-to {
  max-height: 400px;
  opacity: 1;
}
.slide-leave-from {
  max-height: 400px;
  opacity: 1;
}
.slide-leave-to {
  max-height: 0;
  opacity: 0;
  margin-top: -8px;
}

/* 加载旋转动画 */
.inline-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ===== 操作按钮 ===== */
.actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 16px;
}
.action-btn {
  border-radius: 8px;
}

/* ===== 响应式 ===== */
@media (max-width: 480px) {
  .info-card { margin: 0 12px 12px; }
  .actions { padding: 0 12px; }
  .user-header { padding: 28px 16px 16px; }
  .info-item.is-editing { margin: 0 -8px; padding: 12px 8px; }
  .user-avatar { width: 64px; height: 64px; }
}
</style>
