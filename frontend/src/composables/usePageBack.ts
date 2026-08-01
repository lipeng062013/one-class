import { useRouter } from 'vue-router'

/**
 * 规范化路径：去掉 query/hash、尾部斜杠，便于比较「是否同一页」。
 */
export function normalizeRoutePath(fullPath: string): string {
  if (!fullPath) return '/'
  const q = fullPath.indexOf('?')
  const h = fullPath.indexOf('#')
  let end = fullPath.length
  if (q >= 0) end = Math.min(end, q)
  if (h >= 0) end = Math.min(end, h)
  let path = fullPath.slice(0, end) || '/'
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1)
  return path || '/'
}

/**
 * 是否为本应用内、可安全作为「返回目标」的路径（排除登录页与外链）。
 */
export function isSafeAppHistoryPath(fullPath: string): boolean {
  if (!fullPath || typeof fullPath !== 'string') return false
  // 必须是站内相对 path；拒绝协议相对 //evil.com
  if (!fullPath.startsWith('/') || fullPath.startsWith('//')) return false
  const path = normalizeRoutePath(fullPath)
  if (path === '/login' || path.startsWith('/login/')) return false
  return true
}

/**
 * 历史上一页是否适合用 browser back：
 * 仅当上一页就是声明的父级（fallback，忽略 query 比较）时才 back，
 * 从而保留列表筛选 query / 滚动位置，又避免跨模块乱跳。
 */
export function canHistoryBackToParent(prevFullPath: string, fallback: string): boolean {
  if (!isSafeAppHistoryPath(prevFullPath)) return false
  return normalizeRoutePath(prevFullPath) === normalizeRoutePath(fallback)
}

function readHistoryBack(): string | null {
  const state = window.history.state as { back?: unknown } | null
  const back = state?.back
  return typeof back === 'string' && back.length > 0 ? back : null
}

function toFallbackList(fallback: string | string[]): string[] {
  const list = (Array.isArray(fallback) ? fallback : [fallback])
    .map((x) => x?.trim())
    .filter((x): x is string => Boolean(x))
  return list.length ? list : ['/']
}

export type PageBackOptions = {
  /**
   * 无法安全 back 时：用 replace（默认）避免「详情仍留在历史上、再点浏览器后退又回来」；
   * 传 false 则 push。
   */
  replace?: boolean
}

/**
 * 页面「返回」行为（PC / 各模块详情与子页 el-page-header 统一使用）：
 *
 * 1. 若历史上一页恰好是本模块父级之一（fallback 链，忽略 query 比较）→ `router.back()`
 *    这样能还原列表上的筛选参数与浏览位置。
 * 2. 否则（跨模块、直达深链、上一页是登录/上传表单等）→ 进入主 fallback
 *    默认 `replace`，路径可预期，不堆叠无意义历史。
 *
 * `fallback` 可为字符串，或按优先级排列的父级路径数组：
 * - 历史匹配按数组顺序尝试（例如 `['/posters/generate', '/posters']`）
 * - 无合适历史时 replace 到第一项（模块主入口）
 *
 * 不要对「返回」使用无条件 `router.back()`：侧栏切换、生成页跳转、提交后进详情
 * 都会把无关页面压进历史，导致连点返回在模块间乱跳。
 */
export function usePageBack(fallback: string | string[] = '/') {
  const router = useRouter()
  const fallbacks = toFallbackList(fallback)
  const primary = fallbacks[0]

  function goBack(toFallback?: string, options?: PageBackOptions) {
    // 兼容 @back="goBack" / 误写成 @click="goBack" 时首参可能是事件对象
    const explicit = typeof toFallback === 'string' ? toFallback.trim() : ''
    const replaceTarget = explicit || primary
    const prev = readHistoryBack()

    if (prev) {
      const candidates = explicit
        ? [explicit, ...fallbacks.filter((f) => f !== explicit)]
        : fallbacks
      for (const fb of candidates) {
        if (canHistoryBackToParent(prev, fb)) {
          router.back()
          return
        }
      }
    }

    const replace = options?.replace !== false
    if (replace) {
      void router.replace(replaceTarget)
    } else {
      void router.push(replaceTarget)
    }
  }

  return { goBack }
}
