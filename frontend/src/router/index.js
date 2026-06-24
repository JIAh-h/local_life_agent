import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录', guest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { title: '注册', guest: true }
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPassword.vue'),
    meta: { title: '找回密码', guest: true }
  },
  {
    path: '/location',
    name: 'Location',
    component: () => import('@/views/Location.vue'),
    meta: { title: '定位服务', requiresAuth: true }
  },
  {
    path: '/food',
    name: 'Food',
    component: () => import('@/views/Food.vue'),
    meta: { title: '美食推荐', requiresAuth: true }
  },
  {
    path: '/food/:id',
    name: 'FoodDetail',
    component: () => import('@/views/FoodDetail.vue'),
    meta: { title: '美食详情', requiresAuth: true }
  },
  {
    path: '/attraction',
    name: 'Attraction',
    component: () => import('@/views/Attraction.vue'),
    meta: { title: '景点推荐', requiresAuth: true }
  },
  {
    path: '/attraction/:id',
    name: 'AttractionDetail',
    component: () => import('@/views/AttractionDetail.vue'),
    meta: { title: '景点详情', requiresAuth: true }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/Chat.vue'),
    meta: { title: '智能助手', requiresAuth: true }
  },
  {
    path: '/favorites',
    name: 'Favorites',
    component: () => import('@/views/Favorites.vue'),
    meta: { title: '我的收藏', requiresAuth: true }
  },
  {
    path: '/recommend',
    name: 'Recommend',
    component: () => import('@/views/Recommend.vue'),
    meta: { title: '今日推荐', requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/Profile.vue'),
    meta: { title: '个人中心', requiresAuth: true }
  },
  {
    path: '/note/:id',
    name: 'XiaohongshuNoteDetail',
    component: () => import('@/views/XiaohongshuNoteDetail.vue'),
    meta: { title: '笔记详情', requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  // 设置页面标题
  document.title = to.meta.title ? `${to.meta.title} - 小紫薯` : '小紫薯'
  
  const authStore = useAuthStore()
  
  // 检查是否需要认证
  if (to.meta.requiresAuth) {
    if (!authStore.isAuthenticated) {
      // 未登录，跳转到登录页
      next({
        path: '/login',
        query: { redirect: to.fullPath }
      })
      return
    }
    
    // 验证Token是否有效
    const isValid = await authStore.verifyToken()
    if (!isValid) {
      // Token无效，尝试刷新
      try {
        await authStore.refreshAccessToken()
      } catch (error) {
        // 刷新失败，跳转到登录页
        next({
          path: '/login',
          query: { redirect: to.fullPath }
        })
        return
      }
    }
  }
  
  // 如果是访客页面（登录、注册）且已登录，跳转到首页
  if (to.meta.guest && authStore.isAuthenticated) {
    next({ path: '/' })
    return
  }
  
  next()
})

export default router
