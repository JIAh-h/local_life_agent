const baseURL = import.meta.env.VITE_APP_API_BASE_URL || '/api/v1'

function getUserId() {
  return localStorage.getItem('user_id') || '1'
}

export const favoritesApi = {
  async getFavorites(params = {}) {
    let url = `${baseURL}/favorites?user_id=${getUserId()}`
    Object.entries(params).forEach(([k, v]) => { if (v) url += `&${k}=${encodeURIComponent(v)}` })
    const r = await fetch(url)
    if (!r.ok) throw new Error('获取收藏失败')
    return r.json()
  },

  async addFavorite(data) {
    const r = await fetch(`${baseURL}/favorites?user_id=${getUserId()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!r.ok) throw new Error('收藏失败')
    return r.json()
  },

  async removeFavorite(id) {
    const r = await fetch(`${baseURL}/favorites/${id}?user_id=${getUserId()}`, { method: 'DELETE' })
    if (!r.ok) throw new Error('取消收藏失败')
    return r.json()
  },

  async checkFavorited(noteId) {
    const r = await fetch(`${baseURL}/favorites/check?note_id=${noteId}&user_id=${getUserId()}`)
    return r.json()
  },

  async batchRemoveFavorites(ids) {
    const r = await fetch(`${baseURL}/favorites/batch-delete?user_id=${getUserId()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(ids),
    })
    if (!r.ok) throw new Error('批量删除失败')
    return r.json()
  },
}
