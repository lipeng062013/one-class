import client from './client'
import { asPageResult, type PageResult } from './paging'

export type PosterMode = 'layout' | 'ai_image' | 'upload'

/** 海报 mode 字段的中文展示 */
export function posterModeLabel(mode: string | null | undefined): string {
  switch (mode) {
    case 'layout':
      return '版式导出'
    case 'ai_image':
      return 'AI 生图'
    case 'upload':
      return '手动上传'
    default:
      return mode?.trim() ? mode : '未知'
  }
}

export interface GeneratedPoster {
  id: number
  material_id: number | null
  template_id: number | null
  mode: string
  title: string
  payload_json: string
  file_path: string
  created_by?: number | null
  created_at?: string | null
  image_error?: string | null
}

export interface GeneratePosterInput {
  material_id?: number | null
  template_id?: number | null
  mode?: PosterMode | string
  title?: string
  payload?: Record<string, unknown>
  prompt?: string | null
}

interface ApiResponse<T> {
  data: T | null
  error: { code: string; message: string } | null
}

function unwrap<T>(res: { data: ApiResponse<T> }, fallback: string): T {
  if (!res.data.data) {
    throw new Error(res.data.error?.message || fallback)
  }
  return res.data.data
}

export async function listPosters(params: {
  q?: string
  mode?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<GeneratedPoster>> {
  const res = await client.get('/posters', {
    params: {
      q: params.q || undefined,
      mode: params.mode || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
  return asPageResult<GeneratedPoster>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function generatePoster(payload: GeneratePosterInput): Promise<GeneratedPoster> {
  // AI 生图常需 30–120s；默认 axios 15s 会提前失败（timeout of 15000ms exceeded）
  const res = await client.post<ApiResponse<GeneratedPoster>>('/posters/generate', payload, {
    timeout: 180_000,
  })
  return unwrap(res, 'Failed to generate poster')
}

/** Manually upload an image into the poster list (mode=upload). */
export async function uploadPoster(file: File, title?: string): Promise<GeneratedPoster> {
  const form = new FormData()
  form.append('file', file)
  if (title != null && title.trim()) {
    form.append('title', title.trim())
  }
  const res = await client.post<ApiResponse<GeneratedPoster>>('/posters/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  })
  return unwrap(res, 'Failed to upload poster')
}

export type PosterFileOpts = {
  /** bulk preview 404 should not spam global toasts */
  silent?: boolean
  /**
   * 列表/网格缩略图：后端返回 JPEG 缩小图，体积远小于原图。
   * 下载原图时请保持 false。
   */
  thumb?: boolean
  /** 缩略图最长边（仅 thumb 时生效），默认后端 640 */
  w?: number
}

export async function downloadPosterBlob(
  id: number,
  opts?: PosterFileOpts,
): Promise<Blob> {
  const params: Record<string, string | number | boolean> = {}
  if (opts?.thumb) {
    params.thumb = true
    if (opts.w != null) params.w = opts.w
  }
  const res = await client.get<Blob>(`/files/posters/${id}`, {
    responseType: 'blob',
    params,
    // bulk preview 404 should not spam global toasts
    skipErrorToast: opts?.silent === true,
  } as Parameters<typeof client.get>[1])
  const blob = res.data
  // Some gateways still return 200 + JSON error as blob
  if (blob.type && (blob.type.includes('json') || blob.type === 'text/plain')) {
    const text = await blob.text()
    let msg = 'Poster file not found'
    try {
      const j = JSON.parse(text) as { detail?: string; error?: { message?: string } }
      msg = j?.error?.message || j?.detail || msg
    } catch {
      if (text.trim()) msg = text.trim().slice(0, 200)
    }
    throw new Error(msg)
  }
  return blob
}

/**
 * @param silent default true for list previews (no toast on missing file)
 * @param thumb default false；列表预览请传 true
 */
export async function posterObjectUrl(
  id: number,
  silent = true,
  thumb = false,
): Promise<string> {
  const blob = await downloadPosterBlob(id, { silent, thumb })
  return URL.createObjectURL(blob)
}

export async function openPosterDownload(id: number, filename?: string): Promise<void> {
  // silent: caller (列表「下载」) 负责提示，避免与拦截器双重 toast
  const blob = await downloadPosterBlob(id, { silent: true })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || `poster-${id}.png`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export async function deletePoster(id: number): Promise<void> {
  await client.delete(`/posters/${id}`)
}

export async function bulkDeletePosters(
  ids: number[],
): Promise<{ deleted_count: number; deleted_ids: number[] }> {
  const res = await client.post<ApiResponse<{ deleted_count: number; deleted_ids: number[] }>>(
    '/posters/bulk-delete',
    { ids },
  )
  return unwrap(res, 'Failed to bulk delete posters')
}
