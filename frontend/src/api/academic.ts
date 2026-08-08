import client from './client'
import { asPageResult, type PageResult } from './paging'

export type CourseType = 'group' | 'one_to_one'
export type ClassMode = 'group' | 'one_to_one'

export interface Course {
  id: number
  name: string
  course_type: CourseType
  type_label: string
  grade: string
  subject: string
  term: string
  billing_mode: string
  billing_label: string
  unit_price: number
  price_label: string
  leave_rule: string
  absent_rule: string
  color: string
  enabled: boolean
  student_count: number
  remark: string
  created_at?: string
  updated_at?: string
}

export interface CourseInput {
  name: string
  course_type?: CourseType
  grade?: string
  subject?: string
  term?: string
  billing_mode?: string
  unit_price?: number
  leave_rule?: string
  absent_rule?: string
  color?: string
  enabled?: boolean
  remark?: string
}

export interface CourseEligibleStudent {
  id: number
  name: string
  grade: string
  school: string
  phone: string
  status: string
  course_id: number
  has_package: boolean
  remain_hours: number
  grade_matched: boolean
}

export interface ClassMemberBrief {
  id: number
  name: string
  phone: string
  gender?: string
  remain_hours?: number
  consume_label?: string
}

export interface ClassRoom {
  id: number
  name: string
  mode: ClassMode
  mode_label?: string
  course_id?: number | null
  course_name: string
  teachers: string
  teacher_ids: number[]
  student_ids: number[]
  members?: ClassMemberBrief[]
  member_count: number
  capacity?: number | null
  capacity_label: string
  over_capacity: boolean
  open_count?: number | null
  category: string
  hours_per_session: number
  default_room?: string
  primary_student_id?: number | null
  student_name?: string | null
  phone?: string | null
  scheduled_label: string
  done_sessions?: number
  scheduled_sessions?: number
  taught_hours: number
  remain_hours: number
  status: string
  status_label?: string
  remark: string
}

export interface ClassInput {
  name: string
  mode?: ClassMode
  course_id?: number | null
  capacity?: number | null
  over_capacity?: boolean
  open_count?: number | null
  category?: string
  hours_per_session?: number
  default_room?: string
  teacher_ids?: number[]
  head_teacher_id?: number | null
  student_ids?: number[]
  primary_student_id?: number | null
  remark?: string
  status?: string
}

export interface ScheduleLesson {
  id: number
  class_id: number
  class_name: string
  course_id?: number | null
  course_name: string
  course_color?: string
  start_at: string
  end_at: string
  room: string
  status: string
  teacher_ids: number[]
  teachers: string
  capacity?: number | null
  capacity_label: string
  over_capacity?: boolean
  students: string
  member_count: number
  /** 授课课时（班级单次课次，非墙钟时长） */
  hours?: number
  hours_per_session?: number
  /** 是否允许点名（当天及过去课次，且未点名） */
  can_roll_call?: boolean
  remark: string
}

export interface ScheduleLessonMember {
  id: number
  name: string
  phone: string
  remain_hours: number
  consume_label: string
  deducted_hours?: number | null
}

export interface ScheduleLessonDetail extends ScheduleLesson {
  hours?: number
  hours_per_session?: number
  open_count?: number | null
  open_count_label?: string
  capacity_value?: number | null
  capacity_text?: string
  status_label?: string
  members?: ScheduleLessonMember[]
}

export interface ScheduleRoomOption {
  name: string
  busy?: boolean
  status?: string
  conflicts?: ScheduleConflictItem[]
}

export interface ScheduleConflictItem {
  id: number
  class_name: string
  start_at: string
  end_at: string
  room?: string
  teachers?: string
}

export interface TeacherAvailability {
  id: number
  name: string
  username?: string
  phone?: string
  busy: boolean
  status: string
  conflicts: ScheduleConflictItem[]
}

export interface ScheduleBatchInput {
  class_id: number
  start_date: string
  start_time: string
  end_time: string
  repeat_mode?: 'daily' | 'alternate' | 'weekly' | 'biweekly'
  end_mode?: 'by_date' | 'by_count'
  end_date?: string
  session_count?: number
  weekdays?: number[]
  room?: string
  teacher_ids?: number[]
  remark?: string
  on_conflict?: 'skip' | 'fail' | 'force'
}

export interface ScheduleBatchResult {
  created_count: number
  skipped_count: number
  items: ScheduleLesson[]
  skipped: { date: string; start_at: string; end_at: string; reason: string }[]
}

export interface RollCallOptions {
  date: string
  /** 查询区间开始（含），周课表点名时返回 */
  start?: string
  /** 查询区间结束（含） */
  end?: string
  classes: ClassRoom[]
  schedules: ScheduleLesson[]
}

export interface ClassRecord {
  id: number
  class_id: number
  class_name: string
  schedule_id?: number | null
  course_id?: number | null
  course_name: string
  course_type: string
  course_type_label: string
  roll_at: string
  class_start?: string | null
  class_end?: string | null
  room?: string
  teachers: string
  teacher_ids: number[]
  hours: number
  salary_hours: number
  status: string
  status_label: string
  content: string
  amount: number
  attendance: string
  present_count: number
  total_count: number
  created_at?: string
  creator_name?: string
}

export interface ClassAttendanceDetail {
  student_id: number
  student_name: string
  phone: string
  status: string
  status_label: string
  hours_consumed: number
  uncovered_hours: number
  amount: number
}

export interface ClassRecordDetail extends ClassRecord {
  attendances: ClassAttendanceDetail[]
  uncovered_hours: number
}

export interface ClassRecordOperationLog {
  id: number
  action: string
  action_label: string
  detail: string
  operator_id?: number | null
  operator_name: string
  created_at: string
}

export interface TimeoutClassRecord {
  id: number
  class_id: number
  class_name: string
  course_id?: number | null
  course_name: string
  start_at: string
  end_at: string
  room: string
  status: string
  teachers: string
  teacher_ids: number[]
  content?: string
}

export interface MakeupClassRecord {
  id: number
  record_id: number
  student_id: number
  student_name: string
  phone: string
  class_id: number
  class_name: string
  course_id?: number | null
  course_name: string
  class_start?: string | null
  class_end?: string | null
  teachers: string
  absence_status: string
  absence_status_label: string
  consume_label: string
  expected_hours: number
  actual_hours: number
  amount: number
  makeup_status: string
  makeup_status_label: string
  content: string
}

export interface TeacherManage {
  id: number
  name: string
  username: string
  role: string
  role_code: string
  subject: string
  phone: string
  class_count: number
  status: string
  is_active: boolean
}

export async function listCoursesApi(
  params: {
    q?: string
    course_type?: string
    enabled?: boolean
    page?: number
    page_size?: number
  } = {},
  opts?: { skipErrorToast?: boolean },
): Promise<PageResult<Course>> {
  const res = await client.get('/academic/courses', {
    params,
    skipErrorToast: opts?.skipErrorToast,
  } as import('./client').AppAxiosRequestConfig)
  return asPageResult<Course>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function getCourseApi(id: number): Promise<Course> {
  const res = await client.get(`/academic/courses/${id}`)
  return res.data.data
}

export async function listCourseEligibleStudentsApi(
  courseId: number,
  params: { q?: string; page?: number; page_size?: number } = {},
): Promise<PageResult<CourseEligibleStudent>> {
  const res = await client.get(`/academic/courses/${courseId}/eligible-students`, { params })
  return asPageResult<CourseEligibleStudent>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function createCourseApi(payload: CourseInput): Promise<Course> {
  const res = await client.post('/academic/courses', payload)
  return res.data.data
}

export async function updateCourseApi(id: number, payload: Partial<CourseInput>): Promise<Course> {
  const res = await client.patch(`/academic/courses/${id}`, payload)
  return res.data.data
}

export async function deleteCourseApi(id: number): Promise<void> {
  await client.delete(`/academic/courses/${id}`)
}

export async function listClassesApi(
  params: {
    mode?: string
    q?: string
    course_id?: number
    teacher_id?: number
    only_mine?: boolean
    page?: number
    page_size?: number
  } = {},
  opts?: { skipErrorToast?: boolean },
): Promise<PageResult<ClassRoom>> {
  const res = await client.get('/academic/classes', {
    params,
    skipErrorToast: opts?.skipErrorToast,
  } as import('./client').AppAxiosRequestConfig)
  return asPageResult<ClassRoom>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function getClassApi(id: number): Promise<ClassRoom> {
  const res = await client.get(`/academic/classes/${id}`)
  return res.data.data
}

export async function createClassApi(payload: ClassInput): Promise<ClassRoom> {
  const res = await client.post('/academic/classes', payload)
  return res.data.data
}

export async function updateClassApi(id: number, payload: Partial<ClassInput> & { status?: string }): Promise<ClassRoom> {
  const res = await client.patch(`/academic/classes/${id}`, payload)
  return res.data.data
}

export async function addClassStudentsApi(id: number, studentIds: number[]): Promise<ClassRoom> {
  const res = await client.post(`/academic/classes/${id}/students`, { student_ids: studentIds })
  return res.data.data
}

export async function removeClassStudentApi(id: number, studentId: number): Promise<ClassRoom> {
  const res = await client.delete(`/academic/classes/${id}/students/${studentId}`)
  return res.data.data
}

export async function deleteClassApi(id: number): Promise<void> {
  await client.delete(`/academic/classes/${id}`)
}

export async function listSchedulesApi(params: {
  start?: string
  end?: string
  class_id?: number
  course_id?: number
  teacher_id?: number
  room?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<ScheduleLesson>> {
  const res = await client.get('/academic/schedules', { params })
  return asPageResult<ScheduleLesson>(res.data.data, params.page ?? 1, params.page_size ?? 200)
}

export async function getRollCallOptionsApi(params: {
  date?: string
  start?: string
  end?: string
} = {}): Promise<RollCallOptions> {
  const res = await client.get('/academic/class-records/roll-options', { params })
  return res.data.data
}

export async function getScheduleApi(id: number): Promise<ScheduleLessonDetail> {
  const res = await client.get(`/academic/schedules/${id}`)
  return res.data.data
}

export async function listRoomsApi(): Promise<{ name: string }[]> {
  const res = await client.get('/academic/rooms')
  return res.data.data?.items ?? []
}

export async function checkScheduleConflictsApi(payload: {
  start_at: string
  end_at: string
  teacher_ids?: number[]
  room?: string
  exclude_id?: number
}): Promise<{
  ok: boolean
  has_conflict: boolean
  teachers: TeacherAvailability[]
  rooms: ScheduleRoomOption[]
  error?: string
}> {
  const res = await client.post('/academic/schedules/conflicts', payload)
  return res.data.data
}

export async function scheduleAvailabilityApi(payload: {
  start_at: string
  end_at: string
  exclude_id?: number
}): Promise<{ teachers: TeacherAvailability[]; rooms: ScheduleRoomOption[] }> {
  const res = await client.post('/academic/schedules/availability', payload)
  return res.data.data
}

export async function createScheduleApi(payload: {
  class_id: number
  start_at: string
  end_at: string
  room?: string
  teacher_ids?: number[]
  remark?: string
  force?: boolean
}): Promise<ScheduleLesson> {
  const res = await client.post('/academic/schedules', payload)
  return res.data.data
}

export async function createSchedulesBatchApi(payload: ScheduleBatchInput): Promise<ScheduleBatchResult> {
  const res = await client.post('/academic/schedules/batch', payload)
  return res.data.data
}

export async function updateScheduleApi(
  id: number,
  payload: {
    start_at?: string
    end_at?: string
    room?: string
    teacher_ids?: number[]
    status?: string
    remark?: string
    force?: boolean
  },
): Promise<ScheduleLesson> {
  const res = await client.patch(`/academic/schedules/${id}`, payload)
  return res.data.data
}

export interface ScheduleBatchUpdateInput {
  ids: number[]
  update_teachers?: boolean
  update_room?: boolean
  update_remark?: boolean
  update_time?: boolean
  teacher_ids?: number[]
  room?: string
  remark?: string
  /** HH:mm，仅改时刻，日期保留 */
  start_time?: string
  end_time?: string
  force?: boolean
}

export interface ScheduleBatchUpdateResult {
  updated_count: number
  failed_count: number
  skipped_count: number
  items: ScheduleLesson[]
  failed: { id: number; reason: string }[]
  skipped: { id: number; reason: string }[]
}

export interface ScheduleBatchDeleteResult {
  deleted_count: number
  cancelled_count: number
  failed_count: number
  failed: { id: number; reason: string }[]
}

/** 批量修改课次（换老师/教室等），与课表同源自动同步 */
export async function updateSchedulesBatchApi(
  payload: ScheduleBatchUpdateInput,
): Promise<ScheduleBatchUpdateResult> {
  const res = await client.post('/academic/schedules/batch-update', payload)
  return res.data.data
}

export async function deleteSchedulesBatchApi(ids: number[]): Promise<ScheduleBatchDeleteResult> {
  const res = await client.post('/academic/schedules/batch-delete', { ids })
  return res.data.data
}

export async function deleteScheduleApi(id: number): Promise<void> {
  await client.delete(`/academic/schedules/${id}`)
}

export async function listClassRecordsApi(params: {
  class_id?: number
  course_id?: number
  teacher_id?: number
  status?: string
  start?: string
  end?: string
  class_start?: string
  class_end?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<ClassRecord>> {
  const res = await client.get('/academic/class-records', { params })
  return asPageResult<ClassRecord>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function listTimeoutClassRecordsApi(params: {
  class_id?: number
  course_id?: number
  teacher_id?: number
  start?: string
  end?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<TimeoutClassRecord>> {
  const res = await client.get('/academic/class-records/timeout', { params })
  return asPageResult<TimeoutClassRecord>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function listMakeupClassRecordsApi(params: {
  q?: string
  class_id?: number
  start?: string
  end?: string
  page?: number
  page_size?: number
} = {}): Promise<PageResult<MakeupClassRecord>> {
  const res = await client.get('/academic/class-records/makeup', { params })
  return asPageResult<MakeupClassRecord>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function getClassRecordApi(id: number): Promise<ClassRecordDetail> {
  const res = await client.get(`/academic/class-records/${id}`)
  return res.data.data
}

export async function listClassRecordLogsApi(id: number): Promise<ClassRecordOperationLog[]> {
  const res = await client.get(`/academic/class-records/${id}/logs`)
  return res.data.data?.items ?? []
}

export async function updateClassRecordApi(
  id: number,
  payload: {
    class_start?: string | null
    class_end?: string | null
    hours?: number
    salary_hours?: number
    room?: string
    teacher_ids?: number[]
    content?: string
  },
): Promise<ClassRecordDetail> {
  const res = await client.patch(`/academic/class-records/${id}`, payload)
  return res.data.data
}

export async function updateClassAttendanceApi(
  recordId: number,
  studentId: number,
  status: string,
): Promise<ClassRecordDetail> {
  const res = await client.patch(`/academic/class-records/${recordId}/attendances/${studentId}`, { status })
  return res.data.data
}

export async function removeClassAttendanceApi(
  recordId: number,
  studentId: number,
): Promise<ClassRecordDetail> {
  const res = await client.delete(`/academic/class-records/${recordId}/attendances/${studentId}`)
  return res.data.data
}

export async function createClassRecordApi(payload: {
  class_id: number
  schedule_id?: number | null
  class_start?: string | null
  class_end?: string | null
  hours?: number
  salary_hours?: number
  teacher_ids?: number[]
  content?: string
  attendances?: { student_id: number; status: string }[]
}): Promise<ClassRecord> {
  const res = await client.post('/academic/class-records', payload)
  return res.data.data
}

export async function voidClassRecordApi(id: number): Promise<ClassRecord> {
  const res = await client.post(`/academic/class-records/${id}/void`)
  return res.data.data
}

export async function listAcademicTeachersApi(
  params: {
    q?: string
    page?: number
    page_size?: number
  } = {},
  opts?: { skipErrorToast?: boolean },
): Promise<PageResult<TeacherManage>> {
  const res = await client.get('/academic/teachers', {
    params,
    skipErrorToast: opts?.skipErrorToast,
  } as import('./client').AppAxiosRequestConfig)
  return asPageResult<TeacherManage>(res.data.data, params.page ?? 1, params.page_size ?? 50)
}
