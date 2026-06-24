/**
 * 高德地图 REST API 服务层
 * 所有请求通过后端代理，密钥仅存储在后端
 */

const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'

/**
 * 通用后端代理请求
 * @param {string} path - API 路径
 * @param {object} data - 请求数据
 * @returns {Promise<object>}
 */
async function proxyPost(path, data) {
  const response = await fetch(`${baseURL}/map${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || '请求失败')
  }
  return response.json()
}

/**
 * 地理编码：地址 → 经纬度
 * @param {string} address - 详细地址
 * @param {string} [city] - 所在城市
 * @returns {Promise<{latitude: number, longitude: number, address: string}>}
 */
export async function geocode(address, city = '') {
  return proxyPost('/geocode', { address, city })
}

/**
 * 逆地理编码：经纬度 → 地址
 * @param {number} latitude
 * @param {number} longitude
 * @param {number} [radius=1000]
 * @returns {Promise<object>}
 */
export async function regeocode(latitude, longitude, radius = 1000) {
  return proxyPost('/regeocode', { latitude, longitude, radius })
}

/**
 * 周边 POI 搜索
 * @param {object} options
 * @param {number} options.latitude
 * @param {number} options.longitude
 * @param {string} [options.types]
 * @param {number} [options.radius=3000]
 * @param {number} [options.page=1]
 * @param {number} [options.pageSize=20]
 * @param {string} [options.keywords]
 * @returns {Promise<{pois: Array, total: number}>}
 */
export async function searchAround(options) {
  return proxyPost('/place/around', options)
}

/**
 * 关键词 POI 搜索
 * @param {object} options
 * @param {string} options.keywords
 * @param {string} [options.city]
 * @param {string} [options.types]
 * @param {number} [options.page=1]
 * @param {number} [options.pageSize=20]
 * @returns {Promise<{pois: Array, total: number}>}
 */
export async function searchText(options) {
  return proxyPost('/place/text', options)
}

/**
 * 输入提示：关键词联想（用于搜索框自动补全）
 * @param {object} options
 * @param {string} options.keywords - 输入关键词
 * @param {string} [options.city] - 限定城市
 * @param {string} [options.type] - POI 类型
 * @param {boolean} [options.citylimit=false] - 是否限制城市
 * @returns {Promise<{tips: Array}>}
 */
export async function inputTips(options) {
  return proxyPost('/inputtips', options)
}

/**
 * 步行路线规划
 * @param {{latitude: number, longitude: number}} origin
 * @param {{latitude: number, longitude: number}} destination
 * @returns {Promise<object>}
 */
export async function walkingRoute({ origin, destination }) {
  return proxyPost('/direction/walking', { origin, destination })
}

/**
 * 驾车路线规划
 * @param {{latitude: number, longitude: number}} origin
 * @param {{latitude: number, longitude: number}} destination
 * @param {number} [strategy=0]
 * @returns {Promise<object>}
 */
export async function drivingRoute({ origin, destination, strategy = 0 }) {
  return proxyPost('/direction/driving', { origin, destination, strategy })
}

/**
 * 生成高德地图 URI 导航链接（纯前端，不涉及密钥）
 * @param {{latitude: number, longitude: number}} destination
 * @param {string} [name]
 * @param {'navi'|'route'} [type='navi']
 * @returns {string}
 */
export function buildAMapURI(destination, name = '', type = 'navi') {
  const params = [
    `to=${destination.longitude},${destination.latitude}`,
    `name=${encodeURIComponent(name || '目的地')}`,
    `coordinate=gaode`,
    `mode=0`
  ]
  if (type === 'route') {
    return `https://uri.amap.com/route?${params.join('&')}`
  }
  return `https://uri.amap.com/navigation?${params.join('&')}`
}

/**
 * 获取搜索半径配置参数
 * @returns {Promise<{min:number, max:number, default:number, step:number, presets:Array}>}
 */
export async function getRadiusConfig() {
  const response = await fetch(`${baseURL}/map/radius/config`)
  if (!response.ok) throw new Error('获取半径配置失败')
  return response.json()
}

/**
 * 获取实时天气（复用高德API Key，无需额外配置）
 * 后端带Redis缓存，同城市当天内直接返回缓存数据
 * @param {string} city - 城市编码adcode（如 "440600"）或城市名（如 "佛山"）
 * @returns {Promise<{city, weather, temperature, humidity, reporttime}>}
 */
export async function getCurrentWeather(city) {
  return proxyPost('/weather/current', { city })
}

/**
 * 高德定位 MCP 服务：获取客户端位置
 * 基于客户端IP（后端代理）调用高德IP定位API
 * @param {string} [ip] - 客户端IP（可选，后端自动获取）
 * @returns {Promise<{latitude: number, longitude: number, address: string, province: string, city: string, district: string, adcode: string, source: string}>}
 */
export async function getPosition(ip) {
  return proxyPost('/position', { ip })
}

export default {
  geocode, regeocode, searchAround, searchText, inputTips,
  walkingRoute, drivingRoute, buildAMapURI, getRadiusConfig,
  getCurrentWeather, getPosition
}
