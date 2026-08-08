<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addClassStudentsApi,
  createClassRecordApi,
  createScheduleApi,
  createSchedulesBatchApi,
  deleteScheduleApi,
  deleteSchedulesBatchApi,
  getClassApi,
  getClassRecordApi,
  listAcademicTeachersApi,
  listClassRecordsApi,
  listCourseEligibleStudentsApi,
  listCoursesApi,
  listRoomsApi,
  listSchedulesApi,
  removeClassStudentApi,
  updateClassApi,
  updateScheduleApi,
  updateSchedulesBatchApi,
  voidClassRecordApi,
  type ClassMemberBrief,
  type ClassRecord,
  type ClassRecordDetail,
  type ClassRoom,
  type Course,
  type CourseEligibleStudent,
  type ScheduleLesson,
  type ScheduleLessonDetail,
  type TeacherManage,
} from '../../api/academic'
import AppSheet from '../../components/AppSheet.vue'
import MobileActionBar from '../../components/MobileActionBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import ScheduleLessonDetailDrawer from './ScheduleLessonDetailDrawer.vue'

const auth = useAuthStore()
const { isApp } = useBreakpoint()
const route = useRoute()
const router = useRouter()

const { surface: editSurface, surfaceProps: editSurfaceProps } = useResponsiveSurface({
  dialogMaxWidth: '560px',
  size: '460px',
})
const { surface: addStudentSurface, surfaceProps: addStudentSurfaceProps } = useResponsiveSurface({
  dialogMaxWidth: '440px',
  size: '420px',
  compactSize: '72%',
})
const { surface: rollSurface, surfaceProps: rollSurfaceProps } = useResponsiveSurface({
  dialogWidth: '94%',
  dialogMaxWidth: '640px',
  size: '520px',
  compactSize: '92%',
  dialogProps: { top: '6vh', class: 'roll-dialog' },
  modalClass: 'class-roll-sheet',
})
const { surface: attendanceSurface, surfaceProps: attendanceSurfaceProps } = useResponsiveSurface({
  dialogWidth: '94%',
  dialogMaxWidth: '760px',
  size: '520px',
  compactSize: '88%',
  dialogProps: { class: 'attendance-detail-dialog' },
  modalClass: 'class-attendance-sheet',
})

const classId = computed(() => Number(route.params.id))
const loading = ref(false)
const detail = ref<ClassRoom | null>(null)
const activeTab = ref((route.query.tab as string) || 'schedule')

const schedules = ref<ScheduleLesson[]>([])
const records = ref<ClassRecord[]>([])
const courses = ref<Course[]>([])
const teachers = ref<TeacherManage[]>([])
const rooms = ref<{ name: string }[]>([])
const studentOptions = ref<CourseEligibleStudent[]>([])

const editVisible = ref(false)
const editSaving = ref(false)
const editForm = reactive({
  name: '',
  course_id: undefined as number | undefined,
  capacity: undefined as number | undefined,
  over_capacity: true,
  open_count: undefined as number | undefined,
  category: '',
  hours_per_session: 1,
  default_room: '',
  teacher_ids: [] as number[],
  remark: '',
})

const addStudentVisible = ref(false)
const addStudentIds = ref<number[]>([])
const addStudentSaving = ref(false)

const rollVisible = ref(false)
const rollLoading = ref(false)
const rollSaving = ref(false)
const rollMembers = ref<ClassMemberBrief[]>([])
const attendMap = ref<Record<number, string>>({})
const lockedRollScheduleId = ref<number | null>(null)
const rollForm = reactive({
  schedule_id: undefined as number | undefined,
  hours: 1,
  content: '',
})

const attendanceWeekAnchor = ref(new Date())
const lessonDetailVisible = ref(false)
const lessonDetailId = ref<number | null>(null)
const attendanceDetailVisible = ref(false)
const attendanceDetailLoading = ref(false)
const attendanceDetail = ref<ClassRecordDetail | null>(null)

const scheduleFormVisible = ref(false)
const scheduleFormKey = ref(0)
const scheduleSaving = ref(false)
const scheduleEditingId = ref<number | null>(null)
const scheduleForm = reactive({
  date: '',
  start_time: '09:00',
  end_time: '10:30',
  room: '',
  teacher_ids: [] as number[],
  remark: '',
  batch: false,
  repeat_mode: 'weekly' as 'daily' | 'weekly',
  weekdays: [] as number[],
  end_date: '',
  session_count: 8,
  end_mode: 'by_count' as 'by_date' | 'by_count',
})

/** 排课列表多选 */
const scheduleTableRef = ref<{ clearSelection: () => void } | null>(null)
const selectedSchedules = ref<ScheduleLesson[]>([])
const bulkEditVisible = ref(false)
const bulkEditKey = ref(0)
const bulkEditSaving = ref(false)
const bulkEditForm = reactive({
  update_teachers: true,
  update_room: false,
  update_time: false,
  update_remark: false,
  teacher_ids: [] as number[],
  room: '',
  start_time: '',
  end_time: '',
  remark: '',
  force: false,
})

const WEEKDAY_OPTIONS = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' },
]

const ATTENDANCE_OPTIONS = [
  { value: 'present', label: '出勤' },
  { value: 'late', label: '迟到' },
  { value: 'leave', label: '请假' },
  { value: 'absent', label: '缺勤' },
]

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const isGroup = computed(() => detail.value?.mode === 'group')
const isOneToOne = computed(() => detail.value?.mode === 'one_to_one')
/** 班级管理（建班/编辑/学员/删课次/撤销点名）：负责人与学管师一致 */
const canManageClass = computed(() => auth.hasPermission('academic.write') || auth.isAdmin)
/** 排课/点名等日常操作：管理权限或老师 */
const canManage = computed(() => canManageClass.value || auth.isTeacher)

interface AttendanceOverviewRow {
  key: string
  schedule?: ScheduleLesson
  record?: ClassRecord
  start_at: string
  end_at?: string | null
  course_name: string
  room: string
  teachers: string
  content: string
  roll_at?: string | null
  attendance: string
}

const weekRecords = computed<AttendanceOverviewRow[]>(() => {
  const weekStart = startOfWeek(attendanceWeekAnchor.value)
  const startAt = weekStart.getTime()
  const endAt = addDays(weekStart, 7).getTime()
  const normalRecords = records.value.filter((record) => record.status === 'normal')
  const recordsBySchedule = new Map<number, ClassRecord>()
  for (const record of normalRecords) {
    if (record.schedule_id) recordsBySchedule.set(record.schedule_id, record)
  }

  const rows: AttendanceOverviewRow[] = []
  for (const schedule of schedules.value) {
    const time = new Date(schedule.start_at).getTime()
    if (!Number.isFinite(time) || time < startAt || time >= endAt || schedule.status === 'cancelled') continue
    const record = recordsBySchedule.get(schedule.id)
    rows.push({
      key: `schedule-${schedule.id}`,
      schedule,
      record,
      start_at: record?.class_start || schedule.start_at,
      end_at: record?.class_end || schedule.end_at,
      course_name: record?.course_name || schedule.course_name,
      room: schedule.room || '',
      teachers: record?.teachers || schedule.teachers,
      content: record?.content || schedule.remark || '',
      roll_at: record?.roll_at,
      attendance: record?.attendance || '',
    })
  }

  for (const record of normalRecords) {
    if (record.schedule_id) continue
    const time = new Date(record.class_start || record.roll_at).getTime()
    if (!Number.isFinite(time) || time < startAt || time >= endAt) continue
    rows.push({
      key: `record-${record.id}`,
      record,
      start_at: record.class_start || record.roll_at,
      end_at: record.class_end,
      course_name: record.course_name,
      room: record.room || detail.value?.default_room || '',
      teachers: record.teachers,
      content: record.content,
      roll_at: record.roll_at,
      attendance: record.attendance,
    })
  }

  return rows.sort(
    (a, b) => new Date(b.start_at).getTime() - new Date(a.start_at).getTime(),
  )
})

// The weekly table is a schedule overview; history is the complete roll-call ledger.
const historyRecords = computed(() => records.value)

const attendanceWeekLabel = computed(() => {
  const start = startOfWeek(attendanceWeekAnchor.value)
  const end = addDays(start, 6)
  return `${dateKey(start)} ~ ${dateKey(end)}`
})

const isCurrentAttendanceWeek = computed(
  () => dateKey(startOfWeek(attendanceWeekAnchor.value)) === dateKey(startOfWeek(new Date())),
)

const rollScheduleOptions = computed(() =>
  schedules.value.filter(
    (schedule) => schedule.status === 'scheduled' || schedule.status === 'completed',
  ),
)

const rollRoom = computed(() => {
  if (rollForm.schedule_id) {
    return schedules.value.find((schedule) => schedule.id === rollForm.schedule_id)?.room || ''
  }
  return detail.value?.default_room || ''
})

const nameInitial = computed(() => (detail.value?.name || '?').slice(0, 1))

const statCards = computed(() => {
  const d = detail.value
  if (!d) return []
  if (isOneToOne.value) {
    return [
      { label: '已授课时', value: String(d.taught_hours ?? 0), unit: '课时', tone: 'gold' },
      { label: '剩余课时', value: String(d.remain_hours ?? 0), unit: '课时', tone: 'green' },
      { label: '已上/排课', value: d.scheduled_label || '0/0', unit: '', tone: 'amber' },
      { label: '单次课时', value: String(d.hours_per_session ?? 1), unit: '课时', tone: 'stone' },
    ]
  }
  return [
    { label: '班级人数', value: String(d.member_count ?? 0), unit: '人', tone: 'gold' },
    { label: '已上/排课', value: d.scheduled_label || '0/0', unit: '', tone: 'amber' },
    { label: '已授课时', value: String(d.taught_hours ?? 0), unit: '课时', tone: 'green' },
    { label: '单次课时', value: String(d.hours_per_session ?? 1), unit: '课时', tone: 'stone' },
  ]
})

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function dateKey(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function startOfWeek(value: Date) {
  const date = new Date(value)
  date.setHours(0, 0, 0, 0)
  const day = date.getDay() || 7
  date.setDate(date.getDate() - day + 1)
  return date
}

function addDays(value: Date, days: number) {
  const date = new Date(value)
  date.setDate(date.getDate() + days)
  return date
}

function padTime(d: Date) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatDateWeek(iso: string) {
  const d = new Date(iso)
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}(周${week})`
}

function timeRangeOf(start: string, end: string) {
  return `${padTime(new Date(start))}~${padTime(new Date(end))}`
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return `${dateKey(date)} ${padTime(date)}`
}

function formatMoney(value: number) {
  return `¥ ${value.toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getClassApi(classId.value)
  } catch {
    detail.value = null
    ElMessage.error('班级不存在或已删除')
  } finally {
    loading.value = false
  }
}

async function loadSchedules() {
  try {
    const res = await listSchedulesApi({
      class_id: classId.value,
      page: 1,
      page_size: 500,
    })
    schedules.value = res.items
  } catch {
    schedules.value = []
  }
  // 数据刷新后清掉多选，避免选中态与列表脱节
  clearScheduleSelection()
}

async function loadRecords() {
  try {
    const res = await listClassRecordsApi({
      class_id: classId.value,
      page: 1,
      page_size: 100,
    })
    records.value = res.items
  } catch {
    records.value = []
  }
}

async function loadMeta() {
  const [c, t, r] = await Promise.all([
    listCoursesApi({ enabled: true, page_size: 100 }).catch(() => ({ items: [] as Course[] })),
    listAcademicTeachersApi({ page_size: 100 }).catch(() => ({ items: [] as TeacherManage[] })),
    listRoomsApi().catch(() => [] as { name: string }[]),
  ])
  courses.value = c.items
  teachers.value = t.items
  rooms.value = r
}

function goBack() {
  const listMode =
    route.query.mode === 'one_to_one' || detail.value?.mode === 'one_to_one'
      ? 'one_to_one'
      : 'group'
  void router.push({
    name: 'academic-classes',
    query: { mode: listMode },
  })
}

function openEdit() {
  const d = detail.value
  if (!d) return
  editForm.name = d.name
  editForm.course_id = d.course_id ?? undefined
  editForm.capacity = d.capacity ?? undefined
  editForm.over_capacity = d.over_capacity
  editForm.open_count = d.open_count ?? undefined
  editForm.category = d.category || ''
  editForm.hours_per_session = d.hours_per_session || 1
  editForm.default_room = d.default_room || ''
  editForm.teacher_ids = [...(d.teacher_ids || [])]
  editForm.remark = d.remark || ''
  editVisible.value = true
}

async function saveEdit() {
  if (!editForm.name.trim()) {
    ElMessage.warning('请输入班级名称')
    return
  }
  editSaving.value = true
  try {
    detail.value = await updateClassApi(classId.value, {
      name: editForm.name.trim(),
      course_id: editForm.course_id,
      capacity: editForm.capacity,
      over_capacity: editForm.over_capacity,
      open_count: editForm.open_count,
      category: editForm.category,
      hours_per_session: editForm.hours_per_session,
      default_room: editForm.default_room,
      teacher_ids: editForm.teacher_ids,
      remark: editForm.remark,
    })
    ElMessage.success('班级信息已更新')
    editVisible.value = false
  } catch {
    /* */
  } finally {
    editSaving.value = false
  }
}

async function searchStudents(q: string) {
  if (!q.trim() || !detail.value?.course_id) return
  const res = await listCourseEligibleStudentsApi(detail.value.course_id, {
    q: q.trim(),
    page: 1,
    page_size: 20,
  }).catch(() => ({ items: [] as CourseEligibleStudent[] }))
  const map = new Map(studentOptions.value.map((s) => [s.id, s]))
  for (const s of res.items) map.set(s.id, s)
  studentOptions.value = Array.from(map.values())
}

function openAddStudents() {
  addStudentIds.value = []
  studentOptions.value = (detail.value?.members || []).map(
    (m) =>
      ({
        id: m.id,
        name: m.name,
        phone: m.phone || '',
        grade: '',
        school: '',
        status: 'active',
        course_id: detail.value?.course_id || 0,
        has_package: true,
        remain_hours: m.remain_hours || 0,
        grade_matched: true,
      }) as CourseEligibleStudent,
  )
  addStudentVisible.value = true
}

function isStudentInClass(studentId: number) {
  return (detail.value?.student_ids || []).includes(studentId)
}

function onAddStudentChange(studentIds: number[]) {
  const duplicateId = studentIds.find(isStudentInClass)
  if (duplicateId == null) return
  addStudentIds.value = studentIds.filter((id) => !isStudentInClass(id))
  const student = studentOptions.value.find((item) => item.id === duplicateId)
  ElMessage.warning(`学员「${student?.name || duplicateId}」已经在班，不用重复添加`)
}

async function saveAddStudents() {
  if (!detail.value) return
  const newStudentIds = addStudentIds.value.filter((id) => !isStudentInClass(id))
  if (!newStudentIds.length) {
    ElMessage.warning('请选择学员')
    return
  }
  addStudentSaving.value = true
  try {
    detail.value = await addClassStudentsApi(classId.value, newStudentIds)
    ElMessage.success('学员已添加')
    addStudentVisible.value = false
  } catch {
    /* */
  } finally {
    addStudentSaving.value = false
  }
}

async function removeStudent(studentId: number, name: string) {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(`确定将「${name}」移出本班？`, '移出本班', { type: 'warning' })
    detail.value = await removeClassStudentApi(classId.value, studentId)
    ElMessage.success('已移出')
  } catch {
    /* */
  }
}

function resetScheduleCreateForm(batch: boolean) {
  const d = detail.value
  // 同步新建班级时的默认教室 / 任课老师，避免一键排课、单次排课再手填
  Object.assign(scheduleForm, {
    date: '',
    start_time: '',
    end_time: '',
    room: d?.default_room || '',
    teacher_ids: [...(d?.teacher_ids || [])],
    remark: '',
    batch,
    repeat_mode: 'weekly' as const,
    weekdays: [] as number[],
    end_date: '',
    // 按次数时优先用班级开班课时数
    session_count: d?.open_count && d.open_count > 0 ? d.open_count : 8,
    end_mode: 'by_count' as const,
  })
}

async function openScheduleCreate(batch = false) {
  scheduleFormVisible.value = false
  scheduleEditingId.value = null
  // 打开前尽量拉最新班级资料，保证教室/老师与建班数据一致
  if (!detail.value) {
    await loadDetail()
  }
  resetScheduleCreateForm(batch)
  scheduleFormKey.value += 1
  await nextTick()
  scheduleFormVisible.value = true
}

async function openScheduleEdit(row: ScheduleLesson) {
  if (row.status === 'completed') {
    ElMessage.warning('已上课的排课不可编辑')
    return
  }
  scheduleEditingId.value = row.id
  scheduleForm.batch = false
  const s = new Date(row.start_at)
  const e = new Date(row.end_at)
  scheduleForm.date = dateKey(s)
  scheduleForm.start_time = padTime(s)
  scheduleForm.end_time = padTime(e)
  scheduleForm.room = row.room || ''
  scheduleForm.teacher_ids = [...(row.teacher_ids || [])]
  scheduleForm.remark = row.remark || ''
  scheduleFormKey.value += 1
  await nextTick()
  scheduleFormVisible.value = true
}

async function saveSchedule() {
  if (!scheduleForm.date || !scheduleForm.start_time || !scheduleForm.end_time) {
    ElMessage.warning('请填写上课日期与时间')
    return
  }
  if (scheduleForm.end_time <= scheduleForm.start_time) {
    ElMessage.warning('结束时间须晚于开始时间')
    return
  }
  if (scheduleForm.batch && scheduleForm.repeat_mode === 'weekly' && !scheduleForm.weekdays.length) {
    ElMessage.warning('请选择每周上课日')
    return
  }
  if (scheduleForm.batch && scheduleForm.end_mode === 'by_date') {
    if (!scheduleForm.end_date) {
      ElMessage.warning('请选择排课结束日期')
      return
    }
    if (scheduleForm.end_date < scheduleForm.date) {
      ElMessage.warning('结束日期不能早于开始日期')
      return
    }
  }
  if (scheduleForm.batch && scheduleForm.end_mode === 'by_count' && scheduleForm.session_count < 1) {
    ElMessage.warning('请填写排课次数')
    return
  }
  scheduleSaving.value = true
  try {
    if (scheduleEditingId.value != null) {
      await updateScheduleApi(scheduleEditingId.value, {
        start_at: `${scheduleForm.date}T${scheduleForm.start_time}:00`,
        end_at: `${scheduleForm.date}T${scheduleForm.end_time}:00`,
        room: scheduleForm.room,
        teacher_ids: scheduleForm.teacher_ids,
        remark: scheduleForm.remark,
      })
      ElMessage.success('排课已更新')
    } else if (scheduleForm.batch) {
      const result = await createSchedulesBatchApi({
        class_id: classId.value,
        start_date: scheduleForm.date,
        start_time: scheduleForm.start_time,
        end_time: scheduleForm.end_time,
        repeat_mode: scheduleForm.repeat_mode,
        end_mode: scheduleForm.end_mode,
        end_date: scheduleForm.end_date || undefined,
        session_count: scheduleForm.session_count,
        weekdays: scheduleForm.repeat_mode === 'weekly' ? scheduleForm.weekdays : undefined,
        room: scheduleForm.room,
        teacher_ids: scheduleForm.teacher_ids,
        remark: scheduleForm.remark,
        on_conflict: 'skip',
      })
      ElMessage.success(`已生成 ${result.created_count} 节课`)
    } else {
      await createScheduleApi({
        class_id: classId.value,
        start_at: `${scheduleForm.date}T${scheduleForm.start_time}:00`,
        end_at: `${scheduleForm.date}T${scheduleForm.end_time}:00`,
        room: scheduleForm.room,
        teacher_ids: scheduleForm.teacher_ids,
        remark: scheduleForm.remark,
      })
      ElMessage.success('排课已创建')
    }
    scheduleFormVisible.value = false
    await loadSchedules()
    await loadDetail()
  } catch {
    /* */
  } finally {
    scheduleSaving.value = false
  }
}

async function deleteSchedule(row: ScheduleLesson): Promise<boolean> {
  try {
    await ElMessageBox.confirm('确定删除该排课？', '删除确认', { type: 'warning' })
    await deleteScheduleApi(row.id)
    ElMessage.success('已删除')
    clearScheduleSelection()
    await loadSchedules()
    await loadDetail()
    return true
  } catch {
    return false
  }
}

function scheduleRowSelectable(row: ScheduleLesson) {
  return row.status !== 'completed' && row.status !== 'cancelled'
}

function onScheduleSelectionChange(rows: ScheduleLesson[]) {
  selectedSchedules.value = rows
}

function clearScheduleSelection() {
  selectedSchedules.value = []
  scheduleTableRef.value?.clearSelection?.()
}

function openBulkEdit() {
  if (!selectedSchedules.value.length) {
    ElMessage.warning('请先勾选要修改的课次')
    return
  }
  const editable = selectedSchedules.value.filter(scheduleRowSelectable)
  if (!editable.length) {
    ElMessage.warning('所选课次均已上课，不可批量修改')
    return
  }
  // 预填：取首条可编辑课次的老师/教室，方便换人时改动
  const first = editable[0]
  bulkEditForm.update_teachers = true
  bulkEditForm.update_room = false
  bulkEditForm.update_time = false
  bulkEditForm.update_remark = false
  bulkEditForm.teacher_ids = [...(first.teacher_ids || [])]
  bulkEditForm.room = first.room || detail.value?.default_room || ''
  bulkEditForm.start_time = first.start_at ? padTime(new Date(first.start_at)) : ''
  bulkEditForm.end_time = first.end_at ? padTime(new Date(first.end_at)) : ''
  bulkEditForm.remark = first.remark || ''
  bulkEditForm.force = false
  bulkEditKey.value += 1
  bulkEditVisible.value = true
}

async function saveBulkEdit() {
  const ids = selectedSchedules.value.filter(scheduleRowSelectable).map((r) => r.id)
  if (!ids.length) {
    ElMessage.warning('没有可修改的课次')
    return
  }
  if (
    !bulkEditForm.update_teachers &&
    !bulkEditForm.update_room &&
    !bulkEditForm.update_time &&
    !bulkEditForm.update_remark
  ) {
    ElMessage.warning('请至少勾选一项要修改的内容')
    return
  }
  if (bulkEditForm.update_teachers && !bulkEditForm.teacher_ids.length) {
    ElMessage.warning('请选择上课老师')
    return
  }
  if (bulkEditForm.update_time) {
    if (!bulkEditForm.start_time || !bulkEditForm.end_time) {
      ElMessage.warning('请填写上课开始与结束时间')
      return
    }
    if (bulkEditForm.end_time <= bulkEditForm.start_time) {
      ElMessage.warning('结束时间须晚于开始时间')
      return
    }
  }

  bulkEditSaving.value = true
  try {
    const result = await updateSchedulesBatchApi({
      ids,
      update_teachers: bulkEditForm.update_teachers,
      update_room: bulkEditForm.update_room,
      update_time: bulkEditForm.update_time,
      update_remark: bulkEditForm.update_remark,
      teacher_ids: bulkEditForm.teacher_ids,
      room: bulkEditForm.room,
      start_time: bulkEditForm.start_time || undefined,
      end_time: bulkEditForm.end_time || undefined,
      remark: bulkEditForm.remark,
      force: bulkEditForm.force,
    })
    const parts = [`已更新 ${result.updated_count} 节`]
    if (result.skipped_count) parts.push(`跳过 ${result.skipped_count}`)
    if (result.failed_count) parts.push(`失败 ${result.failed_count}`)
    if (result.failed_count && result.failed[0]?.reason) {
      ElMessage.warning(`${parts.join('，')}：${result.failed[0].reason}`)
    } else {
      ElMessage.success(parts.join('，') + '（课表已同步）')
    }
    bulkEditVisible.value = false
    clearScheduleSelection()
    await loadSchedules()
    await loadDetail()
  } catch {
    /* interceptor */
  } finally {
    bulkEditSaving.value = false
  }
}

async function bulkDeleteSchedules() {
  const ids = selectedSchedules.value.filter(scheduleRowSelectable).map((r) => r.id)
  if (!ids.length) {
    ElMessage.warning('请先勾选要删除的课次（已上课不可删）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 节课？删除后课表同步移除；已有点名记录的课次将改为取消。`,
      '批量删除',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const result = await deleteSchedulesBatchApi(ids)
    const parts = [`已删除 ${result.deleted_count} 节`]
    if (result.cancelled_count) parts.push(`取消 ${result.cancelled_count}`)
    if (result.failed_count) parts.push(`失败 ${result.failed_count}`)
    ElMessage.success(parts.join('，'))
    clearScheduleSelection()
    await loadSchedules()
    await loadDetail()
  } catch {
    /* interceptor */
  }
}

function changeAttendanceWeek(offset: number) {
  attendanceWeekAnchor.value = addDays(startOfWeek(attendanceWeekAnchor.value), offset * 7)
}

function resetAttendanceWeek() {
  attendanceWeekAnchor.value = new Date()
}

function openLessonDetail(lessonId: number) {
  lessonDetailId.value = lessonId
  lessonDetailVisible.value = true
}

function onLessonDetailEdit(lesson: ScheduleLessonDetail) {
  lessonDetailVisible.value = false
  openScheduleEdit(lesson)
}

async function onLessonDetailRemove(lesson: ScheduleLessonDetail) {
  const removed = await deleteSchedule(lesson)
  if (removed) {
    lessonDetailVisible.value = false
    lessonDetailId.value = null
    await loadRecords()
  }
}

function onLessonDetailRoll(lesson: ScheduleLessonDetail) {
  lessonDetailVisible.value = false
  void openRoll(lesson.id)
}

async function refreshAttendance() {
  await Promise.all([loadSchedules(), loadRecords(), loadDetail()])
}

function scheduleLabel(schedule: ScheduleLesson) {
  const start = new Date(schedule.start_at)
  const end = new Date(schedule.end_at)
  const futureTag =
    schedule.status === 'scheduled' && !isScheduleRollable(schedule) ? '（未到时间）' : ''
  return `${dateKey(start)} ${padTime(start)}-${padTime(end)}${schedule.room ? ` · ${schedule.room}` : ''}${schedule.status === 'completed' ? '（已点名）' : ''}${futureTag}`
}

/** 仅当天及过去的课次可点名 */
function isScheduleRollable(schedule: Pick<ScheduleLesson, 'start_at' | 'status' | 'can_roll_call'>) {
  if (schedule.status === 'completed' || schedule.status === 'cancelled') return false
  if (typeof schedule.can_roll_call === 'boolean') return schedule.can_roll_call
  const start = new Date(schedule.start_at)
  if (Number.isNaN(start.getTime())) return false
  const lessonDay = new Date(start)
  lessonDay.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return lessonDay.getTime() <= today.getTime()
}

function futureRollMessage() {
  return '不能对未来课程点名，仅可点当天及过去的课次'
}

function onRollScheduleChange(scheduleId: number | undefined) {
  // 授课课时按班级单次课次（默认 1）；机构 2 小时墙钟仍计 1 课时，与计薪课时无关
  rollForm.hours = Number(detail.value?.hours_per_session) > 0
    ? Number(detail.value?.hours_per_session)
    : 1
  if (!scheduleId) return
  const schedule = schedules.value.find((item) => item.id === scheduleId)
  if (!schedule) return
  if (!isScheduleRollable(schedule)) {
    ElMessage.warning(futureRollMessage())
    rollForm.schedule_id = undefined
    return
  }
  if (!rollForm.content && schedule.remark) rollForm.content = schedule.remark
}

async function openRoll(scheduleId?: number) {
  if (scheduleId && scheduleId > 0) {
    const schedule = schedules.value.find((item) => item.id === scheduleId)
    if (schedule && !isScheduleRollable(schedule)) {
      ElMessage.warning(futureRollMessage())
      return
    }
  }
  lockedRollScheduleId.value = scheduleId && scheduleId > 0 ? scheduleId : null
  rollForm.schedule_id = lockedRollScheduleId.value ?? undefined
  rollForm.hours = Number(detail.value?.hours_per_session) > 0
    ? Number(detail.value?.hours_per_session)
    : 1
  rollForm.content = ''
  rollMembers.value = []
  attendMap.value = {}
  rollVisible.value = true
  rollLoading.value = true
  try {
    const fresh = await getClassApi(classId.value)
    detail.value = fresh
    rollMembers.value = fresh.members || []
    attendMap.value = Object.fromEntries(
      rollMembers.value.map((member) => [member.id, 'present']),
    )
    onRollScheduleChange(scheduleId)
  } catch {
    rollMembers.value = []
  } finally {
    rollLoading.value = false
  }
}

function markAllAttendance(status: string) {
  attendMap.value = Object.fromEntries(
    rollMembers.value.map((member) => [member.id, status]),
  )
}

async function submitRoll() {
  if (!rollMembers.value.length) {
    ElMessage.warning('班级暂无学员，无法点名')
    return
  }
  const scheduleId = lockedRollScheduleId.value ?? rollForm.schedule_id
  if (scheduleId) {
    const schedule = schedules.value.find((item) => item.id === scheduleId)
    if (schedule && !isScheduleRollable(schedule)) {
      ElMessage.warning(futureRollMessage())
      return
    }
  }
  rollSaving.value = true
  try {
    await createClassRecordApi({
      class_id: classId.value,
      schedule_id: scheduleId ?? null,
      hours: rollForm.hours || 1,
      content: rollForm.content,
      attendances: rollMembers.value.map((member) => ({
        student_id: member.id,
        status: attendMap.value[member.id] || 'present',
      })),
    })
    ElMessage.success('点名成功，已生成上课记录与课消')
    rollVisible.value = false
    await Promise.all([loadRecords(), loadSchedules(), loadDetail()])
  } catch {
    /* interceptor */
  } finally {
    rollSaving.value = false
  }
}

async function openAttendanceDetail(record: ClassRecord) {
  attendanceDetailVisible.value = true
  attendanceDetailLoading.value = true
  attendanceDetail.value = null
  try {
    attendanceDetail.value = await getClassRecordApi(record.id)
  } catch {
    attendanceDetailVisible.value = false
  } finally {
    attendanceDetailLoading.value = false
  }
}

async function voidRecord(record: ClassRecord) {
  try {
    await ElMessageBox.confirm(
      '确定撤销该点名记录？课消将作废，并回滚已扣课时。',
      '撤销点名',
      { type: 'warning' },
    )
    await voidClassRecordApi(record.id)
    ElMessage.success('点名已撤销，课时已回滚')
    await Promise.all([loadRecords(), loadSchedules(), loadDetail()])
  } catch {
    /* cancelled or intercepted */
  }
}

function recordRoom(record: ClassRecord) {
  if (record.room) return record.room
  if (record.schedule_id) {
    return schedules.value.find((schedule) => schedule.id === record.schedule_id)?.room || '-'
  }
  return detail.value?.default_room || '-'
}

watch(activeTab, (tab) => {
  if (tab === 'schedule') void loadSchedules()
  if (tab === 'attendance') void loadRecords()
})

onMounted(async () => {
  await loadMeta()
  await loadDetail()
  if (route.query.tab === 'students') activeTab.value = 'students'
  if (route.query.tab === 'attendance') activeTab.value = 'attendance'
  await loadSchedules()
  if (activeTab.value === 'attendance') await loadRecords()
})
</script>

<template>
  <div class="class-detail-page oc-page-shell" :class="{ 'is-app': isApp }" v-loading="loading">
    <div v-if="!isApp" class="page-toolbar">
      <el-page-header content="班级详情" @back="goBack" />
      <el-button
        v-if="canManageClass && detail"
        type="primary"
        class="tb-btn tb-btn--primary"
        @click="openEdit"
      >
        <el-icon><Edit /></el-icon>
        编辑班级信息
      </el-button>
    </div>

    <el-empty v-if="!loading && !detail" description="班级不存在或已删除" />

    <template v-else-if="detail">
      <el-card class="hero-card" shadow="never">
        <div class="hero-top">
          <div class="hero-identity">
            <div class="hero-avatar" :class="isOneToOne ? 'is-oto' : 'is-group'">
              {{ nameInitial }}
            </div>
            <div class="hero-main">
              <div class="title-row">
                <h2 class="class-title">{{ detail.name }}</h2>
                <el-tag
                  size="small"
                  :type="isOneToOne ? 'info' : 'warning'"
                  effect="plain"
                  class="mode-tag"
                >
                  {{ detail.mode_label || (isOneToOne ? '一对一' : '班课') }}
                </el-tag>
                <el-tag v-if="detail.status === 'graduated'" size="small" type="info">结业</el-tag>
                <el-tag v-else-if="detail.status === 'active'" size="small" type="success" effect="plain">
                  在读
                </el-tag>
              </div>
              <div class="hero-meta">
                <span v-if="detail.course_name" class="meta-item">
                  <el-icon><Reading /></el-icon>
                  {{ detail.course_name }}
                </span>
                <span class="meta-item">
                  <el-icon><User /></el-icon>
                  {{ detail.teachers || '待分配老师' }}
                </span>
                <span v-if="detail.default_room" class="meta-item">
                  <el-icon><OfficeBuilding /></el-icon>
                  {{ detail.default_room }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="stat-row">
          <div v-for="s in statCards" :key="s.label" class="stat-card" :class="'tone-' + s.tone">
            <div class="stat-label">{{ s.label }}</div>
            <div class="stat-value">
              {{ s.value }}
              <span v-if="s.unit" class="stat-unit">{{ s.unit }}</span>
            </div>
          </div>
        </div>

        <div class="info-panel">
          <div class="info-panel-title">班级资料</div>
          <div class="info-grid" :class="{ 'is-oto': isOneToOne }">
            <div class="info-item">
              <span class="k">关联课程</span>
              <span class="v">{{ detail.course_name || '—' }}</span>
            </div>
            <div v-if="isGroup" class="info-item">
              <span class="k">人数/容量</span>
              <span class="v">{{ detail.capacity_label }}</span>
            </div>
            <div v-if="isOneToOne" class="info-item">
              <span class="k">关联学员</span>
              <span class="v">{{ detail.student_name || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="k">上课教室</span>
              <span class="v">{{ detail.default_room || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="k">班级分类</span>
              <span class="v">{{ detail.category || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="k">班级老师</span>
              <span class="v">{{ detail.teachers || '待分配' }}</span>
            </div>
            <div class="info-item">
              <span class="k">授课课时</span>
              <span class="v">{{ detail.hours_per_session }}{{ isOneToOne ? ' 课时' : '' }}</span>
            </div>
            <div v-if="isOneToOne" class="info-item">
              <span class="k">已授课时</span>
              <span class="v">{{ detail.taught_hours }} 课时</span>
            </div>
            <div v-if="isOneToOne" class="info-item">
              <span class="k">剩余课时</span>
              <span class="v highlight">{{ detail.remain_hours }} 课时</span>
            </div>
            <div class="info-item info-item--wide">
              <span class="k">备注</span>
              <span class="v">{{ detail.remark || '—' }}</span>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="module-card" shadow="never">
        <el-tabs v-model="activeTab" class="detail-tabs">
          <el-tab-pane name="schedule">
            <template #label>
              <span class="tab-label">
                <el-icon><Calendar /></el-icon>
                排课信息
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane v-if="isGroup" name="students">
            <template #label>
              <span class="tab-label">
                <el-icon><UserFilled /></el-icon>
                班级学员
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane name="attendance">
            <template #label>
              <span class="tab-label">
                <el-icon><Checked /></el-icon>
                点名情况
              </span>
            </template>
          </el-tab-pane>
        </el-tabs>

        <!-- 排课信息 -->
        <div v-if="activeTab === 'schedule'" class="tab-body">
          <div class="tab-actions">
            <el-button
              v-if="canManage"
              type="primary"
              class="tb-btn tb-btn--primary"
              @click="openScheduleCreate(true)"
            >
              一键排课
            </el-button>
            <el-button
              v-if="canManage"
              class="tb-btn"
              plain
              @click="openScheduleCreate(false)"
            >
              单次排课
            </el-button>
            <div class="spacer" />
            <el-button text class="refresh-btn" @click="loadSchedules">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>

          <!-- 多选操作条：换老师 / 改教室等批量编辑，修改后课表同步 -->
          <div v-if="canManage && selectedSchedules.length" class="bulk-bar">
            <span class="bulk-bar-text">
              已选
              <strong>{{ selectedSchedules.length }}</strong>
              节
            </span>
            <el-button type="primary" class="tb-btn tb-btn--primary" @click="openBulkEdit">
              批量编辑
            </el-button>
            <el-button
              v-if="canManageClass"
              class="tb-btn"
              plain
              type="danger"
              @click="bulkDeleteSchedules"
            >
              批量删除
            </el-button>
            <el-button text class="refresh-btn" @click="clearScheduleSelection">取消选择</el-button>
          </div>

          <div class="sub-title">
            <span class="sub-bar" />
            排课列表
            <span class="sub-count">{{ schedules.length }} 节</span>
            <span v-if="canManage" class="sub-hint">勾选后可批量换老师 / 改教室</span>
          </div>
          <el-table
            v-if="!isApp"
            ref="scheduleTableRef"
            :data="schedules"
            row-key="id"
            border
            stripe
            class="data-table detail-table"
            empty-text="暂无排课，可使用「一键排课」或「单次排课」"
            :header-cell-style="pcHeaderStyle"
            @selection-change="onScheduleSelectionChange"
          >
            <el-table-column
              v-if="canManage"
              type="selection"
              width="48"
              :selectable="scheduleRowSelectable"
              fixed="left"
            />
            <el-table-column label="上课日期" min-width="150">
              <template #default="{ row }">{{ formatDateWeek(row.start_at) }}</template>
            </el-table-column>
            <el-table-column prop="course_name" label="授课课程" min-width="140" show-overflow-tooltip />
            <el-table-column label="上课时间" width="120">
              <template #default="{ row }">{{ timeRangeOf(row.start_at, row.end_at) }}</template>
            </el-table-column>
            <el-table-column prop="room" label="上课教室" width="110">
              <template #default="{ row }">{{ row.room || '-' }}</template>
            </el-table-column>
            <el-table-column prop="teachers" label="上课老师" min-width="140" show-overflow-tooltip />
            <el-table-column prop="remark" label="上课内容" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.remark || '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right" align="right">
              <template #default="{ row }">
                <el-button
                  v-if="canManage"
                  link
                  type="primary"
                  :disabled="row.status === 'completed'"
                  @click="openScheduleEdit(row)"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="canManageClass"
                  link
                  type="danger"
                  :disabled="row.status === 'completed'"
                  @click="deleteSchedule(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="compact-record-grid">
            <article v-for="row in schedules" :key="row.id" class="compact-record-card">
              <div class="compact-record-head">
                <strong>{{ formatDateWeek(row.start_at) }}</strong>
                <span>{{ timeRangeOf(row.start_at, row.end_at) }}</span>
              </div>
              <div class="compact-record-meta">
                <span>{{ row.course_name }}</span>
                <span>{{ row.teachers || '未填老师' }}</span>
                <span>{{ row.room || '未填教室' }}</span>
              </div>
              <div v-if="canManage" class="compact-record-actions">
                <el-button text type="primary" :disabled="row.status === 'completed'" @click="openScheduleEdit(row)">编辑</el-button>
                <el-button v-if="canManageClass" text type="danger" :disabled="row.status === 'completed'" @click="deleteSchedule(row)">删除</el-button>
              </div>
            </article>
            <p v-if="!schedules.length" class="compact-record-empty">暂无排课</p>
          </div>
          <div class="table-foot">共 {{ schedules.length }} 条数据</div>
        </div>

        <!-- 班级学员（班课） -->
        <div v-else-if="activeTab === 'students' && isGroup" class="tab-body">
          <div class="tab-actions">
            <el-button
              v-if="canManageClass"
              type="primary"
              class="tb-btn tb-btn--primary"
              @click="openAddStudents"
            >
              <el-icon><Plus /></el-icon>
              添加学员
            </el-button>
            <div class="spacer" />
            <span class="member-summary">在班 <b>{{ (detail.members || []).length }}</b> 人</span>
          </div>
          <el-table
            v-if="!isApp"
            :data="detail.members || []"
            row-key="id"
            border
            stripe
            class="data-table detail-table"
            empty-text="暂无学员，点击「添加学员」加入本班"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="name" label="姓名" min-width="100" />
            <el-table-column label="性别" width="70" align="center">
              <template #default="{ row }">{{ row.gender || '-' }}</template>
            </el-table-column>
            <el-table-column prop="phone" label="手机号" width="130">
              <template #default="{ row }">{{ row.phone || '-' }}</template>
            </el-table-column>
            <el-table-column label="消耗方式" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{ row.consume_label || '—' }}</template>
            </el-table-column>
            <el-table-column label="剩余额度" width="110" align="center">
              <template #default="{ row }">
                {{ row.remain_hours != null ? `${row.remain_hours}课时` : '-' }}
              </template>
            </el-table-column>
            <el-table-column v-if="canManageClass" label="操作" width="160" fixed="right" align="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="removeStudent(row.id, row.name)">
                  移出本班
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="compact-record-grid">
            <article v-for="row in detail.members || []" :key="row.id" class="compact-record-card">
              <div class="compact-record-head">
                <strong>{{ row.name }}</strong>
                <b>{{ row.remain_hours != null ? `${row.remain_hours}课时` : '-' }}</b>
              </div>
              <div class="compact-record-meta">
                <span>{{ row.phone || '未填手机' }}</span>
                <span>{{ row.consume_label || '未设置消耗' }}</span>
              </div>
              <div v-if="canManageClass" class="compact-record-actions">
                <el-button text type="danger" @click="removeStudent(row.id, row.name)">移出本班</el-button>
              </div>
            </article>
            <p v-if="!detail.members?.length" class="compact-record-empty">暂无学员</p>
          </div>
          <div class="table-foot">共 {{ (detail.members || []).length }} 名学员</div>
        </div>

        <!-- 点名情况 -->
        <div v-else-if="activeTab === 'attendance'" class="tab-body">
          <div class="tab-actions attendance-toolbar">
            <span class="att-hint">一周点名情况 {{ attendanceWeekLabel }}</span>
            <div class="spacer" />
            <el-button-group class="week-nav">
              <el-button @click="changeAttendanceWeek(-1)">
                <el-icon><ArrowLeft /></el-icon>
                上周
              </el-button>
              <el-button :disabled="isCurrentAttendanceWeek" @click="resetAttendanceWeek">
                本周
              </el-button>
              <el-button @click="changeAttendanceWeek(1)">
                下周
                <el-icon><ArrowRight /></el-icon>
              </el-button>
            </el-button-group>
            <el-button
              v-if="canManage"
              type="primary"
              class="tb-btn tb-btn--primary"
              @click="openRoll()"
            >
              未排课直接点名
            </el-button>
            <el-button text class="refresh-btn" @click="refreshAttendance">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>

          <div class="sub-title">
            <span class="sub-bar" />
            本周课次
          </div>
          <el-table
            v-if="!isApp"
            :data="weekRecords"
            row-key="key"
            border
            stripe
            class="data-table"
            empty-text="本周暂无排课或点名记录"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column label="上课时间" min-width="180">
              <template #default="{ row }">
                <template v-if="row.start_at && row.end_at">
                  {{ formatDateWeek(row.start_at) }}
                  {{ timeRangeOf(row.start_at, row.end_at) }}
                </template>
                <template v-else>{{ formatDateWeek(row.start_at) }}</template>
              </template>
            </el-table-column>
            <el-table-column prop="course_name" label="授课课程" min-width="130" show-overflow-tooltip />
            <el-table-column label="上课教室" width="100">
              <template #default="{ row }">{{ row.room || '-' }}</template>
            </el-table-column>
            <el-table-column prop="teachers" label="上课老师" min-width="140" show-overflow-tooltip />
            <el-table-column prop="content" label="上课内容" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.content || '-' }}</template>
            </el-table-column>
            <el-table-column label="点名时间" width="150">
              <template #default="{ row }">
                {{
                  row.roll_at
                    ? `${dateKey(new Date(row.roll_at))} ${padTime(new Date(row.roll_at))}`
                    : '--'
                }}
              </template>
            </el-table-column>
            <el-table-column label="实到人数" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.attendance" class="hours-num">{{ row.attendance }}</span>
                <span v-else class="record-muted">--</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="290" fixed="right" align="right">
              <template #default="{ row }">
                <el-button
                  v-if="!row.record && row.schedule && isScheduleRollable(row.schedule) && canManage"
                  link
                  type="primary"
                  @click="openRoll(row.schedule.id)"
                >
                  点名
                </el-button>
                <el-tag
                  v-else-if="!row.record && row.schedule?.status === 'scheduled' && !isScheduleRollable(row.schedule)"
                  size="small"
                  type="info"
                  effect="plain"
                >
                  未到时间
                </el-tag>
                <el-button
                  v-if="!row.record && row.schedule?.status === 'scheduled' && canManage"
                  link
                  type="warning"
                  @click="openScheduleEdit(row.schedule)"
                >
                  调整课次
                </el-button>
                <el-button
                  v-if="row.schedule"
                  link
                  type="primary"
                  @click="openLessonDetail(row.schedule.id)"
                >
                  查看详情
                </el-button>
                <el-button
                  v-if="!row.record && row.schedule?.status === 'scheduled' && canManageClass"
                  link
                  type="danger"
                  @click="deleteSchedule(row.schedule)"
                >
                  删除
                </el-button>
                <el-button
                  v-if="row.record?.status === 'normal' && canManageClass"
                  link
                  type="danger"
                  @click="voidRecord(row.record)"
                >
                  撤销点名
                </el-button>
                <el-tag
                  v-if="row.record && !canManageClass"
                  size="small"
                  type="success"
                >
                  已点名
                </el-tag>
                <span v-if="!row.schedule && !row.record" class="record-muted">--</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="compact-record-grid">
            <article v-for="row in weekRecords" :key="row.key" class="compact-record-card">
              <div class="compact-record-head">
                <strong>{{ row.course_name || '课次' }}</strong>
                <span>{{ row.attendance || '--' }} 人</span>
              </div>
              <div class="compact-record-meta">
                <span>{{ formatDateWeek(row.start_at) }}</span>
                <span>{{ row.start_at && row.end_at ? timeRangeOf(row.start_at, row.end_at) : '' }}</span>
                <span>{{ row.teachers || '未填老师' }}</span>
              </div>
              <div class="compact-record-actions">
                <el-button v-if="!row.record && row.schedule && isScheduleRollable(row.schedule) && canManage" text type="primary" @click="openRoll(row.schedule.id)">点名</el-button>
                <el-button v-if="row.schedule" text type="primary" @click="openLessonDetail(row.schedule.id)">详情</el-button>
                <el-button v-if="row.record?.status === 'normal' && canManageClass" text type="danger" @click="voidRecord(row.record)">撤销</el-button>
              </div>
            </article>
            <p v-if="!weekRecords.length" class="compact-record-empty">本周暂无课次</p>
          </div>
          <div class="table-foot">共 {{ weekRecords.length }} 条数据</div>

          <div class="sub-title sub-title--gap">
            <span class="sub-bar" />
            历史点名情况
          </div>
          <el-table
            v-if="!isApp"
            :data="historyRecords"
            row-key="id"
            border
            stripe
            class="data-table"
            empty-text="暂无更早的点名记录"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column label="上课时间" min-width="180">
              <template #default="{ row }">
                <template v-if="row.class_start && row.class_end">
                  {{ formatDateWeek(row.class_start) }}
                  {{ timeRangeOf(row.class_start, row.class_end) }}
                </template>
                <template v-else>{{ formatDateWeek(row.roll_at) }}</template>
              </template>
            </el-table-column>
            <el-table-column prop="course_name" label="授课课程" min-width="130" />
            <el-table-column label="上课教室" width="100">
              <template #default="{ row }">{{ recordRoom(row) }}</template>
            </el-table-column>
            <el-table-column prop="teachers" label="上课老师" min-width="140" />
            <el-table-column prop="content" label="上课内容" min-width="100">
              <template #default="{ row }">{{ row.content || '-' }}</template>
            </el-table-column>
            <el-table-column label="点名时间" width="150">
              <template #default="{ row }">
                {{
                  row.roll_at
                    ? `${dateKey(new Date(row.roll_at))} ${padTime(new Date(row.roll_at))}`
                    : '--'
                }}
              </template>
            </el-table-column>
            <el-table-column prop="hours" label="授课课时" width="90" align="center" />
            <el-table-column label="实到人数" width="90" align="center">
              <template #default="{ row }">
                <span class="hours-num">{{ row.present_count }}/{{ row.total_count }}</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="row.status === 'void' ? 'info' : 'success'" size="small">
                  {{ row.status_label }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="270" fixed="right" align="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.schedule_id"
                  link
                  type="primary"
                  @click="openLessonDetail(row.schedule_id)"
                >
                  课次详情
                </el-button>
                <el-button
                  link
                  type="primary"
                  @click="openAttendanceDetail(row)"
                >
                  点名详情
                </el-button>
                <el-button
                  v-if="canManageClass && row.status === 'normal'"
                  link
                  type="danger"
                  @click="voidRecord(row)"
                >
                  撤销点名
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="compact-record-grid">
            <article v-for="row in historyRecords" :key="row.id" class="compact-record-card">
              <div class="compact-record-head">
                <strong>{{ row.course_name || '点名记录' }}</strong>
                <el-tag :type="row.status === 'void' ? 'info' : 'success'" size="small">{{ row.status_label }}</el-tag>
              </div>
              <div class="compact-record-meta">
                <span>{{ formatDateWeek(row.class_start || row.roll_at) }}</span>
                <span>{{ row.teachers || '未填老师' }}</span>
                <span>实到 {{ row.present_count }}/{{ row.total_count }}</span>
              </div>
              <div class="compact-record-actions">
                <el-button text type="primary" @click="openAttendanceDetail(row)">点名详情</el-button>
                <el-button v-if="row.schedule_id" text type="primary" @click="openLessonDetail(row.schedule_id)">课次</el-button>
                <el-button v-if="canManageClass && row.status === 'normal'" text type="danger" @click="voidRecord(row)">撤销</el-button>
              </div>
            </article>
            <p v-if="!historyRecords.length" class="compact-record-empty">暂无历史点名</p>
          </div>
          <div class="table-foot">共 {{ historyRecords.length }} 条数据</div>
        </div>
      </el-card>

      <MobileActionBar
        :visible="isApp && Boolean(detail) && (canManageClass || canManage)"
      >
        <el-button
          v-if="canManage"
          plain
          @click="openScheduleCreate(true)"
        >
          排课
        </el-button>
        <el-button
          v-if="canManage"
          type="primary"
          plain
          @click="openRoll()"
        >
          点名
        </el-button>
        <el-button
          v-if="canManageClass"
          type="primary"
          @click="openEdit"
        >
          编辑班级
        </el-button>
      </MobileActionBar>
    </template>

    <!-- 编辑班级：App → AppSheet / PC → Dialog -->
    <component
      :is="editSurface"
      v-model="editVisible"
      v-bind="editSurfaceProps"
      title="编辑班级信息"
      destroy-on-close
    >
      <el-form label-position="top">
        <div class="form-section">基本信息</div>
        <el-form-item label="班级名称" required>
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="关联课程">
          <el-select v-model="editForm.course_id" filterable style="width: 100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isGroup" label="班级容量">
          <div class="inline-fields">
            <el-input-number v-model="editForm.capacity" :min="1" controls-position="right" />
            <el-radio-group v-model="editForm.over_capacity">
              <el-radio :value="true">可超额</el-radio>
              <el-radio :value="false">不可超额</el-radio>
            </el-radio-group>
          </div>
        </el-form-item>
        <el-form-item v-if="isGroup" label="开课人数">
          <el-input-number v-model="editForm.open_count" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="班级分类">
          <el-input v-model="editForm.category" />
        </el-form-item>
        <div class="form-section">上课信息</div>
        <el-form-item label="授课课时">
          <el-input-number
            v-model="editForm.hours_per_session"
            :min="0.01"
            :step="0.25"
            :precision="2"
          />
          <span class="field-hint">单次课次扣课时，默认 1（2 小时墙钟通常仍计 1 课时）</span>
        </el-form-item>
        <el-form-item label="上课教室">
          <el-select
            v-model="editForm.default_room"
            filterable
            clearable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option v-for="r in rooms" :key="r.name" :label="r.name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级老师">
          <el-select v-model="editForm.teacher_ids" multiple filterable style="width: 100%">
            <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveEdit">保存</el-button>
      </template>
    </component>

    <!-- 添加学员 -->
    <component
      :is="addStudentSurface"
      v-model="addStudentVisible"
      v-bind="addStudentSurfaceProps"
      title="添加学员"
      destroy-on-close
    >
      <el-select
        v-model="addStudentIds"
        multiple
        filterable
        remote
        :remote-method="searchStudents"
        @change="onAddStudentChange"
        placeholder="搜索学员姓名/手机"
        style="width: 100%"
      >
        <el-option
          v-for="s in studentOptions"
          :key="s.id"
          :label="`${s.name}${s.phone ? ' · ' + s.phone : ''}${isStudentInClass(s.id) ? ' · 已在班' : ''}`"
          :value="s.id"
        />
      </el-select>
      <template #footer>
        <el-button @click="addStudentVisible = false">取消</el-button>
        <el-button type="primary" :loading="addStudentSaving" @click="saveAddStudents">确定</el-button>
      </template>
    </component>

    <!-- 课堂点名 -->
    <component
      :is="rollSurface"
      v-model="rollVisible"
      v-bind="rollSurfaceProps"
      title="课堂点名"
      destroy-on-close
    >
      <div v-loading="rollLoading">
        <el-form :label-position="isApp ? 'top' : 'right'" :label-width="isApp ? undefined : '90px'">
          <el-form-item label="班级">
            <el-input :model-value="detail?.name || ''" disabled />
          </el-form-item>
          <el-form-item label="关联排课">
            <el-select
              v-model="rollForm.schedule_id"
              :clearable="!lockedRollScheduleId"
              :disabled="Boolean(lockedRollScheduleId)"
              filterable
              style="width: 100%"
              :placeholder="lockedRollScheduleId ? '已锁定当前课次' : '不选择则为未排课直接点名'"
              @change="onRollScheduleChange"
            >
              <el-option
                v-for="schedule in rollScheduleOptions"
                :key="schedule.id"
                :label="scheduleLabel(schedule)"
                :value="schedule.id"
                :disabled="schedule.status === 'completed' || !isScheduleRollable(schedule)"
              />
            </el-select>
            <div v-if="lockedRollScheduleId" class="form-tip">
              从课次发起点名时，关联排课固定为当前课次。
            </div>
          </el-form-item>
          <el-form-item label="上课教室">
            <el-input :model-value="rollRoom || '未设置'" disabled />
          </el-form-item>
          <el-form-item label="授课课时">
            <el-input-number v-model="rollForm.hours" :min="0.01" :step="0.25" :precision="2" />
            <span class="field-hint">按课次扣学员课时，默认单次 1 课时（与上课墙钟时长无关）</span>
          </el-form-item>
          <el-form-item label="上课内容">
            <el-input v-model="rollForm.content" type="textarea" :rows="2" placeholder="可选" />
          </el-form-item>
        </el-form>

        <div v-if="rollMembers.length" class="attend-block">
          <div class="attend-head">
            <span class="attend-title">
              <span class="sec-dot" />
              学员考勤
              <em>{{ rollMembers.length }} 人</em>
            </span>
            <div class="attend-quick">
              <el-button link type="primary" @click="markAllAttendance('present')">全勤</el-button>
              <el-button link @click="markAllAttendance('absent')">全缺</el-button>
            </div>
          </div>
          <div class="attend-list">
            <div v-for="member in rollMembers" :key="member.id" class="attend-row">
              <div class="attend-name">
                <span class="roll-avatar">{{ (member.name || '?').slice(0, 1) }}</span>
                <div>
                  <span class="name">{{ member.name }}</span>
                  <span v-if="member.phone" class="phone">{{ member.phone }}</span>
                </div>
              </div>
              <el-radio-group v-model="attendMap[member.id]" size="small">
                <el-radio-button v-for="option in ATTENDANCE_OPTIONS" :key="option.value" :value="option.value">
                  {{ option.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <p class="attend-note">扣课规则：出勤/迟到扣课；请假/缺勤不扣课时。</p>
        </div>
        <el-empty v-else-if="!rollLoading" description="该班级暂无在班学员，无法点名" :image-size="64" />
      </div>

      <template #footer>
        <el-button class="tb-btn" @click="rollVisible = false">取消</el-button>
        <el-button type="primary" class="tb-btn tb-btn--primary" :loading="rollSaving" @click="submitRoll">
          确认点名
        </el-button>
      </template>
    </component>

    <!-- 点名详情 -->
    <component
      :is="attendanceSurface"
      v-model="attendanceDetailVisible"
      v-bind="attendanceSurfaceProps"
      title="点名详情"
      destroy-on-close
    >
      <div v-loading="attendanceDetailLoading">
        <div v-if="attendanceDetail" class="record-summary">
          <div class="record-summary-main">
            <span class="roll-avatar lg">{{ (attendanceDetail.class_name || '?').slice(0, 1) }}</span>
            <div>
              <strong>{{ attendanceDetail.class_name }}</strong>
              <div class="record-summary-meta">
                <span>{{ attendanceDetail.course_name || '未关联课程' }}</span>
                <span>{{ formatDateTime(attendanceDetail.class_start || attendanceDetail.roll_at) }}</span>
              </div>
            </div>
          </div>
          <div class="record-summary-amount">
            <span>合计</span>
            <strong>{{ attendanceDetail.hours }} 课时</strong>
            <em>{{ formatMoney(attendanceDetail.amount) }}</em>
          </div>
        </div>
        <el-table
          v-if="attendanceDetail && !isApp"
          :data="attendanceDetail.attendances"
          border
          stripe
          size="small"
          class="data-table"
          :header-cell-style="pcHeaderStyle"
        >
          <el-table-column prop="student_name" label="学员" min-width="120" />
          <el-table-column prop="status_label" label="点名状态" width="92" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                :type="row.status === 'absent' ? 'danger' : row.status === 'present' ? 'success' : 'warning'"
              >
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="扣除额度" width="100" align="center">
            <template #default="{ row }">
              <span class="hours-pill">{{ row.hours_consumed }}课时</span>
            </template>
          </el-table-column>
          <el-table-column label="欠课时" width="88" align="right">
            <template #default="{ row }">
              <span :class="{ 'hours-shortage': row.uncovered_hours > 0 }">
                {{ row.uncovered_hours }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="课消金额" width="112" align="right">
            <template #default="{ row }">
              <span class="pc-mono">{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
        </el-table>
        <div v-else-if="attendanceDetail" class="attendance-detail-cards">
          <article v-for="row in attendanceDetail.attendances" :key="row.student_id || row.student_name" class="attendance-detail-card">
            <div class="attendance-detail-card__head">
              <strong>{{ row.student_name }}</strong>
              <el-tag size="small" effect="plain" :type="row.status === 'absent' ? 'danger' : row.status === 'present' ? 'success' : 'warning'">{{ row.status_label }}</el-tag>
            </div>
            <div class="attendance-detail-card__meta">
              <span>扣除 {{ row.hours_consumed }} 课时</span>
              <span>欠课 {{ row.uncovered_hours }}</span>
              <span>课消 {{ formatMoney(row.amount) }}</span>
            </div>
          </article>
        </div>
      </div>
      <template #footer>
        <el-button @click="attendanceDetailVisible = false">关闭</el-button>
      </template>
    </component>

    <!-- 排课表单 -->
    <AppSheet
      :key="scheduleFormKey"
      v-model="scheduleFormVisible"
      :title="scheduleEditingId ? '编辑排课' : scheduleForm.batch ? '一键排课' : '单次排课'"
      size="420px"
    >
      <el-form label-position="top">
        <el-form-item
          :label="scheduleForm.batch ? '排课开始日期' : scheduleEditingId ? '上课日期' : '具体上课日期'"
          required
        >
          <el-date-picker
            v-model="scheduleForm.date"
            type="date"
            value-format="YYYY-MM-DD"
            :placeholder="scheduleForm.batch ? '请选择排课开始日期' : '请选择具体上课日期'"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="上课时间" required>
          <div class="inline-fields">
            <el-time-select
              v-model="scheduleForm.start_time"
              start="07:00"
              step="00:10"
              end="21:00"
              placeholder="开始"
            />
            <span>~</span>
            <el-time-select
              v-model="scheduleForm.end_time"
              start="07:00"
              step="00:10"
              end="22:00"
              placeholder="结束"
            />
          </div>
        </el-form-item>
        <template v-if="scheduleForm.batch && !scheduleEditingId">
          <el-form-item label="重复方式">
            <el-radio-group v-model="scheduleForm.repeat_mode">
              <el-radio value="weekly">每周</el-radio>
              <el-radio value="daily">每天</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item
            v-if="scheduleForm.repeat_mode === 'weekly'"
            label="每周上课日（可多选）"
            required
          >
            <el-checkbox-group v-model="scheduleForm.weekdays" class="weekday-options">
              <el-checkbox-button
                v-for="weekday in WEEKDAY_OPTIONS"
                :key="weekday.value"
                :value="weekday.value"
              >
                {{ weekday.label }}
              </el-checkbox-button>
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="结束方式">
            <el-radio-group v-model="scheduleForm.end_mode">
              <el-radio value="by_count">按次数</el-radio>
              <el-radio value="by_date">按日期</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="scheduleForm.end_mode === 'by_count'" label="排课次数">
            <el-input-number v-model="scheduleForm.session_count" :min="1" :max="100" />
          </el-form-item>
          <el-form-item v-else label="结束日期">
            <el-date-picker
              v-model="scheduleForm.end_date"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
            />
          </el-form-item>
        </template>
        <el-form-item label="上课教室">
          <el-select
            v-model="scheduleForm.room"
            filterable
            clearable
            allow-create
            default-first-option
            style="width: 100%"
          >
            <el-option v-for="r in rooms" :key="r.name" :label="r.name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="上课老师">
          <el-select v-model="scheduleForm.teacher_ids" multiple filterable style="width: 100%">
            <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="上课内容">
          <el-input v-model="scheduleForm.remark" type="textarea" :rows="2" maxlength="100" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scheduleFormVisible = false">取消</el-button>
        <el-button type="primary" :loading="scheduleSaving" @click="saveSchedule">
          {{ scheduleForm.batch && !scheduleEditingId ? '生成排课' : '保存' }}
        </el-button>
      </template>
    </AppSheet>

    <!-- 批量编辑排课（换老师/教室等，修改后课表同步） -->
    <AppSheet
      :key="bulkEditKey"
      v-model="bulkEditVisible"
      title="批量编辑排课"
      size="420px"
    >
      <p class="bulk-edit-tip">
        已选
        <strong>{{ selectedSchedules.filter(scheduleRowSelectable).length }}</strong>
        节可编辑课次。勾选要改的项后保存，课表管理会同步显示。
      </p>
      <el-form label-position="top" class="bulk-edit-form">
        <el-form-item>
          <el-checkbox v-model="bulkEditForm.update_teachers">修改上课老师</el-checkbox>
          <el-select
            v-model="bulkEditForm.teacher_ids"
            multiple
            filterable
            :disabled="!bulkEditForm.update_teachers"
            placeholder="选择上课老师"
            style="width: 100%; margin-top: 8px"
          >
            <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="bulkEditForm.update_room">修改上课教室</el-checkbox>
          <el-select
            v-model="bulkEditForm.room"
            filterable
            clearable
            allow-create
            default-first-option
            :disabled="!bulkEditForm.update_room"
            placeholder="选择或输入教室"
            style="width: 100%; margin-top: 8px"
          >
            <el-option v-for="r in rooms" :key="r.name" :label="r.name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="bulkEditForm.update_time">修改上课时间（仅改时刻，日期不变）</el-checkbox>
          <div class="inline-fields" style="margin-top: 8px">
            <el-time-select
              v-model="bulkEditForm.start_time"
              start="07:00"
              step="00:10"
              end="21:00"
              placeholder="开始"
              :disabled="!bulkEditForm.update_time"
            />
            <span>~</span>
            <el-time-select
              v-model="bulkEditForm.end_time"
              start="07:00"
              step="00:10"
              end="22:00"
              placeholder="结束"
              :disabled="!bulkEditForm.update_time"
            />
          </div>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="bulkEditForm.update_remark">修改上课内容</el-checkbox>
          <el-input
            v-model="bulkEditForm.remark"
            type="textarea"
            :rows="2"
            maxlength="100"
            :disabled="!bulkEditForm.update_remark"
            placeholder="上课内容"
            style="margin-top: 8px"
          />
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="bulkEditForm.force">强制保存（忽略老师/教室时段冲突）</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bulkEditVisible = false">取消</el-button>
        <el-button type="primary" :loading="bulkEditSaving" @click="saveBulkEdit">
          保存到选中课次
        </el-button>
      </template>
    </AppSheet>

    <ScheduleLessonDetailDrawer
      v-model="lessonDetailVisible"
      :lesson-id="lessonDetailId"
      :can-manage="canManage"
      @edit="onLessonDetailEdit"
      @remove="onLessonDetailRemove"
      @roll="onLessonDetailRoll"
      @refreshed="refreshAttendance"
    />
  </div>
</template>

<style scoped>
.class-detail-page {
  width: 100%;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.hero-card {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    linear-gradient(135deg, rgba(245, 240, 230, 0.65) 0%, transparent 42%),
    var(--oc-card, #fffdf8);
  margin-bottom: 14px;
  box-shadow: 0 8px 24px rgba(41, 37, 36, 0.05);
  overflow: hidden;
}

.hero-card :deep(.el-card__body) {
  padding: 18px 20px 16px;
}

.hero-top {
  margin-bottom: 16px;
}

.hero-identity {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.hero-avatar {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.22);
}

.hero-avatar.is-group {
  background: linear-gradient(145deg, #c9a066, #a16207);
}

.hero-avatar.is-oto {
  background: linear-gradient(145deg, #a8a29e, #57534e);
}

.hero-main {
  min-width: 0;
  flex: 1;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.class-title {
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.01em;
  line-height: 1.3;
}

.mode-tag {
  border-radius: 6px;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.meta-item .el-icon {
  color: var(--oc-primary, #a16207);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fff;
  padding: 12px 14px;
  min-height: 72px;
}

.stat-card.tone-gold {
  background: linear-gradient(160deg, #fffdf8, #faf3e6);
  border-color: #e6d2b3;
}

.stat-card.tone-amber {
  background: linear-gradient(160deg, #fffbeb, #fef3c7);
  border-color: #fde68a;
}

.stat-card.tone-green {
  background: linear-gradient(160deg, #f0fdf4, #dcfce7);
  border-color: #bbf7d0;
}

.stat-card.tone-stone {
  background: linear-gradient(160deg, #fafaf9, #f5f5f4);
  border-color: #e7e5e4;
}

.stat-label {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 22px;
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.tone-gold .stat-value {
  color: var(--oc-primary, #a16207);
}

.tone-green .stat-value {
  color: #15803d;
}

.tone-amber .stat-value {
  color: #b45309;
}

.stat-unit {
  font-size: 12px;
  font-weight: 600;
  margin-left: 2px;
  color: var(--oc-muted, #78716c);
}

.info-panel {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #f0e9dc;
  padding: 12px 14px 8px;
}

.info-panel-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-panel-title::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--oc-primary, #a16207);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
  min-width: 0;
}

.info-item--wide {
  grid-column: 1 / -1;
}

.info-item .k {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.info-item .v {
  font-size: 13px;
  color: var(--oc-ink, #44403c);
  font-weight: 550;
  word-break: break-word;
}

.info-item .v.highlight {
  color: #16a34a;
  font-weight: 700;
}

.module-card {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 6px 20px rgba(41, 37, 36, 0.04);
}

.module-card :deep(.el-card__body) {
  padding: 8px 16px 16px;
}

.detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.detail-tabs :deep(.el-tabs__item) {
  height: 42px;
  line-height: 42px;
  font-size: 14px;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.detail-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--oc-primary, #a16207);
  height: 3px;
  border-radius: 2px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-body {
  padding-top: 4px;
}

.tab-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
  padding: 10px 12px;
  background: linear-gradient(180deg, #faf6ee, #f7f1e6);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
}

.spacer {
  flex: 1;
}

.refresh-btn {
  color: var(--oc-muted, #78716c);
}

.sub-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin-bottom: 10px;
}

.sub-title--gap {
  margin-top: 22px;
}

.sub-bar {
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--oc-primary, #a16207);
}

.sub-count {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-muted, #78716c);
  background: #f5f0e6;
  border-radius: 999px;
  padding: 1px 8px;
}

.sub-hint {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
  color: var(--oc-muted, #78716c);
}

.bulk-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  background: linear-gradient(180deg, #fef9ef, #faf3e3);
  border: 1px solid #e6d2b3;
  border-radius: 10px;
}

.bulk-bar-text {
  font-size: 13px;
  color: var(--oc-ink, #44403c);
  margin-right: 4px;
}

.bulk-bar-text strong {
  color: var(--oc-primary, #a16207);
  font-variant-numeric: tabular-nums;
}

.bulk-edit-tip {
  margin: 0 0 14px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
  background: #faf6ee;
  border-radius: 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.bulk-edit-tip strong {
  color: var(--oc-primary, #a16207);
}

.bulk-edit-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.bulk-edit-form :deep(.el-checkbox) {
  color: var(--oc-ink, #44403c);
  font-weight: 600;
}

.member-summary {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.member-summary b {
  color: var(--oc-primary, #a16207);
}

.detail-table {
  border-radius: 10px;
  overflow: hidden;
}

.table-foot {
  padding: 10px 4px 2px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.hours-num {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
}

.att-hint {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.attendance-toolbar .att-hint {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
}

.week-nav {
  flex-shrink: 0;
}

.record-muted {
  color: var(--oc-muted, #78716c);
}

.record-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px 20px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(180deg, #fffdfb, #faf6ee);
  color: var(--oc-text-secondary, #57534e);
  font-size: 13px;
}

.record-summary-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.record-summary-main strong {
  display: block;
  color: var(--oc-ink, #44403c);
  font-size: 15px;
  font-weight: 700;
}

.record-summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 4px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.record-summary-amount {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e6d2b3;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.record-summary-amount strong {
  color: var(--oc-ink, #44403c);
  font-weight: 700;
}

.record-summary-amount em {
  font-style: normal;
  color: var(--oc-primary, #a16207);
  font-weight: 750;
  font-variant-numeric: tabular-nums;
}

.attendance-detail-cards {
  display: grid;
  gap: 8px;
}

.attendance-detail-card {
  padding: 10px 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: var(--oc-card, #fffdf8);
}

.attendance-detail-card__head,
.attendance-detail-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
}

.attendance-detail-card__meta {
  flex-wrap: wrap;
  margin-top: 8px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
}

.hours-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
}

.hours-shortage {
  color: var(--el-color-danger);
  font-weight: 600;
}

.attend-block {
  margin-top: 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 12px 14px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
}

.attend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.attend-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.attend-title em {
  font-style: normal;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
  background: rgba(161, 98, 7, 0.1);
  padding: 1px 8px;
  border-radius: 999px;
}

.roll-avatar {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(145deg, #c9a066, #a16207);
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.18);
}

.roll-avatar.lg {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  font-size: 16px;
}

.attend-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 280px;
  overflow: auto;
}

.attend-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px dashed #e8e0d0;
}

.attend-row:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.attend-row:first-child {
  padding-top: 0;
}

.attend-name {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.attend-name .name {
  display: block;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
}

.attend-name .phone,
.attend-note {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.attend-note {
  margin: 12px 0 0;
  line-height: 1.5;
  padding-top: 10px;
  border-top: 1px solid #f0e9dc;
}

.sec-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 3px rgba(161, 98, 7, 0.15);
  flex-shrink: 0;
}

.form-section {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin: 8px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.form-section::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 3px rgba(161, 98, 7, 0.15);
}

.field-hint,
.form-tip {
  display: block;
  width: 100%;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.inline-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.weekday-options {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}

.weekday-options :deep(.el-checkbox-button) {
  width: 100%;
}

.weekday-options :deep(.el-checkbox-button__inner) {
  width: 100%;
  border: 1px solid var(--oc-border, #e8e0d0) !important;
  border-radius: 6px !important;
  padding: 8px 6px;
  box-shadow: none !important;
}

.weekday-options :deep(.el-checkbox-button.is-checked .el-checkbox-button__inner) {
  border-color: var(--oc-primary, #a16207) !important;
  background: var(--oc-primary, #a16207);
}

@media (max-width: 960px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .info-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .attendance-toolbar .att-hint {
    flex-basis: 100%;
  }

  .attendance-toolbar .spacer {
    display: none;
  }

  .week-nav {
    display: flex;
    width: 100%;
  }

  .week-nav :deep(.el-button) {
    flex: 1;
  }

  .weekday-options {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .stat-row {
    grid-template-columns: 1fr 1fr;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .hero-avatar {
    width: 44px;
    height: 44px;
    font-size: 16px;
  }

  .class-title {
    font-size: 17px;
  }
}

.compact-record-grid {
  display: grid;
  gap: 8px;
}

.compact-record-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 6px;
  background: #fff;
}

.compact-record-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.compact-record-head strong {
  min-width: 0;
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-record-head > span,
.compact-record-head b {
  flex-shrink: 0;
  color: var(--oc-primary, #a16207);
  font-size: 12px;
}

.compact-record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 6px;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
}

.compact-record-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.compact-record-actions :deep(.el-button) {
  margin: 0;
}

.compact-record-empty {
  grid-column: 1 / -1;
  margin: 18px 0;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  text-align: center;
}

@media (min-width: 768px) and (max-width: 1199px) {
  .compact-record-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* ── WAP / Pad 班级详情 App 化 ── */
@media (max-width: 1199px) {
  .class-detail-page.is-app {
    display: grid;
    gap: 12px;
    padding-bottom: 8px;
  }

  .hero-card {
    margin: 0;
    border-radius: 18px;
    border-color: rgba(181, 145, 83, 0.3);
    background:
      linear-gradient(145deg, rgba(255, 255, 255, 0.92), transparent 42%),
      linear-gradient(180deg, #fffefb, #faf3e6);
    box-shadow:
      0 12px 28px rgba(88, 60, 24, 0.08),
      0 1px 0 rgba(255, 255, 255, 0.9) inset;
  }

  .hero-card :deep(.el-card__body) {
    padding: 16px 14px 14px;
  }

  .hero-avatar {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    font-size: 18px;
  }

  .class-title {
    font-size: 18px;
  }

  .hero-meta {
    gap: 6px;
  }

  .meta-item {
    min-height: 26px;
    padding: 2px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(181, 145, 83, 0.18);
    font-size: 12px;
  }

  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 12px;
  }

  .stat-card {
    min-height: 68px;
    padding: 12px;
    border-radius: 14px;
  }

  .info-panel {
    border-radius: 14px;
    background: rgba(255, 253, 248, 0.88);
    border-color: rgba(181, 145, 83, 0.18);
  }

  .module-card {
    margin: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .module-card :deep(.el-card__body) {
    padding: 0;
  }

  .detail-tabs {
    margin: 0 0 12px;
    padding: 4px;
    border-radius: 14px;
    border: 1px solid rgba(181, 145, 83, 0.2);
    background: #f3ebe0;
  }

  .detail-tabs :deep(.el-tabs__header) {
    margin: 0;
  }

  .detail-tabs :deep(.el-tabs__nav-wrap::after),
  .detail-tabs :deep(.el-tabs__active-bar) {
    display: none;
  }

  .detail-tabs :deep(.el-tabs__nav) {
    width: 100%;
    display: flex;
  }

  .detail-tabs :deep(.el-tabs__item) {
    flex: 1;
    height: 40px;
    line-height: 40px;
    padding: 0 8px !important;
    border-radius: 11px;
    justify-content: center;
    color: #78716c;
    font-weight: 650;
  }

  .detail-tabs :deep(.el-tabs__item.is-active) {
    color: #fffdf8 !important;
    background: linear-gradient(145deg, #c07a12, #a16207);
    box-shadow: 0 4px 12px rgba(161, 98, 7, 0.25);
  }

  .detail-tabs :deep(.tab-label) {
    justify-content: center;
    gap: 4px;
  }

  .tab-actions {
    gap: 8px;
    margin: 0 0 10px;
    padding: 12px;
    border-radius: 16px;
    border: 1px solid rgba(181, 145, 83, 0.22);
    background:
      linear-gradient(135deg, rgba(255, 255, 255, 0.9), transparent 50%),
      linear-gradient(180deg, #fffefb, #faf3e6);
    box-shadow: 0 6px 16px rgba(88, 60, 24, 0.05);
  }

  .tab-actions .tb-btn {
    min-height: 40px;
    border-radius: 12px;
    font-weight: 650;
  }

  .sub-hint {
    display: none;
  }

  .compact-record-card {
    border-radius: 16px;
    border-color: rgba(181, 145, 83, 0.28);
    box-shadow: 0 8px 18px rgba(88, 60, 24, 0.06);
  }

  .week-nav .el-button {
    min-height: 36px;
  }
}
</style>
