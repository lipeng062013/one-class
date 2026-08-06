import client from './client'

export interface DashboardSummary {
  materials_new: number
  leads_follow_today: number
  recent_copies: number
}

export interface TodayTodo {
  id: number
  user_id: number
  title: string
  content: string
  is_done: boolean
  created_at?: string | null
  completed_at?: string | null
  kind?: string
  path?: string
  /** system 待办来源：schedule=课表/点名，lead=线索 */
  source?: string | null
  ref_id?: number | null
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

export async function listTodayTodosApi(): Promise<TodayTodo[]> {
  const res = await client.get<ApiResponse<TodayTodo[]>>('/dashboard/today-todos')
  return unwrap(res, 'Failed to load today todos')
}
