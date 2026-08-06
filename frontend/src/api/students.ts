import client from './client'
import { asPageResult, type PageResult } from './paging'
import { assertValidOptionalPhone } from '../utils/phone'
// PageResult used by listStudentsApi / listLearningApi

export type StudentStatus = 'active' | 'paused' | 'graduated' | 'quit'
export type ClassStatus = 'attended' | 'absent' | 'late' | 'leave' | 'makeup'

export interface StudentCourseLink {
  id?: number | null
  name: string
  type?: string
  price_label?: string
}

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
  linked_courses?: StudentCourseLink[]
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
  /** 新建时必选至少一门关联课程 */
  courses: StudentCourseLink[]
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

/** 报读课程（课包聚合） */
export interface StudentPackageOrderRow {
  package_id: number
  order_id?: number | null
  order_no: string
  purchase_hours: number
  gift_hours: number
  consumed_hours: number
  refund_hours: number
  remain_hours: number
  valid_until?: string | null
  priority_consume: boolean
  status: string
  unit_price: number
  created_at?: string
}

export interface StudentCoursePackageGroup {
  course_id?: number | null
  course_name: string
  course_type?: string
  type_label?: string
  remain_hours: number
  consumed_hours: number
  total_hours: number
  class_id?: number | null
  class_name: string
  packages: StudentPackageOrderRow[]
  from_link_only?: boolean
}

export interface StudentCoursePackagesResult {
  summary: {
    remain_hours: number
    overtime_hours: number
    consumed_hours: number
    total_hours: number
  }
  courses: StudentCoursePackageGroup[]
}

export async function getStudentCoursePackagesApi(
  studentId: number,
): Promise<StudentCoursePackagesResult> {
  const res = await client.get(`/students/${studentId}/course-packages`)
  return res.data.data
}

export interface StudentOrdersResult {
  summary: {
    order_amount: number
    received_amount: number
    arrears_amount: number
  }
  items: {
    id: number
    order_no: string
    order_type: string
    order_type_label: string
    item: string
    receivable: number
    received: number
    arrears: number
    status: string
    status_label: string
    source: string
    performance_owner: string
    handler: string
    created_at?: string
  }[]
  total: number
}

export async function getStudentOrdersApi(
  studentId: number,
  params: { page?: number; page_size?: number } = {},
): Promise<StudentOrdersResult & { page?: number; page_size?: number }> {
  const res = await client.get(`/students/${studentId}/orders`, {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
  return res.data.data
}

export interface StudentActivityEvent {
  id: string
  kind: string
  kind_label: string
  title: string
  at?: string | null
  lines: string[]
  order_id?: number | null
  order_no?: string
  meta?: Record<string, unknown>
}

export async function getStudentActivityApi(
  studentId: number,
  limit = 50,
): Promise<{ items: StudentActivityEvent[]; total: number }> {
  const res = await client.get(`/students/${studentId}/activity`, { params: { limit } })
  return res.data.data
}

export type StudentClassRecordView = 'completed' | 'pending'

export interface StudentClassRecordRow {
  id: number
  row_type: StudentClassRecordView
  schedule_id?: number | null
  roll_at?: string | null
  class_id: number
  class_name: string
  course_id?: number | null
  course_name: string
  class_start?: string | null
  class_end?: string | null
  teachers: string
  teacher_ids: number[]
  attendance_status: string
  attendance_status_label: string
  makeup_status_label: string
  consumption_type: string
  hours_consumed: number
  amount: number
  content: string
  notes: string
  record_status: string
  record_status_label: string
}

export interface StudentClassRecordsResult {
  items: StudentClassRecordRow[]
  total: number
  page: number
  page_size: number
  summary: { present: number; late: number; leave: number; absent: number }
  filters: {
    classes: { id: number; name: string }[]
    courses: { id: number; name: string }[]
    teachers: { id: number; name: string }[]
  }
}

export interface StudentClassRecordParams {
  view?: StudentClassRecordView
  start?: string
  end?: string
  class_id?: number
  course_id?: number
  teacher_id?: number
  attendance_status?: string
  record_status?: string
  page?: number
  page_size?: number
}

export async function getStudentClassRecordsApi(
  studentId: number,
  params: StudentClassRecordParams = {},
): Promise<StudentClassRecordsResult> {
  const res = await client.get(`/students/${studentId}/class-records`, { params })
  return res.data.data
}

export async function createStudentApi(payload: StudentInput): Promise<Student> {
  assertValidOptionalPhone(payload.phone)
  const res = await client.post('/students', payload)
  return res.data.data
}

export async function patchStudentApi(
  id: number,
  payload: Partial<StudentInput>,
): Promise<Student> {
  if ('phone' in payload) assertValidOptionalPhone(payload.phone)
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
  q?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<LearningRecord>> {
  const res = await client.get('/learning-records', {
    params: {
      student_id: params.student_id,
      teacher_id: params.teacher_id,
      mine: params.mine,
      q: params.q || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  })
  return asPageResult<LearningRecord>(res.data.data, params.page ?? 1, params.page_size ?? 20)
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
