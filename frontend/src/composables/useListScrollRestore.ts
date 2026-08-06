import { nextTick, type Ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'

export type ListScrollSnapshot = {
  scrollTop: number
  visibleCount?: number
  /** 离开时的列表路径，返回时校验，防止串模块 */
  fromPath: string
  savedAt: number
}

const PREFIX = 'oc-list-pos:'

function storageKey(listKey: string) {
  return `${PREFIX}${listKey}`
}

/**
 * 仅当「去向」是该列表的详情页时才保存。
 * 侧栏切换模块 → 不保存并清快照。
 */
const DETAIL_MATCHERS: Record<string, (toPath: string) => boolean> = {
  copies: (p) => /^\/copies\/\d+\/?$/.test(p),
  materials: (p) => /^\/materials\/\d+\/?$/.test(p),
  posters: () => false,
  leads: (p) => /^\/leads\/\d+\/?$/.test(p),
  students: (p) => /^\/students\/\d+\/?$/.test(p),
  orders: (p) => /^\/finance\/orders\/\d+\/?$/.test(p),
  users: () => false,
  knowledge: () => false,
  templates: (p) =>
    /^\/templates\/copies\/\d+\/?$/.test(p) || /^\/templates\/posters\/\d+\/?$/.test(p),
  learning: (p) => p === '/learning/new' || p.startsWith('/learning/new'),
}

export function isListDetailNavigation(listKey: string, toPath: string): boolean {
  const fn = DETAIL_MATCHERS[listKey]
  return fn ? fn(toPath) : false
}

/** 列表路径（用于校验快照是否属于当前列表） */
const LIST_PATH_MATCHERS: Record<string, (path: string) => boolean> = {
  copies: (p) => p === '/copies' || p === '/copies/',
  materials: (p) => p === '/materials' || p === '/materials/',
  posters: (p) => p === '/posters' || p === '/posters/',
  leads: (p) => p === '/leads' || p === '/leads/',
  students: (p) => p === '/students' || p === '/students/',
  orders: (p) => p === '/finance/orders' || p === '/finance/orders/',
  users: (p) => p === '/users' || p === '/users/',
  knowledge: (p) => p.startsWith('/knowledge'),
  templates: (p) => p === '/templates' || p === '/templates/',
  learning: (p) => p === '/learning' || p === '/learning/',
}

export function isCurrentListPath(listKey: string, path: string): boolean {
  const fn = LIST_PATH_MATCHERS[listKey]
  return fn ? fn(path) : false
}

export function findListScrollRoot(): HTMLElement | null {
  if (typeof document === 'undefined') return null
  return (
    (document.querySelector('.layout .main') as HTMLElement | null) ||
    (document.querySelector('.mobile-shell .body') as HTMLElement | null) ||
    (document.querySelector('.el-main.main') as HTMLElement | null)
  )
}

function readScrollTop(el: HTMLElement | null): number {
  if (!el) {
    return typeof window !== 'undefined' ? window.scrollY || document.documentElement.scrollTop || 0 : 0
  }
  return el.scrollTop
}

function writeScrollTop(el: HTMLElement | null, top: number) {
  if (!el) {
    window.scrollTo({ top, left: 0, behavior: 'instant' as ScrollBehavior })
    return
  }
  el.scrollTop = top
}

export function readListScrollSnapshot(listKey: string): ListScrollSnapshot | null {
  try {
    const raw = sessionStorage.getItem(storageKey(listKey))
    if (!raw) return null
    const data = JSON.parse(raw) as ListScrollSnapshot
    if (typeof data?.scrollTop !== 'number') return null
    if (data.savedAt && Date.now() - data.savedAt > 30 * 60 * 1000) {
      sessionStorage.removeItem(storageKey(listKey))
      return null
    }
    return data
  } catch {
    return null
  }
}

export function clearListScrollSnapshot(listKey: string) {
  try {
    sessionStorage.removeItem(storageKey(listKey))
  } catch {
    /* ignore */
  }
}

function clearSessionState(stateStorageKey: string) {
  try {
    sessionStorage.removeItem(stateStorageKey)
  } catch {
    /* ignore */
  }
}

/** 详情页仅在返回原列表时保留筛选，转去其他模块则清除。 */
export function useListDetailStateCleanup(listKey: string, stateStorageKey: string) {
  onBeforeRouteLeave((to) => {
    if (isCurrentListPath(listKey, to.path)) return
    clearListScrollSnapshot(listKey)
    clearSessionState(stateStorageKey)
  })
}

/**
 * wap/pad 列表滚动恢复：
 * - 仅「列表 → 本模块详情 → 返回列表」恢复
 * - 侧栏切换模块：强制回顶，不读旧快照
 */
export function useListScrollRestore(
  listKey: string,
  options?: {
    visibleCount?: Ref<number>
    enabled?: Ref<boolean>
    /** 列表筛选/分页状态键；切换到其他模块时与滚动快照一起清除。 */
    stateStorageKey?: string
  },
) {
  const visibleCount = options?.visibleCount
  const enabled = options?.enabled
  const stateStorageKey = options?.stateStorageKey

  function isEnabled() {
    return !enabled || enabled.value
  }

  function saveSnapshot(fromPath: string) {
    if (!isEnabled()) return
    try {
      const el = findListScrollRoot()
      const snap: ListScrollSnapshot = {
        scrollTop: readScrollTop(el),
        visibleCount: visibleCount?.value,
        fromPath,
        savedAt: Date.now(),
      }
      sessionStorage.setItem(storageKey(listKey), JSON.stringify(snap))
    } catch {
      /* ignore */
    }
  }

  /**
   * load 时读取快照。若快照不属于「当前列表路径」则丢弃。
   */
  function takeSnapshotForLoad(currentPath: string): ListScrollSnapshot | null {
    if (!isEnabled()) return null
    const snap = readListScrollSnapshot(listKey)
    if (!snap) return null
    // 必须是从本列表离开时存的
    if (snap.fromPath && !isCurrentListPath(listKey, snap.fromPath)) {
      clearSnapshot()
      return null
    }
    // 当前必须仍在本列表
    if (!isCurrentListPath(listKey, currentPath)) {
      clearSnapshot()
      return null
    }
    return snap
  }

  function clearSnapshot() {
    clearListScrollSnapshot(listKey)
  }

  function clearStoredListState() {
    if (!stateStorageKey) return
    clearSessionState(stateStorageKey)
  }

  /** 切换模块 / 查询：主区强制回顶（.main 跨路由不卸载，会带着旧 scrollTop） */
  function resetScrollToTop() {
    const apply = () => writeScrollTop(findListScrollRoot(), 0)
    apply()
    void nextTick(apply)
    requestAnimationFrame(apply)
  }

  /**
   * 列表数据就绪后调用：
   * - 有合法详情返回快照 → 恢复滚动
   * - 否则 → 回顶（修复「切换模块仍停在上一页滚动位置」）
   */
  async function finishListEnter(opts: {
    /** takeSnapshotForLoad 的结果；null 表示不要恢复 */
    snap: ListScrollSnapshot | null
    /** 查询/重置时 true：清快照并回顶 */
    forceTop?: boolean
  }) {
    if (!isEnabled()) {
      // PC 宽屏也回顶，避免 main 残留
      if (opts.forceTop || !opts.snap) resetScrollToTop()
      return
    }

    if (opts.forceTop) {
      clearSnapshot()
      resetScrollToTop()
      return
    }

    const snap = opts.snap
    const top = snap?.scrollTop
    if (top == null || top <= 0) {
      clearSnapshot()
      resetScrollToTop()
      return
    }

    const apply = () => writeScrollTop(findListScrollRoot(), top)
    await nextTick()
    apply()
    requestAnimationFrame(apply)
    window.setTimeout(apply, 50)
    window.setTimeout(apply, 120)
    window.setTimeout(() => {
      apply()
      clearSnapshot()
    }, 280)
  }

  onBeforeRouteLeave((to, from) => {
    const enteringDetail =
      isListDetailNavigation(listKey, to.path) && isCurrentListPath(listKey, from.path)
    if (!isEnabled()) {
      clearSnapshot()
      if (!enteringDetail) clearStoredListState()
      return
    }
    // 只有进入「本列表的详情」才记位置
    if (enteringDetail) {
      saveSnapshot(from.path)
      return
    }
    // 侧栏切换到其它模块 / 工作台等：清掉，禁止下次误恢复
    clearSnapshot()
    clearStoredListState()
  })

  return {
    saveSnapshot,
    takeSnapshotForLoad,
    finishListEnter,
    resetScrollToTop,
    clearSnapshot,
    clearStoredListState,
    /** @deprecated 使用 finishListEnter */
    restoreScroll: async (overrideTop?: number) => {
      const snap = readListScrollSnapshot(listKey)
      await finishListEnter({
        snap:
          overrideTop != null
            ? {
                scrollTop: overrideTop,
                visibleCount: snap?.visibleCount,
                fromPath: snap?.fromPath || '',
                savedAt: Date.now(),
              }
            : snap,
      })
    },
  }
}
