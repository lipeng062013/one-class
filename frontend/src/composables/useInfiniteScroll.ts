import { computed, nextTick, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'

const DEFAULT_CHUNK = 10

/**
 * 移动端 / pad 列表：首屏加载 chunk 条，滚动到底部再加载 chunk 条。
 * 数据源为已在内存中的全量列表（筛选后），不额外请求接口。
 */
export function useInfiniteScroll<T>(
  source: Ref<T[]>,
  options?: {
    chunk?: number
    /** 仅在 enabled 为 true 时观察（如 isCompact） */
    enabled?: Ref<boolean>
    /** 可选：由页面声明并在模板 ref 绑定，避免解构后被 noUnusedLocals 误报 */
    sentinelRef?: Ref<HTMLElement | null>
  },
) {
  const chunk = options?.chunk ?? DEFAULT_CHUNK
  const enabled = options?.enabled
  const visibleCount = ref(chunk)
  const sentinelRef = options?.sentinelRef ?? ref<HTMLElement | null>(null)
  const loadingMore = ref(false)
  let observer: IntersectionObserver | null = null

  const displayRows = computed(() => source.value.slice(0, visibleCount.value))
  const hasMore = computed(() => visibleCount.value < source.value.length)

  function resetVisible() {
    visibleCount.value = chunk
  }

  /** 恢复到至少 n 条（从详情返回时用） */
  function ensureVisible(n: number) {
    const target = Math.max(chunk, Math.floor(n) || chunk)
    visibleCount.value = Math.min(Math.max(visibleCount.value, target), Math.max(source.value.length, chunk))
  }

  function loadMore() {
    if (!hasMore.value || loadingMore.value) return
    loadingMore.value = true
    requestAnimationFrame(() => {
      visibleCount.value = Math.min(visibleCount.value + chunk, source.value.length)
      loadingMore.value = false
      // 首屏未撑满视口时，哨兵仍在可见区，IO 不一定再触发，主动再补一批
      nextTick(() => {
        const el = sentinelRef.value
        if (!el || !hasMore.value) return
        const rect = el.getBoundingClientRect()
        if (rect.top < window.innerHeight + 160) loadMore()
      })
    })
  }

  function setupObserver() {
    teardownObserver()
    if (enabled && !enabled.value) return
    const el = sentinelRef.value
    if (!el) return
    observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) loadMore()
      },
      { root: null, rootMargin: '160px 0px', threshold: 0 },
    )
    observer.observe(el)
  }

  function teardownObserver() {
    observer?.disconnect()
    observer = null
  }

  watch(
    () => source.value.length,
    () => {
      // 数据变少时收紧 visibleCount，避免空白
      if (visibleCount.value > source.value.length) {
        visibleCount.value = Math.max(chunk, source.value.length) || chunk
        if (source.value.length === 0) visibleCount.value = chunk
      }
    },
  )

  if (enabled) {
    watch(enabled, async (on) => {
      if (on) {
        resetVisible()
        await nextTick()
        setupObserver()
      } else {
        teardownObserver()
      }
    })
  }

  watch(sentinelRef, async () => {
    await nextTick()
    setupObserver()
  })

  onMounted(async () => {
    await nextTick()
    setupObserver()
  })
  onUnmounted(teardownObserver)

  return {
    sentinelRef,
    displayRows,
    hasMore,
    loadingMore,
    visibleCount,
    resetVisible,
    ensureVisible,
    loadMore,
  }
}
