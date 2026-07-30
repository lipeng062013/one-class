import { onMounted, onUnmounted, ref } from 'vue'

/** 手机竖屏 / 窄屏（抽屉导航） */
export const MOBILE_MAX = 767
/** 平板及以下：列表改卡片，避免宽表挤压 */
export const COMPACT_MAX = 991

/**
 * 响应式断点：供 PC 业务页在 wap / pad 上切换布局。
 */
export function useBreakpoint() {
  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1200)
  const isMobile = ref(width.value <= MOBILE_MAX)
  const isCompact = ref(width.value <= COMPACT_MAX)

  function update() {
    width.value = window.innerWidth
    isMobile.value = width.value <= MOBILE_MAX
    isCompact.value = width.value <= COMPACT_MAX
  }

  onMounted(() => {
    update()
    window.addEventListener('resize', update)
  })
  onUnmounted(() => window.removeEventListener('resize', update))

  return { width, isMobile, isCompact }
}
