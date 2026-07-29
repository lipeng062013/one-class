import client from './client'

export type KnowledgeCategory = 'course' | 'faq' | 'tone' | 'banned' | 'staff' | 'process'

export interface KnowledgeEntry {
  id: number
  category: string
  title: string
  content: string
  tags: string
  is_active: boolean
  updated_by?: number | null
  updated_at?: string | null
}

export interface KnowledgeCreateInput {
  category: KnowledgeCategory | string
  title?: string
  content?: string
  tags?: string
  is_active?: boolean
}

export interface KnowledgeUpdateInput {
  category?: KnowledgeCategory | string
  title?: string
  content?: string
  tags?: string
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

export async function listKnowledge(category?: string): Promise<KnowledgeEntry[]> {
  const res = await client.get<ApiResponse<KnowledgeEntry[]>>('/knowledge', {
    params: category ? { category } : undefined,
  })
  return unwrap(res, 'Failed to list knowledge')
}

export async function createKnowledge(payload: KnowledgeCreateInput): Promise<KnowledgeEntry> {
  const res = await client.post<ApiResponse<KnowledgeEntry>>('/knowledge', payload)
  return unwrap(res, 'Failed to create knowledge')
}

export async function updateKnowledge(
  id: number,
  payload: KnowledgeUpdateInput,
): Promise<KnowledgeEntry> {
  const res = await client.patch<ApiResponse<KnowledgeEntry>>(`/knowledge/${id}`, payload)
  return unwrap(res, 'Failed to update knowledge')
}

export async function deleteKnowledge(id: number): Promise<{ id: number }> {
  const res = await client.delete<ApiResponse<{ id: number }>>(`/knowledge/${id}`)
  return unwrap(res, 'Failed to delete knowledge')
}
