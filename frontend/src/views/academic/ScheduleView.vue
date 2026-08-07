<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  checkScheduleConflictsApi,
  createScheduleApi,
  createSchedulesBatchApi,
  deleteScheduleApi,
  listAcademicTeachersApi,
  listClassesApi,
  listCoursesApi,
  listRoomsApi,
  listSchedulesApi,
  scheduleAvailabilityApi,
  updateScheduleApi,
  type ClassRoom,
  type Course,
  type ScheduleLesson,
  type ScheduleLessonDetail,
  type ScheduleRoomOption,
  type TeacherAvailability,
  type TeacherManage,
} from '../../api/academic'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import AppSheet from '../../components/AppSheet.vue'
import ScheduleLessonPop from './ScheduleLessonPop.vue'
import ScheduleLessonDetailDrawer from './ScheduleLessonDetailDrawer.vue'

type ViewTab = 'time' | 'teacher' | 'room' | 'class'
type PeriodMode = 'day' | 'week' | 'month'
type MatrixMode = 'teacher' | 'room' | 'class'

interface DayCol {
  index: number
  label: string
  short: string
  dateKey: string
  date: Date
  isToday: boolean
  isOtherMonth?: boolean
}

const auth = useAuthStore()
const router = useRouter()
const { isCompact } = useBreakpoint()
/** 排课写操作需 academic.write；老师默认仅查看自己的课表 */
const canManage = computed(() => auth.hasPermission('academic.write'))
/** 老师账号：强制只看本人所带课次 */
const selfTeacherOnly = computed(() => auth.isTeacher)
const selfTeacherId = computed(() => (auth.isTeacher ? auth.user?.id : undefined))
/** PC 悬停气泡；wap/pad 无悬停，点击课次直接打开详情侧栏 */
const useLessonPopover = computed(() => !isCompact.value)
const viewTab = ref<ViewTab>('time')
const periodMode = ref<PeriodMode>('week')
const loading = ref(false)
const lessons = ref<ScheduleLesson[]>([])
const courses = ref<Course[]>([])
const classes = ref<ClassRoom[]>([])
const teachers = ref<TeacherManage[]>([])
const rooms = ref<{ name: string }[]>([])

const courseFilter = ref<number | undefined>()
const classFilter = ref<number | undefined>()
const teacherFilter = ref<number | undefined>()

/** 当前定位日（日/周/月导航基准） */
const anchorDate = ref(startOfDay(new Date()))

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const saving = ref(false)
const availLoading = ref(false)
const teacherAvail = ref<TeacherAvailability[]>([])
const roomAvail = ref<ScheduleRoomOption[]>([])

/** 点击课次时间 → 快捷改时间 */
const timeEditVisible = ref(false)
const timeEditSaving = ref(false)
const timeEditId = ref<number | null>(null)
const timeEditTitle = ref('')
const timeEditForm = reactive({
  date: '' as string,
  start_time: '09:00',
  end_time: '10:30',
})

/** 课次详情侧栏（查看详情，不跳转） */
const detailVisible = ref(false)
const detailLessonId = ref<number | null>(null)

const HOUR_START = 7
const HOUR_END = 21
const HOUR_PX = 56

const hours = computed(() =>
  Array.from({ length: HOUR_END - HOUR_START + 1 }, (_, i) => `${HOUR_START + i}:00`),
)

const COMMON_SLOTS = [
  { label: '08:00-09:50', start: '08:00', end: '09:50' },
  { label: '10:00-11:50', start: '10:00', end: '11:50' },
  { label: '13:00-14:50', start: '13:00', end: '14:50' },
  { label: '15:00-16:50', start: '15:00', end: '16:50' },
  { label: '18:00-19:50', start: '18:00', end: '19:50' },
  { label: '19:00-21:00', start: '19:00', end: '21:00' },
]

const form = reactive({
  course_id: undefined as number | undefined,
  class_id: undefined as number | undefined,
  schedule_mode: 'rule' as 'rule' | 'calendar',
  start_date: '' as string,
  start_time: '09:00',
  end_time: '10:30',
  repeat_mode: 'weekly' as 'daily' | 'alternate' | 'weekly' | 'biweekly',
  weekdays: [] as number[],
  end_mode: 'by_date' as 'by_date' | 'by_count',
  end_date: '' as string,
  session_count: 8 as number,
  room: '' as string,
  teacher_ids: [] as number[],
  remark: '',
  on_conflict: 'skip' as 'skip' | 'fail' | 'force',
  ignore_conflicts: false,
})

const formTitle = computed(() => (formMode.value === 'edit' ? '改期 / 编辑排课' : '新建排课'))

const WEEK_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/** 1=周一 … 7=周日，与后端 weekdays 约定一致 */
const WEEKDAY_OPTIONS = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' },
]

function isoWeekdayFromDateKey(key: string): number | null {
  if (!key) return null
  const d = new Date(`${key}T00:00:00`)
  if (Number.isNaN(d.getTime())) return null
  const day = d.getDay()
  return day === 0 ? 7 : day
}

function seedWeekdaysFromStartDate() {
  const wd = isoWeekdayFromDateKey(form.start_date)
  form.weekdays = wd ? [wd] : []
}

const needsWeekdayPick = computed(
  () => form.repeat_mode === 'weekly' || form.repeat_mode === 'biweekly',
)

function startOfDay(d: Date) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

function startOfWeek(d: Date) {
  const x = startOfDay(d)
  const day = x.getDay()
  const diff = day === 0 ? -6 : 1 - day
  x.setDate(x.getDate() + diff)
  return x
}

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

function endOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0)
}

function dateKey(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function toIsoLocal(d: Date) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`
}

function padTime(d: Date) {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function isSameDay(a: Date, b: Date) {
  return dateKey(a) === dateKey(b)
}

function weekdayLabel(d: Date) {
  const day = d.getDay()
  return WEEK_NAMES[day === 0 ? 6 : day - 1]
}

/** 当前查询区间 [start, end) */
const rangeBounds = computed(() => {
  const a = anchorDate.value
  if (periodMode.value === 'day') {
    const start = startOfDay(a)
    const end = new Date(start)
    end.setDate(end.getDate() + 1)
    return { start, end }
  }
  if (periodMode.value === 'week') {
    const start = startOfWeek(a)
    const end = new Date(start)
    end.setDate(end.getDate() + 7)
    return { start, end }
  }
  const start = startOfMonth(a)
  const end = new Date(a.getFullYear(), a.getMonth() + 1, 1)
  return { start, end }
})

/** 日/周：列头；月：自然日列（矩阵用） */
const dayLabels = computed<DayCol[]>(() => {
  const today = startOfDay(new Date())
  const { start, end } = rangeBounds.value
  const out: DayCol[] = []
  const cur = new Date(start)
  let i = 0
  while (cur < end) {
    const d = new Date(cur)
    const week = weekdayLabel(d)
    out.push({
      index: i,
      label:
        periodMode.value === 'day'
          ? `${week} ${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
          : periodMode.value === 'month'
            ? `${d.getMonth() + 1}/${d.getDate()}`
            : `${week} ${d.getMonth() + 1}月${d.getDate()}日`,
      short: periodMode.value === 'month' ? `${d.getDate()}` : week,
      dateKey: dateKey(d),
      date: d,
      isToday: isSameDay(d, today),
    })
    cur.setDate(cur.getDate() + 1)
    i += 1
  }
  return out
})

/** 月视图时间课表：含上月末/下月初补齐的日历格 */
const monthCalendarCells = computed(() => {
  if (periodMode.value !== 'month') return [] as DayCol[]
  const a = anchorDate.value
  const first = startOfMonth(a)
  const last = endOfMonth(a)
  const gridStart = startOfWeek(first)
  const today = startOfDay(new Date())
  // 补齐到完整 6 周或到月末所在周的周日
  let gridEnd = startOfWeek(last)
  gridEnd.setDate(gridEnd.getDate() + 7)
  const out: DayCol[] = []
  const cur = new Date(gridStart)
  let i = 0
  while (cur < gridEnd) {
    const d = new Date(cur)
    out.push({
      index: i,
      label: `${d.getDate()}`,
      short: weekdayLabel(d),
      dateKey: dateKey(d),
      date: d,
      isToday: isSameDay(d, today),
      isOtherMonth: d.getMonth() !== a.getMonth(),
    })
    cur.setDate(cur.getDate() + 1)
    i += 1
  }
  return out
})

const periodLabel = computed(() => {
  const a = anchorDate.value
  const pad = (n: number) => String(n).padStart(2, '0')
  if (periodMode.value === 'day') {
    return `${a.getFullYear()}年${pad(a.getMonth() + 1)}月${pad(a.getDate())}日 ${weekdayLabel(a)}`
  }
  if (periodMode.value === 'week') {
    const s = startOfWeek(a)
    const e = new Date(s)
    e.setDate(s.getDate() + 6)
    return `${s.getFullYear()}年${pad(s.getMonth() + 1)}月${pad(s.getDate())}日~${pad(e.getMonth() + 1)}月${pad(e.getDate())}日`
  }
  return `${a.getFullYear()}年${pad(a.getMonth() + 1)}月`
})

const jumpLabel = computed(() => {
  if (periodMode.value === 'day') return '今日'
  if (periodMode.value === 'week') return '本周'
  return '本月'
})

const periodPickerType = computed<'date' | 'week' | 'month'>(() => {
  if (periodMode.value === 'week') return 'week'
  if (periodMode.value === 'month') return 'month'
  return 'date'
})

const periodPickerFormat = computed(() => {
  if (periodMode.value === 'month') return 'YYYY年MM月'
  return 'YYYY年MM月DD日'
})

/** 日期选择器选中后统一归一化到当前的日/周/月周期。 */
const periodPickerDate = computed<Date | null>({
  get: () => anchorDate.value,
  set: (value) => {
    if (!value) return
    const picked = value instanceof Date ? value : new Date(value)
    if (Number.isNaN(picked.getTime())) return
    const next =
      periodMode.value === 'week'
        ? startOfWeek(picked)
        : periodMode.value === 'month'
          ? startOfMonth(picked)
          : startOfDay(picked)
    if (dateKey(next) === dateKey(anchorDate.value)) return
    anchorDate.value = next
    void load()
  },
})

const formClassOptions = computed(() => {
  if (!form.course_id) return classes.value
  return classes.value.filter((c) => c.course_id === form.course_id)
})

const filterClassOptions = computed(() => {
  if (!courseFilter.value) return classes.value
  return classes.value.filter((c) => c.course_id === courseFilter.value)
})

const formHint = computed(() => {
  if (formMode.value === 'edit') return ''
  if (form.schedule_mode === 'calendar') {
    return form.start_date
      ? `将于 ${form.start_date} ${form.start_time}~${form.end_time} 生成 1 节课`
      : '请选择上课日期与时间'
  }
  const modeMap: Record<string, string> = {
    daily: '每天',
    alternate: '隔天',
    weekly: '每周',
    biweekly: '隔周',
  }
  const rep = modeMap[form.repeat_mode] || '每周'
  const dayLabels =
    needsWeekdayPick.value && form.weekdays.length
      ? form.weekdays
          .slice()
          .sort((a, b) => a - b)
          .map((v) => WEEKDAY_OPTIONS.find((o) => o.value === v)?.label || '')
          .filter(Boolean)
          .join('、')
      : ''
  const dayPart = dayLabels ? `（${dayLabels}）` : needsWeekdayPick.value ? '（请选择上课日）' : ''
  if (form.end_mode === 'by_count') {
    return `课次将从 ${form.start_date || '…'} 起${rep}${dayPart}同时间段排课，共 ${form.session_count} 节`
  }
  return `课次将从 ${form.start_date || '…'} 至 ${form.end_date || '…'}，${rep}${dayPart}同时间段排课`
})

const trackHeight = computed(() => (HOUR_END - HOUR_START + 1) * HOUR_PX)

interface TimeBlockLayout {
  lane: number
  laneCount: number
}

function lessonTimeValue(lesson: ScheduleLesson, field: 'start_at' | 'end_at') {
  return new Date(lesson[field]).getTime()
}

function sortedLessons(items: ScheduleLesson[]) {
  return [...items].sort(
    (a, b) =>
      lessonTimeValue(a, 'start_at') - lessonTimeValue(b, 'start_at') ||
      lessonTimeValue(a, 'end_at') - lessonTimeValue(b, 'end_at') ||
      a.id - b.id,
  )
}

/** 同一天内有时间交集的课次分配到不同横向栏位。 */
const timeBlockLayouts = computed(() => {
  const layouts = new Map<number, TimeBlockLayout>()

  for (const day of dayLabels.value) {
    const dayLessons = sortedLessons(
      lessons.value.filter((lesson) => dateKey(new Date(lesson.start_at)) === day.dateKey),
    )
    let group: ScheduleLesson[] = []
    let groupEnd = Number.NEGATIVE_INFINITY

    const layoutGroup = () => {
      if (!group.length) return
      const active: { end: number; lane: number }[] = []
      const assigned = new Map<number, number>()
      let laneCount = 1

      for (const lesson of group) {
        const start = lessonTimeValue(lesson, 'start_at')
        for (let i = active.length - 1; i >= 0; i -= 1) {
          if (active[i]!.end <= start) active.splice(i, 1)
        }
        const used = new Set(active.map((item) => item.lane))
        let lane = 0
        while (used.has(lane)) lane += 1
        assigned.set(lesson.id, lane)
        active.push({ end: lessonTimeValue(lesson, 'end_at'), lane })
        laneCount = Math.max(laneCount, lane + 1)
      }

      for (const lesson of group) {
        layouts.set(lesson.id, { lane: assigned.get(lesson.id) || 0, laneCount })
      }
    }

    for (const lesson of dayLessons) {
      const start = lessonTimeValue(lesson, 'start_at')
      if (group.length && start >= groupEnd) {
        layoutGroup()
        group = []
        groupEnd = Number.NEGATIVE_INFINITY
      }
      group.push(lesson)
      groupEnd = Math.max(groupEnd, lessonTimeValue(lesson, 'end_at'))
    }
    layoutGroup()
  }

  return layouts
})

const maxTimeLaneCount = computed(() => {
  let max = 1
  for (const layout of timeBlockLayouts.value.values()) max = Math.max(max, layout.laneCount)
  return max
})

const calGridStyle = computed(() => {
  const n = Math.max(1, dayLabels.value.length)
  const baseDayWidth = periodMode.value === 'day' ? 220 : 130
  const dayWidth = Math.max(baseDayWidth, maxTimeLaneCount.value * 110)
  return {
    gridTemplateColumns: `56px repeat(${n}, minmax(${dayWidth}px, 1fr))`,
    minWidth: `${56 + n * dayWidth}px`,
  }
})

const matrixGridStyle = computed(() => {
  const n = Math.max(1, dayLabels.value.length)
  const colMin = periodMode.value === 'month' ? 72 : periodMode.value === 'day' ? 180 : 120
  return {
    gridTemplateColumns: `140px repeat(${n}, minmax(${colMin}px, 1fr))`,
  }
})

function timeRange(l: ScheduleLesson) {
  const s = new Date(l.start_at)
  const e = new Date(l.end_at)
  return `${padTime(s)}-${padTime(e)}`
}

function softColor(hex: string) {
  if (!hex.startsWith('#') || hex.length < 7) return '#f5f0e6'
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, 0.14)`
}

function blockStyle(lesson: ScheduleLesson) {
  const start = new Date(lesson.start_at)
  const end = new Date(lesson.end_at)
  const topBase = HOUR_START * 60
  const s = start.getHours() * 60 + start.getMinutes()
  const e = end.getHours() * 60 + end.getMinutes()
  const top = ((s - topBase) / 60) * HOUR_PX
  const height = Math.max(36, ((e - s) / 60) * HOUR_PX - 4)
  const color = lesson.course_color || '#a16207'
  const { lane, laneCount } = timeBlockLayouts.value.get(lesson.id) || { lane: 0, laneCount: 1 }
  const gap = 3
  const widthOffset = (8 + (laneCount - 1) * gap) / laneCount
  const leftOffset = 4 + (lane * (gap - 8)) / laneCount
  return {
    top: `${Math.max(0, top)}px`,
    height: `${height}px`,
    left: `calc(${(lane * 100) / laneCount}% + ${leftOffset}px)`,
    right: 'auto',
    width: `calc(${100 / laneCount}% - ${widthOffset}px)`,
    borderLeft: `3px solid ${color}`,
    background: softColor(color),
  }
}

function lessonsOnDate(key: string) {
  return sortedLessons(lessons.value.filter((l) => dateKey(new Date(l.start_at)) === key))
}

function lessonsForDay(day: number) {
  const col = dayLabels.value[day]
  if (!col) return []
  return lessonsOnDate(col.dateKey)
}

/** 该小时格是否已被课次占用（用于隐藏「新建排课」悬浮） */
function hourOccupied(day: number, hourLabel: string): boolean {
  const hour = Number(String(hourLabel).split(':')[0])
  if (Number.isNaN(hour)) return false
  const slotStart = hour * 60
  const slotEnd = slotStart + 60
  return lessonsForDay(day).some((l) => {
    const s = new Date(l.start_at)
    const e = new Date(l.end_at)
    const a = s.getHours() * 60 + s.getMinutes()
    const b = e.getHours() * 60 + e.getMinutes()
    return a < slotEnd && b > slotStart
  })
}

function emptyHourHint(day: number, hourLabel: string): string {
  // wap/pad 无悬停，不展示「新建排课」蒙层（点空白格仍可新建）
  if (isCompact.value || !canManage.value) return ''
  if (hourOccupied(day, hourLabel)) return ''
  return '新建排课'
}

function lessonsForEntityDay(entityKey: string, day: number, mode: MatrixMode): ScheduleLesson[] {
  return sortedLessons(lessonsForDay(day).filter((l) => matchEntity(l, entityKey, mode)))
}

function matrixCellEmpty(rowKey: string, day: number): boolean {
  return lessonsForEntityDay(rowKey, day, matrixMode.value).length === 0
}

function matrixEmptyHint(row: { label: string }, rowKey: string, day: number): string {
  if (isCompact.value || !canManage.value) return ''
  if (!matrixCellEmpty(rowKey, day)) return ''
  return newHintForRow(row)
}

function matchEntity(l: ScheduleLesson, entityKey: string, mode: MatrixMode) {
  if (mode === 'teacher') {
    if (l.teacher_ids?.length) {
      return l.teacher_ids.map(String).includes(entityKey) || l.teachers === entityKey
    }
    return (l.teachers || '待分配') === entityKey
  }
  if (mode === 'room') return (l.room || '教室待定') === entityKey
  return String(l.class_id) === entityKey || l.class_name === entityKey
}

const dayCounts = computed(() => dayLabels.value.map((_, i) => lessonsForDay(i).length))

const matrixMode = computed<MatrixMode>(() => {
  if (viewTab.value === 'teacher') return 'teacher'
  if (viewTab.value === 'room') return 'room'
  return 'class'
})

const matrixRows = computed(() => {
  if (viewTab.value === 'teacher') {
    const map = new Map<string, { key: string; label: string; sub?: string }>()
    for (const t of teachers.value) {
      if (teacherFilter.value && t.id !== teacherFilter.value) continue
      map.set(String(t.id), { key: String(t.id), label: t.name, sub: '查看空闲时间' })
    }
    for (const l of lessons.value) {
      if (l.teacher_ids?.length) {
        for (const id of l.teacher_ids) {
          if (teacherFilter.value && id !== teacherFilter.value) continue
          if (!map.has(String(id))) {
            map.set(String(id), {
              key: String(id),
              label: l.teachers || `老师#${id}`,
              sub: '查看空闲时间',
            })
          }
        }
      } else if (l.teachers) {
        if (!map.has(l.teachers)) {
          map.set(l.teachers, { key: l.teachers, label: l.teachers, sub: '查看空闲时间' })
        }
      }
    }
    if (!map.size) map.set('待分配', { key: '待分配', label: '待分配', sub: '查看空闲时间' })
    return Array.from(map.values())
  }
  if (viewTab.value === 'room') {
    const map = new Map<string, { key: string; label: string; sub?: string }>()
    for (const r of rooms.value) {
      map.set(r.name, { key: r.name, label: r.name, sub: '查看空闲时间' })
    }
    for (const l of lessons.value) {
      const name = l.room || '教室待定'
      if (!map.has(name)) map.set(name, { key: name, label: name, sub: '查看空闲时间' })
    }
    if (!map.size) map.set('教室待定', { key: '教室待定', label: '教室待定', sub: '查看空闲时间' })
    return Array.from(map.values())
  }
  const map = new Map<string, { key: string; label: string; sub?: string }>()
  for (const c of classes.value) {
    if (courseFilter.value && c.course_id !== courseFilter.value) continue
    if (classFilter.value && c.id !== classFilter.value) continue
    map.set(String(c.id), { key: String(c.id), label: c.name, sub: '查看空闲时间' })
  }
  for (const l of lessons.value) {
    const k = String(l.class_id)
    if (!map.has(k)) {
      map.set(k, { key: k, label: l.class_name || `班级#${l.class_id}`, sub: '查看空闲时间' })
    }
  }
  return Array.from(map.values())
})

function newHintForRow(row: { label: string }) {
  if (viewTab.value === 'teacher') return `新建${row.label}排课`
  if (viewTab.value === 'room') return `新建${row.label}排课`
  if (viewTab.value === 'class') return `新建${row.label}排课`
  return '新建排课'
}

async function load() {
  loading.value = true
  try {
    const { start, end } = rangeBounds.value
    // 老师端后端也会强制按本人过滤；前端同步锁定，避免筛选框误导
    const teacherId = selfTeacherOnly.value
      ? selfTeacherId.value
      : teacherFilter.value
    const res = await listSchedulesApi({
      start: toIsoLocal(start),
      end: toIsoLocal(end),
      class_id: classFilter.value,
      course_id: courseFilter.value,
      teacher_id: teacherId,
      page: 1,
      page_size: 500,
    })
    lessons.value = res.items
  } catch {
    lessons.value = []
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  const [c, cl, t, r] = await Promise.all([
    listCoursesApi({ enabled: true, page_size: 100 }).catch(() => ({ items: [] as Course[] })),
    listClassesApi({ page_size: 100 }).catch(() => ({ items: [] as ClassRoom[] })),
    listAcademicTeachersApi({ page_size: 100 }).catch(() => ({ items: [] as TeacherManage[] })),
    listRoomsApi().catch(() => [] as { name: string }[]),
  ])
  courses.value = c.items
  classes.value = cl.items
  teachers.value = t.items
  rooms.value = r
}

function setPeriodMode(mode: PeriodMode) {
  if (periodMode.value === mode) return
  periodMode.value = mode
  // 切到周时对齐到本周；切到月时保持当前月
  if (mode === 'week') {
    anchorDate.value = startOfWeek(anchorDate.value)
  } else if (mode === 'month') {
    anchorDate.value = startOfMonth(anchorDate.value)
  } else {
    anchorDate.value = startOfDay(anchorDate.value)
  }
  void load()
}

function shiftPeriod(delta: number) {
  const d = new Date(anchorDate.value)
  if (periodMode.value === 'day') {
    d.setDate(d.getDate() + delta)
  } else if (periodMode.value === 'week') {
    d.setDate(d.getDate() + delta * 7)
  } else {
    d.setMonth(d.getMonth() + delta)
    d.setDate(1)
  }
  anchorDate.value = startOfDay(d)
  void load()
}

function goCurrent() {
  const now = new Date()
  if (periodMode.value === 'week') anchorDate.value = startOfWeek(now)
  else if (periodMode.value === 'month') anchorDate.value = startOfMonth(now)
  else anchorDate.value = startOfDay(now)
  void load()
}

function resetForm() {
  form.course_id = undefined
  form.class_id = undefined
  form.schedule_mode = 'rule'
  form.start_date = dateKey(new Date())
  form.start_time = '09:00'
  form.end_time = '10:30'
  form.repeat_mode = 'weekly'
  seedWeekdaysFromStartDate()
  form.end_mode = 'by_date'
  const end = new Date()
  end.setDate(end.getDate() + 28)
  form.end_date = dateKey(end)
  form.session_count = 8
  form.room = ''
  form.teacher_ids = []
  form.remark = ''
  form.on_conflict = 'skip'
  form.ignore_conflicts = false
  teacherAvail.value = []
  roomAvail.value = []
}

function openCreate(pref?: {
  date?: string
  teacherId?: number
  room?: string
  classId?: number
  startTime?: string
  endTime?: string
}) {
  formMode.value = 'create'
  editingId.value = null
  resetForm()
  if (pref?.date) form.start_date = pref.date
  if (pref?.startTime) form.start_time = pref.startTime
  if (pref?.endTime) form.end_time = pref.endTime
  if (pref?.teacherId) form.teacher_ids = [pref.teacherId]
  if (pref?.room && pref.room !== '教室待定') form.room = pref.room
  if (pref?.classId) {
    form.class_id = pref.classId
    const cls = classes.value.find((c) => c.id === pref.classId)
    if (cls?.course_id) form.course_id = cls.course_id
    if (cls?.default_room && !pref.room) form.room = cls.default_room
    if (cls?.teacher_ids?.length && !pref.teacherId) {
      form.teacher_ids = [...cls.teacher_ids]
    }
  }
  if (courseFilter.value && !form.course_id) form.course_id = courseFilter.value
  if (classFilter.value && !form.class_id) {
    form.class_id = classFilter.value
    onClassChange(classFilter.value)
  }
  if (teacherFilter.value && !form.teacher_ids.length) {
    form.teacher_ids = [teacherFilter.value]
  }
  // 预填开始日期对应的星期，方便从格子点开时直接生成规则排课
  seedWeekdaysFromStartDate()
  formVisible.value = true
  void refreshAvailability()
}

function openEdit(l: ScheduleLesson) {
  if (l.status === 'completed') {
    ElMessage.warning('已上课的排课不可改期，请先撤销点名')
    return
  }
  formMode.value = 'edit'
  editingId.value = l.id
  form.course_id = l.course_id ?? undefined
  form.class_id = l.class_id
  form.schedule_mode = 'calendar'
  const s = new Date(l.start_at)
  const e = new Date(l.end_at)
  form.start_date = dateKey(s)
  form.start_time = padTime(s)
  form.end_time = padTime(e)
  form.room = l.room || ''
  form.teacher_ids = [...(l.teacher_ids || [])]
  form.remark = l.remark || ''
  formVisible.value = true
  void refreshAvailability()
}

/** 点击课次上的时间，弹出快捷改时间 */
function openTimeEdit(l: ScheduleLesson, e?: Event) {
  e?.stopPropagation()
  e?.preventDefault()
  if (!canManage.value) return
  if (l.status === 'completed') {
    ElMessage.warning('已上课的排课不可改时间，请先撤销点名')
    return
  }
  const s = new Date(l.start_at)
  const end = new Date(l.end_at)
  timeEditId.value = l.id
  timeEditTitle.value = l.class_name || '修改上课时间'
  timeEditForm.date = dateKey(s)
  timeEditForm.start_time = padTime(s)
  timeEditForm.end_time = padTime(end)
  timeEditVisible.value = true
}

async function saveTimeEdit() {
  if (timeEditId.value == null) return
  if (!timeEditForm.date) {
    ElMessage.warning('请选择日期')
    return
  }
  if (
    !timeEditForm.start_time ||
    !timeEditForm.end_time ||
    timeEditForm.end_time <= timeEditForm.start_time
  ) {
    ElMessage.warning('请填写正确的上课时间')
    return
  }
  const start_at = `${timeEditForm.date}T${timeEditForm.start_time}:00`
  const end_at = `${timeEditForm.date}T${timeEditForm.end_time}:00`
  timeEditSaving.value = true
  try {
    let force = false
    const lesson = lessons.value.find((x) => x.id === timeEditId.value)
    const detailConf = await checkScheduleConflictsApi({
      start_at,
      end_at,
      teacher_ids: lesson?.teacher_ids || [],
      room: lesson?.room || '',
      exclude_id: timeEditId.value,
    }).catch(() => null)
    if (detailConf?.has_conflict) {
      try {
        await ElMessageBox.confirm('改后的时段存在老师或教室冲突，是否仍要保存？', '冲突提示', {
          type: 'warning',
          confirmButtonText: '强制保存',
          cancelButtonText: '取消',
        })
        force = true
      } catch {
        timeEditSaving.value = false
        return
      }
    }
    await updateScheduleApi(timeEditId.value, {
      start_at,
      end_at,
      force,
    })
    ElMessage.success('上课时间已更新')
    timeEditVisible.value = false
    await load()
  } catch {
    /* */
  } finally {
    timeEditSaving.value = false
  }
}

function onCourseChange(cid: number | undefined) {
  if (!cid) return
  const cls = classes.value.find((c) => c.id === form.class_id)
  if (cls && cls.course_id !== cid) {
    form.class_id = undefined
    form.teacher_ids = []
  }
}

function onClassChange(classId: number | undefined) {
  if (!classId) return
  const cls = classes.value.find((c) => c.id === classId)
  if (!cls) return
  if (cls.course_id) form.course_id = cls.course_id
  // 同步班级默认教室 / 任课老师
  if (cls.default_room) form.room = cls.default_room
  if (cls.teacher_ids?.length) form.teacher_ids = [...cls.teacher_ids]
  void refreshAvailability()
}

function buildRangeIso() {
  if (!form.start_date || !form.start_time || !form.end_time) return null
  const start_at = `${form.start_date}T${form.start_time}:00`
  const end_at = `${form.start_date}T${form.end_time}:00`
  if (end_at <= start_at) return null
  return { start_at, end_at }
}

async function refreshAvailability() {
  const range = buildRangeIso()
  if (!range) {
    teacherAvail.value = teachers.value.map((t) => ({
      id: t.id,
      name: t.name,
      busy: false,
      status: '空闲',
      conflicts: [],
    }))
    roomAvail.value = [
      ...rooms.value.map((r) => ({ name: r.name, busy: false, status: '空闲', conflicts: [] })),
      { name: '不指定', busy: false, status: '空闲', conflicts: [] },
    ]
    return
  }
  availLoading.value = true
  try {
    const res = await scheduleAvailabilityApi({
      start_at: range.start_at,
      end_at: range.end_at,
      exclude_id: editingId.value ?? undefined,
    })
    teacherAvail.value = res.teachers
    roomAvail.value = res.rooms
  } catch {
    teacherAvail.value = teachers.value.map((t) => ({
      id: t.id,
      name: t.name,
      busy: false,
      status: '空闲',
      conflicts: [],
    }))
    roomAvail.value = rooms.value.map((r) => ({
      name: r.name,
      busy: false,
      status: '空闲',
      conflicts: [],
    }))
  } finally {
    availLoading.value = false
  }
}

watch(
  () => [form.start_date, form.start_time, form.end_time, formVisible.value],
  () => {
    if (formVisible.value) void refreshAvailability()
  },
)

async function saveForm() {
  if (!form.class_id) {
    ElMessage.warning('请选择班级')
    return
  }
  if (!form.start_date) {
    ElMessage.warning('请选择开始日期')
    return
  }
  if (!form.start_time || !form.end_time || form.end_time <= form.start_time) {
    ElMessage.warning('请填写正确的上课时间')
    return
  }

  const room = form.room === '不指定' ? '' : form.room
  saving.value = true
  try {
    if (formMode.value === 'edit' && editingId.value != null) {
      const start_at = `${form.start_date}T${form.start_time}:00`
      const end_at = `${form.start_date}T${form.end_time}:00`
      await updateScheduleApi(editingId.value, {
        start_at,
        end_at,
        room,
        teacher_ids: form.teacher_ids,
        remark: form.remark,
      })
      ElMessage.success('排课已更新')
    } else if (form.schedule_mode === 'calendar') {
      const start_at = `${form.start_date}T${form.start_time}:00`
      const end_at = `${form.start_date}T${form.end_time}:00`
      const conf = await checkScheduleConflictsApi({
        start_at,
        end_at,
        teacher_ids: form.teacher_ids,
        room,
      }).catch(() => null)
      let force = form.ignore_conflicts
      if (conf?.has_conflict && !force) {
        try {
          await ElMessageBox.confirm('所选老师或教室存在时段冲突，是否仍要创建？', '冲突提示', {
            type: 'warning',
            confirmButtonText: '强制创建',
            cancelButtonText: '取消',
          })
          force = true
        } catch {
          saving.value = false
          return
        }
      }
      await createScheduleApi({
        class_id: form.class_id!,
        start_at,
        end_at,
        room,
        teacher_ids: form.teacher_ids,
        remark: form.remark,
        force,
      })
      ElMessage.success('排课已创建')
    } else {
      if (needsWeekdayPick.value && !form.weekdays.length) {
        ElMessage.warning('请选择每周上课日（可多选）')
        saving.value = false
        return
      }
      if (form.end_mode === 'by_date' && !form.end_date) {
        ElMessage.warning('请选择结束日期')
        saving.value = false
        return
      }
      if (form.end_mode === 'by_count' && (!form.session_count || form.session_count < 1)) {
        ElMessage.warning('请填写排课次数')
        saving.value = false
        return
      }
      const result = await createSchedulesBatchApi({
        class_id: form.class_id!,
        start_date: form.start_date,
        start_time: form.start_time,
        end_time: form.end_time,
        repeat_mode: form.repeat_mode,
        end_mode: form.end_mode,
        end_date: form.end_date || undefined,
        session_count: form.session_count,
        weekdays: needsWeekdayPick.value ? [...form.weekdays].sort((a, b) => a - b) : undefined,
        room,
        teacher_ids: form.teacher_ids,
        remark: form.remark,
        on_conflict: form.ignore_conflicts ? 'force' : form.on_conflict,
      })
      const msg =
        result.skipped_count > 0
          ? `已生成 ${result.created_count} 节课，跳过冲突 ${result.skipped_count} 节`
          : `已生成 ${result.created_count} 节课`
      ElMessage.success(msg)
    }
    formVisible.value = false
    await load()
  } catch {
    /* axios 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

async function onDeleteLesson(l: ScheduleLesson): Promise<boolean> {
  try {
    await ElMessageBox.confirm(`确定删除排课「${l.class_name}」？`, '删除确认', { type: 'warning' })
    await deleteScheduleApi(l.id)
    ElMessage.success('已删除')
    await load()
    return true
  } catch {
    return false
  }
}

function onEmptyCellClick(row: { key: string; label: string }, day: number) {
  if (!canManage.value) return
  if (!matrixCellEmpty(row.key, day)) return
  const d = dayLabels.value[day]
  if (!d) return
  const pref: {
    date?: string
    teacherId?: number
    room?: string
    classId?: number
  } = { date: d.dateKey }
  if (viewTab.value === 'teacher') {
    const tid = Number(row.key)
    if (!Number.isNaN(tid)) pref.teacherId = tid
  } else if (viewTab.value === 'room') {
    pref.room = row.key === '教室待定' ? '' : row.key
  } else if (viewTab.value === 'class') {
    const cid = Number(row.key)
    if (!Number.isNaN(cid)) pref.classId = cid
  }
  openCreate(pref)
}

function onTimeCellClick(day: number, hourLabel: string) {
  if (!canManage.value) return
  if (hourOccupied(day, hourLabel)) return
  const d = dayLabels.value[day]
  if (!d) return
  const parts = hourLabel.split(':')
  const hourNum = Number(parts[0]) || 9
  const hh = String(hourNum).padStart(2, '0')
  const startTime = `${hh}:00`
  const endH = Math.min(22, hourNum + 2)
  const endTime = `${String(endH).padStart(2, '0')}:00`
  openCreate({ date: d.dateKey, startTime, endTime })
}

function onMonthDayClick(cell: DayCol) {
  if (!canManage.value) return
  if (cell.isOtherMonth) {
    anchorDate.value = startOfDay(cell.date)
    periodMode.value = 'day'
    void load()
    return
  }
  // 当日已有课次时不弹新建，避免误触；点空白/标题区仍可新建
  openCreate({ date: cell.dateKey, startTime: '09:00', endTime: '10:30' })
}

function isScheduleRollable(l: ScheduleLesson) {
  if (l.status === 'completed' || l.status === 'cancelled') return false
  if (typeof l.can_roll_call === 'boolean') return l.can_roll_call
  const start = new Date(l.start_at)
  if (Number.isNaN(start.getTime())) return false
  const lessonDay = new Date(start)
  lessonDay.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return lessonDay.getTime() <= today.getTime()
}

function goRoll(l: ScheduleLesson) {
  if (!isScheduleRollable(l)) {
    ElMessage.warning('不能对未来课程点名，仅可点当天及过去的课次')
    return
  }
  void router.push({
    path: '/academic/class-records',
    query: {
      roll: '1',
      class_id: String(l.class_id),
      schedule_id: String(l.id),
    },
  })
}

function openLessonDetail(l: ScheduleLesson | ScheduleLessonDetail) {
  if (!l?.id) {
    ElMessage.info('课次无效')
    return
  }
  detailLessonId.value = l.id
  detailVisible.value = true
}

function onDetailEdit(d: ScheduleLessonDetail) {
  detailVisible.value = false
  openEdit(d)
}

async function onDetailRemove(d: ScheduleLessonDetail) {
  const ok = await onDeleteLesson(d)
  if (ok) {
    detailVisible.value = false
    detailLessonId.value = null
  }
}

function onDetailRoll(d: ScheduleLessonDetail) {
  detailVisible.value = false
  goRoll(d)
}

function applyTimeSlot(
  target: 'form' | 'timeEdit',
  slot: { start: string; end: string },
) {
  if (target === 'form') {
    form.start_time = slot.start
    form.end_time = slot.end
    void refreshAvailability()
  } else {
    timeEditForm.start_time = slot.start
    timeEditForm.end_time = slot.end
  }
}

function cardMeta(l: ScheduleLesson) {
  if (viewTab.value === 'teacher') {
    return `${l.teachers || '待分配'} · ${l.room || '教室待定'}`
  }
  if (viewTab.value === 'room') return `${l.teachers || '待分配'}`
  return `${l.teachers || '待分配'} · ${l.room || '教室待定'}`
}

function lessonTone(l: ScheduleLesson) {
  if (l.status === 'completed') return 'is-done'
  const color = l.course_color || ''
  if (color.toLowerCase().includes('3b82') || color.toLowerCase().includes('2563')) return 'is-blue'
  if (color.toLowerCase().includes('16a3') || color.toLowerCase().includes('22c5')) return 'is-green'
  return ''
}

onMounted(async () => {
  if (selfTeacherOnly.value && selfTeacherId.value != null) {
    teacherFilter.value = selfTeacherId.value
  }
  await loadMeta()
  await load()
})
</script>

<template>
  <div class="schedule-page">
    <div class="page-toolbar">
      <div class="toolbar-title-block">
        <el-page-header
          class="is-title-only"
          :content="selfTeacherOnly ? '我的课表' : '课表管理'"
        />
        <p class="page-sub">
          {{
            selfTeacherOnly
              ? '仅展示您所带的课程安排 · 日 / 周 / 月视图'
              : '时间 / 老师 / 教室 / 班级 · 日周月视图与一键排课'
          }}
        </p>
      </div>
      <div class="toolbar-right">
        <el-button class="tb-btn" plain @click="load">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button
          v-if="canManage"
          type="primary"
          class="tb-btn tb-btn--primary"
          @click="openCreate()"
        >
          <el-icon><Plus /></el-icon>
          新建排课
        </el-button>
      </div>
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <el-select v-if="isCompact" v-model="viewTab" class="mobile-view-switch" aria-label="课表视图">
        <el-option label="时间课表" value="time" />
        <el-option v-if="!selfTeacherOnly" label="老师课表" value="teacher" />
        <el-option label="教室课表" value="room" />
        <el-option label="班级课表" value="class" />
      </el-select>
      <el-tabs v-else v-model="viewTab" class="mode-tabs">
        <el-tab-pane name="time">
          <template #label>
            <span class="tab-label">
              <el-icon><Clock /></el-icon>
              时间课表
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane v-if="!selfTeacherOnly" name="teacher">
          <template #label>
            <span class="tab-label">
              <el-icon><User /></el-icon>
              老师课表
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="room">
          <template #label>
            <span class="tab-label">
              <el-icon><OfficeBuilding /></el-icon>
              教室课表
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="class">
          <template #label>
            <span class="tab-label">
              <el-icon><School /></el-icon>
              班级课表
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>

      <div class="filter-bar">
        <div class="filter-bar-head">
          <div class="filter-bar-title">
            <span class="sec-dot" />
            筛选与导航
          </div>
          <span class="filter-hint">
            {{
              viewTab === 'time'
                ? '按时间轴查看课次'
                : viewTab === 'teacher'
                  ? '按老师横向对照'
                  : viewTab === 'room'
                    ? '按教室占用查看'
                    : '按班级课次对照'
            }}
          </span>
        </div>

        <div class="filter-row">
          <div class="filter-item">
            <span class="filter-label">所属课程</span>
            <el-select
              v-model="courseFilter"
              clearable
              filterable
              placeholder="请选择课程"
              class="filter-select"
              @change="
                () => {
                  if (classFilter && !filterClassOptions.some((c) => c.id === classFilter)) {
                    classFilter = undefined
                  }
                  load()
                }
              "
            >
              <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">上课班级</span>
            <el-select
              v-model="classFilter"
              clearable
              filterable
              placeholder="请选择班级"
              class="filter-select"
              @change="load"
            >
              <el-option v-for="c in filterClassOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </div>
          <div v-if="!selfTeacherOnly" class="filter-item">
            <span class="filter-label">上课老师</span>
            <el-select
              v-model="teacherFilter"
              clearable
              filterable
              placeholder="请选择老师"
              class="filter-select"
              @change="load"
            >
              <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
          </div>
        </div>

        <div class="action-row">
          <el-button
            v-if="canManage"
            type="primary"
            class="tb-btn tb-btn--primary action-create"
            @click="openCreate()"
          >
            <el-icon><Plus /></el-icon>
            新建排课
          </el-button>
          <div class="spacer" />
          <div class="period-nav">
            <el-radio-group
              :model-value="periodMode"
              size="small"
              class="period-switch"
              @change="(v: string | number | boolean | undefined) => setPeriodMode(String(v) as PeriodMode)"
            >
              <el-radio-button value="day">日</el-radio-button>
              <el-radio-button value="week">周</el-radio-button>
              <el-radio-button value="month">月</el-radio-button>
            </el-radio-group>
            <el-button text size="small" class="jump-btn" @click="goCurrent">{{ jumpLabel }}</el-button>
            <el-button text class="nav-arrow" @click="shiftPeriod(-1)">
              <el-icon><ArrowLeft /></el-icon>
            </el-button>
            <el-popover
              placement="bottom"
              :width="300"
              trigger="click"
              popper-class="period-picker-popper"
            >
              <template #reference>
                <button type="button" class="period-picker-trigger" :title="`选择${periodMode === 'day' ? '日期' : periodMode === 'week' ? '周' : '月份'}`">
                  <el-icon><Calendar /></el-icon>
                  <span>{{ periodLabel }}</span>
                </button>
              </template>
              <el-date-picker
                v-model="periodPickerDate"
                :type="periodPickerType"
                :format="periodPickerFormat"
                :clearable="false"
                :editable="false"
                style="width: 100%"
              />
            </el-popover>
            <el-button text class="nav-arrow" @click="shiftPeriod(1)">
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>
      </div>

      <div class="summary-bar">
        <div class="summary-main">
          <span class="summary-chip">
            共 <b>{{ lessons.length }}</b> 节课
          </span>
          <span v-if="periodMode !== 'month' && dayCounts.some((n) => n)" class="summary-days">
            <template v-for="(n, i) in dayCounts" :key="i">
              <span v-if="n" class="day-count-pill">{{ dayLabels[i]?.short }} {{ n }}</span>
            </template>
          </span>
        </div>
        <span class="summary-tip">
          {{
            isCompact
              ? '点击课次打开详情侧栏'
              : '悬停课次可查看气泡 · 点「查看详情」打开课次侧栏'
          }}
        </span>
      </div>

      <!-- 时间课表 · 日/周：小时轴 -->
      <div v-if="viewTab === 'time' && periodMode !== 'month'" class="calendar-wrap">
        <div class="cal-grid" :style="calGridStyle">
          <div class="cal-corner" />
          <div
            v-for="d in dayLabels"
            :key="d.index"
            class="cal-day-head"
            :class="{ 'is-today': d.isToday }"
          >
            <div class="day-title">{{ d.label }}</div>
            <div class="day-sub">
              <span class="day-count-badge">{{ dayCounts[d.index] }}</span>
              节课
            </div>
          </div>

          <div class="cal-time-col" :style="{ height: trackHeight + 'px' }">
            <div v-for="h in hours" :key="h" class="time-slot" :style="{ height: HOUR_PX + 'px' }">
              {{ h }}
            </div>
          </div>

          <div v-for="d in dayLabels" :key="'col-' + d.index" class="cal-day-col">
            <div class="day-track" :style="{ height: trackHeight + 'px' }">
              <div
                v-for="h in hours"
                :key="h"
                class="hour-line"
                :class="{
                  'hour-clickable': canManage && !hourOccupied(d.index, h),
                  'is-occupied': hourOccupied(d.index, h),
                  // compact 仍可点空白新建，但不做 hover 蒙层
                  'no-hover-hint': isCompact,
                }"
                :style="{ height: HOUR_PX + 'px' }"
                :data-hint="emptyHourHint(d.index, h)"
                @click="onTimeCellClick(d.index, h)"
              />
              <template v-for="b in lessonsForDay(d.index)" :key="b.id">
                <el-popover
                  v-if="useLessonPopover"
                  placement="top"
                  :width="320"
                  trigger="hover"
                  :show-after="200"
                  :hide-after="120"
                  popper-class="schedule-lesson-popper"
                >
                  <template #reference>
                    <button
                      type="button"
                      class="lesson-block"
                      :class="lessonTone(b)"
                      :style="blockStyle(b)"
                      @click.stop
                      @dblclick.stop="openEdit(b)"
                    >
                      <div
                        class="lb-time is-editable"
                        title="点击修改时间"
                        @click.stop="openTimeEdit(b, $event)"
                      >
                        {{ timeRange(b) }}
                      </div>
                      <div class="lb-title">{{ b.class_name }}</div>
                      <div class="lb-meta">{{ b.teachers || '待分配' }}</div>
                      <div class="lb-meta">{{ b.room || '教室待定' }}</div>
                    </button>
                  </template>
                  <ScheduleLessonPop
                    :lesson="b"
                    :can-manage="canManage"
                    @roll="goRoll(b)"
                    @adjust="openEdit(b)"
                    @detail="openLessonDetail(b)"
                    @edit-time="openTimeEdit(b)"
                    @remove="onDeleteLesson(b)"
                  />
                </el-popover>
                <button
                  v-else
                  type="button"
                  class="lesson-block"
                  :class="lessonTone(b)"
                  :style="blockStyle(b)"
                  @click.stop="openLessonDetail(b)"
                >
                  <div class="lb-time">{{ timeRange(b) }}</div>
                  <div class="lb-title">{{ b.class_name }}</div>
                  <div class="lb-meta">{{ b.teachers || '待分配' }}</div>
                  <div class="lb-meta">{{ b.room || '教室待定' }}</div>
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 时间课表 · 月：月历 -->
      <div v-else-if="viewTab === 'time' && periodMode === 'month'" class="month-wrap">
        <div class="month-weekhead">
          <div v-for="w in WEEK_NAMES" :key="w" class="month-wh">{{ w }}</div>
        </div>
        <div class="month-grid">
          <div
            v-for="cell in monthCalendarCells"
            :key="cell.dateKey"
            class="month-cell"
            :class="{
              'is-other': cell.isOtherMonth,
              'is-today': cell.isToday,
              'is-empty-hover':
                !isCompact &&
                canManage &&
                lessonsOnDate(cell.dateKey).length === 0 &&
                !cell.isOtherMonth,
            }"
            :data-hint="
              !isCompact &&
              canManage &&
              lessonsOnDate(cell.dateKey).length === 0 &&
              !cell.isOtherMonth
                ? '新建排课'
                : ''
            "
            @click="onMonthDayClick(cell)"
          >
            <div class="month-daynum">{{ cell.label }}</div>
            <div class="month-lessons">
              <template v-for="l in lessonsOnDate(cell.dateKey)" :key="l.id">
                <el-popover
                  v-if="useLessonPopover"
                  placement="top"
                  :width="320"
                  trigger="hover"
                  :show-after="200"
                  :hide-after="120"
                  popper-class="schedule-lesson-popper"
                >
                  <template #reference>
                    <button
                      type="button"
                      class="month-chip"
                      :style="{
                        borderLeftColor: l.course_color || '#a16207',
                        background: softColor(l.course_color || '#a16207'),
                      }"
                      @click.stop
                      @dblclick.stop="openEdit(l)"
                    >
                      <span
                        class="mc-time is-editable"
                        title="点击修改时间"
                        @click.stop="openTimeEdit(l, $event)"
                      >
                        {{ timeRange(l) }}
                      </span>
                      <span class="mc-name">{{ l.class_name }}</span>
                    </button>
                  </template>
                  <ScheduleLessonPop
                    :lesson="l"
                    :can-manage="canManage"
                    @roll="goRoll(l)"
                    @adjust="openEdit(l)"
                    @detail="openLessonDetail(l)"
                    @edit-time="openTimeEdit(l)"
                    @remove="onDeleteLesson(l)"
                  />
                </el-popover>
                <button
                  v-else
                  type="button"
                  class="month-chip"
                  :style="{
                    borderLeftColor: l.course_color || '#a16207',
                    background: softColor(l.course_color || '#a16207'),
                  }"
                  @click.stop="openLessonDetail(l)"
                >
                  <span class="mc-time">{{ timeRange(l) }}</span>
                  <span class="mc-name">{{ l.class_name }}</span>
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 老师 / 教室 / 班级矩阵 -->
      <div v-else class="matrix-wrap">
        <el-empty v-if="!matrixRows.length" description="暂无数据，请先维护老师/教室/班级" />
        <div v-else class="matrix-table" :style="{ minWidth: periodMode === 'month' ? '2200px' : '1100px' }">
          <div class="mx-head" :style="matrixGridStyle">
            <div class="mx-corner">
              {{ viewTab === 'teacher' ? '老师' : viewTab === 'room' ? '教室' : '班级' }}
            </div>
            <div
              v-for="d in dayLabels"
              :key="d.index"
              class="mx-day-head"
              :class="{ 'is-today': d.isToday }"
            >
              <div class="day-title">{{ d.label }}</div>
              <div class="day-sub">
                <span class="day-count-badge">{{ dayCounts[d.index] }}</span>
                节课
              </div>
            </div>
          </div>
          <div v-for="row in matrixRows" :key="row.key" class="mx-row" :style="matrixGridStyle">
            <div class="mx-entity">
              <div class="mx-entity-name">{{ row.label }}</div>
              <div v-if="row.sub" class="mx-entity-sub">{{ row.sub }}</div>
            </div>
            <div
              v-for="d in dayLabels"
              :key="row.key + '-' + d.index"
              class="mx-cell"
              :class="{
                'is-empty-hover': !isCompact && canManage && matrixCellEmpty(row.key, d.index),
                'has-lessons': !matrixCellEmpty(row.key, d.index),
              }"
              :data-hint="matrixEmptyHint(row, row.key, d.index)"
              @click="onEmptyCellClick(row, d.index)"
            >
              <template v-if="!matrixCellEmpty(row.key, d.index)">
                <template
                  v-for="l in lessonsForEntityDay(row.key, d.index, matrixMode)"
                  :key="l.id"
                >
                  <el-popover
                    v-if="useLessonPopover"
                    placement="top"
                    :width="320"
                    trigger="hover"
                    :show-after="200"
                    :hide-after="120"
                    popper-class="schedule-lesson-popper"
                  >
                    <template #reference>
                      <button
                        type="button"
                        class="mx-card"
                        :class="lessonTone(l)"
                        :style="{
                          borderLeftColor: l.course_color || '#a16207',
                          background: softColor(l.course_color || '#a16207'),
                        }"
                        @click.stop
                        @dblclick.stop="openEdit(l)"
                      >
                        <div
                          class="mx-card-time is-editable"
                          title="点击修改时间"
                          @click.stop="openTimeEdit(l, $event)"
                        >
                          {{ timeRange(l) }}
                        </div>
                        <div class="mx-card-title">{{ l.class_name }}</div>
                        <div class="mx-card-meta">{{ cardMeta(l) }}</div>
                        <div v-if="viewTab !== 'room'" class="mx-card-meta">
                          {{ l.room || '教室待定' }}
                        </div>
                      </button>
                    </template>
                    <ScheduleLessonPop
                      :lesson="l"
                      :can-manage="canManage"
                      @roll="goRoll(l)"
                      @adjust="openEdit(l)"
                      @detail="openLessonDetail(l)"
                      @edit-time="openTimeEdit(l)"
                      @remove="onDeleteLesson(l)"
                    />
                  </el-popover>
                  <button
                    v-else
                    type="button"
                    class="mx-card"
                    :class="lessonTone(l)"
                    :style="{
                      borderLeftColor: l.course_color || '#a16207',
                      background: softColor(l.course_color || '#a16207'),
                    }"
                    @click.stop="openLessonDetail(l)"
                  >
                    <div class="mx-card-time">{{ timeRange(l) }}</div>
                    <div class="mx-card-title">{{ l.class_name }}</div>
                    <div class="mx-card-meta">{{ cardMeta(l) }}</div>
                    <div v-if="viewTab !== 'room'" class="mx-card-meta">
                      {{ l.room || '教室待定' }}
                    </div>
                  </button>
                </template>
              </template>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <AppSheet
      v-model="formVisible"
      :title="formTitle"
      size="460px"
      modal-class="schedule-drawer"
    >
      <el-form label-position="top" class="sch-form" v-loading="availLoading">
        <div class="form-section">
          <span class="sec-dot" />
          班级与课程
        </div>
        <el-form-item label="课程" required>
          <el-select
            v-model="form.course_id"
            filterable
            clearable
            placeholder="请选择课程"
            style="width: 100%"
            :disabled="formMode === 'edit'"
            @change="onCourseChange"
          >
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="班级" required>
          <el-select
            v-model="form.class_id"
            filterable
            placeholder="请选择班级"
            style="width: 100%"
            :disabled="formMode === 'edit'"
            @change="onClassChange"
          >
            <el-option v-for="c in formClassOptions" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>

        <div class="form-section">
          <span class="sec-dot" />
          时间与规则
        </div>

        <el-form-item v-if="formMode === 'create'" label="排课方式">
          <el-radio-group v-model="form.schedule_mode" class="mode-radios">
            <el-radio-button value="rule">规则排课</el-radio-button>
            <el-radio-button value="calendar">日历排课</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item
          :label="form.schedule_mode === 'calendar' || formMode === 'edit' ? '上课日期' : '开始日期'"
          required
        >
          <el-date-picker
            v-model="form.start_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            placeholder="选择日期"
          />
        </el-form-item>

        <template v-if="formMode === 'create' && form.schedule_mode === 'rule'">
          <el-form-item label="重复方式">
            <el-radio-group v-model="form.repeat_mode">
              <el-radio value="daily">每天重复</el-radio>
              <el-radio value="alternate">隔天重复</el-radio>
              <el-radio value="weekly">每周重复</el-radio>
              <el-radio value="biweekly">隔周重复</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="needsWeekdayPick" label="每周上课日" required>
            <el-checkbox-group v-model="form.weekdays" class="weekday-options">
              <el-checkbox-button
                v-for="weekday in WEEKDAY_OPTIONS"
                :key="weekday.value"
                :value="weekday.value"
              >
                {{ weekday.label }}
              </el-checkbox-button>
            </el-checkbox-group>
            <div class="weekday-hint">可多选，例如周一、周三、周五</div>
          </el-form-item>
        </template>

        <el-form-item label="上课时间" required>
          <div class="time-row">
            <el-time-picker
              v-model="form.start_time"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="开始时间"
              :clearable="false"
              class="time-picker"
            />
            <span class="tilde">~</span>
            <el-time-picker
              v-model="form.end_time"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="结束时间"
              :clearable="false"
              class="time-picker"
            />
          </div>
          <div class="slot-chips">
            <span class="slot-chips-label">常用时段（点击选择）</span>
            <div class="slot-chips-list">
              <button
                v-for="s in COMMON_SLOTS"
                :key="s.label"
                type="button"
                class="slot-chip"
                :class="{
                  'is-active': form.start_time === s.start && form.end_time === s.end,
                }"
                @click="applyTimeSlot('form', s)"
              >
                {{ s.label }}
              </button>
            </div>
          </div>
        </el-form-item>

        <template v-if="formMode === 'create' && form.schedule_mode === 'rule'">
          <el-form-item label="结束方式">
            <el-radio-group v-model="form.end_mode">
              <el-radio value="by_date">按日期结束</el-radio>
              <el-radio value="by_count">按次数结束</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="form.end_mode === 'by_date'" label="结束日期" required>
            <el-date-picker
              v-model="form.end_date"
              type="date"
              value-format="YYYY-MM-DD"
              style="width: 100%"
              placeholder="请选择结束日期"
            />
          </el-form-item>
          <el-form-item v-else label="排课次数" required>
            <el-input-number v-model="form.session_count" :min="1" :max="200" style="width: 100%" />
          </el-form-item>
          <el-form-item label="冲突处理">
            <el-radio-group v-model="form.on_conflict" :disabled="form.ignore_conflicts">
              <el-radio value="skip">跳过冲突</el-radio>
              <el-radio value="fail">遇冲突整批取消</el-radio>
            </el-radio-group>
          </el-form-item>
        </template>

        <el-form-item v-if="formMode === 'create'" label="时间冲突">
          <el-checkbox v-model="form.ignore_conflicts">
            忽略冲突，仍然添加课表
          </el-checkbox>
        </el-form-item>

        <div class="form-section">
          <span class="sec-dot" />
          老师 · 教室 · 内容
        </div>

        <el-form-item label="上课老师">
          <el-select
            v-model="form.teacher_ids"
            multiple
            filterable
            placeholder="请选择老师"
            style="width: 100%"
          >
            <el-option
              v-for="t in teacherAvail.length ? teacherAvail : teachers"
              :key="t.id"
              :label="t.name"
              :value="t.id"
            >
              <div class="opt-row">
                <span class="opt-name">{{ t.name }}</span>
                <span class="opt-status" :class="'busy' in t && t.busy ? 'is-busy' : 'is-free'">
                  {{ 'status' in t ? t.status : '空闲' }}
                </span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="上课教室">
          <el-select
            v-model="form.room"
            filterable
            clearable
            allow-create
            default-first-option
            placeholder="不指定"
            style="width: 100%"
          >
            <el-option
              v-for="r in roomAvail.length
                ? roomAvail
                : [
                    ...rooms.map((x) => ({ name: x.name, busy: false, status: '空闲' })),
                    { name: '不指定', busy: false, status: '空闲' },
                  ]"
              :key="r.name"
              :label="r.name"
              :value="r.name === '不指定' ? '' : r.name"
            >
              <div class="opt-row">
                <span class="opt-name">{{ r.name }}</span>
                <span class="opt-status" :class="r.busy ? 'is-busy' : 'is-free'">
                  {{ r.status || '空闲' }}
                </span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="上课内容">
          <el-input
            v-model="form.remark"
            type="textarea"
            :rows="3"
            maxlength="100"
            show-word-limit
            placeholder="最多100字"
          />
        </el-form-item>

        <div v-if="formHint" class="form-hint">
          <el-icon><InfoFilled /></el-icon>
          {{ formHint }}
        </div>
      </el-form>

      <template #footer>
        <el-button class="tb-btn" @click="formVisible = false">取消</el-button>
        <el-button type="primary" class="tb-btn tb-btn--primary" :loading="saving" @click="saveForm">
          {{ formMode === 'edit' ? '保存' : form.schedule_mode === 'rule' ? '生成排课' : '创建排课' }}
        </el-button>
      </template>
    </AppSheet>

    <!-- 快捷修改上课时间 -->
    <el-dialog
      v-model="timeEditVisible"
      :title="`修改时间 · ${timeEditTitle}`"
      width="420px"
      destroy-on-close
      append-to-body
      align-center
      class="time-edit-dialog"
    >
      <el-form label-width="88px">
        <el-form-item label="上课日期" required>
          <el-date-picker
            v-model="timeEditForm.date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
            placeholder="选择日期"
          />
        </el-form-item>
        <el-form-item label="上课时间" required>
          <div class="time-row">
            <el-time-picker
              v-model="timeEditForm.start_time"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="开始"
              :clearable="false"
              class="time-picker"
            />
            <span class="tilde">~</span>
            <el-time-picker
              v-model="timeEditForm.end_time"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="结束"
              :clearable="false"
              class="time-picker"
            />
          </div>
          <div class="slot-chips">
            <span class="slot-chips-label">常用时段（点击选择）</span>
            <div class="slot-chips-list">
              <button
                v-for="s in COMMON_SLOTS"
                :key="s.label"
                type="button"
                class="slot-chip"
                :class="{
                  'is-active':
                    timeEditForm.start_time === s.start && timeEditForm.end_time === s.end,
                }"
                @click="applyTimeSlot('timeEdit', s)"
              >
                {{ s.label }}
              </button>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button class="tb-btn" @click="timeEditVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="tb-btn tb-btn--primary"
          :loading="timeEditSaving"
          @click="saveTimeEdit"
        >
          保存时间
        </el-button>
      </template>
    </el-dialog>

    <ScheduleLessonDetailDrawer
      v-model="detailVisible"
      :lesson-id="detailLessonId"
      :can-manage="canManage"
      @edit="onDetailEdit"
      @remove="onDetailRemove"
      @roll="onDetailRoll"
      @refreshed="load"
    />
  </div>
</template>

<style scoped>
.schedule-page {
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
  gap: 8px;
  flex-wrap: wrap;
}

.module-card {
  margin-top: 12px;
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 6px 20px rgba(41, 37, 36, 0.04);
}

.module-card :deep(.el-card__body) {
  padding: 8px 16px 16px;
}

.mode-tabs {
  margin-bottom: 4px;
}

.mobile-view-switch {
  width: 100%;
  margin: 8px 0 12px;
}

.mode-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.mode-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  height: 42px;
  line-height: 42px;
}

.mode-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.mode-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--oc-primary, #a16207);
  height: 3px;
  border-radius: 2px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.filter-bar {
  padding: 12px 14px;
  margin-bottom: 12px;
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(180deg, #faf6ee 0%, #f7f1e6 100%);
}

.filter-bar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.filter-bar-title {
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

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 18px;
  margin-bottom: 12px;
  align-items: center;
}

.filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  white-space: nowrap;
}

.filter-select {
  width: 200px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.action-create {
  display: none;
}

.spacer {
  flex: 1;
}

.period-nav {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  padding: 4px 8px;
  border-radius: 12px;
  background: rgba(255, 253, 248, 0.95);
  border: 1px solid var(--oc-border, #e8e0d0);
  box-shadow: 0 2px 8px rgba(41, 37, 36, 0.04);
}

.period-switch :deep(.el-radio-button__inner) {
  padding: 6px 14px;
  border-radius: 8px !important;
  box-shadow: none !important;
  border: 0 !important;
  background: transparent;
  color: var(--oc-muted, #78716c);
  font-weight: 600;
}

.period-switch :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(145deg, #c9a066, #a16207) !important;
  color: #fff !important;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.25) !important;
}

.jump-btn {
  color: var(--oc-primary, #a16207) !important;
  font-weight: 600;
}

.nav-arrow {
  padding: 4px 6px !important;
  color: var(--oc-ink, #44403c) !important;
  border-radius: 8px !important;
}

.nav-arrow:hover {
  background: rgba(161, 98, 7, 0.08) !important;
  color: var(--oc-primary, #a16207) !important;
}

.period-picker-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 190px;
  border: 0;
  border-radius: 8px;
  padding: 5px 10px;
  background: transparent;
  color: var(--oc-ink, #44403c);
  font: inherit;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.period-picker-trigger:hover,
.period-picker-trigger:focus-visible {
  background: rgba(161, 98, 7, 0.08);
  color: var(--oc-primary, #a16207);
  outline: none;
}

.period-picker-trigger .el-icon {
  flex-shrink: 0;
  color: var(--oc-primary, #a16207);
}

.summary-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  background: linear-gradient(90deg, #faf3e6, #f5f0e6);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 12px;
}

.summary-main {
  display: inline-flex;
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

.summary-chip b,
.summary-bar b {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  margin: 0 3px;
}

.summary-days {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
}

.day-count-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
}

.summary-tip {
  font-size: 12px;
  color: #a8a29e;
}

.day-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  margin-right: 2px;
  border-radius: 999px;
  background: rgba(161, 98, 7, 0.12);
  color: var(--oc-primary, #a16207);
  font-size: 10px;
  font-weight: 700;
}

.calendar-wrap {
  overflow-x: auto;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: var(--oc-card, #fffdf8);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.cal-grid {
  display: grid;
}

.cal-corner {
  grid-column: 1;
  grid-row: 1;
  background: #f5f0e6;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  border-right: 1px solid var(--oc-border, #e8e0d0);
}

.cal-day-head {
  grid-row: 1;
  padding: 10px 8px;
  background: linear-gradient(180deg, #faf6ee, #f5f0e6);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  border-right: 1px solid var(--oc-border, #e8e0d0);
  text-align: center;
}

.cal-day-head.is-today,
.mx-day-head.is-today {
  background: linear-gradient(180deg, #fff7ed, #fde68a33);
  box-shadow: inset 0 -2px 0 var(--oc-primary, #a16207);
}

.cal-day-head.is-today .day-title,
.mx-day-head.is-today .day-title {
  color: var(--oc-primary, #a16207);
}

.day-title {
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.day-sub {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
  margin-top: 2px;
}

.cal-time-col {
  grid-column: 1;
  grid-row: 2;
  border-right: 1px solid var(--oc-border, #e8e0d0);
  background: #faf8f3;
}

.time-slot {
  padding: 6px 4px;
  font-size: 11px;
  color: var(--oc-muted, #78716c);
  border-bottom: 1px solid #f0e9dc;
  text-align: right;
  box-sizing: border-box;
}

.cal-day-col {
  grid-row: 2;
  border-right: 1px solid var(--oc-border, #e8e0d0);
  position: relative;
}

.day-track {
  position: relative;
}

.hour-line {
  border-bottom: 1px solid #f0e9dc;
  box-sizing: border-box;
  position: relative;
}

.hour-clickable {
  cursor: pointer;
}

.hour-clickable:hover {
  background: rgba(161, 98, 7, 0.05);
}

.hour-line.is-occupied {
  pointer-events: none;
  cursor: default;
}

/* 仅空白格悬浮显示新建提示；已占用小时格不显示 */
.hour-clickable[data-hint]:not([data-hint='']):hover::after,
.mx-cell.is-empty-hover[data-hint]:not([data-hint='']):hover::after,
.month-cell.is-empty-hover[data-hint]:not([data-hint='']):hover::after {
  content: attr(data-hint);
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
  background: rgba(245, 240, 230, 0.92);
  pointer-events: none;
  z-index: 1;
  text-align: center;
  padding: 4px;
  line-height: 1.3;
  word-break: break-all;
}

.lesson-block {
  position: absolute;
  left: 4px;
  right: 4px;
  z-index: 5;
  border: 1px solid #dbbf94;
  border-left: 3px solid var(--oc-primary, #a16207);
  border-radius: 9px;
  background: linear-gradient(165deg, #fffdf8 0%, #f5f0e6 55%, #ebe3d4 100%);
  padding: 5px 7px;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  pointer-events: auto;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.1);
  transition: box-shadow 0.15s, transform 0.15s, border-color 0.15s;
}

.lesson-block:hover {
  box-shadow: 0 6px 16px rgba(161, 98, 7, 0.18);
  transform: translateY(-1px);
  border-color: #c9a066;
}

.lesson-block.is-blue {
  border-color: #93c5fd;
  border-left-color: #3b82f6;
  background: linear-gradient(165deg, #eff6ff, #dbeafe);
}

.lesson-block.is-green {
  border-color: #86efac;
  border-left-color: #16a34a;
  background: linear-gradient(165deg, #f0fdf4, #dcfce7);
}

.lesson-block.is-done {
  opacity: 0.72;
  filter: grayscale(0.15);
}

.lb-time {
  font-size: 10px;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
}

.is-editable {
  cursor: pointer;
  border-radius: 3px;
  transition: background 0.15s, color 0.15s;
}

.lb-time.is-editable:hover,
.mx-card-time.is-editable:hover,
.mc-time.is-editable:hover {
  background: rgba(161, 98, 7, 0.12);
  text-decoration: underline;
}

.pop-time.is-editable {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 2px 4px;
  margin: 0 -4px;
  border-radius: 4px;
}

.pop-time.is-editable:hover {
  background: #f5f0e6;
  color: var(--oc-primary, #a16207);
}

.pop-time-action {
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  flex-shrink: 0;
}

.lb-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.lb-meta {
  font-size: 10px;
  color: var(--oc-muted, #78716c);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pop-detail {
  font-size: 13px;
  line-height: 1.6;
}

.pop-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.pop-line {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.pop-actions {
  margin-top: 8px;
  display: flex;
  gap: 4px;
}

/* 月历 */
.month-wrap {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: var(--oc-card, #fffdf8);
  overflow: hidden;
}

.month-weekhead {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  background: linear-gradient(180deg, #faf6ee, #f5f0e6);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.month-wh {
  padding: 10px 6px;
  text-align: center;
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  border-right: 1px solid var(--oc-border, #e8e0d0);
}

.month-wh:last-child {
  border-right: none;
}

.month-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
}

.month-cell {
  min-height: 110px;
  border-right: 1px solid #f0e9dc;
  border-bottom: 1px solid #f0e9dc;
  padding: 6px;
  position: relative;
  cursor: pointer;
  transition: background 0.15s;
}

.month-cell:nth-child(7n) {
  border-right: none;
}

.month-cell:hover {
  background: rgba(161, 98, 7, 0.03);
}

.month-cell.is-other {
  background: #faf8f3;
  opacity: 0.55;
}

.month-cell.is-today {
  background: linear-gradient(160deg, #fffbeb, #fef3c7);
}

.month-cell.is-today .month-daynum {
  background: linear-gradient(145deg, #c9a066, #a16207);
  color: #fff;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.28);
}

.month-daynum {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin-bottom: 4px;
}

.month-lessons {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.month-chip {
  width: 100%;
  border: 1px solid #e8e0d0;
  border-left-width: 3px;
  border-radius: 6px;
  padding: 3px 5px;
  text-align: left;
  cursor: pointer;
  font-size: 11px;
  line-height: 1.3;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(41, 37, 36, 0.04);
  transition: box-shadow 0.15s, transform 0.15s;
}

.month-chip:hover {
  box-shadow: 0 3px 8px rgba(161, 98, 7, 0.14);
  transform: translateY(-1px);
}

.mc-time {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
  margin-right: 4px;
  display: inline-block;
}

.mc-name {
  color: var(--oc-ink, #44403c);
}

/* 矩阵课表 */
.matrix-wrap {
  overflow-x: auto;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: var(--oc-card, #fffdf8);
}

.matrix-table {
  width: max-content;
  min-width: 100%;
}

.mx-head,
.mx-row {
  display: grid;
}

.mx-head {
  position: sticky;
  top: 0;
  z-index: 3;
  background: linear-gradient(180deg, #faf6ee, #f5f0e6);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.mx-corner,
.mx-day-head {
  padding: 10px 8px;
  text-align: center;
  border-right: 1px solid var(--oc-border, #e8e0d0);
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.mx-corner {
  text-align: left;
  padding-left: 14px;
  display: flex;
  align-items: center;
  position: sticky;
  left: 0;
  z-index: 4;
  background: linear-gradient(180deg, #faf6ee, #f5f0e6);
  color: var(--oc-primary, #a16207);
  font-weight: 700;
}

.mx-row {
  border-bottom: 1px solid #f0e9dc;
  min-height: 88px;
}

.mx-entity {
  padding: 12px 14px;
  border-right: 1px solid var(--oc-border, #e8e0d0);
  background: #faf8f3;
  display: flex;
  flex-direction: column;
  justify-content: center;
  position: sticky;
  left: 0;
  z-index: 2;
}

.mx-entity-name {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
  word-break: break-all;
}

.mx-entity-sub {
  font-size: 11px;
  color: #d97706;
  margin-top: 4px;
  cursor: default;
}

.mx-cell {
  border-right: 1px solid #f0e9dc;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 88px;
  cursor: default;
  transition: background 0.15s;
  position: relative;
}

.mx-cell.is-empty-hover {
  cursor: pointer;
}

.mx-cell.has-lessons {
  cursor: default;
}

.mx-cell.is-empty-hover:hover {
  background: rgba(161, 98, 7, 0.03);
}

.mx-card {
  width: 100%;
  border: 1px solid #dbbf94;
  border-left-width: 3px;
  border-radius: 9px;
  padding: 7px 9px;
  text-align: left;
  cursor: pointer;
  background: linear-gradient(165deg, #fffdf8, #f5f0e6);
  position: relative;
  z-index: 2;
  box-shadow: 0 2px 5px rgba(41, 37, 36, 0.05);
  transition: box-shadow 0.15s, transform 0.15s, border-color 0.15s;
}

.mx-card:hover {
  box-shadow: 0 5px 14px rgba(161, 98, 7, 0.16);
  border-color: #c9a066;
  transform: translateY(-1px);
}

.mx-card.is-blue {
  border-color: #93c5fd;
}

.mx-card.is-green {
  border-color: #86efac;
}

.mx-card-time {
  font-size: 11px;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
  display: inline-block;
  max-width: 100%;
}

.mx-card-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  margin-top: 2px;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mx-card-meta {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.sch-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.time-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.time-picker {
  flex: 1;
  min-width: 0;
  width: 100%;
}

.time-picker :deep(.el-input__wrapper) {
  width: 100%;
  cursor: pointer;
}

.tilde {
  color: var(--oc-muted, #78716c);
  flex-shrink: 0;
}

.slot-chips {
  margin-top: 10px;
  width: 100%;
}

.slot-chips-label {
  display: block;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 6px;
}

.slot-chips-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.slot-chip {
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fffdf8;
  color: var(--oc-ink, #44403c);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  line-height: 1.4;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.slot-chip:hover {
  border-color: #d4b483;
  color: var(--oc-primary, #a16207);
  background: #faf3e6;
}

.slot-chip.is-active {
  border-color: var(--oc-primary, #a16207);
  background: rgba(161, 98, 7, 0.1);
  color: var(--oc-primary, #a16207);
  font-weight: 600;
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

.weekday-hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.opt-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.opt-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.opt-status {
  font-size: 12px;
  flex-shrink: 0;
}

.opt-status.is-free {
  color: #16a34a;
}

.opt-status.is-free::before {
  content: '● ';
  font-size: 8px;
}

.opt-status.is-busy {
  color: #dc2626;
}

.opt-status.is-busy::before {
  content: '● ';
  font-size: 8px;
}

.form-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 10px 12px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 10px;
  font-size: 12px;
  color: #9a3412;
  line-height: 1.5;
  margin-top: 4px;
}

.form-section {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin: 4px 0 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.mode-radios {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}

.mode-radios :deep(.el-radio-button__inner) {
  border-radius: 8px !important;
  box-shadow: none !important;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 991px) {
  .page-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .toolbar-right {
    width: 100%;
  }

  .toolbar-right .el-button {
    flex: 1;
  }

  .filter-item,
  .filter-select {
    width: 100%;
  }

  .filter-item {
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
  }

  .action-row {
    flex-direction: column;
    align-items: stretch;
  }

  .action-create {
    display: inline-flex;
  }

  .period-nav {
    width: 100%;
    justify-content: center;
  }

  .summary-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .weekday-options {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
