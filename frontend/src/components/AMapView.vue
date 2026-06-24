<template>
  <div :class="['amap-wrapper', className]" :style="wrapperStyle">
    <div ref="mapContainer" class="amap-container" :style="{ height: height }"></div>

    <!-- 地图控件插槽 -->
    <div class="amap-controls" v-if="$slots.default">
      <slot />
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="amap-loading">
      <van-loading size="24" color="#667eea" />
      <span>地图加载中...</span>
    </div>

    <!-- 错误状态 -->
    <div v-if="error" class="amap-error">
      <van-icon name="warning-o" size="24" color="#ff4757" />
      <span>{{ error }}</span>
      <van-button size="small" @click="initMap" type="primary" plain>重试</van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { loadAMapFromEnv } from '@/utils/amap'

const props = defineProps({
  height: { type: String, default: '300px' },
  className: { type: String, default: '' },
  center: { type: Array, default: null },  // 由父组件传入，null时不初始化
  zoom: { type: Number, default: 15 },
  markers: { type: Array, default: () => [] },
  showZoom: { type: Boolean, default: true },
  showTraffic: { type: Boolean, default: false },
  mapStyle: { type: String, default: '' },
  enableScrollWheel: { type: Boolean, default: true },
  editable: { type: Boolean, default: false },
  wrapperStyle: { type: [String, Object], default: '' },
  /** 半径可视化：{ radius: number, center?: array, color?: string, opacity?: number } */
  circle: { type: Object, default: null }
})

const emit = defineEmits(['ready', 'click', 'moveend', 'markerClick', 'locationChange'])

const mapContainer = ref(null)
const loading = ref(true)
const error = ref('')

let map = null
let markerLayer = []
let circleOverlay = null

// 所需加载的高德插件列表
const PLUGINS = [
  'AMap.ToolBar',
  'AMap.Scale',
  'AMap.MapType',
  'AMap.Geolocation',
  'AMap.Traffic'
]

onMounted(async () => {
  await nextTick()
  // 等待 DOM 容器渲染并确保有尺寸
  await waitForContainerSize()
  // 只有 center 不为 null 时才初始化地图
  if (props.center) {
    await initMap()
  } else {
    // center 为 null 时，地图不初始化，取消 loading 并提示等待定位
    loading.value = false
    if (!props.center) {
      error.value = '等待定位中...'
    }
  }
})

onUnmounted(() => {
  destroyMap()
})

watch(() => props.center, async (newCenter) => {
  if (!newCenter) return
  if (map) {
    // 地图已初始化，直接设置中心
    map.setCenter(newCenter)
    updateMarkers()
  } else {
    // 地图尚未初始化（center 从 null → 有值），延迟半帧后初始化
    await nextTick()
    await waitForContainerSize()
    await initMap()
  }
}, { deep: true })

watch(() => props.markers, () => {
  if (map) updateMarkers()
}, { deep: true })

watch(() => props.zoom, (newZoom) => {
  if (map) map.setZoom(newZoom)
})

watch(() => props.circle, (newCircle) => {
  updateCircle()
}, { deep: true, immediate: false })

/**
 * 等待容器元素渲染完成且拥有有效宽高
 */
async function waitForContainerSize() {
  for (let i = 0; i < 50; i++) {
    const el = mapContainer.value
    if (el && el.offsetWidth > 0 && el.offsetHeight > 0) return
    await new Promise(r => setTimeout(r, 100))
  }
  console.warn('AMapView: 容器尺寸为 0，地图可能出现渲染问题')
}

/**
 * 加载高德插件（Promise 化）
 */
function loadPlugins(AMap, plugins) {
  return new Promise((resolve, reject) => {
    AMap.plugin(plugins, () => {
      resolve()
    })
    // 插件加载超时保护
    setTimeout(() => reject(new Error('插件加载超时')), 15000)
  })
}

async function initMap() {
  if (map) return

  loading.value = true
  error.value = ''

  try {
    // 1. 加载 AMap 核心库
    const AMap = await loadAMapFromEnv()

    // 2. 加载所有插件
    await loadPlugins(AMap, PLUGINS)

    // 3. 创建地图实例（此时所有插件已可用）
    map = new AMap.Map(mapContainer.value, {
      center: props.center,
      zoom: props.zoom,
      zooms: [3, 19],
      resizeEnable: true,
      showIndoorMap: false,
      mapStyle: props.mapStyle || '',
      features: ['bg', 'road', 'building', 'point'],
      viewMode: '2D'
    })

    // 4. 添加控件
    // 工具条（包含缩放、定位等）
    if (props.showZoom) {
      map.addControl(new AMap.ToolBar({
        position: {
          top: '10px',
          right: '10px'
        }
      }))
    }

    // 比例尺
    map.addControl(new AMap.Scale())

    // 地图类型切换
    map.addControl(new AMap.MapType({
      defaultType: 0,
      showTraffic: props.showTraffic
    }))

    // 定位插件
    const geolocation = new AMap.Geolocation({
      enableHighAccuracy: true,
      timeout: 10000,
      zoomToAccuracy: true,
      GeoLocationFirst: true,
      buttonPosition: 'RB',
      buttonOffset: new AMap.Pixel(10, 20)
    })
    map.addControl(geolocation)

    // 交通路况层
    if (props.showTraffic) {
      const traffic = new AMap.Traffic()
      traffic.setMap(map)
    }

    // 滚轮缩放
    map.setStatus({ scrollWheel: props.enableScrollWheel })

    // 5. 事件绑定
    map.on('click', (e) => {
      emit('click', {
        latitude: e.lnglat.lat,
        longitude: e.lnglat.lng,
        pixel: e.pixel
      })
    })

    map.on('moveend', () => {
      const center = map.getCenter()
      emit('moveend', {
        latitude: center.lat,
        longitude: center.lng,
        zoom: map.getZoom()
      })
    })

    // 6. 渲染标记
    if (props.markers.length > 0) {
      updateMarkers()
    }

    // 7. 渲染半径圈
    if (props.circle) {
      updateCircle()
    }

    loading.value = false
    emit('ready', map)

  } catch (err) {
    loading.value = false
    error.value = err.message || '地图加载失败'
    console.error('AMap 初始化失败:', err)
  }
}

function updateMarkers() {
  if (!map) return
  clearMarkers()

  const AMap = window.AMap
  if (!AMap) return

  props.markers.forEach((item, index) => {
    let position
    if (Array.isArray(item)) {
      position = item
    } else if (item.position) {
      position = item.position
    } else if (item.latlng) {
      position = [item.latlng.lng || item.latlng.longitude, item.latlng.lat || item.latlng.latitude]
    } else if (item.longitude != null) {
      position = [item.longitude, item.latitude]
    } else {
      return
    }

    const marker = new AMap.Marker({
      position: position,
      title: item.title || item.name || '',
      zIndex: item.zIndex || 100,
      extData: { index, data: item }
    })

    if (item.info) {
      const infoWindow = new AMap.InfoWindow({
        content: item.info,
        offset: new AMap.Pixel(0, -30),
        closeWhenClickMap: true
      })
      marker.on('click', () => {
        infoWindow.open(map, marker.getPosition())
        emit('markerClick', item, index)
      })
    } else {
      marker.on('click', () => {
        emit('markerClick', item, index)
      })
    }

    marker.setMap(map)
    markerLayer.push(marker)
  })

  if (markerLayer.length > 0) {
    map.setFitView(markerLayer, false, [30, 30, 30, 30])
  }
}

function clearMarkers() {
  markerLayer.forEach(m => m.setMap(null))
  markerLayer = []
}

function updateCircle() {
  if (!map || !window.AMap) return
  // 移除旧圆
  if (circleOverlay) {
    circleOverlay.setMap(null)
    circleOverlay = null
  }
  const circleData = props.circle
  if (!circleData || !circleData.radius) return

  const center = circleData.center || props.center
  circleOverlay = new window.AMap.Circle({
    center: center,
    radius: Math.max(100, Math.min(circleData.radius, 50000)),
    strokeColor: circleData.color || '#667eea',
    strokeOpacity: 0.6,
    strokeWeight: 2,
    strokeStyle: 'dashed',
    strokeDasharray: [8, 6],
    fillColor: circleData.color || '#667eea',
    fillOpacity: circleData.opacity ?? 0.08
  })
  circleOverlay.setMap(map)
}

function destroyMap() {
  if (circleOverlay) {
    circleOverlay.setMap(null)
    circleOverlay = null
  }
  if (map) {
    map.destroy()
    map = null
  }
  markerLayer = []
}

function getCenter() {
  if (!map) return null
  const c = map.getCenter()
  return { latitude: c.lat, longitude: c.lng }
}

function setCenter(latlng) {
  if (map) map.setCenter(latlng)
}

function addMarker(options) {
  if (!map || !window.AMap) return null
  const marker = new window.AMap.Marker({
    position: options.position,
    title: options.title || '',
    map: map
  })
  markerLayer.push(marker)
  return marker
}

function calculateDistance(p1, p2) {
  if (!window.AMap) return 0
  return window.AMap.GeometryUtil.distance(p1, p2)
}

defineExpose({
  getCenter, setCenter, addMarker,
  calculateDistance, clearMarkers,
  getMap: () => map
})
</script>

<style scoped>
.amap-wrapper {
  position: relative;
  width: 100%;
  min-height: 200px;
}
.amap-container {
  width: 100%;
  height: 100%;
}
.amap-controls {
  position: absolute;
  bottom: 16px;
  right: 16px;
  z-index: 10;
}
.amap-loading,
.amap-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: #f5f5f5;
  color: #666;
  font-size: 14px;
  z-index: 5;
}
.amap-error {
  background: #fff5f5;
  color: #ff4757;
}
</style>
