<template>
  <div class="location-container">
    <PageHeader title="定位服务" :showBack="true" />

    <!-- 高德地图区域 -->
    <div class="map-container">
      <AMapView
        ref="mapRef"
        height="300px"
        :center="mapCenter"
        :zoom="zoomLevel"
        :markers="mapMarkers"
        :circle="radiusCircle"
        @ready="onMapReady"
        @click="onMapClick"
        @moveend="onMapMoveEnd"
      >
        <van-button size="small" icon="aim" @click="relocate" :loading="relocating">
          重新定位
        </van-button>
      </AMapView>
    </div>

    <!-- 地点搜索栏 -->
    <div class="search-section card">
      <div class="search-bar">
        <van-icon name="search" size="18" color="#999" />
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索地点、地址..."
          @input="onSearchInput"
          @keydown="onSearchKeydown"
          @focus="showDropdown = true"
        />
        <van-icon
          v-if="searchQuery"
          name="clear"
          size="18"
          color="#999"
          class="clear-icon"
          @click="clearSearch"
        />
        <van-loading v-if="searchLoading" size="18" color="#667eea" />
      </div>

      <!-- 下拉候选列表 -->
      <div v-if="showDropdown && searchQuery.trim()" class="search-dropdown">
        <div v-if="searchLoading && !searchResults.length" class="dropdown-loading">
          <van-loading size="20" color="#667eea" />
          <span>搜索中...</span>
        </div>
        <div v-else-if="searchResults.length === 0 && !searchLoading" class="dropdown-empty">
          <van-icon name="search" size="24" color="#ccc" />
          <span>未找到相关地点</span>
        </div>
        <div v-else class="dropdown-list">
          <div
            v-for="(tip, index) in searchResults"
            :key="tip.id || index"
            class="dropdown-item"
            :class="{ 'is-active': index === activeIndex }"
            @click="selectTip(tip)"
            @mouseenter="activeIndex = index"
          >
            <div class="tip-icon">
              <van-icon name="location-o" size="16" color="#667eea" />
            </div>
            <div class="tip-content">
              <div class="tip-name">{{ tip.name }}</div>
              <div class="tip-address" v-if="tip.address || tip.district">
                {{ tip.district }}{{ tip.address ? ' ' + tip.address : '' }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 当前位置信息 -->
    <div class="location-info card">
      <div class="info-header">
        <van-icon name="location" color="#667eea" size="20" />
        <span class="info-title">当前位置</span>
        <van-tag v-if="positionLoading" type="warning" size="medium">定位中</van-tag>
        <van-tag v-else-if="positionError" type="danger" size="medium">定位失败</van-tag>
        <van-tag v-else-if="currentCity" type="success" size="medium">已定位</van-tag>
        <van-tag v-else type="warning" size="medium">未定位</van-tag>
      </div>
      <div class="info-content">
        <!-- 定位加载中 -->
        <div v-if="positionLoading" class="position-loading">
          <van-loading size="16" color="#667eea" />
          <span>正在获取您的位置信息...</span>
        </div>
        <!-- 定位失败 -->
        <div v-else-if="positionError" class="position-error">
          <p class="error-text">{{ positionError }}</p>
          <van-button size="small" type="primary" plain @click="retryPosition">
            重新定位
          </van-button>
        </div>
        <!-- 定位成功 -->
        <template v-else>
          <p class="address">{{ currentAddress || '未知位置' }}</p>
          <p class="coordinate" v-if="mapCenter && mapCenter.length === 2">
            坐标: {{ mapCenter[1].toFixed(6) }}, {{ mapCenter[0].toFixed(6) }}
          </p>
          <p class="city" v-if="currentCity">
            {{ currentCity }} {{ currentDistrict }}
          </p>
        </template>
      </div>
    </div>

    <!-- 搜索半径设置（增强版） -->
    <div class="radius-setting card">
      <div class="setting-header">
        <span class="setting-title">搜索半径</span>
        <div class="radius-value-group">
          <span class="setting-value">{{ formatRadius(radiusValue) }}</span>
          <van-icon v-if="radiusWarning" name="info-o" size="16" color="#ff976a" @click="showRadiusTip" />
        </div>
      </div>

      <!-- 预设快捷按钮 -->
      <div class="radius-presets">
        <button
          v-for="preset in radiusPresets"
          :key="preset.value"
          class="preset-btn"
          :class="{ active: radiusValue === preset.value }"
          @click="setRadius(preset.value)"
        >
          {{ preset.label }}
        </button>
      </div>

      <!-- 平滑缩放滑杆 -->
      <van-slider
        v-model="radiusValue"
        :min="radiusMin"
        :max="radiusMax"
        :step="radiusStep"
        :active-color="radiusWarning ? '#ff976a' : '#667eea'"
        bar-height="4px"
        @change="onRadiusChange"
        @drag-end="onRadiusChange"
      />
      <div class="radius-labels">
        <span>{{ formatRadius(radiusMin) }}</span>
        <span class="radius-limit-hint" v-if="isNearMax">已接近上限</span>
        <span>{{ formatRadius(radiusMax) }}</span>
      </div>

      <!-- 自定义输入 -->
      <div class="radius-input-row">
        <span class="radius-input-label">自定义半径：</span>
        <div class="radius-input-group">
          <input
            v-model="radiusInput"
            type="number"
            :min="radiusMin"
            :max="radiusMax"
            class="radius-input"
            :class="{ 'has-error': radiusInputError }"
            @change="applyCustomRadius"
            @keyup.enter="applyCustomRadius"
          />
          <span class="radius-input-unit">m</span>
          <van-button size="mini" type="primary" plain @click="applyCustomRadius">应用</van-button>
        </div>
      </div>
      <p v-if="radiusInputError" class="radius-error">{{ radiusInputError }}</p>
    </div>

    <!-- 周边搜索与结果 -->
    <div class="nearby-section card">
      <div class="section-header">
        <div class="section-title-group">
          <span class="section-title">周边搜索</span>
          <span class="section-subtitle">{{ formatRadius(radiusValue) }}内</span>
        </div>
        <van-button
          size="small"
          :type="nearbySearching ? 'default' : 'primary'"
          icon="search"
          :loading="nearbySearching"
          :disabled="nearbySearching"
          @click="searchNearby('')"
        >
          {{ nearbySearching ? '搜索中' : '搜索周边' }}
        </van-button>
      </div>

      <!-- 分类快捷搜索 -->
      <div class="nearby-types" v-if="!nearbySearching">
        <button
          v-for="cat in nearbyCategories"
          :key="cat.type"
          class="type-btn"
          :class="{ active: nearbyActiveType === cat.type }"
          @click="searchNearby(cat.type, cat.label)"
        >
          <van-icon :name="cat.icon" size="16" />
          <span>{{ cat.label }}</span>
        </button>
      </div>

      <!-- 搜索结果 -->
      <div v-if="nearbyResults.length > 0" class="nearby-results">
        <div class="results-header">
          <span>找到 {{ nearbyTotal }} 个结果</span>
        </div>
        <div class="results-scroll" ref="resultsScrollRef">
          <div class="results-list">
            <div
              v-for="(poi, index) in nearbyResults"
              :key="poi.id || index"
              class="result-item"
              @click="focusPOI(poi)"
            >
              <div class="poi-icon">
                <van-icon name="location-o" size="18" color="#667eea" />
              </div>
              <div class="poi-info">
                <div class="poi-name">{{ poi.name }}</div>
                <div class="poi-address">{{ poi.address || '暂无地址' }}</div>
              </div>
              <div class="poi-tags">
                <span v-if="poi.distance" class="poi-distance-tag">{{ formatDistance(poi.distance) }}</span>
                <span v-if="poi.rating" class="poi-rating-tag">{{ poi.rating }}</span>
              </div>
            </div>
          </div>
          <!-- 无限滚动触发哨兵 -->
          <div ref="scrollSentinelRef" class="scroll-sentinel">
            <div v-if="nearbySearching && nearbyResults.length > 0" class="scroll-loading">
              <van-loading size="16" color="#667eea" />
              <span>加载更多...</span>
            </div>
            <div v-else-if="!nearbyHasMore && nearbyResults.length >= POI_PAGE_SIZE" class="scroll-all-loaded">
              <span>已加载全部</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态提示 -->
      <EmptyState
        v-if="nearbySearched && !nearbySearching && nearbyResults.length === 0"
        description="当前范围内未找到附近地点"
        actionText="扩大搜索范围"
        @action="expandRadius"
      />
    </div>

    <!-- 常用位置列表 -->
    <div class="favorites-section card">
      <div class="section-header">
        <span class="section-title">常用位置</span>
        <van-button size="small" type="primary" icon="plus" @click="openAddDialog">
          添加
        </van-button>
      </div>
      <div class="favorites-list" v-if="locationStore.favoriteLocations.length">
        <div
          v-for="location in locationStore.favoriteLocations"
          :key="location.id"
          class="favorite-item"
          @click="switchLocation(location.id)"
        >
          <div class="favorite-icon">
            <van-icon :name="getLocationIcon(location.name)" color="#667eea" size="24" />
          </div>
          <div class="favorite-info">
            <span class="favorite-name">{{ location.name }}</span>
            <span class="favorite-address">{{ location.address }}</span>
          </div>
          <div class="favorite-actions">
            <van-icon name="edit" class="action-icon" @click.stop="editLocation(location)" />
            <van-icon name="delete" class="action-icon danger" @click.stop="deleteLocation(location.id)" />
          </div>
        </div>
      </div>
      <EmptyState v-else description="暂无常用位置" actionText="添加位置" @action="openAddDialog" />
    </div>

    <!-- 添加/编辑位置弹窗 -->
    <van-dialog
      v-model:show="showAddDialog"
      :title="editMode ? '编辑常用位置' : '添加常用位置'"
      show-cancel-button
      @confirm="saveLocation"
      @cancel="resetForm"
    >
      <div class="dialog-form">
        <van-field
          v-model="locationForm.name"
          label="位置名称"
          placeholder="如：家、公司、学校"
          :rules="[{ required: true, message: '请输入位置名称' }]"
        />
        <van-field
          v-model="locationForm.address"
          label="详细地址"
          placeholder="输入地址"
          clearable
          :rules="[{ required: true, message: '请输入地址' }]"
        />
      </div>
    </van-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useLocationStore } from '@/stores/location'
import { showToast, showConfirmDialog, showDialog } from 'vant'
import { regeocode, inputTips, searchAround, getRadiusConfig } from '@/api/amap'
import { locate, clearPositionCache } from '@/services/positionService'
import PageHeader from '@/components/PageHeader.vue'
import EmptyState from '@/components/EmptyState.vue'
import AMapView from '@/components/AMapView.vue'

const router = useRouter()
const locationStore = useLocationStore()
const mapRef = ref(null)
const searchInputRef = ref(null)

// ===== 搜索相关状态 =====
const searchQuery = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const showDropdown = ref(false)
const activeIndex = ref(-1)
let debounceTimer = null

// ===== 无限滚动 =====
const resultsScrollRef = ref(null)
const scrollSentinelRef = ref(null)
let scrollObserver = null

// ===== 半径配置 =====
const radiusConfig = ref(null)         // 从后端获取的配置
const radiusMin = ref(100)
const radiusMax = ref(50000)
const radiusStep = ref(100)
const radiusValue = ref(3000)          // 当前半径值（受控）
const radiusInput = ref('3000')        // 自定义输入文本
const radiusInputError = ref('')       // 输入校验错误
const radiusPresets = ref([])          // 预设按钮列表

// 计算是否接近上限
const isNearMax = computed(() => radiusValue.value >= radiusMax.value * 0.8)
const radiusWarning = computed(() => isNearMax.value)

// ===== 周边搜索状态 =====
const nearbySearching = ref(false)
const nearbyResults = ref([])
const nearbyTotal = ref(0)
const nearbyPage = ref(1)
const nearbyHasMore = ref(false)
const nearbySearched = ref(false)
const nearbyActiveType = ref('')
const nearbySearchLabel = ref('')
const POI_PAGE_SIZE = 20

// 周边搜索分类（编码对应高德地图Web服务API POI分类体系）
// 参考：https://lbs.amap.com/api/webservice/guide/api/search
// 050000=餐饮服务, 060000=购物服务, 070000=生活服务,
// 080000=体育休闲服务(娱乐), 090000=医疗保健服务,
// 140000=科教文化服务(教育), 150000=交通设施服务
const nearbyCategories = [
  { type: '',       label: '全部',      icon: 'search' },
  { type: '050000', label: '餐饮',      icon: 'point-gift' },
  { type: '060000', label: '购物',      icon: 'shopping-cart-o' },
  { type: '150000', label: '交通',      icon: 'logistics' },
  { type: '140000', label: '教育',      icon: 'bookmark-o' },
  { type: '070000', label: '生活',      icon: 'gem-o' },
  { type: '080000', label: '娱乐',      icon: 'tv-o' },
  { type: '090000', label: '医疗',      icon: 'plus' },
]

// ===== 定位相关状态 =====
const positionLoading = ref(true)
const positionError = ref('')
const relocating = ref(false)

// ===== 其他状态 =====
const showAddDialog = ref(false)
const editMode = ref(false)
const editingId = ref(null)
const locationForm = ref({ name: '', address: '' })

// 地图状态（初始为 null，定位成功后才赋值）
const mapCenter = ref(null)
const zoomLevel = ref(15)
const mapMarkers = ref([])
const currentAddress = ref('')
const currentCity = ref('')
const currentDistrict = ref('')

// 半径可视化（传给 AMapView）
const radiusCircle = computed(() => {
  if (!radiusValue.value || !mapCenter.value) return null
  return {
    radius: radiusValue.value,
    center: mapCenter.value,
    color: radiusWarning.value ? '#ff976a' : '#667eea',
    opacity: radiusWarning.value ? 0.12 : 0.08
  }
})

onMounted(async () => {
  await locationStore.fetchFavoriteLocations()

  // 获取半径配置
  try {
    const config = await getRadiusConfig()
    radiusConfig.value = config
    radiusMin.value = config.min
    radiusMax.value = config.max
    radiusStep.value = config.step
    radiusPresets.value = config.presets
    radiusValue.value = config.default
    radiusInput.value = String(config.default)
  } catch (err) {
    console.error('获取半径配置失败，使用默认值:', err)
  }

  // 使用高德定位MCP服务获取位置
  await doPosition()

  // 点击外部关闭下拉
  document.addEventListener('click', handleClickOutside)

  // 初始化无限滚动观察器
  initScrollObserver()
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  if (debounceTimer) clearTimeout(debounceTimer)
  destroyScrollObserver()
})

/**
 * 核心定位函数：调用高德定位MCP服务
 * 内置10m容错缓存，位置未变化时不重复请求
 */
async function doPosition() {
  positionLoading.value = true
  positionError.value = ''

  const result = await locate({ forceRefresh: false })

  if (result.success && result.data) {
    const { latitude, longitude, address, province, city, district, adcode, source, reused } = result.data

    // 更新地图/UI状态
    currentAddress.value = address || '未知位置'
    currentCity.value = city || ''
    currentDistrict.value = district || ''
    mapCenter.value = [longitude, latitude]
    zoomLevel.value = 15

    mapMarkers.value = [{
      position: [longitude, latitude],
      title: '当前位置',
      info: `<div style="padding:8px;font-size:13px;"><b>当前位置</b></div>`
    }]

    // 同步到 store
    locationStore.setLocation({
      latitude,
      longitude,
      address: address,
      city: city || '',
      district: district || '',
      province: province || '',
      adcode: adcode || ''
    })

    // 若复用了缓存，静默提示
    if (reused) {
      console.log('[定位MCP] 位置未发生明显变化，复用缓存数据')
    } else {
      const sourceLabel = { jsapi: '高德JSAPI', browser: '浏览器', ip: 'IP定位' }[source] || source
      console.log(`[定位MCP] 定位成功（${sourceLabel}）: ${address}`)
    }

    positionLoading.value = false
  } else {
    // 定位完全失败，回退到默认定位（广州北京路步行街）
    const fallbackLat = 23.126
    const fallbackLng = 113.264
    const fallback = {
      latitude: fallbackLat,
      longitude: fallbackLng,
      address: '广州市越秀区北京路步行街',
      city: '广州',
      district: '越秀区',
      province: '广东省',
      adcode: '440100'
    }

    console.warn('[定位MCP] 定位完全失败（详情见上方日志），使用默认位置（广州北京路）:', result.error)

    currentAddress.value = fallback.address
    currentCity.value = fallback.city
    currentDistrict.value = fallback.district
    mapCenter.value = [fallback.longitude, fallback.latitude]
    zoomLevel.value = 15

    mapMarkers.value = [{
      position: [fallback.longitude, fallback.latitude],
      title: '当前位置（默认）',
      info: `<div style="padding:8px;font-size:13px;"><b>当前位置（默认）</b></div>`
    }]

    locationStore.setLocation(fallback)

    // 保留错误提示，但用 toast 轻提示代替阻断
    positionError.value = ''
    const errMsg = result.error || '定位失败'
    showToast(`${errMsg}，已使用默认位置`)
    positionLoading.value = false
  }
}

/** 重新定位（用户主动触发，清除缓存） */
async function retryPosition() {
  clearPositionCache()
  await doPosition()
}

async function updateLocation(latitude, longitude, cityName, districtName, addressText, source = 'gps') {
  mapCenter.value = [longitude, latitude]
  mapMarkers.value = [{
    position: [longitude, latitude],
    title: '当前位置',
    info: `<div style="padding:8px;font-size:13px;"><b>当前位置</b></div>`
  }]

  // 如果传入了地址信息直接用，否则逆地理编码
  if (addressText && cityName) {
    currentAddress.value = addressText
    currentCity.value = cityName
    currentDistrict.value = districtName || ''
    locationStore.setLocation({
      latitude,
      longitude,
      address: addressText,
      city: cityName,
      district: districtName || '',
      adcode: ''
    }, source)
    return
  }

  try {
    // 使用高德逆地理编码获取详细地址
    const result = await regeocode(latitude, longitude)
    currentAddress.value = result.address
    currentCity.value = result.city
    currentDistrict.value = result.district

    // 同步到 store
    locationStore.setLocation({
      latitude,
      longitude,
      address: result.address,
      city: result.city,
      district: result.district,
      province: result.province,
      adcode: result.adcode
    })
  } catch (err) {
    currentAddress.value = `${latitude.toFixed(4)}, ${longitude.toFixed(4)}`
    console.error('逆地理编码失败:', err)
  }
}

function goBack() {
  router.back()
}

async function relocate() {
  relocating.value = true
  showToast('正在重新定位...')

  // 强制刷新（忽略缓存）
  positionLoading.value = true
  positionError.value = ''
  clearPositionCache()

  const result = await locate({ forceRefresh: true })

  if (result.success && result.data) {
    const { latitude, longitude, address, city, district } = result.data
    await updateLocation(latitude, longitude, city, district, address)
    showToast('定位成功')
  } else {
    positionError.value = result.error || '定位失败'
    showToast('定位失败，请重试')
  }

  positionLoading.value = false
  relocating.value = false
}

// ========== 半径功能 ==========

function formatRadius(meters) {
  if (meters >= 1000) {
    const km = (meters / 1000).toFixed(meters % 1000 === 0 ? 0 : 1)
    return `${km}km`
  }
  return `${meters}m`
}

function formatDistance(meters) {
  if (!meters || meters === 0) return ''
  if (meters < 1000) return `${Math.round(meters)}m`
  return `${(meters / 1000).toFixed(1)}km`
}

function setRadius(value) {
  const clamped = Math.max(radiusMin.value, Math.min(value, radiusMax.value))
  radiusValue.value = clamped
  radiusInput.value = String(clamped)
  radiusInputError.value = ''
  onRadiusChange(clamped)
}

function onRadiusChange(value) {
  radiusValue.value = Math.max(radiusMin.value, Math.min(value, radiusMax.value))
  radiusInput.value = String(radiusValue.value)
  radiusInputError.value = ''
  // 根据半径自适应缩放
  adjustZoomByRadius()
}

function adjustZoomByRadius() {
  const r = radiusValue.value
  if (r <= 500) zoomLevel.value = 17
  else if (r <= 1000) zoomLevel.value = 16
  else if (r <= 3000) zoomLevel.value = 15
  else if (r <= 5000) zoomLevel.value = 14
  else if (r <= 10000) zoomLevel.value = 13
  else if (r <= 20000) zoomLevel.value = 12
  else zoomLevel.value = 11
}

function applyCustomRadius() {
  const val = parseInt(radiusInput.value, 10)
  if (isNaN(val) || val < radiusMin.value) {
    radiusInputError.value = `最小半径 ${formatRadius(radiusMin.value)}`
    return
  }
  if (val > radiusMax.value) {
    radiusInputError.value = `最大半径 ${formatRadius(radiusMax.value)}，已自动截断`
    radiusValue.value = radiusMax.value
    radiusInput.value = String(radiusMax.value)
    onRadiusChange(radiusMax.value)
    return
  }
  radiusInputError.value = ''
  setRadius(val)
}

function showRadiusTip() {
  showDialog({
    title: '半径提示',
    message: `当前搜索半径为 ${formatRadius(radiusValue.value)}，已达到最大范围 ${formatRadius(radiusMax.value)} 的 ${Math.round(radiusValue.value / radiusMax.value * 100)}%。过大的搜索范围可能导致返回结果不够精确。建议根据实际需要选择合适范围。`,
    confirmButtonText: '知道了'
  })
}

function expandRadius() {
  const newVal = Math.min(radiusValue.value * 2, radiusMax.value)
  setRadius(newVal)
  searchNearby(nearbyActiveType.value, nearbySearchLabel.value)
}

// ========== 周边搜索功能 ==========

async function searchNearby(type = '', label = '') {
  if (!mapCenter.value || mapCenter.value.length < 2) {
    showToast('请先定位')
    return
  }

  nearbyActiveType.value = type
  nearbySearchLabel.value = label || type
  nearbySearching.value = true
  nearbySearched.value = true
  nearbyPage.value = 1

  try {
    const result = await searchAround({
      latitude: mapCenter.value[1],
      longitude: mapCenter.value[0],
      radius: radiusValue.value,
      types: type,
      page: 1,
      pageSize: POI_PAGE_SIZE
    })
    nearbyResults.value = result.pois || []
    nearbyTotal.value = result.total || 0
    nearbyHasMore.value = nearbyResults.value.length < nearbyTotal.value
  } catch (err) {
    console.error('周边搜索失败:', err)
    showToast('搜索失败')
    nearbyResults.value = []
    nearbyTotal.value = 0
  } finally {
    nearbySearching.value = false
    attachScrollObserver()
  }
}

async function loadMoreNearby() {
  if (nearbySearching.value || !nearbyHasMore.value) return
  nearbySearching.value = true
  nearbyPage.value++

  try {
    const result = await searchAround({
      latitude: mapCenter.value[1],
      longitude: mapCenter.value[0],
      radius: radiusValue.value,
      types: nearbyActiveType.value,
      page: nearbyPage.value,
      pageSize: POI_PAGE_SIZE
    })
    const newPois = result.pois || []
    nearbyResults.value = [...nearbyResults.value, ...newPois]
    nearbyTotal.value = result.total || 0
    nearbyHasMore.value = nearbyResults.value.length < nearbyTotal.value
  } catch (err) {
    console.error('加载更多失败:', err)
    nearbyPage.value--
    showToast('加载失败')
  } finally {
    nearbySearching.value = false
    attachScrollObserver()
  }
}

// ========== 无限滚动 ==========

function initScrollObserver() {
  destroyScrollObserver()
  scrollObserver = new IntersectionObserver((entries) => {
    const entry = entries[0]
    if (entry.isIntersecting && nearbyHasMore.value && !nearbySearching.value) {
      loadMoreNearby()
    }
  }, {
    root: resultsScrollRef.value,
    rootMargin: '20px',
    threshold: 0
  })
}

function destroyScrollObserver() {
  if (scrollObserver) {
    scrollObserver.disconnect()
    scrollObserver = null
  }
}

/** 每次搜索结果更新后重新附着观察器 */
function attachScrollObserver() {
  destroyScrollObserver()
  if (!nearbyHasMore.value) return
  nextTick(() => {
    if (scrollSentinelRef.value) {
      initScrollObserver()
      scrollObserver.observe(scrollSentinelRef.value)
    }
  })
}

function focusPOI(poi) {
  if (!poi.location) return
  const parts = poi.location.split(',')
  if (parts.length !== 2) return
  const lng = parseFloat(parts[0])
  const lat = parseFloat(parts[1])
  if (isNaN(lng) || isNaN(lat)) return
  mapCenter.value = [lng, lat]
  zoomLevel.value = 16
  mapMarkers.value = [{
    position: [lng, lat],
    title: poi.name,
    info: `<div style="padding:8px;font-size:13px;"><b>${poi.name}</b><br/>${poi.address || ''}</div>`
  }]
}

// ========== 搜索功能 ==========

function handleClickOutside(e) {
  const searchSection = document.querySelector('.search-section')
  if (searchSection && !searchSection.contains(e.target)) {
    showDropdown.value = false
  }
}

function onSearchInput() {
  if (debounceTimer) clearTimeout(debounceTimer)

  if (!searchQuery.value.trim()) {
    searchResults.value = []
    activeIndex.value = -1
    return
  }

  debounceTimer = setTimeout(() => {
    performSearch(searchQuery.value.trim())
  }, 300)
}

async function performSearch(keywords) {
  if (!keywords) return

  searchLoading.value = true
  showDropdown.value = true
  activeIndex.value = -1

  try {
    // 不传 city 和 citylimit，让高德 API 返回全国范围结果
    // 用户可输入城市名自由搜索任意城市
    const result = await inputTips({
      keywords
    })
    searchResults.value = result.tips || []
  } catch (err) {
    console.error('搜索失败:', err)
    searchResults.value = []
  } finally {
    searchLoading.value = false
  }
}

function onSearchKeydown(e) {
  if (!showDropdown.value || !searchResults.value.length) return

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    activeIndex.value = Math.min(activeIndex.value + 1, searchResults.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    activeIndex.value = Math.max(activeIndex.value - 1, 0)
  } else if (e.key === 'Enter') {
    e.preventDefault()
    if (activeIndex.value >= 0 && activeIndex.value < searchResults.value.length) {
      selectTip(searchResults.value[activeIndex.value])
    }
  } else if (e.key === 'Escape') {
    showDropdown.value = false
  }
}

async function selectTip(tip) {
  showDropdown.value = false
  searchQuery.value = tip.name

  if (tip.location && tip.location.longitude && tip.location.latitude) {
    await updateLocation(tip.location.latitude, tip.location.longitude, '', '', '', 'search')
    locationStore.searchLocationName = tip.name
    showToast(`已定位到: ${tip.name}`)
  } else {
    showToast('该地点无坐标信息')
  }
}

function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  activeIndex.value = -1
  showDropdown.value = false
  searchInputRef.value?.focus()
}

function onMapReady() {
  // 地图初始化完成
}

function onMapClick(e) {
  // 用户点击地图选择新位置时，通过逆地理获取详细地址
  updateLocation(e.latitude, e.longitude, '', '', '')
}

function onMapMoveEnd(e) {
  // 用户拖拽地图后可选更新（暂不自动触发更新以避免频繁 API 调用）
}

function getLocationIcon(name) {
  if (name.includes('家') || /home/i.test(name)) return 'wap-home-o'
  if (name.includes('公司') || /工作|办公/i.test(name)) return 'work-o'
  if (name.includes('学校') || name.includes('大学')) return 'education-o'
  return 'location-o'
}

function openAddDialog() {
  editMode.value = false
  editingId.value = null
  locationForm.value = { name: '', address: '' }
  showAddDialog.value = true
}

function editLocation(location) {
  editMode.value = true
  editingId.value = location.id
  locationForm.value = { name: location.name, address: location.address }
  showAddDialog.value = true
}

function resetForm() {
  locationForm.value = { name: '', address: '' }
  editMode.value = false
  editingId.value = null
}

async function switchLocation(locationId) {
  try {
    await locationStore.switchLocation(locationId)
    locationStore.locationSource = 'saved'
    showToast('切换成功')
  } catch {
    showToast('切换失败')
  }
}

async function deleteLocation(locationId) {
  try {
    await showConfirmDialog({
      title: '确认删除',
      message: '确定要删除这个常用位置吗？'
    })
    await locationStore.removeFavoriteLocation(locationId)
    showToast('删除成功')
  } catch (err) {
    if (err !== 'cancel') showToast('删除失败')
  }
}

async function saveLocation() {
  if (!locationForm.value.name || !locationForm.value.address) {
    showToast('请填写完整信息')
    return
  }
  try {
    if (editMode.value && editingId.value) {
      await locationStore.updateFavoriteLocation(editingId.value, locationForm.value)
      showToast('修改成功')
    } else {
      await locationStore.addFavoriteLocation(locationForm.value)
      showToast('添加成功')
    }
    showAddDialog.value = false
    resetForm()
  } catch {
    showToast(editMode.value ? '修改失败' : '添加失败')
  }
}
</script>

<style scoped>
.location-container {
  min-height: 100vh;
  background-color: #f5f5f5;
  padding-bottom: 24px;
}
.card {
  background: white;
  padding: 16px;
  margin: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.map-container {
  position: relative;
  height: 300px;
  background: #e8e8e8;
}

/* 搜索栏样式 */
.search-section {
  position: relative;
  padding: 12px 16px;
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 10px 14px;
  border: 2px solid transparent;
  transition: border-color 0.2s, background 0.2s;
}

.search-bar:focus-within {
  border-color: #667eea;
  background: #fff;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: #333;
  padding: 0;
}

.search-input::placeholder {
  color: #999;
}

.clear-icon {
  cursor: pointer;
  transition: color 0.2s;
}

.clear-icon:hover {
  color: #667eea;
}

.search-dropdown {
  position: absolute;
  top: 100%;
  left: 16px;
  right: 16px;
  background: #fff;
  border-radius: 0 0 12px 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  max-height: 300px;
  overflow-y: auto;
  z-index: 100;
}

.dropdown-loading,
.dropdown-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 20px;
  color: #999;
  font-size: 14px;
}

.dropdown-list {
  padding: 4px 0;
}

.dropdown-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.15s;
}

.dropdown-item:hover,
.dropdown-item.is-active {
  background: #f5f7fa;
}

.tip-icon {
  margin-top: 2px;
  flex-shrink: 0;
}

.tip-content {
  flex: 1;
  min-width: 0;
}

.tip-name {
  font-size: 14px;
  color: #333;
  font-weight: 500;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tip-address {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.info-title { font-size: 16px; font-weight: 600; color: #333; flex: 1; }
.info-content { padding-left: 28px; }
.position-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 14px;
  color: #999;
}
.position-error {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}
.error-text { font-size: 14px; color: #ff4757; margin: 0; }
.address { font-size: 14px; color: #333; margin: 0 0 4px; }
.coordinate { font-size: 11px; color: #999; margin: 0 0 4px; font-family: monospace; }
.city { font-size: 12px; color: #666; margin: 0; }
.setting-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
}
.setting-title { font-size: 16px; font-weight: 600; color: #333; }
.radius-value-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.setting-value { font-size: 14px; color: #667eea; font-weight: 600; }

/* 预设快捷按钮 */
.radius-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}
.preset-btn {
  padding: 4px 10px;
  border: 1px solid #e0e0e0;
  border-radius: 14px;
  background: #fff;
  font-size: 12px;
  color: #666;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.preset-btn:hover { border-color: #667eea; color: #667eea; }
.preset-btn.active {
  background: #667eea;
  color: #fff;
  border-color: #667eea;
}
.radius-labels {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  color: #999;
  margin-top: 6px;
  padding: 0 2px;
}
.radius-limit-hint {
  color: #ff976a;
  font-weight: 600;
}
/* 自定义输入 */
.radius-input-row {
  display: flex;
  align-items: center;
  margin-top: 12px;
  gap: 8px;
}
.radius-input-label {
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}
.radius-input-group {
  display: flex;
  align-items: center;
  gap: 6px;
}
.radius-input {
  width: 80px;
  padding: 4px 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 13px;
  text-align: right;
  outline: none;
  transition: border-color 0.2s;
}
.radius-input:focus { border-color: #667eea; }
.radius-input.has-error { border-color: #ff4757; }
.radius-input-unit { font-size: 12px; color: #999; }
.radius-error {
  margin: 4px 0 0;
  font-size: 11px;
  color: #ff4757;
}

/* 周边搜索面板 */
.nearby-section {
  padding: 16px;
}
.section-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
}
.section-title-group {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.section-title { font-size: 16px; font-weight: 600; color: #333; }
.section-subtitle { font-size: 12px; color: #999; }
.nearby-types {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.type-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #eee;
  border-radius: 16px;
  background: #fafafa;
  font-size: 12px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}
.type-btn:hover { border-color: #667eea; color: #667eea; }
.type-btn.active {
  background: rgba(102, 126, 234, 0.08);
  color: #667eea;
  border-color: #667eea;
}
/* 搜索结果 */
.nearby-results { margin-top: 4px; }
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #666;
}
/* 可滚动结果容器 - 约10项高度 */
.results-scroll {
  max-height: 420px;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
}
.results-scroll::-webkit-scrollbar {
  width: 4px;
}
.results-scroll::-webkit-scrollbar-track {
  background: transparent;
}
.results-scroll::-webkit-scrollbar-thumb {
  background: #ddd;
  border-radius: 2px;
}
.results-scroll::-webkit-scrollbar-thumb:hover {
  background: #bbb;
}
.results-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
/* 无限滚动哨兵 */
.scroll-sentinel {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 8px 0;
}
.scroll-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #999;
  animation: fadeInUp 0.3s ease;
}
.scroll-all-loaded {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.scroll-all-loaded span {
  font-size: 12px;
  color: #ccc;
  position: relative;
}
.scroll-all-loaded span::before,
.scroll-all-loaded span::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 40px;
  height: 1px;
  background: #e8e8e8;
}
.scroll-all-loaded span::before {
  right: calc(100% + 8px);
}
.scroll-all-loaded span::after {
  left: calc(100% + 8px);
}
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.result-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #f9f9f9;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}
.result-item:hover,
.result-item:active { background: #f0f0f0; }
.poi-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: rgba(102, 126, 234, 0.1);
  flex-shrink: 0;
}
.poi-info {
  flex: 1;
  min-width: 0;
}
.poi-name {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}
.poi-address {
  font-size: 12px;
  color: #999;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}
.poi-tags {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 4px;
}
.poi-distance-tag {
  font-size: 11px;
  color: #667eea;
  font-weight: 600;
  background: rgba(102, 126, 234, 0.08);
  padding: 3px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.poi-rating-tag {
  font-size: 10px;
  color: #fff;
  font-weight: 700;
  background: #ff6b35;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1.2;
}
.favorites-list { display: flex; flex-direction: column; gap: 8px; }
.favorite-item {
  display: flex; align-items: center; gap: 12px; padding: 12px;
  background: #f9f9f9; border-radius: 8px; cursor: pointer;
  transition: background 0.2s, transform 0.2s;
}
.favorite-item:active { background: #f0f0f0; transform: scale(0.98); }
.favorite-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: rgba(102, 126, 234, 0.1);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.favorite-info { flex: 1; min-width: 0; }
.favorite-name { font-size: 14px; font-weight: 600; color: #333; display: block; margin-bottom: 2px; }
.favorite-address {
  font-size: 12px; color: #666; display: block;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.favorite-actions { display: flex; gap: 12px; color: #999; }
.action-icon { padding: 4px; cursor: pointer; transition: color 0.2s; }
.action-icon:hover { color: #667eea; }
.action-icon.danger:hover { color: #ff4757; }
.dialog-form { padding: 16px 0; }
@media (max-width: 480px) {
  .card { margin: 8px 12px; padding: 14px; }
  .map-container { height: 240px; }
  .search-section { padding: 10px 12px; }
  .search-dropdown { left: 12px; right: 12px; }
}
</style>
