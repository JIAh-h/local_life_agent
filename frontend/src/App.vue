<template>
  <div id="app">
    <!-- PC 导航栏 -->
    <nav class="navbar" v-if="!isAuthPage">
      <div class="nav-container">
        <router-link to="/" class="nav-brand">小紫薯</router-link>

        <!-- PC 导航链接 -->
        <div class="nav-links">
          <router-link to="/" class="nav-link">
            <van-icon name="wap-home-o" /> 首页
          </router-link>
          <router-link to="/location" class="nav-link">
            <van-icon name="location-o" /> 定位
          </router-link>
          <router-link to="/food" class="nav-link">
            <van-icon name="food-o" /> 美食
          </router-link>
          <router-link to="/attraction" class="nav-link">
            <van-icon name="guide-o" /> 景点
          </router-link>
          <router-link to="/chat" class="nav-link">
            <van-icon name="chat-o" /> 助手
          </router-link>
          <router-link to="/favorites" class="nav-link">
            <van-icon name="star-o" /> 收藏
          </router-link>
          <router-link to="/recommend" class="nav-link">
            <van-icon name="gift-o" /> 推荐
          </router-link>
        </div>

        
        <!-- PC 用户区域 -->
        <div class="nav-user">
          <template v-if="authStore.isAuthenticated">
            <router-link to="/profile" class="user-link">
              <img v-if="authStore.currentUser?.avatar_url"
                :src="authStore.currentUser.avatar_url"
                class="user-avatar-img"
                alt="头像"
              />
              <span v-else class="user-avatar">👤</span>
            </router-link>
            <button @click="handleLogout" class="logout-btn">退出</button>
          </template>
          <template v-else>
            <router-link to="/login" class="login-link">登录</router-link>
            <router-link to="/register" class="register-link">注册</router-link>
          </template>
        </div>

        <!-- 天气组件 -->
        <div class="nav-weather-wrapper">
          <NavWeather />
        </div>


        <!-- 移动端汉堡菜单按钮 -->
        <button class="hamburger-btn" @click="toggleMobileMenu" :aria-label="showMobileMenu ? '关闭菜单' : '打开菜单'">
          <span :class="['hamburger-icon', { active: showMobileMenu }]">
            <span></span>
            <span></span>
            <span></span>
          </span>
        </button>
      </div>
    </nav>

    <!-- 移动端菜单遮罩 -->
    <div v-if="showMobileMenu" class="mobile-overlay" @click="showMobileMenu = false"></div>

    <!-- 移动端侧边菜单 -->
    <div :class="['mobile-menu', { open: showMobileMenu }]">
      <div class="mobile-menu-header">
        <div v-if="authStore.isAuthenticated" class="mobile-user-info">
          <img v-if="authStore.currentUser?.avatar_url"
            :src="authStore.currentUser.avatar_url"
            class="mobile-avatar-img"
            alt="头像"
          />
          <span v-else class="mobile-avatar">👤</span>
        </div>
        <div v-else class="mobile-auth-links">
          <router-link to="/login" class="mobile-login-btn" @click="showMobileMenu = false">登录</router-link>
          <router-link to="/register" class="mobile-register-btn" @click="showMobileMenu = false">注册</router-link>
        </div>
      </div>
      <div class="mobile-menu-items">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path" class="mobile-menu-item" @click="showMobileMenu = false">
          <van-icon :name="item.icon" size="20" />
          <span>{{ item.label }}</span>
        </router-link>
      </div>
      <div v-if="authStore.isAuthenticated" class="mobile-menu-footer">
        <router-link to="/profile" class="mobile-menu-item" @click="showMobileMenu = false">
          <van-icon name="user-o" size="20" />
          <span>个人中心</span>
        </router-link>
        <div class="mobile-menu-item danger" @click="handleMobileLogout">
          <van-icon name="cross" size="20" />
          <span>退出登录</span>
        </div>
      </div>
    </div>

    <!-- 主内容 -->
    <main :class="{ 'with-navbar': !isAuthPage }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import NavWeather from '@/components/NavWeather.vue'
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { showConfirmDialog } from 'vant'

const route = useRoute()
const authStore = useAuthStore()

const showMobileMenu = ref(false)

const navItems = [
  { path: '/', icon: 'wap-home-o', label: '首页' },
  { path: '/location', icon: 'location-o', label: '定位' },
  { path: '/food', icon: 'food-o', label: '美食' },
  { path: '/attraction', icon: 'guide-o', label: '景点' },
  { path: '/chat', icon: 'chat-o', label: '智能助手' },
  { path: '/favorites', icon: 'star-o', label: '我的收藏' },
  { path: '/recommend', icon: 'gift-o', label: '今日推荐' }
]

const isAuthPage = computed(() => route.meta?.guest === true)

// 路由切换时关闭菜单
watch(() => route.path, () => { showMobileMenu.value = false })

function toggleMobileMenu() {
  showMobileMenu.value = !showMobileMenu.value
}

async function handleLogout() {
  try {
    await showConfirmDialog({ title: '退出登录', message: '确定要退出登录吗？' })
    await authStore.logout()
  } catch { /* 用户取消 */ }
}

async function handleMobileLogout() {
  try {
    await showConfirmDialog({ title: '退出登录', message: '确定要退出登录吗？' })
    showMobileMenu.value = false
    await authStore.logout()
  } catch { /* 用户取消 */ }
}

// 初始化（定位由 Location.vue 中的 MCP 定位服务负责，不在全局初始化）
authStore.initialize()
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; }
#app { height: 100%; background-color: #f5f5f5; }

/* 导航栏 */
.navbar {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 0 20px;
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 1000;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
.nav-container {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
}
.nav-brand {
  color: white;
  font-size: 20px;
  font-weight: 700;
  text-decoration: none;
  margin-right: 30px;
}
.nav-links { display: flex; gap: 8px; flex: 1; }
.nav-link {
  color: rgba(255,255,255,0.9);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 8px 12px;
  border-radius: 6px;
  transition: background 0.3s;
  display: flex;
  align-items: center;
  gap: 4px;
}
.nav-link:hover, .nav-link.router-link-active {
  background: rgba(255,255,255,0.2);
  color: white;
}
.nav-user { display: flex; align-items: center; gap: 15px; }
.user-link {
  display: flex; align-items: center; gap: 8px;
  color: white; text-decoration: none;
  padding: 6px 12px; border-radius: 20px;
  background: rgba(255,255,255,0.2); transition: background 0.3s;
}
.user-link:hover { background: rgba(255,255,255,0.3); }
.user-avatar { font-size: 18px; }
.user-avatar-img {
  width: 28px; height: 28px; border-radius: 50%;
  object-fit: cover; border: 2px solid rgba(255,255,255,0.6);
}
.user-name { font-size: 14px; font-weight: 500; }
.logout-btn {
  background: rgba(255,255,255,0.2); color: white; border: none;
  padding: 6px 12px; border-radius: 6px; font-size: 14px;
  cursor: pointer; transition: background 0.3s;
}
.logout-btn:hover { background: rgba(255,255,255,0.3); }
.login-link, .register-link {
  color: white; text-decoration: none;
  padding: 6px 12px; border-radius: 6px;
  font-size: 14px; font-weight: 500; transition: background 0.3s;
}
.login-link { background: rgba(255,255,255,0.2); }
.login-link:hover { background: rgba(255,255,255,0.3); }
.register-link { background: white; color: #667eea; }
.register-link:hover { background: #f0f0f0; }
.with-navbar { padding-top: 60px; }

/* 汉堡按钮 - 仅移动端 */
.hamburger-btn {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
}
.hamburger-icon {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 22px;
}
.hamburger-icon span {
  display: block;
  height: 2px;
  background: white;
  border-radius: 1px;
  transition: transform 0.3s, opacity 0.3s;
}
.hamburger-icon.active span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.hamburger-icon.active span:nth-child(2) { opacity: 0; }
.hamburger-icon.active span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

/* 移动端菜单 */
.mobile-overlay {
  display: none;
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  z-index: 1001;
}
.mobile-menu {
  display: none;
  position: fixed;
  top: 0;
  right: -280px;
  width: 280px;
  height: 100%;
  background: white;
  z-index: 1002;
  transition: right 0.3s ease;
  overflow-y: auto;
  box-shadow: -4px 0 20px rgba(0,0,0,0.15);
}
.mobile-menu.open { right: 0; }
.mobile-menu-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 30px 20px 20px;
}
.mobile-user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  color: white;
}
.mobile-avatar { font-size: 32px; }
.mobile-avatar-img {
  width: 48px; height: 48px; border-radius: 50%;
  object-fit: cover; border: 2px solid rgba(255,255,255,0.6);
}
.mobile-username { font-size: 18px; font-weight: 600; }
.mobile-auth-links {
  display: flex;
  gap: 12px;
}
.mobile-login-btn, .mobile-register-btn {
  flex: 1;
  text-align: center;
  padding: 10px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}
.mobile-login-btn {
  background: rgba(255,255,255,0.2);
  color: white;
}
.mobile-register-btn {
  background: white;
  color: #667eea;
}
.mobile-menu-items {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}
.mobile-menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  color: #333;
  text-decoration: none;
  font-size: 15px;
  transition: background 0.2s;
  cursor: pointer;
}
.mobile-menu-item:active { background: #f5f5f5; }
.mobile-menu-item.router-link-active {
  color: #667eea;
  background: rgba(102, 126, 234, 0.05);
}
.mobile-menu-item.danger { color: #ff4757; }
.mobile-menu-footer {
  padding: 12px 0;
}

@media (max-width: 768px) {
  .nav-links, .nav-user, .nav-weather-wrapper { display: none; }
  .hamburger-btn { display: block; }
  .mobile-overlay { display: block; }
  .mobile-menu { display: block; }
}
</style>