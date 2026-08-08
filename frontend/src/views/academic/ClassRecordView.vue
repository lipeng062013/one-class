<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createClassRecordApi,
  getClassApi,
  getRollCallOptionsApi,
  getScheduleApi,
  listAcademicTeachersApi,
  listClassRecordsApi,
  listClassesApi,
  listCoursesApi,
  listMakeupClassRecordsApi,
  listTimeoutClassRecordsApi,
  voidClassRecordApi,
  type ClassMemberBrief,
  type ClassRecord,
  type ClassRoom,
  type Course,
  type MakeupClassRecord,
  type ScheduleLesson,
  type TeacherManage,
  type TimeoutClassRecord,
} from '../../api/academic'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import AppSheet from '../../components/AppSheet.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { SCROLL_CHUNK } from '../../composables/useServerPagedList'

type TabName = 'roll' | 'timeout' | 'makeup'
type RollStep = 'pick' | 'form'

interface RollDayCol {
  key: string
  date: Date
  weekLabel: string
  dayNum: number
  monthLabel: string
  isToday: boolean
  isFuture: boolean
  isSelected: boolean
  lessonCount: number
  pendingCount: number
}

const WEEK_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isApp } = useBreakpoint()
/** 点名/课消写操作：老师默认有 academic.write */
const canRollCall = computed(() => auth.hasPermission('academic.write'))

const activeTab = ref<TabName>('roll')
const loading = ref(false)
const loadingMore = ref(false)
const exporting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const recordRows = ref<ClassRecord[]>([])
const timeoutRows = ref<TimeoutClassRecord[]>([])
const makeupRows = ref<MakeupClassRecord[]>([])
const classes = ref<ClassRoom[]>([])
const courses = ref<Course[]>([])
const teachers = ref<TeacherManage[]>([])
const sentinelRef = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null
const hasMore = computed(() => {
  const len =
    activeTab.value === 'timeout'
      ? timeoutRows.value.length
      : activeTab.value === 'makeup'
        ? makeupRows.value.length
        : recordRows.value.length
  return len < total.value
})
const loadedCount = computed(() => {
  if (activeTab.value === 'timeout') return timeoutRows.value.length
  if (activeTab.value === 'makeup') return makeupRows.value.length
  return recordRows.value.length
})

function defaultDateRange(): [string, string] {
  const end = new Date()
  const start = new Date(end)
  start.setDate(start.getDate() - 30)
  return [dateOnly(start), dateOnly(end)]
}

const filters = reactive({
  recordDate: defaultDateRange() as [string, string],
  classDate: defaultDateRange() as [string, string],
  class_id: undefined as number | undefined,
  course_id: undefined as number | undefined,
  teacher_id: undefined as number | undefined,
  status: 'normal' as string | undefined,
  student_q: '',
})
const filterVisible = ref(false)
const activeFilterCount = computed(() =>
  Number(Boolean(filters.class_id)) +
  Number(Boolean(filters.course_id)) +
  Number(Boolean(filters.teacher_id)) +
  Number(filters.status !== 'normal' && Boolean(filters.status)) +
  Number(Boolean(filters.student_q.trim())),
)

const rollVisible = ref(false)
const saving = ref(false)
const rollOptionsLoading = ref(false)
const rollStep = ref<RollStep>('pick')
const rollClasses = ref<ClassRoom[]>([])
const rollSchedules = ref<ScheduleLesson[]>([])
const rollForm = reactive({
  class_id: undefined as number | undefined,
  schedule_id: undefined as number | undefined,
  hours: 1,
  content: '',
})
/** 周课表锚点（该周任意一天即可） */
const rollWeekAnchor = ref(startOfDay(new Date()))
/** 当前选中的上课日 */
const rollSelectedDate = ref(dateOnly(new Date()))

const lockedRollScheduleId = ref<number | null>(null)
const selectedRollLesson = ref<ScheduleLesson | null>(null)
const members = ref<ClassMemberBrief[]>([])
const attendMap = ref<Record<number, string>>({})
const dayStripRef = ref<HTMLElement | null>(null)

const ATTEND_OPTS = [
  { value: 'present', label: '到课' },
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

const tabMeta: Record<TabName, { label: string; hint: string }> = {
  roll: { label: '点名记录', hint: '已完成点名的课堂课消记录' },
  timeout: { label: '超时未点', hint: '已过下课时间仍未点名的排课' },
  makeup: { label: '缺课补课', hint: '请假/缺勤待补课学员' },
}

const currentRows = computed(() => {
  if (activeTab.value === 'timeout') return timeoutRows.value
  if (activeTab.value === 'makeup') return makeupRows.value
  return recordRows.value
})

const tabHint = computed(() => tabMeta[activeTab.value].hint)

const presentSummary = computed(() => {
  if (activeTab.value !== 'roll') return null
  const rows = recordRows.value.filter((r) => r.status === 'normal')
  const amount = rows.reduce((sum, r) => sum + Number(r.amount || 0), 0)
  const hours = rows.reduce((sum, r) => sum + Number(r.hours || 0), 0)
  return { amount, hours, count: rows.length }
})

function startOfDay(d: Date) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

/** 周一为一周起始*/
function startOfWeek(d: Date) {
  const x = startOfDay(d)
  const day = x.getDay()
  const diff = day === 0 ? -6 : 1 - day
  x.setDate(x.getDate() + diff)
  return x
}

function dateOnly(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function dateStart(value?: string) {
  return value ? `${value}T00:00:00` : undefined
}

function dateEnd(value?: string) {
  return value ? `${value}T23:59:59` : undefined
}

function parseDateKey(key: string) {
  const d = new Date(`${key}T00:00:00`)
  return Number.isNaN(d.getTime()) ? startOfDay(new Date()) : startOfDay(d)
}

function lessonDateKey(lesson: ScheduleLesson) {
  return dateOnly(new Date(lesson.start_at))
}

/** 仅当天及过去的课次可点名 */
function isLessonRollable(lesson: Pick<ScheduleLesson, 'start_at' | 'status' | 'can_roll_call'>) {
  if (lesson.status === 'completed' || lesson.status === 'cancelled') return false
  if (typeof lesson.can_roll_call === 'boolean') return lesson.can_roll_call
  const start = new Date(lesson.start_at)
  if (Number.isNaN(start.getTime())) return false
  return startOfDay(start).getTime() <= startOfDay(new Date()).getTime()
}

function futureRollMessage() {
  return '不能对未来课程点名，仅可点当天及过去的课次'
}

function formatClock(v?: string | null) {
  if (!v) return '--:--'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return '--:--'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatClockRange(start?: string | null, end?: string | null) {
  return `${formatClock(start)}-${formatClock(end)}`
}

function formatMoney(n?: number | null) {
  const value = Number(n || 0)
  return `¥ ${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDateTime(v?: string | null) {
  if (!v) return '-'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatTimeRange(start?: string | null, end?: string | null) {
  if (!start && !end) return '-'
  const startText = formatDateTime(start)
  if (!end) return startText
  const endDate = new Date(end)
  if (Number.isNaN(endDate.getTime())) return `${startText} ~ ${end}`
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${startText} ~ ${pad(endDate.getHours())}:${pad(endDate.getMinutes())}`
}

function nameInitial(name?: string | null) {
  return (name || '?').trim().slice(0, 1)
}

function resetPageAndLoad() {
  page.value = 1
  void load()
}

function resetFilters() {
  const range = defaultDateRange()
  filters.recordDate = [...range] as [string, string]
  filters.classDate = [...range] as [string, string]
  filters.class_id = undefined
  filters.course_id = undefined
  filters.teacher_id = undefined
  filters.status = 'normal'
  filters.student_q = ''
  resetPageAndLoad()
}

async function load(options?: { append?: boolean }) {
  const append = Boolean(options?.append && isApp.value)
  if (isApp.value && !append) page.value = 1
  if (append) loadingMore.value = true
  else loading.value = true
  const size = isApp.value ? SCROLL_CHUNK : pageSize.value
  try {
    if (activeTab.value === 'timeout') {
      const [start, end] = filters.classDate || []
      const res = await listTimeoutClassRecordsApi({
        class_id: filters.class_id,
        course_id: filters.course_id,
        teacher_id: filters.teacher_id,
        start: dateStart(start),
        end: dateEnd(end),
        page: page.value,
        page_size: size,
      })
      timeoutRows.value = append ? [...timeoutRows.value, ...res.items] : res.items
      total.value = res.total
      return
    }
    if (activeTab.value === 'makeup') {
      const [start, end] = filters.classDate || []
      const res = await listMakeupClassRecordsApi({
        q: filters.student_q || undefined,
        class_id: filters.class_id,
        start: dateStart(start),
        end: dateEnd(end),
        page: page.value,
        page_size: size,
      })
      makeupRows.value = append ? [...makeupRows.value, ...res.items] : res.items
      total.value = res.total
      return
    }
    const [start, end] = filters.recordDate || []
    const [classStart, classEnd] = filters.classDate || []
    const res = await listClassRecordsApi({
      class_id: filters.class_id,
      course_id: filters.course_id,
      teacher_id: filters.teacher_id,
      status: filters.status || undefined,
      start: dateStart(start),
      end: dateEnd(end),
      class_start: dateStart(classStart),
      class_end: dateEnd(classEnd),
      page: page.value,
      page_size: size,
    })
    recordRows.value = append ? [...recordRows.value, ...res.items] : res.items
    total.value = res.total
  } catch {
    if (append) page.value = Math.max(1, page.value - 1)
    else {
      recordRows.value = []
      timeoutRows.value = []
      makeupRows.value = []
      total.value = 0
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function loadMore() {
  if (!isApp.value || loading.value || loadingMore.value || !hasMore.value) return
  page.value += 1
  void load({ append: true })
}

function setupScrollObserver() {
  teardownScrollObserver()
  if (!isApp.value) return
  const el = sentinelRef.value
  if (!el) return
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore()
    },
    { root: null, rootMargin: '160px 0px', threshold: 0 },
  )
  scrollObserver.observe(el)
}

function teardownScrollObserver() {
  scrollObserver?.disconnect()
  scrollObserver = null
}

async function loadMeta() {
  const [cl, co, te] = await Promise.all([
    listClassesApi({ page_size: 100 }).catch(() => ({ items: [] as ClassRoom[] })),
    listCoursesApi({ enabled: true, page_size: 100 }).catch(() => ({ items: [] as Course[] })),
    listAcademicTeachersApi({ page_size: 100 }).catch(() => ({ items: [] as TeacherManage[] })),
  ])
  classes.value = cl.items
  courses.value = co.items
  teachers.value = te.items
}

function onTabChange() {
  page.value = 1
  void load()
}

const rollWeekRange = computed(() => {
  const start = startOfWeek(rollWeekAnchor.value)
  const end = new Date(start)
  end.setDate(start.getDate() + 6)
  return { start, end, startKey: dateOnly(start), endKey: dateOnly(end) }
})

const rollWeekLabel = computed(() => {
  const { start, end } = rollWeekRange.value
  const pad = (n: number) => String(n).padStart(2, '0')
  const sameYear = start.getFullYear() === end.getFullYear()
  const left = `${start.getFullYear()}年${pad(start.getMonth() + 1)}月${pad(start.getDate())}日`
  const right = sameYear
    ? `${pad(end.getMonth() + 1)}月${pad(end.getDate())}日`
    : `${end.getFullYear()}年${pad(end.getMonth() + 1)}月${pad(end.getDate())}日`
  return `${left} ~ ${right}`
})

const isCurrentRollWeek = computed(() => {
  return dateOnly(startOfWeek(new Date())) === rollWeekRange.value.startKey
})

const rollDayCols = computed<RollDayCol[]>(() => {
  const todayKey = dateOnly(new Date())
  const { start } = rollWeekRange.value
  const out: RollDayCol[] = []
  for (let i = 0; i < 7; i += 1) {
    const d = new Date(start)
    d.setDate(start.getDate() + i)
    const key = dateOnly(d)
    const dayLessons = rollSchedules.value.filter((s) => lessonDateKey(s) === key)
    out.push({
      key,
      date: d,
      weekLabel: WEEK_NAMES[i],
      dayNum: d.getDate(),
      monthLabel: `${d.getMonth() + 1}月`,
      isToday: key === todayKey,
      isFuture: key > todayKey,
      isSelected: key === rollSelectedDate.value,
      lessonCount: dayLessons.length,
      pendingCount: dayLessons.filter((s) => isLessonRollable(s)).length,
    })
  }
  return out
})

const selectedDayLessons = computed(() => {
  return rollSchedules.value
    .filter((s) => lessonDateKey(s) === rollSelectedDate.value)
    .slice()
    .sort(
      (a, b) =>
        new Date(a.start_at).getTime() - new Date(b.start_at).getTime() || a.id - b.id,
    )
})

const selectedDayMeta = computed(() => {
  return rollDayCols.value.find((d) => d.key === rollSelectedDate.value) || null
})

const rollDialogTitle = computed(() => {
  if (rollStep.value === 'pick') return '选择课次点名'
  return '课堂点名'
})



function resetRollFormState() {
  rollForm.hours = 1
  rollForm.content = ''
  rollForm.class_id = undefined
  rollForm.schedule_id = undefined
  members.value = []
  attendMap.value = {}
  selectedRollLesson.value = null
  lockedRollScheduleId.value = null
}

async function openRoll(pref?: { class_id?: number; schedule_id?: number }) {
  if (!canRollCall.value) {
    ElMessage.warning('当前账号无点名权限')
    return
  }
  resetRollFormState()
  const today = startOfDay(new Date())
  rollWeekAnchor.value = today
  rollSelectedDate.value = dateOnly(today)
  lockedRollScheduleId.value =
    pref?.schedule_id && pref.schedule_id > 0 ? pref.schedule_id : null
  rollVisible.value = true

  // 从超时未点 / 外链带 schedule 时，直接进入点名表单
  if (lockedRollScheduleId.value) {
    rollStep.value = 'form'
    await prepareRollFromSchedule(lockedRollScheduleId.value, pref?.class_id)
    return
  }

  rollStep.value = 'pick'
  await loadRollWeekOptions()
  await scrollSelectedDayToCenter()
}

async function loadRollWeekOptions() {
  rollOptionsLoading.value = true
  try {
    const { startKey, endKey } = rollWeekRange.value
    const options = await getRollCallOptionsApi({
      date: rollSelectedDate.value,
      start: startKey,
      end: endKey,
    })
    rollClasses.value = options.classes
    rollSchedules.value = options.schedules
  } catch {
    rollClasses.value = []
    rollSchedules.value = []
  } finally {
    rollOptionsLoading.value = false
  }
}

async function scrollSelectedDayToCenter() {
  await nextTick()
  const strip = dayStripRef.value
  if (!strip) return
  const active = strip.querySelector('.roll-day.is-selected') as HTMLElement | null
  if (!active) return
  const left = active.offsetLeft - (strip.clientWidth - active.clientWidth) / 2
  strip.scrollTo({ left: Math.max(0, left), behavior: 'smooth' })
}

async function changeRollWeek(delta: number) {
  const prevSelected = parseDateKey(rollSelectedDate.value)
  const prevWeekday = prevSelected.getDay() // 0=周日
  const next = new Date(rollWeekAnchor.value)
  next.setDate(next.getDate() + delta * 7)
  rollWeekAnchor.value = startOfDay(next)
  const { start } = rollWeekRange.value
  const target = new Date(start)
  const offset = prevWeekday === 0 ? 6 : prevWeekday - 1
  target.setDate(start.getDate() + offset)
  rollSelectedDate.value = dateOnly(target)
  await loadRollWeekOptions()
  await scrollSelectedDayToCenter()
}

async function resetRollWeekToToday() {
  const today = startOfDay(new Date())
  rollWeekAnchor.value = today
  rollSelectedDate.value = dateOnly(today)
  await loadRollWeekOptions()
  await scrollSelectedDayToCenter()
}

async function selectRollDay(day: RollDayCol) {
  if (rollSelectedDate.value === day.key) return
  rollSelectedDate.value = day.key
  await scrollSelectedDayToCenter()
}

async function tryOpenRollFromQuery() {
  if (route.query.roll !== '1') return
  const classId = Number(route.query.class_id)
  const scheduleId = Number(route.query.schedule_id)
  const nextQuery = { ...route.query }
  delete nextQuery.roll
  delete nextQuery.class_id
  delete nextQuery.schedule_id
  void router.replace({ path: route.path, query: nextQuery })
  if (!canRollCall.value) return
  await openRoll({
    class_id: Number.isFinite(classId) && classId > 0 ? classId : undefined,
    schedule_id: Number.isFinite(scheduleId) && scheduleId > 0 ? scheduleId : undefined,
  })
}

async function prepareMembers(classId: number) {
  const cls =
    rollClasses.value.find((c) => c.id === classId) ||
    classes.value.find((c) => c.id === classId)
  rollForm.hours = Number(cls?.hours_per_session) > 0 ? Number(cls?.hours_per_session) : 1
  try {
    const detail = await getClassApi(classId)
    members.value = detail.members || []
    attendMap.value = Object.fromEntries(members.value.map((m) => [m.id, 'present']))
  } catch {
    members.value = []
    attendMap.value = {}
  }
}

async function prepareRollFromSchedule(scheduleId: number, prefClassId?: number) {
  rollOptionsLoading.value = true
  try {
    let lesson =
      rollSchedules.value.find((s) => s.id === scheduleId) ||
      null
    if (!lesson) {
      lesson = await getScheduleApi(scheduleId)
    }
    if (lesson.status === 'completed') {
      ElMessage.warning('该课次已点名')
      rollStep.value = 'pick'
      lockedRollScheduleId.value = null
      await loadRollWeekOptions()
      return
    }
    if (!isLessonRollable(lesson)) {
      ElMessage.warning(futureRollMessage())
      rollStep.value = 'pick'
      lockedRollScheduleId.value = null
      if (lesson.start_at) {
        const d = startOfDay(new Date(lesson.start_at))
        rollWeekAnchor.value = d
        rollSelectedDate.value = dateOnly(d)
      }
      await loadRollWeekOptions()
      return
    }
    selectedRollLesson.value = lesson
    rollForm.class_id = lesson.class_id || prefClassId
    rollForm.schedule_id = lesson.id
    lockedRollScheduleId.value = lesson.id
    if (lesson.start_at) {
      const d = startOfDay(new Date(lesson.start_at))
      rollWeekAnchor.value = d
      rollSelectedDate.value = dateOnly(d)
    }
    if (rollForm.class_id) {
      await prepareMembers(rollForm.class_id)
    }
  } catch {
    ElMessage.error('加载课次失败')
    rollStep.value = 'pick'
    lockedRollScheduleId.value = null
  } finally {
    rollOptionsLoading.value = false
  }
}

async function selectLessonForRoll(lesson: ScheduleLesson) {
  if (lesson.status === 'completed') {
    ElMessage.info('该课次已点名，可在点名记录中查看')
    return
  }
  if (!isLessonRollable(lesson)) {
    ElMessage.warning(futureRollMessage())
    return
  }
  rollStep.value = 'form'
  lockedRollScheduleId.value = lesson.id
  selectedRollLesson.value = lesson
  rollForm.class_id = lesson.class_id
  rollForm.schedule_id = lesson.id
  rollForm.content = ''
  await prepareMembers(lesson.class_id)
}

async function backToRollPick() {
  rollStep.value = 'pick'
  lockedRollScheduleId.value = null
  selectedRollLesson.value = null
  rollForm.class_id = undefined
  rollForm.schedule_id = undefined
  members.value = []
  attendMap.value = {}
  if (!rollSchedules.value.length) {
    await loadRollWeekOptions()
  }
  await scrollSelectedDayToCenter()
}

function markAll(status: string) {
  attendMap.value = Object.fromEntries(members.value.map((m) => [m.id, status]))
}

async function submitRoll() {
  if (!rollForm.class_id) {
    ElMessage.warning('请选择班级')
    return
  }
  if (!members.value.length) {
    ElMessage.warning('班级暂无学员，无法点名')
    return
  }
  const lesson = selectedRollLesson.value
  if (lesson && !isLessonRollable(lesson)) {
    ElMessage.warning(futureRollMessage())
    return
  }
  saving.value = true
  try {
    await createClassRecordApi({
      class_id: rollForm.class_id,
      schedule_id: lockedRollScheduleId.value ?? rollForm.schedule_id ?? null,
      hours: rollForm.hours || 1,
      content: rollForm.content,
      attendances: members.value.map((m) => ({
        student_id: m.id,
        status: attendMap.value[m.id] || 'present',
      })),
    })
    ElMessage.success('点名成功，已生成上课记录与课消')
    rollVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function onVoid(row: ClassRecord) {
  try {
    await ElMessageBox.confirm(
      '确定撤销该点名记录？课消将作废，并回滚已扣课时。',
      '撤销确认',
      { type: 'warning' },
    )
    await voidClassRecordApi(row.id)
    ElMessage.success('已撤销，课时已回滚')
    await load()
  } catch {
    /* user cancelled */
  }
}

function openDetail(row: ClassRecord | MakeupClassRecord) {
  const id = 'record_id' in row ? row.record_id : row.id
  void router.push({ name: 'academic-class-record-detail', params: { id } })
}

function csvCell(value: unknown) {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

async function exportRecords() {
  if (activeTab.value !== 'roll') {
    ElMessage.info('请切换到点名记录后导出')
    return
  }
  exporting.value = true
  try {
    const [start, end] = filters.recordDate || []
    const [classStart, classEnd] = filters.classDate || []
    const items: ClassRecord[] = []
    let current = 1
    let count = 0
    do {
      const res = await listClassRecordsApi({
        class_id: filters.class_id,
        course_id: filters.course_id,
        teacher_id: filters.teacher_id,
        status: filters.status || undefined,
        start: dateStart(start),
        end: dateEnd(end),
        class_start: dateStart(classStart),
        class_end: dateEnd(classEnd),
        page: current,
        page_size: 100,
      })
      items.push(...res.items)
      count = res.total
      current += 1
    } while (items.length < count)

    if (!items.length) {
      ElMessage.warning('当前筛选条件下暂无可导出数据')
      return
    }
    const rows = [
      ['点名时间', '点名老师', '课程类型', '班级名称', '授课课程', '上课时间', '授课老师', '授课课时', '计薪课时', '实到人数', '总人数', '课消金额', '上课内容', '状态'],
      ...items.map((row) => [
        formatDateTime(row.roll_at),
        row.creator_name || '-',
        row.course_type_label || '-',
        row.class_name,
        row.course_name,
        formatTimeRange(row.class_start, row.class_end),
        row.teachers,
        row.hours,
        row.salary_hours,
        row.present_count,
        row.total_count,
        Number(row.amount || 0).toFixed(2),
        row.content,
        row.status_label,
      ]),
    ]
    const csv = `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = '班级点名记录.csv'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出${items.length} 条点名记录`)
  } finally {
    exporting.value = false
  }
}

function openTimeoutRoll(row: TimeoutClassRecord) {
  void openRoll({ class_id: row.class_id, schedule_id: row.id })
}

watch(isApp, async () => {
  page.value = 1
  await load()
  await nextTick()
  if (isApp.value) setupScrollObserver()
  else teardownScrollObserver()
})

watch(sentinelRef, async () => {
  await nextTick()
  if (isApp.value) setupScrollObserver()
})

onMounted(async () => {
  await loadMeta()
  await load()
  await tryOpenRollFromQuery()
  await nextTick()
  if (isApp.value) setupScrollObserver()
})

onUnmounted(() => teardownScrollObserver())
</script>

<template>
  <div class="record-page">
    <div
      v-if="!isApp || canRollCall"
      class="page-toolbar"
      :class="{ 'is-app-roll': isApp && canRollCall }"
    >
      <div v-if="!isApp" class="toolbar-title-block">
        <el-page-header class="is-title-only" content="上课记录" />
        <p class="page-sub">点名 · 课消 · 超时提醒 · 缺课补课</p>
      </div>
      <div v-if="canRollCall && !isApp" class="toolbar-right">
        <el-button type="primary" class="tb-btn tb-btn--primary" @click="openRoll()">
          <el-icon><EditPen /></el-icon>
          点名
        </el-button>
      </div>
      <button
        v-if="canRollCall && isApp"
        type="button"
        class="roll-entry-cta"
        @click="openRoll()"
      >
        <span class="roll-entry-ico" aria-hidden="true">
          <el-icon><EditPen /></el-icon>
        </span>
        <span class="roll-entry-copy">
          <strong>课堂点名</strong>
          <em>按周选课 · 一键完成课消</em>
        </span>
        <span class="roll-entry-go">
          去点名
          <el-icon><ArrowRight /></el-icon>
        </span>
      </button>
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <el-tabs v-model="activeTab" class="record-tabs" @tab-change="onTabChange">
        <el-tab-pane name="roll">
          <template #label>
            <span class="tab-label">
              <el-icon><Notebook /></el-icon>
              点名记录
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="timeout">
          <template #label>
            <span class="tab-label">
              <el-icon><AlarmClock /></el-icon>
              超时未点
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="makeup">
          <template #label>
            <span class="tab-label">
              <el-icon><RefreshRight /></el-icon>
              缺课补课
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>

      <CompactFilterBar v-if="isApp" :active-count="activeFilterCount" :total="total" :label="`${tabMeta[activeTab].label}`" @open="filterVisible = true" />

      <div v-if="!isApp" class="filter-panel">
        <div class="filter-panel-head">
          <div class="filter-panel-title">
            <span class="sec-dot" />
            筛选条件
          </div>
          <span class="filter-hint">{{ tabHint }}</span>
        </div>

        <div class="filter-grid" :class="`tab-${activeTab}`">
          <template v-if="activeTab === 'roll'">
            <label class="filter-item">
              <span class="filter-label">上课日期</span>
              <el-date-picker
                v-model="filters.classDate"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                range-separator="~"
              />
            </label>
            <label class="filter-item">
              <span class="filter-label">点名日期</span>
              <el-date-picker
                v-model="filters.recordDate"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                range-separator="~"
              />
            </label>
            <label class="filter-item">
              <span class="filter-label">状态</span>
              <el-select v-model="filters.status" clearable placeholder="请选择状态">
                <el-option label="正常" value="normal" />
                <el-option label="已撤销" value="void" />
              </el-select>
            </label>
          </template>

          <template v-if="activeTab === 'timeout'">
            <label class="filter-item">
              <span class="filter-label">上课日期</span>
              <el-date-picker
                v-model="filters.classDate"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                range-separator="~"
              />
            </label>
          </template>

          <template v-if="activeTab === 'makeup'">
            <label class="filter-item">
              <span class="filter-label">搜索学员</span>
              <el-input
                v-model="filters.student_q"
                clearable
                placeholder="请输入学员姓名手机号"
                @keyup.enter="resetPageAndLoad"
              >
                <template #prefix><el-icon><Search /></el-icon></template>
              </el-input>
            </label>
          </template>

          <label class="filter-item">
            <span class="filter-label">所在班级</span>
            <el-select v-model="filters.class_id" clearable filterable placeholder="请选择班级">
              <el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </label>

          <template v-if="activeTab !== 'makeup'">
            <label class="filter-item">
              <span class="filter-label">授课课程</span>
              <el-select v-model="filters.course_id" clearable filterable placeholder="请选择课程">
                <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </label>
            <label class="filter-item">
              <span class="filter-label">上课老师</span>
              <el-select v-model="filters.teacher_id" clearable filterable placeholder="请选择老师">
                <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
            </label>
          </template>

          <template v-if="activeTab === 'makeup'">
            <label class="filter-item">
              <span class="filter-label">上课日期</span>
              <el-date-picker
                v-model="filters.classDate"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                range-separator="~"
              />
            </label>
          </template>
        </div>

        <div class="filter-actions">
          <el-button class="tb-btn" plain @click="resetFilters">
            <el-icon><RefreshLeft /></el-icon>
            重置
          </el-button>
          <el-button type="primary" class="tb-btn tb-btn--primary" @click="resetPageAndLoad">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
        </div>
      </div>

      <MobileFilterSheet v-model="filterVisible" :active-count="activeFilterCount" @apply="resetPageAndLoad" @reset="resetFilters">
        <el-form label-position="top">
          <el-form-item v-if="activeTab === 'makeup'" label="搜索学员"><el-input v-model="filters.student_q" clearable placeholder="学员姓名 / 手机号" /></el-form-item>
          <el-form-item label="上课日期"><el-date-picker v-model="filters.classDate" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="~" /></el-form-item>
          <el-form-item v-if="activeTab === 'roll'" label="点名日期"><el-date-picker v-model="filters.recordDate" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="~" /></el-form-item>
          <el-form-item v-if="activeTab === 'roll'" label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option label="正常" value="normal" /><el-option label="已撤销" value="void" /></el-select></el-form-item>
          <el-form-item label="所在班级"><el-select v-model="filters.class_id" clearable filterable placeholder="全部班级"><el-option v-for="c in classes" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
          <el-form-item v-if="activeTab !== 'makeup'" label="授课课程"><el-select v-model="filters.course_id" clearable filterable placeholder="全部课程"><el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
          <el-form-item v-if="activeTab !== 'makeup'" label="上课老师"><el-select v-model="filters.teacher_id" clearable filterable placeholder="全部老师"><el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" /></el-select></el-form-item>
        </el-form>
      </MobileFilterSheet>

      <div class="table-actions" :class="{ 'is-app-actions': isApp }">
        <div class="action-left">
          <el-button
            v-if="canRollCall && activeTab === 'makeup'"
            type="primary"
            class="tb-btn tb-btn--primary"
            @click="openRoll()"
          >
            开班补课
          </el-button>
          <el-button
            class="tb-btn"
            plain
            :loading="exporting"
            :disabled="activeTab !== 'roll'"
            @click="exportRecords"
          >
            <el-icon><Download /></el-icon>
            导出
          </el-button>
          <span class="summary-chip">
            共 <b>{{ total }}</b> 条{{ tabMeta[activeTab].label }}
          </span>
        </div>
        <div v-if="presentSummary && presentSummary.count" class="summary-bar">
          <span>本页正常记录</span>
          <strong class="hours-num">{{ presentSummary.hours }}</strong>
          <span>课时 · 课消</span>
          <strong class="pc-mono">{{ formatMoney(presentSummary.amount) }}</strong>
        </div>
      </div>

      <div v-if="isApp" class="m-card-list">
        <div v-if="!currentRows.length && !loading" class="m-card m-card-empty record-empty">
          <span class="record-empty-ico" aria-hidden="true">📋</span>
          <strong>暂无{{ tabMeta[activeTab].label }}</strong>
          <em>{{ tabHint }}</em>
        </div>

        <article
          v-for="row in recordRows"
          v-show="activeTab === 'roll'"
          :key="`r-${row.id}`"
          class="m-card record-m-card"
          :class="{ 'is-void': row.status === 'void' }"
          @click="openDetail(row)"
        >
          <div class="m-card-head">
            <div class="record-m-who">
              <span class="name-avatar">{{ nameInitial(row.class_name) }}</span>
              <div class="record-m-text">
                <div class="m-card-title">
                  {{ row.class_name || '-' }}
                  <el-tag
                    size="small"
                    effect="plain"
                    round
                    :type="row.status === 'void' ? 'info' : 'success'"
                  >
                    {{ row.status_label }}
                  </el-tag>
                </div>
                <div class="record-m-sub">{{ row.course_name || '未关联课程' }}</div>
              </div>
            </div>
            <div class="record-m-amount">
              <span class="record-m-amount-label">课消</span>
              <strong class="pc-mono amount-text">{{ formatMoney(row.amount) }}</strong>
            </div>
          </div>
          <div class="record-m-chips">
            <span class="rm-chip">
              <el-icon><Clock /></el-icon>
              {{ formatTimeRange(row.class_start, row.class_end) }}
            </span>
            <span class="rm-chip">授课 {{ row.hours }} 课时</span>
            <span class="rm-chip">计薪 {{ row.salary_hours }} 课时</span>
            <span class="rm-chip">实到 {{ row.attendance }}</span>
            <span v-if="row.teachers" class="rm-chip">{{ row.teachers }}</span>
          </div>
          <div class="record-m-foot">
            <span class="record-m-roll-at">点名 {{ formatDateTime(row.roll_at) }}</span>
          </div>
          <div class="m-card-actions" @click.stop>
            <el-button size="small" type="primary" plain @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="auth.isAdmin && row.status === 'normal'"
              size="small"
              plain
              type="danger"
              @click="onVoid(row)"
            >
              撤销
            </el-button>
          </div>
        </article>

        <article
          v-for="row in timeoutRows"
          v-show="activeTab === 'timeout'"
          :key="`t-${row.id}`"
          class="m-card record-m-card is-timeout"
        >
          <div class="m-card-head">
            <div class="record-m-who">
              <span class="name-avatar is-warn">{{ nameInitial(row.class_name) }}</span>
              <div class="record-m-text">
                <div class="m-card-title">
                  {{ row.class_name }}
                  <el-tag size="small" effect="plain" round type="warning">未点名</el-tag>
                </div>
                <div class="record-m-sub">{{ row.course_name || '未关联课程' }}</div>
              </div>
            </div>
            <span class="timeout-badge">超时</span>
          </div>
          <div class="record-m-chips">
            <span class="rm-chip">
              <el-icon><Clock /></el-icon>
              {{ formatTimeRange(row.start_at, row.end_at) }}
            </span>
            <span v-if="row.teachers" class="rm-chip">{{ row.teachers }}</span>
            <span class="rm-chip">教室 {{ row.room || '未设' }}</span>
          </div>
          <div v-if="canRollCall" class="m-card-actions">
            <el-button size="small" type="primary" @click="openTimeoutRoll(row)">去点名</el-button>
          </div>
        </article>

        <article
          v-for="row in makeupRows"
          v-show="activeTab === 'makeup'"
          :key="`m-${row.id}`"
          class="m-card record-m-card is-makeup"
          @click="openDetail(row)"
        >
          <div class="m-card-head">
            <div class="record-m-who">
              <span class="name-avatar is-danger">{{ nameInitial(row.student_name) }}</span>
              <div class="record-m-text">
                <div class="m-card-title">
                  {{ row.student_name }}
                  <el-tag size="small" effect="plain" round type="danger">
                    {{ row.makeup_status_label }}
                  </el-tag>
                </div>
                <div class="record-m-sub">{{ row.class_name }}</div>
              </div>
            </div>
          </div>
          <div class="record-m-chips">
            <span class="rm-chip tone-danger">缺课 {{ row.absence_status_label }}</span>
            <span class="rm-chip">应扣 {{ row.expected_hours }} 课时</span>
            <span class="rm-chip">实扣 {{ row.actual_hours }} 课时</span>
            <span class="rm-chip">
              <el-icon><Clock /></el-icon>
              {{ formatTimeRange(row.class_start, row.class_end) }}
            </span>
          </div>
          <div class="m-card-actions" @click.stop>
            <el-button size="small" type="primary" plain @click="openDetail(row)">详情</el-button>
          </div>
        </article>
        <div ref="sentinelRef" class="list-load-sentinel">
          <ListLoadStatus
            :has-more="hasMore"
            :loading="loadingMore"
            :loaded="loadedCount"
            :total="total"
            @more="loadMore"
            @retry="loadMore"
          />
        </div>
      </div>

      <div v-else class="table-wrap oc-compact-table-wrap">
        <el-table
          v-if="activeTab === 'roll'"
          :data="recordRows"
          row-key="id"
          stripe
          border
          class="data-table"
          :header-cell-style="pcHeaderStyle"
          empty-text="暂无点名记录"
        >
          <el-table-column label="点名时间" width="160" sortable>
            <template #default="{ row }">
              <span class="cell-muted">{{ formatDateTime(row.roll_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="class_name" label="班级名称" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <button type="button" class="link-name" @click="openDetail(row)">
                <span class="name-avatar sm">{{ nameInitial(row.class_name) }}</span>
                <span class="name-text">{{ row.class_name || '-' }}</span>
              </button>
            </template>
          </el-table-column>
          <el-table-column prop="course_name" label="授课课程" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.course_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="上课时间" width="190" sortable>
            <template #default="{ row }">
              <span class="cell-muted">{{ formatTimeRange(row.class_start, row.class_end) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="teachers" label="上课老师" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.teachers || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="hours" label="授课课时" width="95" align="center">
            <template #default="{ row }">
              <span class="hours-pill">{{ row.hours }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="salary_hours" label="计薪课时" width="95" align="center">
            <template #default="{ row }">
              <span class="hours-num">{{ row.salary_hours }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="attendance" label="实到人数" width="95" align="center">
            <template #default="{ row }">
              <span class="attend-pill">{{ row.attendance }}</span>
            </template>
          </el-table-column>
          <el-table-column label="课消金额" width="120" align="right">
            <template #default="{ row }">
              <span class="pc-mono">{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="上课内容" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.content || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status_label" label="状态" width="96" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                :type="row.status === 'void' ? 'info' : 'success'"
              >
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right" align="right">
            <template #default="{ row }">
              <div class="pc-ops">
                <el-button link type="primary" @click="openDetail(row)">详情</el-button>
                <template v-if="auth.isAdmin && row.status === 'normal'">
                  <span class="op-sep" />
                  <el-button link type="danger" @click="onVoid(row)">撤销</el-button>
                </template>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <el-table
          v-else-if="activeTab === 'timeout'"
          :data="timeoutRows"
          row-key="id"
          stripe
          border
          class="data-table"
          :header-cell-style="pcHeaderStyle"
          empty-text="暂无超时未点名课次"
        >
          <el-table-column label="上课时间" width="190" sortable>
            <template #default="{ row }">
              <span class="cell-muted">{{ formatTimeRange(row.start_at, row.end_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="class_name" label="班级名称" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="pc-name-cell">
                <span class="name-avatar sm is-warn">{{ nameInitial(row.class_name) }}</span>
                <span class="cell-strong">{{ row.class_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="teachers" label="上课老师" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.teachers || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="course_name" label="授课课程" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.course_name || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="room" label="上课教室" width="130">
            <template #default="{ row }">
              <span class="room-pill">{{ row.room || '不指定' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="上课内容" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.content || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="canRollCall" label="操作" width="110" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="openTimeoutRoll(row)">去点名</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-table
          v-else
          :data="makeupRows"
          row-key="id"
          stripe
          border
          class="data-table"
          :header-cell-style="pcHeaderStyle"
          empty-text="暂无缺课待补记录"
        >
          <el-table-column prop="student_name" label="学员姓名" width="130">
            <template #default="{ row }">
              <div class="pc-name-cell">
                <span class="name-avatar sm is-danger">{{ nameInitial(row.student_name) }}</span>
                <span class="cell-strong">{{ row.student_name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="手机号" width="130">
            <template #default="{ row }">
              <span class="cell-muted">{{ row.phone || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="class_name" label="班级名称" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.class_name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="上课时间" width="190">
            <template #default="{ row }">
              <span class="cell-muted">{{ formatTimeRange(row.class_start, row.class_end) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="teachers" label="上课老师" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.teachers || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="absence_status_label" label="缺课状态" width="96" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="plain" type="warning">{{ row.absence_status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="consume_label" label="消耗方式" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.consume_label || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="应扣额度" width="95" align="center">
            <template #default="{ row }">
              <span class="hours-pill">{{ row.expected_hours }}</span>
            </template>
          </el-table-column>
          <el-table-column label="实扣额度" width="95" align="center">
            <template #default="{ row }">
              <span class="hours-num">{{ row.actual_hours }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="makeup_status_label" label="补课状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="plain" type="danger">{{ row.makeup_status_label }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="content" label="上课内容" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.content || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right" align="right">
            <template #default="{ row }">
              <div class="pc-ops">
                <el-button v-if="canRollCall" link type="primary" @click="openRoll()">插班补课</el-button>
                <span v-if="canRollCall" class="op-sep" />
                <el-button link type="primary" @click="openDetail(row)">详情</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <PcPagerBar v-model:page="page" v-model:page-size="pageSize" :total="total" @change="load" />

    <!-- WAP/Pad：点名用底部 AppSheet；PC 用 Dialog -->
    <AppSheet
      v-if="isApp"
      v-model="rollVisible"
      :title="rollDialogTitle"
      compact-size="min(94%, 920px)"
      force-bottom
      modal-class="roll-app-sheet"
      destroy-on-close
    >
      <div v-if="rollStep === 'pick'" v-loading="rollOptionsLoading" class="roll-pick">
        <div class="roll-week-nav">
          <button type="button" class="roll-week-nav-btn" @click="changeRollWeek(-1)">
            <el-icon><ArrowLeft /></el-icon>
            <span>上周</span>
          </button>
          <div class="roll-week-center">
            <div class="roll-week-label">{{ rollWeekLabel }}</div>
            <button
              type="button"
              class="roll-today-link"
              :disabled="isCurrentRollWeek && selectedDayMeta?.isToday"
              @click="resetRollWeekToToday"
            >
              回到今天
            </button>
          </div>
          <button type="button" class="roll-week-nav-btn" @click="changeRollWeek(1)">
            <span>下周</span>
            <el-icon><ArrowRight /></el-icon>
          </button>
        </div>

        <div ref="dayStripRef" class="roll-day-strip">
          <button
            v-for="day in rollDayCols"
            :key="day.key"
            type="button"
            class="roll-day"
            :class="{
              'is-today': day.isToday,
              'is-future': day.isFuture,
              'is-selected': day.isSelected,
              'has-pending': day.pendingCount > 0,
            }"
            @click="selectRollDay(day)"
          >
            <span class="rd-week">{{ day.weekLabel }}</span>
            <span class="rd-num">{{ day.dayNum }}</span>
            <span class="rd-month">{{ day.monthLabel }}</span>
            <span v-if="day.lessonCount" class="rd-badge" :class="{ 'is-pending': day.pendingCount > 0 }">
              {{ day.pendingCount > 0 ? day.pendingCount : day.lessonCount }}
            </span>
            <span v-if="day.isToday" class="rd-today-tag">今</span>
            <span v-else-if="day.isFuture" class="rd-future-tag">未到</span>
          </button>
        </div>

        <div class="roll-day-panel">
          <div class="roll-day-panel-head">
            <span class="sec-dot" />
            <strong>
              {{ selectedDayMeta?.weekLabel || '' }}
              {{ selectedDayMeta ? `${selectedDayMeta.monthLabel}${selectedDayMeta.dayNum}日` : '' }}
            </strong>
            <span class="roll-day-count">
              共 {{ selectedDayLessons.length }} 节
              <template v-if="selectedDayMeta?.pendingCount">
                · 待点名 {{ selectedDayMeta.pendingCount }}
              </template>
            </span>
          </div>

          <p v-if="selectedDayMeta?.isFuture" class="roll-future-hint">
            未来课次不可点名，仅可查看；请选择当天或过去日期。
          </p>

          <div v-if="selectedDayLessons.length" class="roll-lesson-list">
            <button
              v-for="lesson in selectedDayLessons"
              :key="lesson.id"
              type="button"
              class="roll-lesson-card"
              :class="{
                'is-done': lesson.status === 'completed',
                'is-pending': isLessonRollable(lesson),
                'is-future': lesson.status === 'scheduled' && !isLessonRollable(lesson),
              }"
              :disabled="lesson.status === 'scheduled' && !isLessonRollable(lesson)"
              @click="selectLessonForRoll(lesson)"
            >
              <div class="rl-time">
                <span class="rl-clock">{{ formatClockRange(lesson.start_at, lesson.end_at) }}</span>
                <el-tag
                  size="small"
                  effect="plain"
                  :type="
                    lesson.status === 'completed'
                      ? 'success'
                      : isLessonRollable(lesson)
                        ? 'warning'
                        : 'info'
                  "
                >
                  {{
                    lesson.status === 'completed'
                      ? '已点名'
                      : isLessonRollable(lesson)
                        ? '待点名'
                        : '未到时间'
                  }}
                </el-tag>
              </div>
              <div class="rl-title">{{ lesson.class_name }}</div>
              <div class="rl-meta">
                <span>{{ lesson.course_name || '未关联课程' }}</span>
                <span v-if="lesson.teachers">{{ lesson.teachers }}</span>
                <span v-if="lesson.room">{{ lesson.room }}</span>
                <span v-if="lesson.member_count">{{ lesson.member_count }}人</span>
              </div>
              <div class="rl-action">
                <template v-if="lesson.status === 'completed'">已完成</template>
                <template v-else-if="isLessonRollable(lesson)">
                  去点名
                  <el-icon><ArrowRight /></el-icon>
                </template>
                <template v-else>不可点名</template>
              </div>
            </button>
          </div>
          <el-empty
            v-else-if="!rollOptionsLoading"
            description="当天暂无排课，请切换其他日期"
            :image-size="72"
          />
        </div>
      </div>

      <div v-else class="roll-form-step">
        <div v-if="selectedRollLesson" class="roll-selected-card">
          <div class="rsc-top">
            <span class="rsc-badge">已选课次</span>
            <el-button class="rsc-reselect" link type="primary" @click="backToRollPick">重选</el-button>
          </div>
          <div class="rsc-main">
            <span class="rsc-avatar">{{ nameInitial(selectedRollLesson.class_name) }}</span>
            <div class="rsc-body">
              <div class="rsc-title">{{ selectedRollLesson.class_name || '—' }}</div>
              <div class="rsc-time">
                <el-icon><Clock /></el-icon>
                {{ formatClockRange(selectedRollLesson.start_at, selectedRollLesson.end_at) }}
              </div>
            </div>
          </div>
          <div class="rsc-chips">
            <span v-if="selectedRollLesson.course_name" class="rsc-chip">
              <el-icon><Reading /></el-icon>
              {{ selectedRollLesson.course_name }}
            </span>
            <span v-if="selectedRollLesson.teachers" class="rsc-chip">
              <el-icon><User /></el-icon>
              {{ selectedRollLesson.teachers }}
            </span>
            <span v-if="selectedRollLesson.room" class="rsc-chip">
              <el-icon><OfficeBuilding /></el-icon>
              {{ selectedRollLesson.room }}
            </span>
            <span v-if="selectedRollLesson.member_count" class="rsc-chip">
              <el-icon><UserFilled /></el-icon>
              {{ selectedRollLesson.member_count }} 人
            </span>
          </div>
        </div>

        <el-form label-position="top" class="roll-form">
          <el-form-item label="授课课时">
            <el-input-number v-model="rollForm.hours" :min="0.01" :step="0.25" :precision="2" />
            <div class="form-tip">按课次扣学员课时，默认单次 1 课时</div>
          </el-form-item>
          <el-form-item label="上课内容">
            <el-input v-model="rollForm.content" type="textarea" :rows="2" placeholder="可选，记录本节课要点" />
          </el-form-item>
        </el-form>

        <div v-if="members.length" class="attend-block">
          <div class="attend-head">
            <span class="attend-title">
              <span class="sec-dot" />
              学员名单
              <em>{{ members.length }} 人</em>
            </span>
            <div class="attend-quick">
              <el-button link type="primary" @click="markAll('present')">全勤</el-button>
              <el-button link @click="markAll('absent')">全缺</el-button>
            </div>
          </div>
          <div class="attend-list">
            <div v-for="m in members" :key="m.id" class="attend-row">
              <div class="attend-name">
                <span class="name-avatar xs">{{ nameInitial(m.name) }}</span>
                <div>
                  <span class="name">{{ m.name }}</span>
                  <span v-if="m.phone" class="phone">{{ m.phone }}</span>
                </div>
              </div>
              <el-radio-group v-model="attendMap[m.id]" size="small" class="attend-radios">
                <el-radio-button v-for="o in ATTEND_OPTS" :key="o.value" :value="o.value">
                  {{ o.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <p class="attend-hint">扣课规则：出勤/迟到扣课；请假/缺勤不扣课时。</p>
        </div>
        <el-empty v-else-if="rollForm.class_id" description="该班级暂无在读学员" :image-size="64" />
      </div>

      <template #footer>
        <el-button v-if="rollStep === 'form'" @click="backToRollPick">返回课表</el-button>
        <el-button @click="rollVisible = false">取消</el-button>
        <el-button
          v-if="rollStep === 'form'"
          type="primary"
          :loading="saving"
          @click="submitRoll"
        >
          确认点名
        </el-button>
      </template>
    </AppSheet>

    <el-dialog
      v-else
      v-model="rollVisible"
      :title="rollDialogTitle"
      :width="rollStep === 'pick' ? '780px' : '640px'"
      destroy-on-close
      top="4vh"
      align-center
      class="roll-dialog"
    >
      <!-- 步骤一：周课表选课（仅上课记录 / 工作台快捷入口） -->
      <div v-if="rollStep === 'pick'" v-loading="rollOptionsLoading" class="roll-pick">
        <div class="roll-week-nav">
          <button type="button" class="roll-week-nav-btn" @click="changeRollWeek(-1)">
            <el-icon><ArrowLeft /></el-icon>
            <span>上周</span>
          </button>
          <div class="roll-week-center">
            <div class="roll-week-label">{{ rollWeekLabel }}</div>
            <button
              type="button"
              class="roll-today-link"
              :disabled="isCurrentRollWeek && selectedDayMeta?.isToday"
              @click="resetRollWeekToToday"
            >
              回到今天
            </button>
          </div>
          <button type="button" class="roll-week-nav-btn" @click="changeRollWeek(1)">
            <span>下周</span>
            <el-icon><ArrowRight /></el-icon>
          </button>
        </div>

        <div ref="dayStripRef" class="roll-day-strip">
          <button
            v-for="day in rollDayCols"
            :key="day.key"
            type="button"
            class="roll-day"
            :class="{
              'is-today': day.isToday,
              'is-future': day.isFuture,
              'is-selected': day.isSelected,
              'has-pending': day.pendingCount > 0,
            }"
            @click="selectRollDay(day)"
          >
            <span class="rd-week">{{ day.weekLabel }}</span>
            <span class="rd-num">{{ day.dayNum }}</span>
            <span class="rd-month">{{ day.monthLabel }}</span>
            <span v-if="day.lessonCount" class="rd-badge" :class="{ 'is-pending': day.pendingCount > 0 }">
              {{ day.pendingCount > 0 ? day.pendingCount : day.lessonCount }}
            </span>
            <span v-if="day.isToday" class="rd-today-tag">今</span>
            <span v-else-if="day.isFuture" class="rd-future-tag">未到</span>
          </button>
        </div>

        <div class="roll-day-panel">
          <div class="roll-day-panel-head">
            <span class="sec-dot" />
            <strong>
              {{ selectedDayMeta?.weekLabel || '' }}
              {{ selectedDayMeta ? `${selectedDayMeta.monthLabel}${selectedDayMeta.dayNum}日` : '' }}
            </strong>
            <span class="roll-day-count">
              共 {{ selectedDayLessons.length }} 节
              <template v-if="selectedDayMeta?.pendingCount">
                · 待点名 {{ selectedDayMeta.pendingCount }}
              </template>
            </span>
          </div>

          <p v-if="selectedDayMeta?.isFuture" class="roll-future-hint">
            未来课次不可点名，仅可查看；请选择当天或过去日期。
          </p>

          <div v-if="selectedDayLessons.length" class="roll-lesson-list">
            <button
              v-for="lesson in selectedDayLessons"
              :key="lesson.id"
              type="button"
              class="roll-lesson-card"
              :class="{
                'is-done': lesson.status === 'completed',
                'is-pending': isLessonRollable(lesson),
                'is-future': lesson.status === 'scheduled' && !isLessonRollable(lesson),
              }"
              :disabled="lesson.status === 'scheduled' && !isLessonRollable(lesson)"
              @click="selectLessonForRoll(lesson)"
            >
              <div class="rl-time">
                <span class="rl-clock">{{ formatClockRange(lesson.start_at, lesson.end_at) }}</span>
                <el-tag
                  size="small"
                  effect="plain"
                  :type="
                    lesson.status === 'completed'
                      ? 'success'
                      : isLessonRollable(lesson)
                        ? 'warning'
                        : 'info'
                  "
                >
                  {{
                    lesson.status === 'completed'
                      ? '已点名'
                      : isLessonRollable(lesson)
                        ? '待点名'
                        : '未到时间'
                  }}
                </el-tag>
              </div>
              <div class="rl-title">{{ lesson.class_name }}</div>
              <div class="rl-meta">
                <span>{{ lesson.course_name || '未关联课程' }}</span>
                <span v-if="lesson.teachers">{{ lesson.teachers }}</span>
                <span v-if="lesson.room">{{ lesson.room }}</span>
                <span v-if="lesson.member_count">{{ lesson.member_count }}人</span>
              </div>
              <div class="rl-action">
                <template v-if="lesson.status === 'completed'">已完成</template>
                <template v-else-if="isLessonRollable(lesson)">
                  去点名
                  <el-icon><ArrowRight /></el-icon>
                </template>
                <template v-else>不可点名</template>
              </div>
            </button>
          </div>
          <el-empty
            v-else-if="!rollOptionsLoading"
            description="当天暂无排课，请切换其他日期"
            :image-size="72"
          />
        </div>
      </div>

      <!-- 步骤二：点名表单 -->
      <div v-else class="roll-form-step">
        <div v-if="selectedRollLesson" class="roll-selected-card">
          <div class="rsc-top">
            <span class="rsc-badge">已选课次</span>
            <el-button class="rsc-reselect" link type="primary" @click="backToRollPick">重选</el-button>
          </div>
          <div class="rsc-main">
            <span class="rsc-avatar">{{ nameInitial(selectedRollLesson.class_name) }}</span>
            <div class="rsc-body">
              <div class="rsc-title">{{ selectedRollLesson.class_name || '—' }}</div>
              <div class="rsc-time">
                <el-icon><Clock /></el-icon>
                {{ formatClockRange(selectedRollLesson.start_at, selectedRollLesson.end_at) }}
              </div>
            </div>
          </div>
          <div class="rsc-chips">
            <span v-if="selectedRollLesson.course_name" class="rsc-chip">
              <el-icon><Reading /></el-icon>
              {{ selectedRollLesson.course_name }}
            </span>
            <span v-if="selectedRollLesson.teachers" class="rsc-chip">
              <el-icon><User /></el-icon>
              {{ selectedRollLesson.teachers }}
            </span>
            <span v-if="selectedRollLesson.room" class="rsc-chip">
              <el-icon><OfficeBuilding /></el-icon>
              {{ selectedRollLesson.room }}
            </span>
            <span v-if="selectedRollLesson.member_count" class="rsc-chip">
              <el-icon><UserFilled /></el-icon>
              {{ selectedRollLesson.member_count }} 人
            </span>
          </div>
        </div>

        <el-form label-position="right" label-width="90px" class="roll-form">
          <el-form-item label="授课课时">
            <el-input-number v-model="rollForm.hours" :min="0.01" :step="0.25" :precision="2" />
            <div class="form-tip">按课次扣学员课时，默认单次 1 课时（与上课墙钟时长无关；计薪课时另计）</div>
          </el-form-item>
          <el-form-item label="上课内容">
            <el-input v-model="rollForm.content" type="textarea" :rows="2" placeholder="可选，记录本节课要点" />
          </el-form-item>
        </el-form>

        <div v-if="members.length" class="attend-block">
          <div class="attend-head">
            <span class="attend-title">
              <span class="sec-dot" />
              学员名单
              <em>{{ members.length }} 人</em>
            </span>
            <div class="attend-quick">
              <el-button link type="primary" @click="markAll('present')">全勤</el-button>
              <el-button link @click="markAll('absent')">全缺</el-button>
            </div>
          </div>
          <div class="attend-list">
            <div v-for="m in members" :key="m.id" class="attend-row">
              <div class="attend-name">
                <span class="name-avatar xs">{{ nameInitial(m.name) }}</span>
                <div>
                  <span class="name">{{ m.name }}</span>
                  <span v-if="m.phone" class="phone">{{ m.phone }}</span>
                </div>
              </div>
              <el-radio-group v-model="attendMap[m.id]" size="small" class="attend-radios">
                <el-radio-button v-for="o in ATTEND_OPTS" :key="o.value" :value="o.value">
                  {{ o.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>
          <p class="attend-hint">扣课规则：出勤/迟到扣课；请假/缺勤不扣课时。</p>
        </div>
        <el-empty v-else-if="rollForm.class_id" description="该班级暂无在读学员" :image-size="64" />
      </div>

      <template #footer>
        <el-button v-if="rollStep === 'form'" class="tb-btn" @click="backToRollPick">
          返回课表
        </el-button>
        <el-button class="tb-btn" @click="rollVisible = false">取消</el-button>
        <el-button
          v-if="rollStep === 'form'"
          type="primary"
          class="tb-btn tb-btn--primary"
          :loading="saving"
          @click="submitRoll"
        >
          确认点名
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.record-page {
  width: 100%;
}

.page-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.toolbar-title-block {
  min-width: 0;
}

.page-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── App 点名入口 CTA ── */
.roll-entry-cta {
  display: none;
  width: 100%;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(161, 98, 7, 0.28);
  border-radius: 16px;
  background:
    linear-gradient(125deg, #fffefb 0%, #fff7e8 48%, #f5e6c8 120%);
  box-shadow:
    0 10px 22px rgba(88, 60, 24, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
  color: inherit;
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 0.12s ease, box-shadow 0.15s ease;
}

.roll-entry-cta:active {
  transform: scale(0.985);
}

.roll-entry-ico {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
  border-radius: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(145deg, #d97706, #a16207);
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.28);
  font-size: 18px;
}

.roll-entry-copy {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.roll-entry-copy strong {
  font-size: 15px;
  font-weight: 750;
  color: #44403c;
  line-height: 1.25;
}

.roll-entry-copy em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
  line-height: 1.3;
}

.roll-entry-go {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 720;
  color: #fffdf8;
  background: linear-gradient(145deg, #c07a12, #a16207);
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.22);
}

.module-card {
  margin-top: 12px;
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 6px 20px rgba(41, 37, 36, 0.04);
}

.module-card :deep(.el-card__body) {
  padding: 8px 16px 12px;
}

.record-tabs {
  margin-bottom: 4px;
}

.record-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.record-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  height: 42px;
  line-height: 42px;
}

.record-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.record-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--oc-primary, #a16207);
  height: 3px;
  border-radius: 2px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.filter-panel {
  background: linear-gradient(180deg, #faf6ee 0%, #f7f1e6 100%);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 14px;
}

.filter-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.filter-panel-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.filter-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.sec-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 3px rgba(161, 98, 7, 0.15);
  flex-shrink: 0;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 12px 20px;
}

.filter-item {
  display: grid;
  grid-template-columns: 68px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.filter-label {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  white-space: nowrap;
  text-align: right;
}

.filter-item :deep(.el-date-editor),
.filter-item :deep(.el-select),
.filter-item :deep(.el-input) {
  width: 100%;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
}

.table-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 0 12px;
}

.action-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.95);
  border: 1px solid var(--oc-border, #e8e0d0);
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.summary-chip b {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  margin: 0 3px;
}

.summary-bar {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  background: #faf3e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.summary-bar strong {
  font-weight: 700;
}

.table-wrap {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.data-table {
  --el-table-border-color: #f0e9dc;
  font-size: 13px;
}

.data-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #fbf7f0 !important;
}

.link-name {
  border: none;
  background: none;
  padding: 0;
  color: var(--oc-primary, #a16207);
  font-weight: 650;
  cursor: pointer;
  font-size: inherit;
  text-align: left;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}

.link-name:hover .name-text {
  text-decoration: underline;
}

.name-avatar {
  width: 28px;
  height: 28px;
  border-radius: 8px;
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

.name-avatar.sm {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  font-size: 11px;
}

.name-avatar.xs {
  width: 30px;
  height: 30px;
  border-radius: 9px;
}

.name-avatar.is-warn {
  background: linear-gradient(145deg, #fbbf24, #d97706);
}

.name-avatar.is-danger {
  background: linear-gradient(145deg, #f87171, #dc2626);
}

.name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-muted {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.cell-strong {
  color: var(--oc-ink, #44403c);
  font-weight: 600;
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
  letter-spacing: 0.01em;
}

.hours-num {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.hours-pill,
.attend-pill,
.room-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #f5f0e6;
  color: var(--oc-ink, #44403c);
  border: 1px solid #e8e0d0;
}

.hours-pill {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #9a3412;
}

.attend-pill {
  background: #f0fdf4;
  border-color: #bbf7d0;
  color: #15803d;
}

.pc-ops {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}

.op-sep {
  width: 1px;
  height: 12px;
  background: #e8e0d0;
  margin: 0 2px;
}

.record-m-card {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.record-m-card:active {
  border-color: #e6d2b3;
}

.record-m-card.is-timeout {
  cursor: default;
  border-color: #fde68a;
  background: linear-gradient(180deg, #fffdf8, #fffbeb);
}

.record-m-who {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.record-m-text {
  min-width: 0;
}

.record-m-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-m-card .m-card-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.record-m-card .m-card-head {
  margin-bottom: 0;
  align-items: flex-start;
}

.amount-text {
  flex-shrink: 0;
  font-size: 15px;
  font-weight: 750;
}

.record-m-amount {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.record-m-amount-label {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
  font-weight: 600;
}

.record-m-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.rm-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  min-height: 26px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #57534e;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(181, 145, 83, 0.2);
  line-height: 1.3;
  word-break: break-word;
}

.rm-chip .el-icon {
  font-size: 12px;
  color: #a16207;
  flex-shrink: 0;
}

.rm-chip.tone-danger {
  color: #b45309;
  background: #fff7ed;
  border-color: #fed7aa;
}

.record-m-foot {
  margin-top: 10px;
}

.record-m-roll-at {
  font-size: 12px;
  color: #a8a29e;
}

.timeout-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 750;
  color: #b45309;
  background: #fef3c7;
  border: 1px solid #fde68a;
}

.record-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 36px 20px !important;
  text-align: center;
}

.record-empty-ico {
  font-size: 28px;
  line-height: 1;
  filter: grayscale(0.2);
}

.record-empty strong {
  font-size: 15px;
  font-weight: 700;
  color: #44403c;
}

.record-empty em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
  line-height: 1.4;
  max-width: 240px;
}

.form-tip {
  width: 100%;
  margin-top: 4px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  line-height: 1.5;
}

/* ── 周课表点名选择 ── */
.roll-pick {
  min-height: 280px;
}

.roll-week-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.9), transparent 48%),
    linear-gradient(180deg, #fffefb, #faf3e6);
}

.roll-week-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: 11px;
  border: 1px solid rgba(181, 145, 83, 0.28);
  background: rgba(255, 253, 248, 0.95);
  color: #57534e;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(88, 60, 24, 0.04);
  transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.roll-week-nav-btn:hover {
  border-color: rgba(161, 98, 7, 0.4);
  color: #a16207;
  background: #fffdf8;
}

.roll-week-nav-btn .el-icon {
  font-size: 14px;
}

.roll-week-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.roll-week-label {
  font-size: 14px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  text-align: center;
  letter-spacing: 0.01em;
  line-height: 1.35;
}

.roll-today-link {
  border: none;
  background: none;
  padding: 2px 6px;
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  border-radius: 6px;
}

.roll-today-link:hover:not(:disabled) {
  background: rgba(161, 98, 7, 0.08);
}

.roll-today-link:disabled {
  color: #a8a29e;
  cursor: not-allowed;
  opacity: 0.7;
}

.roll-day-strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 2px 12px;
  margin-bottom: 4px;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}

.roll-day-strip::-webkit-scrollbar {
  display: none;
}

.roll-day {
  position: relative;
  flex: 1 0 auto;
  min-width: 72px;
  max-width: 96px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 8px 12px;
  border-radius: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fffdf8;
  cursor: pointer;
  scroll-snap-align: center;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease, transform 0.12s ease;
  color: var(--oc-ink, #44403c);
  -webkit-tap-highlight-color: transparent;
}

.roll-day:hover {
  border-color: #e6d2b3;
  background: #fffaf0;
}

.roll-day.is-today {
  border-color: #f0d9a8;
  background: linear-gradient(180deg, #fff9ef 0%, #faf3e6 100%);
}

.roll-day.is-future {
  opacity: 0.72;
}

.roll-day.is-selected {
  border-color: var(--oc-primary, #a16207);
  background: linear-gradient(180deg, #fff7e8 0%, #f5e6c8 100%);
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.18), 0 6px 16px rgba(161, 98, 7, 0.16);
  transform: translateY(-1px);
}

.roll-day.has-pending .rd-badge,
.rd-badge.is-pending {
  background: #fef3c7;
  color: #b45309;
  border-color: #fde68a;
}

.rd-week {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  font-weight: 600;
}

.rd-num {
  font-size: 22px;
  font-weight: 780;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
}

.rd-month {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
}

.rd-badge {
  margin-top: 4px;
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f5f0e6;
  border: 1px solid #e8e0d0;
  color: var(--oc-ink, #44403c);
}

.rd-today-tag,
.rd-future-tag {
  position: absolute;
  top: 6px;
  right: 6px;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: var(--oc-primary, #a16207);
  border-radius: 999px;
  padding: 1px 5px;
  line-height: 1.3;
}

.rd-future-tag {
  background: #a8a29e;
}

.roll-future-hint {
  margin: 0 0 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #f8f7f5, #f3f1ee);
  border: 1px solid #e7e5e4;
  color: #78716c;
  font-size: 12px;
  line-height: 1.5;
}

.roll-day-panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 16px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
  padding: 14px;
  min-height: 180px;
  box-shadow: 0 4px 14px rgba(88, 60, 24, 0.04);
}

.roll-day-panel-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--oc-ink, #44403c);
}

.roll-day-count {
  margin-left: auto;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.roll-lesson-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: min(42vh, 420px);
  overflow: auto;
}

.roll-lesson-card {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto auto;
  gap: 4px 12px;
  width: 100%;
  text-align: left;
  padding: 14px 14px 14px 16px;
  border-radius: 14px;
  border: 1px solid #e8e0d0;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.95), transparent 50%),
    #fffdf8;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.12s ease;
  color: inherit;
  box-shadow: 0 2px 8px rgba(88, 60, 24, 0.04);
  -webkit-tap-highlight-color: transparent;
}

.roll-lesson-card:hover {
  border-color: #e6d2b3;
  box-shadow: 0 6px 16px rgba(41, 37, 36, 0.08);
}

.roll-lesson-card.is-pending {
  border-left: 3px solid #d97706;
  background:
    linear-gradient(155deg, #fffdf8, transparent 46%),
    linear-gradient(180deg, #fffbeb, #fffdf8);
}

.roll-lesson-card.is-pending:hover {
  border-color: rgba(217, 119, 6, 0.45);
  box-shadow: 0 8px 18px rgba(180, 83, 9, 0.12);
}

.roll-lesson-card.is-future {
  opacity: 0.65;
  cursor: not-allowed;
  border-left: 3px solid #d6d3d1;
}

.roll-lesson-card:disabled {
  cursor: not-allowed;
}

.roll-lesson-card.is-done {
  border-left: 3px solid #16a34a;
  opacity: 0.78;
}

.rl-time {
  grid-column: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.rl-clock {
  font-size: 15px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--oc-primary, #a16207);
}

.rl-title {
  grid-column: 1;
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.rl-meta {
  grid-column: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.rl-action {
  grid-column: 2;
  grid-row: 1 / span 3;
  align-self: center;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: var(--oc-primary, #a16207);
  background: rgba(161, 98, 7, 0.08);
  border: 1px solid rgba(161, 98, 7, 0.14);
  white-space: nowrap;
}

.rl-action .el-icon {
  font-size: 12px;
}

.roll-lesson-card.is-done .rl-action {
  color: #16a34a;
  background: rgba(22, 163, 74, 0.08);
  border-color: rgba(22, 163, 74, 0.16);
}

.roll-lesson-card.is-future .rl-action {
  color: #a8a29e;
  background: #f5f5f4;
  border-color: #e7e5e4;
}

.roll-form-step {
  display: grid;
  gap: 4px;
}

.roll-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.roll-selected-card {
  position: relative;
  margin-bottom: 16px;
  padding: 14px 14px 12px;
  border-radius: 14px;
  border: 1px solid #e8dcc8;
  background:
    linear-gradient(135deg, rgba(161, 98, 7, 0.06) 0%, transparent 42%),
    linear-gradient(180deg, #fffdf8 0%, #faf3e6 100%);
  box-shadow: 0 4px 14px rgba(120, 80, 20, 0.06);
  overflow: hidden;
}

.roll-selected-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, #d97706 0%, #a16207 100%);
  border-radius: 4px 0 0 4px;
}

.rsc-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.rsc-badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 650;
  color: #a16207;
  background: rgba(161, 98, 7, 0.12);
  border: 1px solid rgba(161, 98, 7, 0.16);
}

.rsc-reselect {
  font-weight: 650;
  padding: 0 2px;
}

.rsc-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.rsc-avatar {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 750;
  color: #fff;
  background: linear-gradient(145deg, #d97706 0%, #a16207 100%);
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.28);
}

.rsc-body {
  min-width: 0;
  flex: 1;
}

.rsc-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
  word-break: break-word;
}

.rsc-time {
  margin-top: 4px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  color: var(--oc-primary, #a16207);
}

.rsc-time .el-icon {
  font-size: 14px;
}

.rsc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e8e0d0;
}

.rsc-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.35;
  color: #57534e;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #ebe3d4;
  box-shadow: 0 1px 2px rgba(41, 37, 36, 0.03);
  word-break: break-word;
}

.rsc-chip .el-icon {
  flex-shrink: 0;
  font-size: 13px;
  color: #a16207;
}

.attend-block {
  margin-top: 4px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 12px 14px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
}

.attend-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.attend-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
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

.attend-quick {
  display: flex;
  gap: 4px;
}

.attend-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-height: 300px;
  overflow: auto;
}

.attend-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 0;
  border-bottom: 1px dashed #e8e0d0;
}

.attend-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
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
.attend-hint {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.attend-hint {
  margin: 12px 0 0;
  line-height: 1.5;
  padding-top: 10px;
  border-top: 1px solid #f0e9dc;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(200px, 1fr));
  }
}

@media (max-width: 1199px) {
  .page-toolbar,
  .table-actions,
  .filter-actions {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
  }

  .toolbar-right .el-button,
  .action-left .el-button,
  .filter-actions .el-button {
    width: auto;
  }

  .action-left {
    width: auto;
    flex-wrap: wrap;
  }

  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }

  .filter-item {
    grid-template-columns: 1fr;
    gap: 4px;
  }

  .filter-label {
    text-align: left;
  }

  .summary-bar {
    width: 100%;
    justify-content: center;
  }

  .roll-week-nav {
    flex-wrap: wrap;
  }

  .roll-week-nav-btn {
    flex: 1;
    justify-content: center;
  }

  .roll-week-center {
    order: -1;
    width: 100%;
  }

  .roll-day {
    min-width: 68px;
  }

  .roll-lesson-card {
    grid-template-columns: 1fr;
  }

  .rl-action {
    grid-column: 1;
    grid-row: auto;
    justify-self: start;
    margin-top: 6px;
  }
}

/* ── WAP / Pad 上课记录全面 App 化 ── */
@media (max-width: 1199px) {
  .record-page {
    display: grid;
    gap: 10px;
  }

  .page-toolbar {
    margin: 0;
  }

  .page-toolbar.is-app-roll {
    padding: 0;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .page-sub {
    display: none;
  }

  .roll-entry-cta {
    display: flex;
  }

  .toolbar-right .tb-btn--primary {
    min-height: 42px;
    border-radius: 12px;
    font-weight: 720;
  }

  .module-card {
    margin-top: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .module-card :deep(.el-card__body) {
    padding: 0;
  }

  .record-tabs {
    margin: 0 0 10px;
    padding: 4px;
    border-radius: 14px;
    border: 1px solid rgba(181, 145, 83, 0.2);
    background: #f3ebe0;
  }

  .record-tabs :deep(.el-tabs__header) {
    margin: 0;
  }

  .record-tabs :deep(.el-tabs__nav-wrap::after) {
    display: none;
  }

  .record-tabs :deep(.el-tabs__active-bar) {
    display: none;
  }

  .record-tabs :deep(.el-tabs__item) {
    height: 40px;
    line-height: 40px;
    padding: 0 12px !important;
    border-radius: 11px;
    color: #78716c;
    font-weight: 650;
  }

  .record-tabs :deep(.el-tabs__item.is-active) {
    color: #fffdf8 !important;
    background: linear-gradient(145deg, #c07a12, #a16207);
    box-shadow: 0 4px 12px rgba(161, 98, 7, 0.25);
  }

  .record-tabs :deep(.el-tabs__item .el-icon) {
    margin-right: 4px;
  }

  .table-actions,
  .table-actions.is-app-actions {
    margin: 0 0 10px;
    padding: 12px;
    border-radius: 16px;
    border: 1px solid rgba(181, 145, 83, 0.22);
    background:
      linear-gradient(135deg, rgba(255, 255, 255, 0.9), transparent 50%),
      linear-gradient(180deg, #fffefb, #faf3e6);
    box-shadow: 0 6px 16px rgba(88, 60, 24, 0.05);
    display: grid;
    gap: 10px;
  }

  .table-actions .action-left {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .table-actions .tb-btn {
    min-height: 40px;
    border-radius: 12px;
    font-weight: 650;
  }

  .table-actions .summary-bar {
    width: 100%;
    justify-content: center;
    margin: 0;
    border-radius: 12px;
    background: rgba(255, 253, 248, 0.9);
  }

  .summary-chip {
    height: 32px;
    border-radius: 12px;
    background: linear-gradient(180deg, #fffefb, #faf3e6);
    font-weight: 600;
  }

  .m-card-list {
    gap: 12px;
  }

  .record-m-card {
    padding: 14px 14px 12px 16px;
    border-radius: 18px !important;
    border: 1px solid rgba(181, 145, 83, 0.3) !important;
    background:
      linear-gradient(155deg, rgba(255, 255, 255, 0.92), transparent 46%),
      #fffdf8 !important;
    box-shadow:
      0 12px 28px rgba(88, 60, 24, 0.09),
      0 2px 0 rgba(255, 255, 255, 0.9) inset !important;
  }

  .record-m-card.is-void {
    opacity: 0.82;
    border-color: rgba(168, 162, 158, 0.4) !important;
    background:
      linear-gradient(155deg, rgba(250, 250, 249, 0.95), transparent 50%),
      #fafaf9 !important;
  }

  .record-m-card.is-timeout {
    border-color: rgba(180, 83, 9, 0.38) !important;
    background:
      linear-gradient(155deg, rgba(255, 247, 237, 0.98), transparent 50%),
      #fffdf8 !important;
  }

  .record-m-card.is-makeup {
    border-color: rgba(220, 38, 38, 0.22) !important;
    background:
      linear-gradient(155deg, rgba(254, 242, 242, 0.9), transparent 48%),
      #fffdf8 !important;
  }

  .record-m-card .m-card-actions {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(181, 145, 83, 0.14);
  }

  .record-m-card .m-card-actions .el-button {
    width: 100%;
    margin: 0;
    min-height: 42px;
    border-radius: 12px;
    font-weight: 700;
  }

  .record-m-card .m-card-actions .el-button:only-child {
    grid-column: 1 / -1;
  }

  .record-m-card .m-card-actions .el-button--primary.is-plain {
    background: linear-gradient(180deg, #fffefb, #faf3e6);
    border-color: rgba(161, 98, 7, 0.28);
    color: #a16207;
  }

  .name-avatar {
    width: 42px;
    height: 42px;
    border-radius: 13px;
    font-size: 16px;
    background: linear-gradient(145deg, #f5e6c8, #c9a066);
    box-shadow: 0 4px 10px rgba(161, 98, 7, 0.16);
  }

  .record-tabs {
    box-shadow: 0 4px 12px rgba(88, 60, 24, 0.05);
  }

  .record-tabs :deep(.el-tabs__nav) {
    width: 100%;
    display: flex;
  }

  .record-tabs :deep(.el-tabs__item) {
    flex: 1;
    justify-content: center;
    text-align: center;
    padding: 0 8px !important;
  }

  .record-tabs :deep(.tab-label) {
    justify-content: center;
  }

  /* 点名 Sheet 内容 */
  .roll-pick,
  .roll-form-step {
    display: grid;
    gap: 12px;
  }

  .roll-week-nav {
    gap: 8px;
    padding: 10px;
  }

  .roll-week-nav-btn {
    flex: 0 0 auto;
    min-width: 68px;
    justify-content: center;
    padding: 0 10px;
  }

  .roll-day-strip {
    gap: 8px;
    padding: 4px 2px 8px;
  }

  .roll-day {
    min-width: 64px;
    padding: 10px 8px;
  }

  .roll-day-panel {
    padding: 12px;
  }

  .roll-lesson-card {
    padding: 12px 12px 12px 14px;
  }

  .rl-action {
    margin-top: 0;
  }

  .attend-block {
    padding: 12px;
    border-radius: 16px;
    border: 1px solid rgba(181, 145, 83, 0.2);
    background: linear-gradient(180deg, #fffefb, #faf6ee);
  }

  .attend-row {
    padding: 10px 8px;
    border-radius: 12px;
    border-bottom: 1px solid rgba(181, 145, 83, 0.12);
  }

  .attend-row:last-child {
    border-bottom: 0;
  }

  .attend-row :deep(.el-radio-group) {
    flex-wrap: wrap;
    justify-content: flex-end;
  }
}
</style>

<!-- AppSheet 点名面板：挂 body，需非 scoped -->
<style>
.el-drawer.oc-app-sheet.roll-app-sheet .el-drawer__header {
  margin-bottom: 4px !important;
  padding: 16px 16px 8px !important;
}

.el-drawer.oc-app-sheet.roll-app-sheet .el-drawer__title {
  font-weight: 750 !important;
  color: #44403c !important;
  letter-spacing: 0.01em;
}

.el-drawer.oc-app-sheet.roll-app-sheet .el-drawer__body {
  padding: 8px 14px 8px !important;
  background:
    linear-gradient(180deg, rgba(250, 246, 238, 0.55), transparent 48px),
    #fffdf8;
}

.el-drawer.oc-app-sheet.roll-app-sheet .el-drawer__footer {
  display: flex !important;
  gap: 10px !important;
  padding: 10px 14px calc(12px + env(safe-area-inset-bottom, 0px)) !important;
  border-top: 1px solid rgba(181, 145, 83, 0.18) !important;
  background: linear-gradient(180deg, #fffefb, #faf3e6) !important;
}

.el-drawer.oc-app-sheet.roll-app-sheet .el-drawer__footer .el-button {
  min-height: 46px !important;
  border-radius: 13px !important;
  font-weight: 720 !important;
  margin: 0 !important;
}

.el-drawer.oc-app-sheet.roll-app-sheet .el-drawer__footer .el-button--primary {
  flex: 1.35 1 auto;
  background: linear-gradient(145deg, #c07a12, #a16207) !important;
  border-color: transparent !important;
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.24);
}

.el-dialog.roll-dialog {
  border-radius: 16px !important;
  overflow: hidden;
  border: 1px solid rgba(181, 145, 83, 0.22);
  box-shadow: 0 18px 48px rgba(88, 60, 24, 0.14);
}

.el-dialog.roll-dialog .el-dialog__header {
  padding: 16px 20px 10px;
  margin-right: 0;
  border-bottom: 1px solid rgba(181, 145, 83, 0.14);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
}

.el-dialog.roll-dialog .el-dialog__title {
  font-weight: 750;
  color: #44403c;
}

.el-dialog.roll-dialog .el-dialog__body {
  padding: 16px 20px 8px;
  background: #fffdf8;
}

.el-dialog.roll-dialog .el-dialog__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(181, 145, 83, 0.14);
  background: linear-gradient(180deg, #fffefb, #faf3e6);
}
</style>

