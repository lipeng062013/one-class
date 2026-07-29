import client from './client'

export type LeadSource = 'referral' | 'dianping' | 'wechat' | 'walkin' | 'other'
export type LeadStatus = 'new' | 'contacted' | 'visited' | 'enrolled' | 'lost'

export interface Lead {
  id: number
  student_or_parent_name: string
  phone: string | null
  source: string
  referrer_name: string | null
  channel_note: string
  need: string
  status: string
  next_follow_at: string | null
  owner_id: number | null
  notes: string
  created_at?: string | null
  updated_at?: string | null
}

export interface LeadCreateInput {
  student_or_parent_name: string
  phone?: string | null
  source?: LeadSource | string
  referrer_name?: string | null
  channel_note?: string
  need?: string
  status?: LeadStatus | string
  next_follow_at?: string | null
  owner_id?: number | null
  notes?: string
}

export interface LeadUpdateInput {
  student_or_parent_name?: string
  phone?: string | null
  source?: LeadSource | string
  referrer_name?: string | null
  channel_note?: string
  need?: string
  status?: LeadStatus | string
  next_follow_at?: string | null
  owner_id?: number | null
  notes?: string
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

export async function listLeads(): Promise<Lead[]> {
  const res = await client.get<ApiResponse<Lead[]>>('/leads')
  return unwrap(res, 'Failed to list leads')
}

export async function createLead(payload: LeadCreateInput): Promise<Lead> {
  const res = await client.post<ApiResponse<Lead>>('/leads', payload)
  return unwrap(res, 'Failed to create lead')
}

export async function patchLead(id: number, payload: LeadUpdateInput): Promise<Lead> {
  const res = await client.patch<ApiResponse<Lead>>(`/leads/${id}`, payload)
  return unwrap(res, 'Failed to update lead')
}
