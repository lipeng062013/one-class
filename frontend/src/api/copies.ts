import client from './client'

export type CopyMode = 'template' | 'template_then_llm' | 'llm'

export interface GeneratedCopy {
  id: number
  material_id: number | null
  template_id: number | null
  mode: string
  platform: string
  title: string
  body: string
  prompt_snapshot?: string | null
  model_name?: string | null
  created_by?: number | null
  created_at?: string | null
  banned_hits: string[]
  llm_error?: string | null
}

export interface GenerateCopyInput {
  material_id?: number | null
  template_id?: number | null
  mode?: CopyMode | string
  platform?: string
  extra_instruction?: string | null
}

export interface PatchCopyInput {
  title?: string
  body?: string
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

export async function listCopies(): Promise<GeneratedCopy[]> {
  const res = await client.get<ApiResponse<GeneratedCopy[]>>('/copies')
  return unwrap(res, 'Failed to list copies')
}

export async function generateCopy(payload: GenerateCopyInput): Promise<GeneratedCopy> {
  const res = await client.post<ApiResponse<GeneratedCopy>>('/copies/generate', payload)
  return unwrap(res, 'Failed to generate copy')
}

export async function patchCopy(id: number, payload: PatchCopyInput): Promise<GeneratedCopy> {
  const res = await client.patch<ApiResponse<GeneratedCopy>>(`/copies/${id}`, payload)
  return unwrap(res, 'Failed to update copy')
}
