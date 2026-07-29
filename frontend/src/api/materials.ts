import client from './client'

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

export async function listMaterialsApi(): Promise<Material[]> {
  const res = await client.get('/materials')
  return res.data.data
}

/** Alias used by copy/poster generators */
export const listMaterials = listMaterialsApi

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

export async function fetchMaterialFileBlob(fileId: number): Promise<Blob> {
  const res = await client.get(`/materials/files/${fileId}/content`, {
    responseType: 'blob',
  })
  return res.data
}

/** Load authenticated image into an object URL (caller should revoke). */
export async function materialFileObjectUrl(fileId: number): Promise<string> {
  const blob = await fetchMaterialFileBlob(fileId)
  return URL.createObjectURL(blob)
}
