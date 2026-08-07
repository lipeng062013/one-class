import { computed, onMounted, onUnmounted, ref } from 'vue'

/** 手机竖屏 / 窄屏（抽屉导航） */
export const MOBILE_MAX = 767
/** 平板及以下：列表改卡片，避免宽表挤压 */
export const COMPACT_MAX = 991
/** Pad landscape and narrow desktop: keep tables, but hide secondary columns. */
export const NARROW_DESKTOP_MAX = 1279

function readWidth() {
  return typeof window !== 'undefined' ? window.innerWidth : 1200
}

/**
 * 响应式断点：供 PC 业务页在 wap / pad 上切换布局。
 * setup 阶段即读取 window，避免首屏误判为桌面宽。
 */
export function useBreakpoint() {
  const width = ref(readWidth())
  const isMobile = ref(width.value <= MOBILE_MAX)
  const isCompact = ref(width.value <= COMPACT_MAX)
  const isPad = computed(() => width.value > MOBILE_MAX && width.value <= COMPACT_MAX)
  const isPadPortrait = computed(() => isPad.value && width.value < 900)
  const isPadLandscape = computed(() => isPad.value && width.value >= 900)
  const isNarrowDesktop = computed(
    () => width.value > COMPACT_MAX && width.value <= NARROW_DESKTOP_MAX,
  )

  function update() {
    width.value = readWidth()
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
    isMobile,
    isPad,
    isPadPortrait,
    isPadLandscape,
    isCompact,
    isNarrowDesktop,
  }
}
