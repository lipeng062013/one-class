import { computed, ref, type Ref } from 'vue'

/** 全站统一每页条数选项（与学员/素材等列表一致） */
export const PAGE_SIZES = [10, 20, 50, 100] as const

export type PageSizeOption = (typeof PAGE_SIZES)[number]

/**
 * 服务端分页状态（教务/财务等列表复用）。
 * load 由页面传入；翻页 / 改 pageSize 时自动调用。
 */
export function useServerPager(opts?: {
  initialPage?: number
  initialPageSize?: number
  /** 加载当前页数据 */
  load?: () => void | Promise<void>
}) {
  const page = ref(opts?.initialPage ?? 1)
  const pageSize = ref(opts?.initialPageSize ?? 20)
  const total = ref(0)

  const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value) || 1))

  async function runLoad() {
    if (opts?.load) await opts.load()
  }

  function goFirstPage() {
    page.value = 1
    void runLoad()
  }

  function goLastPage() {
    page.value = totalPages.value
    void runLoad()
  }

  function onPageChange() {
    void runLoad()
  }

  function onPageSizeChange() {
    page.value = 1
    void runLoad()
  }

  /** 查询条件变化时回到第 1 页并加载 */
  function resetAndLoad() {
    page.value = 1
    void runLoad()
  }

  return {
    page,
    pageSize,
    total,
    totalPages,
    PAGE_SIZES: [...PAGE_SIZES] as number[],
    goFirstPage,
    goLastPage,
    onPageChange,
    onPageSizeChange,
    resetAndLoad,
  }
}

/** 仅计算 totalPages（页面自管 page/pageSize/total 时用） */
export function useTotalPages(total: Ref<number>, pageSize: Ref<number>) {
  return computed(() => Math.max(1, Math.ceil(total.value / pageSize.value) || 1))
}
