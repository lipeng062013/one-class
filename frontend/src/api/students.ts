import client from './client'
import { asPageResult, type PageResult } from './paging'

export type StudentStatus = 'active' | 'paused' | 'graduated' | 'quit'
export type ClassStatus = 'attended' | 'absent' | 'late' | 'leave' | 'makeup'

export interface Student {
  id: number
  name: string
  grade: string
  school: string
  phone: string | null
  parent_name: string | null
  academic_manager_id: number | null
  academic_manager_name: string | null
  status: string
  source_lead_id: number | null
  notes: string
  created_by: number | null
  created_at?: string | null
  updated_at?: string | null
  latest_learning_at?: string | null
}

export interface StudentInput {
  name: string
  grade: string
  school?: string
  phone?: string | null
  parent_name?: string | null
  academic_manager_id?: number | null
  status?: StudentStatus | string
  notes?: string
}

export interface ManagerOption {
  id: number
  display_name: string
  username: string
  is_active: boolean
  student_count: number
}

export interface LearningFile {
  id: number
  file_path: string
  file_type: string
  sort_order: number
}

export interface LearningRecord {
  id: number
  student_id: number
  student_name?: string | null
  teacher_id: number
  teacher_name?: string | null
  class_date?: string | null
  class_status: string
  subject?: string | null
  learning_summary: string
  homework_note: string
  notes: string
  created_at?: string | null
  updated_at?: string | null
  files: LearningFile[]
}

export interface LearningInput {
  student_id: number
  class_date?: string | null
  class_status?: ClassStatus | string
  subject?: string | null
  learning_summary: string
  homework_note?: string
  notes?: string
}

export interface StudentListParams {
  grade?: string
  name?: string
  phone?: string
  status?: string
  school?: string
  academic_manager_id?: number
  q?: string
  page?: number
  page_size?: number
}

export async function listManagersApi(includeInactive = true): Promise<ManagerOption[]> {
  const res = await client.get('/students/managers', {
    params: { include_inactive: includeInactive },
  })
  return res.data.data
}

export async function listStudentsApi(
  params: StudentListParams = {},
): Promise<PageResult<Student>> {
  const res = await client.get('/students', {
    params: {
      grade: params.grade || undefined,
      name: params.name || undefined,
      phone: params.phone || undefined,
      status: params.status || undefined,
      school: params.school || undefined,
      academic_manager_id: params.academic_manager_id,
      q: params.q || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
  return asPageResult<Student>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

/** 下拉选学生等：取前若干条 */
export async function listStudentsForPicker(
  params: Omit<StudentListParams, 'page' | 'page_size'> = {},
  limit = 100,
): Promise<Student[]> {
  const page = await listStudentsApi({
    ...params,
    page: 1,
    page_size: Math.min(100, Math.max(1, limit)),
  })
  return page.items
}

export async function getStudentApi(id: number): Promise<Student> {
  const res = await client.get(`/students/${id}`)
  return res.data.data
}

export async function createStudentApi(payload: StudentInput): Promise<Student> {
  const res = await client.post('/students', payload)
  return res.data.data
}

export async function patchStudentApi(
  id: number,
  payload: Partial<StudentInput>,
): Promise<Student> {
  const res = await client.patch(`/students/${id}`, payload)
  return res.data.data
}

export async function deleteStudentApi(id: number): Promise<void> {
  await client.delete(`/students/${id}`)
}

export async function bulkDeleteStudentsApi(
  studentIds: number[],
): Promise<{ deleted_count: number; deleted_ids: number[] }> {
  const res = await client.post('/students/bulk-delete', { student_ids: studentIds })
  return res.data.data
}

export async function reassignStudentsApi(payload: {
  student_ids: number[]
  to_manager_id: number
  from_manager_id?: number | null
}): Promise<{ updated_count: number; to_manager_name: string }> {
  const res = await client.post('/students/reassign', payload)
  return res.data.data
}

export async function listLearningApi(params: {
  student_id?: number
  teacher_id?: number
  mine?: boolean
} = {}): Promise<LearningRecord[]> {
  const res = await client.get('/learning-records', { params })
  return res.data.data
}

export async function getLearningApi(id: number): Promise<LearningRecord> {
  const res = await client.get(`/learning-records/${id}`)
  return res.data.data
}

export async function createLearningApi(payload: LearningInput): Promise<LearningRecord> {
  const res = await client.post('/learning-records', payload)
  return res.data.data
}

export async function patchLearningApi(
  id: number,
  payload: Partial<LearningInput>,
): Promise<LearningRecord> {
  const res = await client.patch(`/learning-records/${id}`, payload)
  return res.data.data
}

export async function deleteLearningApi(id: number): Promise<void> {
  await client.delete(`/learning-records/${id}`)
}

export async function uploadLearningFileApi(id: number, file: File): Promise<LearningFile> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post(`/learning-records/${id}/files`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data.data
}

export type LearningFileOpts = {
  /** 列表/网格缩略图，体积远小于原图 */
  thumb?: boolean
  /** 缩略图最长边（仅 thumb 时生效） */
  w?: number
}

export async function learningFileObjectUrl(
  fileId: number,
  opts?: LearningFileOpts,
): Promise<string> {
  const params: Record<string, string | number | boolean> = {}
  if (opts?.thumb) {
    params.thumb = true
    if (opts.w != null) params.w = opts.w
  }
  const res = await client.get(`/learning-records/files/${fileId}/content`, {
    responseType: 'blob',
    params,
  })
  return URL.createObjectURL(res.data)
}

export interface GrowthReportOptions {
  /** YYYY-MM-DD，可选；与 record_ids 二选一（有 record_ids 时优先） */
  date_from?: string | null
  date_to?: string | null
  /** 指定学情记录 id 列表 */
  record_ids?: number[] | null
}

/** 下载学情成长档案 PDF：全部 / 按区间 / 按指定学情记录（文件名统一为 XXX的成长档案.pdf） */
export async function downloadGrowthReportApi(
  studentId: number,
  studentName: string,
  opts?: GrowthReportOptions,
): Promise<void> {
  const params: Record<string, string> = {}
  if (opts?.record_ids?.length) {
    params.record_ids = opts.record_ids.join(',')
  } else {
    if (opts?.date_from) params.date_from = opts.date_from
    if (opts?.date_to) params.date_to = opts.date_to
  }
  const res = await client.get(`/students/${studentId}/growth-report`, {
    responseType: 'blob',
    params,
    timeout: 120_000,
  })
  const blob = res.data as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const safe = (studentName || '学员').replace(/[\\/:*?"<>|]/g, '-').trim() || '学员'
  a.download = `${safe}的成长档案.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
