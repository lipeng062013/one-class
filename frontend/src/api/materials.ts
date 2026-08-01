import client from './client'
import { asPageResult, type PageParams, type PageResult } from './paging'

export interface MaterialFile {
  id: number
  file_path: string
  file_type: string
  sort_order: number
}

export interface Material {
  id: number
  uploader_id: number
  title: string
  grade?: string | null
  subject?: string | null
  pain_point?: string | null
  teacher_action?: string | null
  next_step?: string | null
  auth_status: string
  status: string
  created_at?: string | null
  files: MaterialFile[]
}

export interface MaterialPayload {
  title: string
  grade?: string
  subject?: string
  pain_point?: string
  teacher_action?: string
  next_step?: string
  auth_status?: string
}

export interface MaterialListParams extends PageParams {
  status?: string
  grade?: string
  subject?: string
  q?: string
}

export async function listMaterialsApi(
  params: MaterialListParams = {},
): Promise<PageResult<Material>> {
  const res = await client.get('/materials', {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
      status: params.status || undefined,
      grade: params.grade || undefined,
      subject: params.subject || undefined,
      q: params.q || undefined,
    },
  })
  return asPageResult<Material>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

/** Picker / 生成页：取前若干条（服务端分页上限 100） */
export async function listMaterialsForPicker(limit = 100): Promise<Material[]> {
  const page = await listMaterialsApi({ page: 1, page_size: Math.min(100, Math.max(1, limit)) })
  return page.items
}

/** @deprecated 使用 listMaterialsApi / listMaterialsForPicker */
export async function listMaterials(): Promise<Material[]> {
  return listMaterialsForPicker(100)
}

export async function getMaterialApi(id: number): Promise<Material> {
  const res = await client.get(`/materials/${id}`)
  return res.data.data
}

export async function createMaterialApi(payload: MaterialPayload): Promise<Material> {
  const res = await client.post('/materials', payload)
  return res.data.data
}

export async function patchMaterialApi(
  id: number,
  payload: Partial<MaterialPayload> & { status?: string },
): Promise<Material> {
  const res = await client.patch(`/materials/${id}`, payload)
  return res.data.data
}

export async function deleteMaterialApi(id: number): Promise<void> {
  await client.delete(`/materials/${id}`)
}

export async function uploadMaterialFileApi(id: number, file: File): Promise<MaterialFile> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post(`/materials/${id}/files`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data.data
}

export type MaterialFileOpts = {
  /** 列表/网格缩略图，体积远小于原图 */
  thumb?: boolean
  /** 缩略图最长边（仅 thumb 时生效） */
  w?: number
}

export async function fetchMaterialFileBlob(
  fileId: number,
  opts?: MaterialFileOpts,
): Promise<Blob> {
  const params: Record<string, string | number | boolean> = {}
  if (opts?.thumb) {
    params.thumb = true
    if (opts.w != null) params.w = opts.w
  }
  const res = await client.get(`/materials/files/${fileId}/content`, {
    responseType: 'blob',
    params,
  })
  return res.data
}

/** Load authenticated image into an object URL (caller should revoke). */
export async function materialFileObjectUrl(
  fileId: number,
  opts?: MaterialFileOpts,
): Promise<string> {
  const blob = await fetchMaterialFileBlob(fileId, opts)
  return URL.createObjectURL(blob)
}
