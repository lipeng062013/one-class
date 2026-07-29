import client from './client'

export interface CopyTemplate {
  id: number
  name: string
  scene: string
  body: string
  is_system: boolean
  is_active: boolean
  created_by?: number | null
  created_at?: string | null
}

export interface PosterTemplate {
  id: number
  name: string
  scene: string
  layout_json: string
  preview_path?: string | null
  is_system: boolean
  is_active: boolean
  created_at?: string | null
}

export interface CopyTemplateCreateInput {
  name: string
  scene: string
  body?: string
  is_active?: boolean
}

export interface PosterTemplateCreateInput {
  name: string
  scene: string
  layout_json?: string
  preview_path?: string | null
  is_active?: boolean
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

export async function listCopyTemplates(): Promise<CopyTemplate[]> {
  const res = await client.get<ApiResponse<CopyTemplate[]>>('/templates/copies')
  return unwrap(res, 'Failed to list copy templates')
}

export async function createCopyTemplate(
  payload: CopyTemplateCreateInput,
): Promise<CopyTemplate> {
  const res = await client.post<ApiResponse<CopyTemplate>>('/templates/copies', payload)
  return unwrap(res, 'Failed to create copy template')
}

export async function listPosterTemplates(): Promise<PosterTemplate[]> {
  const res = await client.get<ApiResponse<PosterTemplate[]>>('/templates/posters')
  return unwrap(res, 'Failed to list poster templates')
}

export async function createPosterTemplate(
  payload: PosterTemplateCreateInput,
): Promise<PosterTemplate> {
  const res = await client.post<ApiResponse<PosterTemplate>>('/templates/posters', payload)
  return unwrap(res, 'Failed to create poster template')
}
