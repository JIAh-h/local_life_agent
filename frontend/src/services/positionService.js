/**
 * 高德地图定位MCP服务
 *
 * 定位策略（从高精度到低精度）：
 *   1. 高德 JSAPI Geolocation 插件（GPS/WiFi/基站，最精确）
 *   2. 浏览器原生 navigator.geolocation（次精确）
 *   3. 后端 IP 定位 MCP 服务（城市级，最后兜底）
 *
 * 缓存策略：
 *   - 页面刷新时，先检查 localStorage 缓存的上一轮定位
 *   - 若缓存存在且与当前浏览器大致位置偏差 ≤ 10m，直接复用缓存不透传 MCP
 *   - 以 localStorage 的 key: `position_cache_v2` 存储
 */

import { getPosition as getPositionFromBackend, regeocode } from '@/api/amap'
import { loadAMapJSAPI } from '@/utils/amap'

// ---- 常量 ----

/** 缓存 key */
const CACHE_KEY = 'position_cache_v2'
/** 10m 容错半径（°），0.0001° ≈ 11.1m */
const TOLERANCE_DEG = 0.0001

// ---- 类型定义（JSDoc）----

/**
 * @typedef {Object} PositionData
 * @property {number} latitude
 * @property {number} longitude
 * @property {string} address
 * @property {string} province
 * @property {string} city
 * @property {string} district
 * @property {string} adcode
 * @property {string} source - 'jsapi' | 'browser' | 'ip'
 * @property {number} [accuracy] - 精度（米）
 * @property {number} timestamp - 定位时间戳
 */

// ---- 缓存工具 ----

/**
 * 从 localStorage 读取缓存的定位数据
 * @returns {PositionData|null}
 */
function readCache() {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    // 简单校验
    if (typeof data.latitude !== 'number' || typeof data.longitude !== 'number') {
      return null
    }
    return data
  } catch {
    return null
  }
}

/**
 * 写入定位缓存到 localStorage
 * @param {PositionData} data
 */
function writeCache(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data))
  } catch {
    // localStorage 满等异常忽略
  }
}

/**
 * 计算两点间的近似距离（米），使用 Haversine 公式
 * @param {number} lat1
 * @param {number} lng1
 * @param {number} lat2
 * @param {number} lng2
 * @returns {number}
 */
function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371000
  const toRad = (deg) => (deg * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

/**
 * 判断两点是否在容错半径内（≤10m）
 * @param {number} lat1
 * @param {number} lng1
 * @param {number} lat2
 * @param {number} lng2
 * @returns {boolean}
 */
function isWithinTolerance(lat1, lng1, lat2, lng2) {
  return haversineDistance(lat1, lng1, lat2, lng2) <= 10
}

// ---- 精确度降级定位 ----

/**
 * 使用高德 JSAPI Geolocation 插件进行精确定位（需等 AMap 加载完成）
 * 先确保 AMap JSAPI 和 Geolocation 插件已加载，再发起定位
 * @returns {Promise<{latitude: number, longitude: number, accuracy: number}>}
 */
async function locateByAMapJSAPI() {
  // 1. 确保 AMap JSAPI 核心库已加载
  let AMap = window.AMap
  if (!AMap) {
    try {
      AMap = await loadAMapJSAPI()
      console.log('[定位诊断] AMap JSAPI 核心库加载成功')
    } catch (err) {
      console.error('[定位诊断] AMap JSAPI 核心库加载失败:', err.message)
      throw new Error('高德地图 JSAPI 加载失败: ' + err.message)
    }
  }

  // 2. 确保 Geolocation 插件已加载（JSAPI v2.0 插件需显式加载）
  if (!AMap.Geolocation) {
    try {
      await new Promise((resolve, reject) => {
        AMap.plugin(['AMap.Geolocation'], () => resolve())
        setTimeout(() => reject(new Error('Geolocation 插件加载超时')), 15000)
      })
      console.log('[定位诊断] AMap Geolocation 插件加载成功')
    } catch (err) {
      console.error('[定位诊断] AMap Geolocation 插件加载失败:', err.message)
      throw new Error('高德 Geolocation 插件加载失败: ' + err.message)
    }
  }

  // 3. 发起定位
  return new Promise((resolve, reject) => {
    const geolocation = new AMap.Geolocation({
      enableHighAccuracy: true,
      timeout: 10000,
      zoomToAccuracy: false,
      GeoLocationFirst: true,
      noIpLocation: false
    })
    console.log('[定位诊断] 开始调用 AMap.getCurrentPosition...')
    geolocation.getCurrentPosition((status, result) => {
      if (status === 'complete') {
        console.log('[定位诊断] AMap 定位成功:', result.position.lat, result.position.lng)
        resolve({
          latitude: result.position.lat,
          longitude: result.position.lng,
          accuracy: result.accuracy || 0
        })
      } else {
        console.warn('[定位诊断] AMap 定位失败:', status, result.message || '未知错误')
        reject(new Error(result.message || '高德JSAPI定位失败'))
      }
    })
  })
}

/**
 * 使用浏览器原生 Geolocation API
 * @returns {Promise<{latitude: number, longitude: number, accuracy: number}>}
 */
function locateByBrowser() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('浏览器不支持定位'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy || 0
        })
      },
      (err) => {
        const messages = {
          1: '定位权限被拒绝',
          2: '无法获取位置信息',
          3: '定位超时'
        }
        reject(new Error(messages[err.code] || `定位失败: ${err.message}`))
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    )
  })
}

// ---- 主入口 ----

/**
 * 定位结果
 * @typedef {Object} LocateResult
 * @property {boolean} success
 * @property {PositionData} [data]
 * @property {string} [error] - 错误消息
 */

/**
 * 获取定位（含缓存判断）
 *
 * 流程：
 *  1. 从缓存读取上次定位
 *  2. 尝试高德JSAPI定位（最精确）
 *  3. 若成功且与缓存偏差 ≤10m，直接返回缓存（不调用后端MCP）
 *  4. 若成功且偏差 >10m，通过逆地理获取详细地址后返回
 *  5. 若高德JSAPI失败，降级到浏览器定位
 *  6. 若浏览器也失败，降级到后端IP定位 MCP
 *
 * @param {Object} [options]
 * @param {boolean} [options.forceRefresh=false] - 强制刷新，忽略缓存
 * @param {number} [options.timeout=15000] - 整体超时（毫秒）
 * @returns {Promise<LocateResult>}
 */
export async function locate(options = {}) {
  const { forceRefresh = false, timeout = 15000 } = options
  const cached = readCache()
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    // ----- 第一阶段：尝试精确定位（JSAPI / 浏览器）-----
    let precise = null
    let preciseSource = ''

    try {
      precise = await locateByAMapJSAPI()
      preciseSource = 'jsapi'
      console.log('[定位诊断] 高德JSAPI定位成功')
    } catch (jsapiErr) {
      console.warn('[定位诊断] 高德JSAPI定位失败:', jsapiErr.message)
      // 降级到浏览器定位
      try {
        precise = await locateByBrowser()
        preciseSource = 'browser'
        console.log('[定位诊断] 浏览器定位成功')
      } catch (browserErr) {
        console.warn('[定位诊断] 浏览器定位也失败:', browserErr.message)
        // 精确定位均失败
      }
    }

    // ----- 第二阶段：缓存命中判断 -----
    if (
      !forceRefresh &&
      cached &&
      precise &&
      isWithinTolerance(
        cached.latitude, cached.longitude,
        precise.latitude, precise.longitude
      )
    ) {
      // 位置未发生明显变化，复用缓存，不消耗 MCP API
      clearTimeout(timeoutId)
      return { success: true, data: { ...cached, reused: true } }
    }

    // ----- 第三阶段：获取详细地址 -----
    let positionData

    if (precise) {
      // 精确定位成功，通过逆地理编码获取地址
      try {
        const addr = await regeocode(precise.latitude, precise.longitude)
        positionData = {
          latitude: precise.latitude,
          longitude: precise.longitude,
          address: addr.address,
          province: addr.province,
          city: addr.city,
          district: addr.district,
          adcode: addr.adcode,
          source: preciseSource,
          accuracy: precise.accuracy,
          timestamp: Date.now()
        }
      } catch {
        // 逆地理失败，用原始坐标
        positionData = {
          latitude: precise.latitude,
          longitude: precise.longitude,
          address: `${precise.latitude.toFixed(4)}, ${precise.longitude.toFixed(4)}`,
          province: '',
          city: '',
          district: '',
          adcode: '',
          source: preciseSource,
          accuracy: precise.accuracy,
          timestamp: Date.now()
        }
      }
    } else {
      // 所有精确定位均失败，降级到后端IP定位MCP
      try {
        const ipResult = await getPositionFromBackend()
        positionData = {
          latitude: ipResult.latitude,
          longitude: ipResult.longitude,
          address: ipResult.address,
          province: ipResult.province,
          city: ipResult.city,
          district: ipResult.district,
          adcode: ipResult.adcode,
          source: 'ip',
          accuracy: 5000, // IP定位精度约5km
          timestamp: Date.now()
        }
      } catch (ipErr) {
        clearTimeout(timeoutId)
        console.error('[定位诊断] IP定位也失败:', ipErr.message || ipErr)
        return {
          success: false,
          error: '所有定位方式均失败（高德JSAPI→浏览器→IP），请检查高德JSAPI Key配置及浏览器定位权限'
        }
      }
    }

    // 写入缓存
    writeCache(positionData)
    clearTimeout(timeoutId)
    return { success: true, data: positionData }

  } catch (err) {
    clearTimeout(timeoutId)
    // 兜底：如果有缓存，返回缓存但标记为降级
    if (cached) {
      return {
        success: true,
        data: { ...cached, degraded: true },
        warning: `定位异常，使用上次定位数据: ${err.message}`
      }
    }
    return {
      success: false,
      error: err.message || '定位服务不可用'
    }
  }
}

/**
 * 清除定位缓存
 */
export function clearPositionCache() {
  try {
    localStorage.removeItem(CACHE_KEY)
  } catch {
    // ignore
  }
}

export default { locate, clearPositionCache }
