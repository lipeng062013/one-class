import client from './client'

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
}

export async function listManagersApi(includeInactive = true): Promise<ManagerOption[]> {
  const res = await client.get('/students/managers', {
    params: { include_inactive: includeInactive },
  })
  return res.data.data
}

export async function listStudentsApi(params: StudentListParams = {}): Promise<Student[]> {
  const res = await client.get('/students', { params })
  return res.data.data
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

export async function learningFileObjectUrl(fileId: number): Promise<string> {
  const res = await client.get(`/learning-records/files/${fileId}/content`, {
    responseType: 'blob',
  })
  return URL.createObjectURL(res.data)
}

/** 下载学情成长档案 PDF，文件名：{姓名}的成长档案.pdf */
export async function downloadGrowthReportApi(studentId: number, studentName: string): Promise<void> {
  const res = await client.get(`/students/${studentId}/growth-report`, {
    responseType: 'blob',
  })
  const blob = res.data as Blob
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${studentName}的成长档案.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
