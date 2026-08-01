/** Server-side list pagination envelope (matches backend page_payload). */
export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface PageParams {
  page?: number
  page_size?: number
}

export function emptyPage<T>(page = 1, pageSize = 20): PageResult<T> {
  return { items: [], total: 0, page, page_size: pageSize }
}

/** Normalize API data that may be legacy array or paginated object. */
export function asPageResult<T>(data: unknown, fallbackPage = 1, fallbackSize = 20): PageResult<T> {
  if (Array.isArray(data)) {
    return {
      items: data as T[],
      total: data.length,
      page: fallbackPage,
      page_size: fallbackSize,
    }
  }
  if (data && typeof data === 'object') {
    const raw = data as Record<string, unknown>
    const items = Array.isArray(raw.items) ? (raw.items as T[]) : []
    const total = typeof raw.total === 'number' ? raw.total : items.length
    const page = typeof raw.page === 'number' ? raw.page : fallbackPage
    const page_size = typeof raw.page_size === 'number' ? raw.page_size : fallbackSize
    return { items, total, page, page_size }
  }
  return emptyPage<T>(fallbackPage, fallbackSize)
}
