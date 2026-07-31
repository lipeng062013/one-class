import { useRouter } from 'vue-router'

/**
 * 页面「返回」行为：
 * - 若浏览器历史中有上一页（本应用内导航过）→ router.back()
 * - 否则 → 跳到 fallback（默认工作台 `/`）
 *
 * 用于各模块详情/列表页 el-page-header，避免无前置时点返回无反应或跳出站点。
 */
export function usePageBack(fallback: string = '/') {
  const router = useRouter()

  function goBack(toFallback?: string) {
    const target = toFallback ?? fallback
    const state = window.history.state as { back?: unknown } | null
    // Vue Router 写入的 history.state：存在 back 表示可后退
    if (state != null && state.back != null) {
      router.back()
      return
    }
    void router.push(target)
  }

  return { goBack }
}
