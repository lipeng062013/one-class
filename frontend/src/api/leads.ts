import client from './client'
import { assertValidOptionalPhone } from '../utils/phone'

export type LeadSource = 'referral' | 'dianping' | 'wechat' | 'walkin' | 'other'
export type LeadStatus = 'new' | 'contacted' | 'visited' | 'enrolled' | 'lost'
export type LeadActivityKind = 'create' | 'update' | 'follow' | 'owner' | 'collaborator' | 'system'
export type LeadContactMethod = '' | 'phone' | 'wechat' | 'visit' | 'sms' | 'other'

export interface LeadFollower {
  id: number
  user_id: number
  name: string
  role: string
  role_label: string
  note: string
  joined_at?: string | null
  is_owner: boolean
}

export interface Lead {
  id: number
  student_or_parent_name: string
  phone: string | null
  external_code: string | null
  school: string
  grade: string
  age: number | null
  campus: string
  imported_creator_name: string
  source: string
  referrer_name: string | null
  channel_note: string
  need: string
  status: string
  next_follow_at: string | null
  owner_id: number | null
  owner_name?: string
  notes: string
  last_contact_at?: string | null
  last_contact_by?: number | null
  last_contact_by_name?: string
  last_contact_method?: string
  collaborator_count?: number
  followers?: LeadFollower[]
  created_at?: string | null
  updated_at?: string | null
  /** 已报名后锁定 */
  locked?: boolean
  converted_student_id?: number | null
  conversion_status?: 'created' | 'already_linked' | 'incomplete' | 'error' | string
  conversion_message?: string
}

export interface LeadActivity {
  id: number
  lead_id: number
  actor_id: number | null
  actor_name: string
  kind: LeadActivityKind | string
  kind_label: string
  title: string
  content: string
  contact_method: string
  contact_method_label: string
  meta: Record<string, unknown>
  created_at?: string | null
}

export interface LeadAssignee {
  id: number
  name: string
  role: string
  role_label: string
}

export interface LeadCreateInput {
  student_or_parent_name: string
  phone?: string | null
  external_code?: string | null
  school?: string
  grade?: string
  age?: number | null
  campus?: string
  imported_creator_name?: string
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
  external_code?: string | null
  school?: string
  grade?: string
  age?: number | null
  campus?: string
  imported_creator_name?: string
  source?: LeadSource | string
  referrer_name?: string | null
  channel_note?: string
  need?: string
  status?: LeadStatus | string
  next_follow_at?: string | null
  owner_id?: number | null
  notes?: string
}

export interface LeadFollowInput {
  content: string
  contact_method?: LeadContactMethod | string
  next_follow_at?: string | null
  status?: LeadStatus | string | null
  join_as_collaborator?: boolean
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

export interface LeadListParams {
  source?: string
  status?: string
  name?: string
  phone?: string
  page?: number
  page_size?: number
}

export interface LeadListResult {
  items: Lead[]
  total: number
  page: number
  page_size: number
}

export type LeadImportStatus = 'imported' | 'duplicate' | 'failed' | 'warning'

export interface LeadImportDetail {
  row: number
  status: LeadImportStatus
  message: string
}

export interface LeadImportResult {
  imported_count: number
  duplicate_count: number
  failed_count: number
  warning_count: number
  details: LeadImportDetail[]
}

type LeadListCacheEntry = {
  data: LeadListResult
  savedAt: number
}

const leadListCache = new Map<string, LeadListCacheEntry>()
const LEAD_LIST_CACHE_LIMIT = 20

function leadListCacheKey(params: LeadListParams) {
  return JSON.stringify({
    source: params.source || '',
    status: params.status || '',
    name: params.name || '',
    phone: params.phone || '',
    page: params.page ?? 1,
    page_size: params.page_size ?? 20,
  })
}

function writeLeadListCache(params: LeadListParams, data: LeadListResult) {
  const key = leadListCacheKey(params)
  leadListCache.delete(key)
  leadListCache.set(key, { data, savedAt: Date.now() })
  if (leadListCache.size > LEAD_LIST_CACHE_LIMIT) {
    const oldestKey = leadListCache.keys().next().value
    if (oldestKey) leadListCache.delete(oldestKey)
  }
}

/** Use the latest rows immediately while the view refreshes them in the background. */
export function peekLeadListCache(
  params: LeadListParams = {},
  maxAgeMs = 60_000,
): LeadListResult | null {
  const key = leadListCacheKey(params)
  const entry = leadListCache.get(key)
  if (!entry) return null
  if (Date.now() - entry.savedAt > maxAgeMs) {
    leadListCache.delete(key)
    return null
  }
  return entry.data
}

export async function listLeads(params: LeadListParams = {}): Promise<LeadListResult> {
  const res = await client.get<ApiResponse<LeadListResult>>('/leads', {
    params: {
      source: params.source || undefined,
      status: params.status || undefined,
      name: params.name || undefined,
      phone: params.phone || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
  const data = unwrap(res, 'Failed to list leads')
  // 兼容旧数组（若有）
  if (Array.isArray(data)) {
    const legacy = { items: data as Lead[], total: (data as Lead[]).length, page: 1, page_size: 20 }
    writeLeadListCache(params, legacy)
    return legacy
  }
  writeLeadListCache(params, data)
  return data
}

export async function getLead(id: number): Promise<Lead> {
  const res = await client.get<ApiResponse<Lead>>(`/leads/${id}`)
  return unwrap(res, 'Failed to get lead')
}

export async function createLead(payload: LeadCreateInput): Promise<Lead> {
  assertValidOptionalPhone(payload.phone)
  const res = await client.post<ApiResponse<Lead>>('/leads', payload)
  return unwrap(res, 'Failed to create lead')
}

export async function importLeadWorkbook(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<LeadImportResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post<ApiResponse<LeadImportResult>>('/leads/import', form, {
    timeout: 120_000,
    onUploadProgress: (event) => {
      if (!event.total) return
      onProgress?.(Math.min(99, Math.round((event.loaded / event.total) * 100)))
    },
  })
  onProgress?.(100)
  return unwrap(res, '导入线索失败')
}

export async function downloadLeadImportTemplate(): Promise<void> {
  const res = await client.get('/leads/import-template', { responseType: 'blob' })
  const url = URL.createObjectURL(res.data as Blob)
  const link = document.createElement('a')
  link.href = url
  link.download = '线索导入模板.xlsx'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export async function patchLead(id: number, payload: LeadUpdateInput): Promise<Lead> {
  if ('phone' in payload) assertValidOptionalPhone(payload.phone)
  const res = await client.patch<ApiResponse<Lead>>(`/leads/${id}`, payload)
  return unwrap(res, 'Failed to update lead')
}

export async function listLeadActivities(
  id: number,
  params: { kind?: string; limit?: number; page?: number; page_size?: number } = {},
): Promise<{ items: LeadActivity[]; total: number; page?: number; page_size?: number }> {
  const res = await client.get<
    ApiResponse<{ items: LeadActivity[]; total: number; page?: number; page_size?: number }>
  >(`/leads/${id}/activities`, {
    params: {
      kind: params.kind || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? params.limit ?? 50,
      limit: params.limit,
    },
  })
  return unwrap(res, 'Failed to list activities')
}

export async function createLeadFollow(
  id: number,
  payload: LeadFollowInput,
): Promise<{ activity: LeadActivity; lead: Lead }> {
  const res = await client.post<ApiResponse<{ activity: LeadActivity; lead: Lead }>>(
    `/leads/${id}/activities`,
    payload,
  )
  return unwrap(res, 'Failed to create follow activity')
}

export async function listLeadAssignees(): Promise<LeadAssignee[]> {
  const res = await client.get<ApiResponse<LeadAssignee[]>>('/leads/assignees')
  return unwrap(res, 'Failed to list assignees')
}

export async function joinLeadCollaborator(id: number): Promise<Lead> {
  const res = await client.post<ApiResponse<Lead>>(`/leads/${id}/collaborators/me`)
  return unwrap(res, 'Failed to join collaborator')
}

export async function addLeadCollaborator(
  id: number,
  payload: { user_id: number; note?: string },
): Promise<Lead> {
  const res = await client.post<ApiResponse<Lead>>(`/leads/${id}/collaborators`, payload)
  return unwrap(res, 'Failed to add collaborator')
}

export async function removeLeadCollaborator(id: number, userId: number): Promise<Lead> {
  const res = await client.delete<ApiResponse<Lead>>(`/leads/${id}/collaborators/${userId}`)
  return unwrap(res, 'Failed to remove collaborator')
}
