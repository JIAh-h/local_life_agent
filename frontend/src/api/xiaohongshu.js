/**
 * 小红书笔记 API 服务层
 */
const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'

/** 判断是否为小红书 CDN 图片 URL */
function isXhsCdnUrl(url) {
  if (!url || typeof url !== 'string') return false
  return /\.(xiaohongshu\.com|xhscdn\.com|xhscdn\.net)/i.test(url)
}

/**
 * 将小红书 CDN 图片 URL 转换为本地代理 URL，绕过防盗链
 * @param {string} url
 * @returns {string}
 */
function proxyImageUrl(url) {
  if (!url || !isXhsCdnUrl(url)) return url
  return `${baseURL}/xiaohongshu/image-proxy?url=${encodeURIComponent(url)}`
}

/**
 * 递归将对象中所有小红书 CDN 图片 URL 替换为代理 URL
 * @param {any} obj - 要处理的对象/数组/值
 */
function proxyImageUrlsInObject(obj) {
  if (typeof obj === 'string') {
    return proxyImageUrl(obj)
  }
  if (Array.isArray(obj)) {
    return obj.map(item => proxyImageUrlsInObject(item))
  }
  if (obj && typeof obj === 'object') {
    const result = {}
    for (const [key, value] of Object.entries(obj)) {
      result[key] = proxyImageUrlsInObject(value)
    }
    return result
  }
  return obj
}

/**
 * 搜索小红书笔记（结果中的图片URL自动转为代理）
 * @param {string} keyword
 * @param {number} [page=1]
 * @param {number} [pageSize=20]
 * @returns {Promise<{notes: Array, total: number}>}
 */
export async function searchNotes(keyword, page = 1, pageSize = 20) {
  const response = await fetch(`${baseURL}/xiaohongshu/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keyword, page, page_size: pageSize })
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || '搜索失败')
  }
  return proxyImageUrlsInObject(await response.json())
}

/**
 * 获取笔记详情（结果中的图片URL自动转为代理）
 * @param {string} noteId
 * @param {string} xsecToken
 * @returns {Promise<{desc: string, image_urls: string[], display_title: string, liked_count: number, ...}>}
 */
export async function getNoteDetail(noteId, xsecToken) {
  const response = await fetch(`${baseURL}/xiaohongshu/note/detail`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note_id: noteId, xsec_token: xsecToken })
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || '获取笔记详情失败')
  }
  return proxyImageUrlsInObject(await response.json())
}

/**
 * 获取笔记评论（头像URL自动转为代理）
 * @param {string} noteId
 * @param {string} xsecToken
 * @param {string} [cursor='']
 * @returns {Promise<{comments: Array, cursor: string, has_more: boolean}>}
 */
export async function getNoteComments(noteId, xsecToken, cursor = '') {
  const response = await fetch(`${baseURL}/xiaohongshu/note/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note_id: noteId, xsec_token: xsecToken, cursor })
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.detail || '获取评论失败')
  }
  return proxyImageUrlsInObject(await response.json())
}

export default { searchNotes, getNoteDetail, getNoteComments }
