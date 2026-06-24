/**
 * 高德地图 JSAPI 加载器
 * 密钥配置从后端获取，不硬编码在前端
 */
const AMAP_CDN_URL = 'https://webapi.amap.com/maps'

let loadPromise = null

/**
 * 从后端获取高德地图 JSAPI 配置
 * @returns {Promise<{key: string, security_key: string, version: string}>}
 */
async function fetchAMapConfig() {
  const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'
  const response = await fetch(`${baseURL}/map/config`)
  if (!response.ok) {
    throw new Error('获取地图配置失败')
  }
  return response.json()
}

/**
 * 动态加载高德 JSAPI
 * @returns {Promise} - 返回 AMap 对象
 */
export function loadAMapJSAPI() {
  if (loadPromise) return loadPromise

  loadPromise = (async () => {
    if (window.AMap && window.AMap.version) {
      return window.AMap
    }

    // 从后端获取密钥配置
    const config = await fetchAMapConfig()
    if (!config.key) {
      throw new Error('高德地图 JSAPI Key 未配置')
    }

    // 设置安全密钥
    window._AMapSecurityConfig = window._AMapSecurityConfig || {}
    window._AMapSecurityConfig.securityJsCode = config.security_key

    // 动态加载 JSAPI 脚本
    return new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = `${AMAP_CDN_URL}?v=${config.version || '2.0'}&key=${config.key}`
      script.async = true
      script.defer = true

      script.onload = () => {
        if (window.AMap) {
          resolve(window.AMap)
        } else {
          reject(new Error('AMap 加载失败：未找到 AMap 对象'))
        }
      }

      script.onerror = () => {
        loadPromise = null
        reject(new Error('AMap JSAPI 脚本加载失败'))
      }

      document.head.appendChild(script)
    })
  })()

  return loadPromise
}

/**
 * 从环境变量获取配置并加载 AMap（保留向后兼容）
 * @returns {Promise<AMap>}
 */
export function loadAMapFromEnv() {
  return loadAMapJSAPI()
}

/**
 * 清理加载状态
 */
export function resetAMapLoader() {
  loadPromise = null
}

export default { loadAMapJSAPI, loadAMapFromEnv, resetAMapLoader }
