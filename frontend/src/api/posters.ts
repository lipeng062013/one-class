import client from './client'

export type PosterMode = 'layout' | 'ai_image'

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

export async function listPosters(): Promise<GeneratedPoster[]> {
  const res = await client.get<ApiResponse<GeneratedPoster[]>>('/posters')
  return unwrap(res, 'Failed to list posters')
}

export async function generatePoster(payload: GeneratePosterInput): Promise<GeneratedPoster> {
  const res = await client.post<ApiResponse<GeneratedPoster>>('/posters/generate', payload)
  return unwrap(res, 'Failed to generate poster')
}

export async function downloadPosterBlob(id: number): Promise<Blob> {
  const res = await client.get<Blob>(`/files/posters/${id}`, {
    responseType: 'blob',
  })
  return res.data
}

export async function posterObjectUrl(id: number): Promise<string> {
  const blob = await downloadPosterBlob(id)
  return URL.createObjectURL(blob)
}

export async function openPosterDownload(id: number, filename?: string): Promise<void> {
  const blob = await downloadPosterBlob(id)
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
