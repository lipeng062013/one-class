import {
  computed,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
  type Ref,
} from 'vue'
import type { PageResult } from '../api/paging'
import { PAGE_SIZES } from './useServerPager'

/** wap/pad 每次追加条数（与学员/素材一致） */
export const SCROLL_CHUNK = 10

export type ServerFetchPage<T> = (
  page: number,
  pageSize: number,
) => Promise<PageResult<T>>

/**
 * 服务端分页 × 三端布局：
 *
 * | 端 | 行为 |
 * |----|------|
 * | **PC**（>991） | `page` + `pageSize` 替换加载；底栏首页/分页/末页 |
 * | **wap/pad**（≤991） | 每次请求 `SCROLL_CHUNK` 条并 **append**；触底再请求下一页 |
 *
 * 禁止对「仅当前服务端页」再套 `useInfiniteScroll`（会假加载、无法翻到第 2 页）。
 */
export function useServerPagedList<T>(opts: {
  /** 拉取一页；筛选条件由闭包捕获 */
  fetchPage: ServerFetchPage<T>
  isCompact: Ref<boolean>
  /** 紧凑端每页条数，默认 10 */
  chunk?: number
  /** PC 默认每页，默认 20 */
  initialPageSize?: number
  /** 列表项 id，用于去重 append（可选） */
  getId?: (row: T) => string | number
}) {
  const chunk = opts.chunk ?? SCROLL_CHUNK
  const page = ref(1)
  const pageSize = ref(opts.initialPageSize ?? 20)
  const total = ref(0)
  const rows = ref<T[]>([]) as Ref<T[]>
  const loading = ref(false)
  const loadingMore = ref(false)
  const sentinelRef = ref<HTMLElement | null>(null)

  let scrollObserver: IntersectionObserver | null = null

  const totalPages = computed(() =>
    Math.max(1, Math.ceil(total.value / pageSize.value) || 1),
  )
  /** 紧凑端：已加载条数 < 服务端 total 则还有下一页 */
  const hasMore = computed(() => rows.value.length < total.value)

  function dedupeAppend(prev: T[], next: T[]): T[] {
    if (!opts.getId) return [...prev, ...next]
    const seen = new Set(prev.map((r) => opts.getId!(r)))
    const extra = next.filter((r) => !seen.has(opts.getId!(r)))
    return [...prev, ...extra]
  }

  /**
   * @param reset 查询/筛选：从第 1 页重载
   * @param append 仅紧凑端上拉：追加下一页
   */
  async function load(options?: { reset?: boolean; append?: boolean }) {
    const compact = opts.isCompact.value
    const append = !!options?.append && compact

    if (options?.reset) {
      page.value = 1
    }

    if (append) {
      if (loadingMore.value || loading.value || !hasMore.value) return
      loadingMore.value = true
    } else {
      loading.value = true
    }

    try {
      if (compact) {
        if (!append) page.value = 1
        const res = await opts.fetchPage(page.value, chunk)
        rows.value = append ? dedupeAppend(rows.value, res.items) : res.items
        total.value = res.total
      } else {
        const res = await opts.fetchPage(page.value, pageSize.value)
        rows.value = res.items
        total.value = res.total
        // 空页回退
        if (page.value > 1 && res.items.length === 0 && res.total > 0) {
          page.value = Math.max(1, Math.ceil(res.total / pageSize.value))
          const again = await opts.fetchPage(page.value, pageSize.value)
          rows.value = again.items
          total.value = again.total
        }
      }
    } finally {
      loading.value = false
      loadingMore.value = false
    }
  }

  async function loadMore() {
    if (!opts.isCompact.value || loadingMore.value || loading.value || !hasMore.value) {
      return
    }
    page.value += 1
    await load({ append: true })
  }

  function goFirstPage() {
    page.value = 1
    void load()
  }

  function goLastPage() {
    page.value = totalPages.value
    void load()
  }

  function onPageChange() {
    void load()
  }

  function onPageSizeChange() {
    page.value = 1
    void load()
  }

  /** 筛选条件变化：重置并加载 */
  function resetAndLoad() {
    page.value = 1
    void load({ reset: true })
  }

  function setupScrollObserver() {
    teardownScrollObserver()
    if (!opts.isCompact.value) return
    const el = sentinelRef.value
    if (!el) return
    scrollObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) void loadMore()
      },
      { root: null, rootMargin: '160px 0px', threshold: 0 },
    )
    scrollObserver.observe(el)
  }

  function teardownScrollObserver() {
    scrollObserver?.disconnect()
    scrollObserver = null
  }

  watch(
    () => opts.isCompact.value,
    async (compact, was) => {
      if (compact === was) return
      page.value = 1
      await load({ reset: true })
      await nextTick()
      if (compact) setupScrollObserver()
      else teardownScrollObserver()
    },
  )

  watch(sentinelRef, async () => {
    await nextTick()
    if (opts.isCompact.value) setupScrollObserver()
  })

  onMounted(async () => {
    await nextTick()
    if (opts.isCompact.value) setupScrollObserver()
  })
  onUnmounted(() => teardownScrollObserver())

  return {
    page,
    pageSize,
    total,
    rows,
    loading,
    loadingMore,
    hasMore,
    totalPages,
    PAGE_SIZES: [...PAGE_SIZES] as number[],
    SCROLL_CHUNK: chunk,
    sentinelRef,
    load,
    loadMore,
    resetAndLoad,
    goFirstPage,
    goLastPage,
    onPageChange,
    onPageSizeChange,
    setupScrollObserver,
    teardownScrollObserver,
  }
}
