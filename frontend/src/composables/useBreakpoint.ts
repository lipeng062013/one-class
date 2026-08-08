import { computed, onMounted, onUnmounted, ref } from 'vue'

/** 手机竖屏 / 窄屏（抽屉导航） */
export const MOBILE_MAX = 767
/** App 设备上限：手机与 Pad 都使用触控壳层 */
export const APP_MAX = 1199
/** 兼容旧页面：现有 isCompact 分支先维持到 991，按模块逐步迁移到 isApp */
export const COMPACT_MAX = 991
/** 桌面窄屏：保留桌面侧栏，但减少部分次要列 */
export const NARROW_DESKTOP_MAX = 1279

function readWidth() {
  return typeof window !== 'undefined' ? window.innerWidth : 1200
}

function readHeight() {
  return typeof window !== 'undefined' ? window.innerHeight : 800
}

/**
 * 响应式断点：供 PC 业务页在 wap / pad 上切换布局。
 * setup 阶段即读取 window，避免首屏误判为桌面宽。
 */
export function useBreakpoint() {
  const width = ref(readWidth())
  const height = ref(readHeight())
  const isMobile = ref(width.value <= MOBILE_MAX)
  const isCompact = ref(width.value <= COMPACT_MAX)
  const isPad = computed(() => width.value > MOBILE_MAX && width.value <= APP_MAX)
  const isPadPortrait = computed(() => isPad.value && height.value >= width.value)
  const isPadLandscape = computed(() => isPad.value && width.value > height.value)
  const isApp = computed(() => width.value <= APP_MAX)
  const isDesktop = computed(() => width.value > APP_MAX)
  const mode = computed<'phone' | 'pad-portrait' | 'pad-landscape' | 'desktop'>(() => {
    if (isMobile.value) return 'phone'
    if (isPadPortrait.value) return 'pad-portrait'
    if (isPadLandscape.value) return 'pad-landscape'
    return 'desktop'
  })
  const isNarrowDesktop = computed(
    () => width.value > APP_MAX && width.value <= NARROW_DESKTOP_MAX,
  )

  function update() {
    width.value = readWidth()
    height.value = readHeight()
    isMobile.value = width.value <= MOBILE_MAX
    isCompact.value = width.value <= COMPACT_MAX
  }

  onMounted(() => {
    update()
    window.addEventListener('resize', update)
    // 部分 WebView / 模拟器首帧宽度不准，下一帧再校准
    requestAnimationFrame(update)
  })
  onUnmounted(() => window.removeEventListener('resize', update))

  return {
    width,
    height,
    isMobile,
    isPad,
    isPadPortrait,
    isPadLandscape,
    isApp,
    isDesktop,
    mode,
    isCompact,
    isNarrowDesktop,
  }
}
