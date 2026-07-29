import client from './client'

export interface DashboardSummary {
  materials_new: number
  leads_follow_today: number
  recent_copies: number
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

export async function getSummary(): Promise<DashboardSummary> {
  const res = await client.get<ApiResponse<DashboardSummary>>('/dashboard/summary')
  return unwrap(res, 'Failed to load dashboard summary')
}
