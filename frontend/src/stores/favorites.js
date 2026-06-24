import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { favoritesApi } from '@/api/favorites'

export const useFavoritesStore = defineStore('favorites', () => {
  const favorites = ref([])
  const loading = ref(false)
  const error = ref(null)
  const noMore = ref(false)
  const pagination = ref({ page: 1, pageSize: 20, total: 0 })

  async function fetchFavorites(params = {}) {
    loading.value = true
    error.value = null
    try {
      const result = await favoritesApi.getFavorites({
        ...params,
        page: pagination.value.page,
        page_size: pagination.value.pageSize,
      })
      favorites.value = result.items || []
      pagination.value.total = result.total || 0
      if ((result.items || []).length < pagination.value.pageSize) {
        noMore.value = true
      }
    } catch (err) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  async function addFavorite(note, category = 1, comments = []) {
    try {
      const result = await favoritesApi.addFavorite({
        note_id: note.id,
        category,
        display_title: note.display_title || '',
        cover_url: note.cover_url || '',
        image_urls: note.image_urls || [],
        description: note.desc || '',
        author_name: note.user?.nickname || '',
        author_avatar: note.user?.avatar || '',
        publish_time: String(note.publish_time ?? ''),
        like_count: Number(note.liked_count) || 0,
        collect_count: Number(note.collected_count) || 0,
        comment_count: Number(note.comment_count) || 0,
        xsec_token: note.xsec_token || '',
        comments,
      })
      return result
    } catch (err) {
      error.value = err.message
      throw err
    }
  }

  async function removeFavorite(favoriteId) {
    try {
      await favoritesApi.removeFavorite(favoriteId)
      favorites.value = favorites.value.filter(f => f.id !== favoriteId)
    } catch (err) {
      error.value = err.message
      throw err
    }
  }

  async function checkFavorited(noteId) {
    return favoritesApi.checkFavorited(noteId)
  }

  return {
    favorites, loading, error, pagination, noMore,
    fetchFavorites, addFavorite, removeFavorite, checkFavorited,
  }
})
