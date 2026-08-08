<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  addClassStudentsApi,
  createClassApi,
  deleteClassApi,
  listAcademicTeachersApi,
  listClassesApi,
  listCourseEligibleStudentsApi,
  listCoursesApi,
  listRoomsApi,
  removeClassStudentApi,
  updateClassApi,
  type ClassMode,
  type ClassRoom,
  type Course,
  type CourseEligibleStudent,
  type TeacherManage,
} from '../../api/academic'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { SCROLL_CHUNK } from '../../composables/useServerPagedList'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { isApp } = useBreakpoint()
const { surface: createSurface, surfaceProps: createSurfaceProps } = useResponsiveSurface({
  dialogMaxWidth: '560px',
  size: '460px',
  modalClass: 'class-create-drawer',
})

/** 班级管理写操作：与负责人一致（学管师默认有 academic.write）*/
const canManageClass = computed(() => auth.hasPermission('academic.write') || auth.isAdmin)

function modeFromQuery(raw: unknown): ClassMode {
  return raw === 'one_to_one' ? 'one_to_one' : 'group'
}

const mode = ref<ClassMode>(modeFromQuery(route.query.mode))
const keyword = ref('')
const courseFilter = ref<number | undefined>()
const teacherFilter = ref<number | undefined>()
const onlyMine = ref(false)
const loading = ref(false)
const loadingMore = ref(false)
const rows = ref<ClassRoom[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const filterVisible = ref(false)
const sentinelRef = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null
const activeFilterCount = computed(() => Number(Boolean(keyword.value.trim())) + Number(Boolean(courseFilter.value)) + Number(Boolean(teacherFilter.value)) + Number(onlyMine.value))
const hasMore = computed(() => rows.value.length < total.value)
const selectedIds = ref<number[]>([])
const assigningId = ref<number | null>(null)

/** 从学生详情「选班调班」进入*/
const assignMode = computed(() => String(route.query.assign || '') === '1')
const assignStudentId = computed(() => {
  const n = Number(route.query.student_id)
  return Number.isInteger(n) && n > 0 ? n : null
})
const assignStudentName = computed(() => String(route.query.student_name || '').trim())
const assignCourseName = computed(() => String(route.query.course_name || '').trim())
const assignFromClassId = computed(() => {
  const n = Number(route.query.from_class_id)
  return Number.isInteger(n) && n > 0 ? n : null
})
const assignFromClassName = computed(() => String(route.query.from_class_name || '').trim())
const assignActionLabel = computed(() => (assignFromClassId.value ? '调班' : '选班'))

const courses = ref<Course[]>([])
const teachers = ref<TeacherManage[]>([])
const rooms = ref<{ name: string }[]>([])
const drawerVisible = ref(false)
const saving = ref(false)
const studentOptions = ref<CourseEligibleStudent[]>([])
const studentSearching = ref(false)
let studentSearchRequest = 0

const form = reactive({
  name: '',
  course_id: undefined as number | undefined,
  capacity: undefined as number | undefined,
  over_capacity: true,
  open_count: undefined as number | undefined,
  category: '',
  hours_per_session: 1,
  default_room: '',
  teacher_ids: [] as number[],
  head_teacher_id: undefined as number | undefined,
  primary_student_id: undefined as number | undefined,
  remark: '',
})

const drawerTitle = computed(() => (mode.value === 'group' ? '新建班级' : '新建一对一'))

const courseOptions = computed(() => {
  if (mode.value === 'group') return courses.value.filter((c) => c.course_type === 'group')
  return courses.value.filter((c) => c.course_type === 'one_to_one')
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function buildClassParams(pageNum: number, size: number) {
  return {
    mode: mode.value,
    q: keyword.value.trim() || undefined,
    course_id: courseFilter.value,
    teacher_id: teacherFilter.value,
    only_mine: onlyMine.value,
    page: pageNum,
    page_size: size,
  }
}

async function load(options?: { append?: boolean }) {
  const append = Boolean(options?.append && isApp.value)
  if (isApp.value && !append) page.value = 1
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const size = isApp.value ? SCROLL_CHUNK : pageSize.value
    const res = await listClassesApi(buildClassParams(page.value, size))
    rows.value = append ? [...rows.value, ...res.items] : res.items
    total.value = res.total
  } catch {
    if (append) page.value = Math.max(1, page.value - 1)
    else {
      rows.value = []
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
  const [c, t, r] = await Promise.all([
    listCoursesApi({ enabled: true, page: 1, page_size: 100 }).catch(() => ({ items: [] as Course[] })),
    listAcademicTeachersApi({ page: 1, page_size: 100 }).catch(() => ({ items: [] as TeacherManage[] })),
    listRoomsApi().catch(() => [] as { name: string }[]),
  ])
  courses.value = c.items
  teachers.value = t.items
  rooms.value = r
}

function onSelectionChange(sel: ClassRoom[]) {
  selectedIds.value = sel.map((r) => r.id)
}

function resetForm() {
  form.name = ''
  form.course_id = undefined
  form.capacity = undefined
  form.over_capacity = true
  form.open_count = undefined
  form.category = ''
  form.hours_per_session = 1
  form.default_room = ''
  form.teacher_ids = []
  form.head_teacher_id = undefined
  form.primary_student_id = undefined
  form.remark = ''
  studentOptions.value = []
}

function openCreate() {
  if (mode.value === 'one_to_one') {
    ElMessage.info('学员报读一对一课程后，会自动创建一对一班级；也可在此手动新建')
  }
  resetForm()
  drawerVisible.value = true
}

function goDetail(row: ClassRoom, tab?: string) {
  void router.push({
    name: 'academic-class-detail',
    params: { id: String(row.id) },
    query: {
      mode: mode.value,
      ...(tab ? { tab } : {}),
    },
  })
}

function goRoll(row: ClassRoom) {
  void router.push({
    path: '/academic/class-records',
    query: { class_id: String(row.id) },
  })
}

function classHasStudent(row: ClassRoom, studentId: number) {
  if (row.primary_student_id === studentId) return true
  return (row.student_ids || []).includes(studentId)
}

function assignButtonLabel(row: ClassRoom) {
  if (!assignStudentId.value) return '加入'
  if (classHasStudent(row, assignStudentId.value)) return '已在此班'
  if (assignFromClassId.value && assignFromClassId.value !== row.id) return '调入此班'
  return '加入此班'
}

async function assignStudentToClass(row: ClassRoom) {
  if (!assignMode.value || !assignStudentId.value) return
  if (!canManageClass.value) {
    ElMessage.warning('无班级管理权限')
    return
  }
  if (row.status === 'graduated') {
    ElMessage.warning('已结业班级不可加入')
    return
  }
  if (classHasStudent(row, assignStudentId.value)) {
    ElMessage.info('该学员已在此班')
    return
  }
  if (mode.value === 'one_to_one' && (row.member_count || 0) >= 1 && row.primary_student_id !== assignStudentId.value) {
    ElMessage.warning('一对一班级已有学员，请另选或新建')
    return
  }

  const name = assignStudentName.value || `学员#${assignStudentId.value}`
  const isTransfer =
    !!assignFromClassId.value && assignFromClassId.value !== row.id
  try {
    await ElMessageBox.confirm(
      isTransfer
        ? `确定将「${name}」从「${assignFromClassName.value || '原班级'}」调入「${row.name}」？`
        : `确定将「${name}」加入班级「${row.name}」？`,
      isTransfer ? '确认调班' : '确认选班',
      { type: 'info', confirmButtonText: isTransfer ? '确认调入' : '确认加入' },
    )
  } catch {
    return
  }

  assigningId.value = row.id
  try {
    if (isTransfer && assignFromClassId.value) {
      try {
        await removeClassStudentApi(assignFromClassId.value, assignStudentId.value)
      } catch {
        // 原班已不在班时忽略，继续加入新班
      }
    }
    await addClassStudentsApi(row.id, [assignStudentId.value])
    ElMessage.success(isTransfer ? `已调入「${row.name}」` : `已加入「${row.name}」`)
    // 更新 from_class，便于继续调班
        await router.replace({
      path: route.path,
      query: {
        ...route.query,
        from_class_id: String(row.id),
        from_class_name: row.name,
      },
    })
    await load()
  } catch {
    /* interceptor */
  } finally {
    assigningId.value = null
  }
}

function exitAssignMode() {
  const q = { ...route.query } as Record<string, string | string[] | undefined>
  delete q.assign
  delete q.student_id
  delete q.student_name
  delete q.course_name
  delete q.from_class_id
  delete q.from_class_name
  // 保留 mode / course_id 便于继续浏览
  void router.replace({ path: route.path, query: q })
}

function openCreateForAssign() {
  openCreate()
  if (assignMode.value && courseFilter.value) {
    form.course_id = courseFilter.value
  }
  if (assignMode.value && mode.value === 'one_to_one' && assignStudentId.value) {
    form.primary_student_id = assignStudentId.value
    // 保证下拉有该学员选项
        if (assignStudentName.value) {
      studentOptions.value = [
        {
          id: assignStudentId.value,
          name: assignStudentName.value,
          grade: '',
          school: '',
          phone: '',
          status: 'active',
          course_id: courseFilter.value || 0,
          has_package: true,
          remain_hours: 0,
          grade_matched: true,
        },
      ]
    }
    if (assignStudentName.value && !form.name) {
      form.name = `${assignStudentName.value}一对一`
    }
  }
}

async function searchStudents(q: string) {
  const keyword = q.trim()
  if (!form.course_id) {
    studentOptions.value = []
    ElMessage.warning('请先选择关联课程')
    return
  }
  const selected = new Set(
    form.primary_student_id ? [form.primary_student_id] : [],
  )
  if (!keyword) {
    studentSearchRequest += 1
    studentSearching.value = false
    studentOptions.value = studentOptions.value.filter((s) => selected.has(s.id))
    return
  }

  const request = ++studentSearchRequest
  studentSearching.value = true
  try {
    const res = await listCourseEligibleStudentsApi(form.course_id, {
      q: keyword,
      page: 1,
      page_size: 20,
    }).catch(() => ({ items: [] as CourseEligibleStudent[] }))
    if (request !== studentSearchRequest) return
    const matches = res.items.filter(
      (s) => s.name.includes(keyword) || (s.phone || '').includes(keyword),
    )
    const selectedOptions = studentOptions.value.filter((s) => selected.has(s.id))
    const resultIds = new Set(matches.map((s) => s.id))
    studentOptions.value = [
      ...matches,
      ...selectedOptions.filter((s) => !resultIds.has(s.id)),
    ]
  } finally {
    if (request === studentSearchRequest) studentSearching.value = false
  }
}

function onCourseChange() {
  form.primary_student_id = undefined
  studentOptions.value = []
}

async function saveDrawer() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入班级名称')
    return
  }
  if (!form.course_id) {
    ElMessage.warning('请选择关联课程')
    return
  }
  if (mode.value === 'one_to_one' && !form.primary_student_id) {
    ElMessage.warning('一对一请选择学员')
    return
  }
  saving.value = true
  try {
    await createClassApi({
      name: form.name.trim(),
      mode: mode.value,
      course_id: form.course_id,
      capacity: form.capacity,
      over_capacity: form.over_capacity,
      open_count: form.open_count,
      category: form.category,
      hours_per_session: form.hours_per_session,
      default_room: form.default_room,
      teacher_ids: form.teacher_ids,
      head_teacher_id: form.head_teacher_id,
      primary_student_id: form.primary_student_id,
      remark: form.remark,
    })
    ElMessage.success('班级已创建')
    drawerVisible.value = false
    await load()
  } catch {
    /* */
  } finally {
    saving.value = false
  }
}

async function onGraduate(row: ClassRoom) {
  try {
    await ElMessageBox.confirm(`确定将班级「${row.name}」设为结业？`, '结业确认', { type: 'warning' })
    await updateClassApi(row.id, { status: 'graduated' })
    ElMessage.success('已结业')
    await load()
  } catch {
    /* */
  }
}

async function onDelete(row: ClassRoom) {
  try {
    await ElMessageBox.confirm(`确定删除/归档班级「${row.name}」？`, '删除确认', { type: 'warning' })
    await deleteClassApi(row.id)
    ElMessage.success('已处理')
    await load()
  } catch {
    /* */
  }
}

async function batchGraduate() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选班级')
    return
  }
  try {
    await ElMessageBox.confirm(`确定将选中的${selectedIds.value.length} 个班级设为结业？`, '批量结业', {
      type: 'warning',
    })
    for (const id of selectedIds.value) {
      await updateClassApi(id, { status: 'graduated' })
    }
    ElMessage.success('批量结业完成')
    selectedIds.value = []
    await load()
  } catch {
    /* */
  }
}

async function batchDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选班级')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除/归档选中的${selectedIds.value.length} 个班级？`, '批量删除', {
      type: 'warning',
    })
    for (const id of selectedIds.value) {
      await deleteClassApi(id)
    }
    ElMessage.success('批量处理完成')
    selectedIds.value = []
    await load()
  } catch {
    /* */
  }
}

function runQuery() {
  page.value = 1
  void load()
}

function resetFilters() {
  keyword.value = ''
  courseFilter.value = undefined
  teacherFilter.value = undefined
  onlyMine.value = false
  runQuery()
}

function syncModeToRoute(next: ClassMode) {
  const cur = modeFromQuery(route.query.mode)
  if (cur === next && route.name === 'academic-classes') return
  void router.replace({
    name: 'academic-classes',
    query: {
      ...route.query,
      mode: next,
    },
  })
}

/** 从学生详情选班入口解析筛选条件*/
function applyAssignQueryFromRoute() {
  const courseId = Number(route.query.course_id)
  if (Number.isInteger(courseId) && courseId > 0) {
    courseFilter.value = courseId
  }
  // 班课选班：按课程列班级，不要用学员姓名当班级名搜索
  // 一对一：可用学员姓名定位已有班级
        if (assignMode.value) {
    if (mode.value === 'one_to_one' && assignStudentName.value) {
      keyword.value = assignStudentName.value
    } else if (mode.value === 'group') {
      keyword.value = ''
    }
  } else {
    const studentQ = String(route.query.student_q || route.query.q || '').trim()
    if (studentQ) keyword.value = studentQ
  }
}

watch(mode, (next, prev) => {
  page.value = 1
  selectedIds.value = []
  if (prev !== undefined) syncModeToRoute(next)
  if (assignMode.value && next === 'group') keyword.value = ''
  void load()
})

// 从详情返回或带?mode= 进入时，恢复对应 Tab
watch(
  () => route.query.mode,
  (m) => {
    const next = modeFromQuery(m)
    if (mode.value !== next) mode.value = next
  },
)

watch(
  () => [route.query.assign, route.query.student_id, route.query.course_id, route.query.student_name],
  () => {
    applyAssignQueryFromRoute()
    page.value = 1
    void load()
  },
)

watch(isApp, async () => {
  selectedIds.value = []
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
  // 确保地址栏带上当前 mode，便于返回恢复
        if (route.query.mode !== mode.value) {
    syncModeToRoute(mode.value)
  }
  applyAssignQueryFromRoute()
  await loadMeta()
  await load()
  await nextTick()
  if (isApp.value) setupScrollObserver()
})

onUnmounted(() => teardownScrollObserver())
</script>

<template>
  <div class="class-list-page">
    <div
      v-if="!isApp || canManageClass"
      class="page-toolbar"
      :class="{ 'is-app-create': isApp && canManageClass }"
    >
      <div v-if="!isApp" class="toolbar-title-block">
        <el-page-header class="is-title-only" content="班级管理" />
        <p class="page-sub">管理班课与一对一班级 · 排课 / 学员 / 点名</p>
      </div>
      <div v-if="!isApp" class="toolbar-right">
        <el-checkbox v-model="onlyMine" class="mine-check" @change="runQuery">只看我的班级</el-checkbox>
        <el-button class="tb-btn" plain @click="load">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <button
        v-if="canManageClass && isApp"
        type="button"
        class="class-entry-cta"
        @click="assignMode ? openCreateForAssign() : openCreate()"
      >
        <span class="class-entry-ico" aria-hidden="true">
          <el-icon><Plus /></el-icon>
        </span>
        <span class="class-entry-copy">
          <strong>{{ mode === 'group' ? '新建班课' : '新建一对一' }}</strong>
          <em>{{ mode === 'group' ? '建班 · 排课 · 学员管理' : '指定学员 · 排课点名' }}</em>
        </span>
        <span class="class-entry-go">
          去创建
          <el-icon><ArrowRight /></el-icon>
        </span>
      </button>
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <el-alert
        v-if="assignMode && assignStudentId"
        type="warning"
        :closable="false"
        show-icon
        class="assign-banner"
      >
        <template #title>
          <span class="assign-banner-title">
            正在为「{{ assignStudentName || `学员#${assignStudentId}` }}」{{ assignActionLabel }}
            <template v-if="assignCourseName"> · 课程 {{ assignCourseName }}</template>
            <template v-if="assignFromClassId">
              · 当前班 {{ assignFromClassName || `#${assignFromClassId}` }}
            </template>
          </span>
        </template>
        <p class="assign-banner-desc">
          {{
            mode === 'group'
              ? '下方列出可选班级，点击「加入此班 / 调入此班」完成操作；班课按课程筛选，可用班级名称继续搜索。'
              : '一对一可搜索已有班级，或点「新建一对一」为该学员建班。'
          }}
        </p>
        <div class="assign-banner-actions">
          <el-button
            v-if="canManageClass"
            type="primary"
            size="small"
            @click="openCreateForAssign"
          >
            {{ mode === 'group' ? '新建班级' : '新建一对一' }}
          </el-button>
          <el-button size="small" @click="exitAssignMode">退出选班</el-button>
          <el-button size="small" text type="primary" @click="router.back()">
            返回学生详情
          </el-button>
        </div>
      </el-alert>

      <el-tabs v-model="mode" class="mode-tabs">
        <el-tab-pane name="group">
          <template #label>
            <span class="tab-label">
              <el-icon><School /></el-icon>
              班课
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane name="one_to_one">
          <template #label>
            <span class="tab-label">
              <el-icon><User /></el-icon>
              一对一
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>

      <div v-if="!isApp" class="filter-panel">
        <div class="filter-row">
          <div class="filter-item">
            <span class="filter-label">{{ mode === 'group' ? '搜索班级' : '搜索学员' }}</span>
            <el-input
              v-model="keyword"
              clearable
              :placeholder="mode === 'group' ? '请输入班级名称' : '请输入学员姓名/手机号'"
              class="filter-search"
              @keyup.enter="runQuery"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
          <div class="filter-item">
            <span class="filter-label">关联课程</span>
            <el-select
              v-model="courseFilter"
              clearable
              filterable
              placeholder="请选择课程"
              class="filter-select"
              @change="runQuery"
            >
              <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">班级老师</span>
            <el-select
              v-model="teacherFilter"
              clearable
              filterable
              placeholder="请选择老师"
              class="filter-select"
              @change="runQuery"
            >
              <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
          </div>
          <el-button type="primary" class="tb-btn tb-btn--primary query-btn" @click="runQuery">
            查询
          </el-button>
        </div>
      </div>

      <CompactFilterBar v-if="isApp" :active-count="activeFilterCount" :total="total" :label="mode === 'group' ? '个班课' : '个一对一班级'" @open="filterVisible = true" />
      <MobileFilterSheet v-model="filterVisible" :active-count="activeFilterCount" @apply="runQuery" @reset="resetFilters">
        <el-form label-position="top" @submit.prevent="runQuery">
          <el-form-item :label="mode === 'group' ? '搜索班级' : '搜索学员'"><el-input v-model="keyword" clearable :placeholder="mode === 'group' ? '班级名称' : '学员姓名 / 手机号'" /></el-form-item>
          <el-form-item label="关联课程"><el-select v-model="courseFilter" clearable filterable placeholder="全部课程"><el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" /></el-select></el-form-item>
          <el-form-item label="班级老师"><el-select v-model="teacherFilter" clearable filterable placeholder="全部老师"><el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" /></el-select></el-form-item>
          <el-form-item><el-checkbox v-model="onlyMine">只看我的班级</el-checkbox></el-form-item>
        </el-form>
      </MobileFilterSheet>

      <div v-if="!isApp" class="action-row">
        <div class="action-left">
          <template v-if="mode === 'group'">
            <el-button
              v-if="canManageClass"
              type="primary"
              class="tb-btn tb-btn--primary"
              @click="assignMode ? openCreateForAssign() : openCreate()"
            >
              <el-icon><Plus /></el-icon>
              添加班级
            </el-button>
            <el-button v-if="canManageClass" class="tb-btn" plain @click="batchGraduate">批量结业</el-button>
            <el-button v-if="canManageClass" class="tb-btn" plain @click="batchDelete">批量删除</el-button>
          </template>
          <template v-else>
            <el-button
              v-if="canManageClass"
              type="primary"
              class="tb-btn tb-btn--primary"
              @click="assignMode ? openCreateForAssign() : openCreate()"
            >
              <el-icon><Plus /></el-icon>
              新建一对一
            </el-button>
            <el-button v-if="canManageClass" class="tb-btn" plain @click="batchDelete">批量删除</el-button>
          </template>
          <span v-if="selectedIds.length" class="selected-pill">已选{{ selectedIds.length }}</span>
        </div>
        <div class="summary-chip">
          共 <b>{{ total }}</b> 个{{ mode === 'group' ? '班课' : '一对一' }}班级
        </div>
      </div>

      <!-- wap/pad 卡片 -->
      <div v-if="isApp" class="m-card-list class-m-list" v-loading="loading">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty class-empty oc-app-empty">
          <span class="class-empty-ico" aria-hidden="true">🏫</span>
          <strong>暂无{{ mode === 'group' ? '班课' : '一对一' }}班级</strong>
          <em>
            {{
              assignMode
                ? '可新建班级或调整筛选条件后重试'
                : activeFilterCount
                  ? '当前筛选没有匹配班级，可清空筛选后重试'
                  : mode === 'group'
                    ? '创建班课后可排课、加学员、点名课消'
                    : '学员报读后可自动建班，也可手动新建一对一'
            }}
          </em>
          <el-button
            v-if="canManageClass"
            type="primary"
            class="tb-btn tb-btn--primary class-empty-cta"
            @click="assignMode ? openCreateForAssign() : openCreate()"
          >
            <el-icon><Plus /></el-icon>
            {{ mode === 'group' ? '添加班级' : '新建一对一' }}
          </el-button>
        </div>
        <article
          v-for="row in rows"
          :key="row.id"
          class="m-card class-m-card"
          @click="goDetail(row)"
        >
          <div class="m-card-head">
            <div class="class-m-who">
              <span class="name-avatar" :class="mode === 'group' ? 'is-group' : 'is-oto'">
                {{ (row.name || '?').slice(0, 1) }}
              </span>
              <div class="class-m-text">
                <div class="m-card-title">
                  {{ row.name }}
                  <el-tag
                    v-if="row.status === 'graduated'"
                    size="small"
                    type="info"
                    effect="plain"
                    round
                  >
                    结业
                  </el-tag>
                </div>
                <div class="class-m-sub">
                  {{ row.course_name || '未关联课程' }}
                  <template v-if="mode === 'one_to_one' && row.student_name">
                    · {{ row.student_name }}
                  </template>
                </div>
              </div>
            </div>
            <el-icon class="class-m-chevron"><ArrowRight /></el-icon>
          </div>
          <div class="class-m-chips oc-meta-chips">
            <span class="cm-chip oc-meta-chip">老师 {{ row.teachers || '待分配' }}</span>
            <span v-if="mode === 'group'" class="cm-chip oc-meta-chip">人数 {{ row.capacity_label }}</span>
            <span class="cm-chip oc-meta-chip">课次 {{ row.scheduled_label }}</span>
            <span class="cm-chip oc-meta-chip">已授 {{ row.taught_hours }} 课时</span>
            <span v-if="mode === 'one_to_one'" class="cm-chip oc-meta-chip">剩余 {{ row.remain_hours }} 课时</span>
            <span v-if="row.category" class="cm-chip oc-meta-chip">{{ row.category }}</span>
          </div>
          <div class="m-card-actions" @click.stop>
            <el-button
              v-if="assignMode && assignStudentId && canManageClass"
              size="small"
              type="warning"
              :disabled="classHasStudent(row, assignStudentId) || row.status === 'graduated'"
              :loading="assigningId === row.id"
              @click="assignStudentToClass(row)"
            >
              {{ assignButtonLabel(row) }}
            </el-button>
            <el-button v-if="mode === 'group'" size="small" @click="goDetail(row, 'students')">
              学员
            </el-button>
            <el-button size="small" type="primary" plain @click="goRoll(row)">点名</el-button>
            <el-button size="small" @click="goDetail(row)">详情</el-button>
          </div>
        </article>
        <div ref="sentinelRef" class="list-load-sentinel">
          <ListLoadStatus
            :has-more="hasMore"
            :loading="loadingMore"
            :loaded="rows.length"
            :total="total"
            @more="loadMore"
            @retry="loadMore"
          />
        </div>
      </div>

      <div v-else class="table-wrap oc-compact-table-wrap">
        <el-table
          :data="rows"
          row-key="id"
          stripe
          border
          class="data-table class-table"
          :header-cell-style="pcHeaderStyle"
          empty-text="暂无班级数据"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="44" fixed />
          <el-table-column prop="name" label="班级名称" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <button type="button" class="link-name" @click="goDetail(row)">
                <span class="name-avatar" :class="mode === 'group' ? 'is-group' : 'is-oto'">
                  {{ (row.name || '?').slice(0, 1) }}
                </span>
                <span class="name-text">{{ row.name }}</span>
                <el-tag
                  v-if="row.status === 'graduated'"
                  size="small"
                  type="info"
                  effect="plain"
                  class="status-tag"
                >
                  结业
                </el-tag>
              </button>
            </template>
          </el-table-column>
          <el-table-column prop="course_name" label="关联课程" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.course_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            v-if="mode === 'one_to_one'"
            prop="student_name"
            label="学员姓名"
            width="100"
          >
            <template #default="{ row }">
              <span class="cell-strong">{{ row.student_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="mode === 'one_to_one'" prop="phone" label="手机号" width="120">
            <template #default="{ row }">
              <span class="cell-muted">{{ row.phone || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="teachers" label="班级老师" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="cell-muted">{{ row.teachers || '待分配' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            v-if="mode === 'group'"
            prop="capacity_label"
            label="人数/容量"
            width="120"
            align="center"
          >
            <template #default="{ row }">
              <span class="cap-pill">{{ row.capacity_label }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="scheduled_label" label="已上/排课课次" width="120" align="center">
            <template #default="{ row }">
              <span class="schedule-pill">{{ row.scheduled_label }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="taught_hours" label="已授课时" width="96" align="center">
            <template #default="{ row }">
              <span class="hours-num">{{ row.taught_hours }}</span>
            </template>
          </el-table-column>
          <el-table-column
            v-if="mode === 'one_to_one'"
            prop="remain_hours"
            label="剩余课时"
            width="96"
            align="center"
          >
            <template #default="{ row }">
              <span class="hours-remain">{{ row.remain_hours }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="category" label="班级分类" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.category" size="small" effect="plain" type="warning" class="cat-tag">
                {{ row.category }}
              </el-tag>
              <span v-else class="cell-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column
            v-if="mode === 'one_to_one'"
            label="上课时长"
            width="90"
            align="center"
          >
            <template #default>
              <span class="cell-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            :width="assignMode ? (mode === 'group' ? 280 : 220) : mode === 'group' ? 210 : 150"
            fixed="right"
            align="right"
          >
            <template #default="{ row }">
              <div class="pc-ops">
                <template v-if="assignMode && assignStudentId && canManageClass">
                  <el-button
                    link
                    type="warning"
                    :disabled="classHasStudent(row, assignStudentId) || row.status === 'graduated'"
                    :loading="assigningId === row.id"
                    @click="assignStudentToClass(row)"
                  >
                    {{ assignButtonLabel(row) }}
                  </el-button>
                  <span class="op-sep" />
                </template>
                <template v-if="mode === 'group'">
                  <el-button link type="primary" @click="goDetail(row, 'students')">学员管理</el-button>
                  <span class="op-sep" />
                  <el-button link type="primary" @click="goRoll(row)">点名</el-button>
                </template>
                <template v-else>
                  <el-button link type="primary" @click="goRoll(row)">点名</el-button>
                </template>
                <template v-if="canManageClass">
                  <span class="op-sep" />
                  <el-dropdown trigger="click">
                    <el-button link type="primary">
                      更多
                      <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item @click="onGraduate(row)">结业</el-dropdown-item>
                        <el-dropdown-item divided @click="onDelete(row)">删除</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </template>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <PcPagerBar
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="load"
    />

    <component
      :is="createSurface"
      v-model="drawerVisible"
      v-bind="createSurfaceProps"
      :title="drawerTitle"
      :class="isApp ? undefined : 'class-create-dialog'"
      destroy-on-close
    >
      <el-alert
        v-if="mode === 'one_to_one'"
        type="warning"
        :closable="false"
        show-icon
        class="create-tip"
        title="学员报读一对一课程后，会自动创建一对一班级"
      />
      <el-form label-position="top" class="create-form">
        <div class="form-section">
          <span class="sec-dot" />
          基本信息
        </div>
        <el-form-item label="班级名称" required>
          <el-input v-model="form.name" placeholder="请输入班级名称" />
        </el-form-item>
        <el-form-item label="关联课程" required>
          <el-select v-model="form.course_id" filterable placeholder="请选择关联课程" style="width: 100%" @change="onCourseChange">
            <el-option
              v-for="c in courseOptions.length ? courseOptions : courses"
              :key="c.id"
              :label="`${c.name}（${c.type_label}）`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="mode === 'group'" label="班级容量">
          <div class="inline-fields">
            <el-input-number
              v-model="form.capacity"
              :min="1"
              controls-position="right"
              placeholder="容量"
            />
            <el-radio-group v-model="form.over_capacity">
              <el-radio :value="true">可超额</el-radio>
              <el-radio :value="false">不可超额</el-radio>
            </el-radio-group>
          </div>
        </el-form-item>
        <el-form-item v-if="mode === 'group'" label="开课人数">
          <el-input-number v-model="form.open_count" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="班级分类">
          <el-input v-model="form.category" placeholder="如：培优 / 不指定" />
        </el-form-item>

        <div class="form-section">
          <span class="sec-dot" />
          上课信息
        </div>
        <el-form-item label="授课课时">
          <el-input-number
            v-model="form.hours_per_session"
            :min="0.01"
            :step="0.25"
            :precision="2"
            controls-position="right"
          />
          <span class="field-hint">单次课次默认扣课时，默认 1（与上课墙钟时长无关）</span>
        </el-form-item>
        <el-form-item label="上课教室">
          <el-select
            v-model="form.default_room"
            filterable
            clearable
            allow-create
            default-first-option
            placeholder="不指定"
            style="width: 100%"
          >
            <el-option v-for="r in rooms" :key="r.name" :label="r.name" :value="r.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="班级老师">
          <el-select
            v-model="form.teacher_ids"
            multiple
            filterable
            placeholder="添加老师"
            style="width: 100%"
          >
            <el-option v-for="t in teachers" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="mode === 'one_to_one'" label="学员" required>
          <el-select
            v-model="form.primary_student_id"
            filterable
            remote
            :remote-method="searchStudents"
            :loading="studentSearching"
            :reserve-keyword="false"
            placeholder="搜索学员姓名/手机"
            style="width: 100%"
          >
            <el-option
              v-for="s in studentOptions"
              :key="s.id"
              :label="`${s.name}${s.phone ? ' · ' + s.phone : ''} · 剩余${s.remain_hours}课时`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveDrawer">保存</el-button>
      </template>
    </component>
  </div>
</template>

<style scoped>
.class-list-page {
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
  gap: 12px;
  flex-wrap: wrap;
}

/* ── App 新建班级 CTA ── */
.class-entry-cta {
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

.class-entry-cta:active {
  transform: scale(0.985);
}

.class-entry-ico {
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

.class-entry-copy {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.class-entry-copy strong {
  font-size: 15px;
  font-weight: 750;
  color: #44403c;
  line-height: 1.25;
}

.class-entry-copy em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
  line-height: 1.3;
}

.class-entry-go {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  color: #a16207;
  background: rgba(255, 253, 248, 0.92);
  border: 1px solid rgba(161, 98, 7, 0.22);
}

.mine-check {
  color: var(--oc-ink, #44403c);
}

.assign-banner {
  margin-bottom: 14px;
}

.assign-banner-title {
  font-weight: 650;
  color: #8b5406;
}

.assign-banner-desc {
  margin: 6px 0 10px;
  font-size: 13px;
  color: #78716c;
  line-height: 1.5;
}

.assign-banner-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

.mode-tabs {
  margin-bottom: 4px;
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

.filter-panel {
  background: linear-gradient(180deg, #faf6ee 0%, #f7f1e6 100%);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 14px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
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

.filter-search {
  width: min(240px, 100%);
}

.filter-select {
  width: 180px;
}

.query-btn {
  margin-left: 2px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  align-items: center;
  justify-content: space-between;
}

.action-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.selected-pill {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f2e8d6;
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  font-weight: 600;
}

.summary-chip {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.summary-chip b {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
}

.table-wrap {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.class-m-list {
  margin-top: 4px;
}

.class-m-card {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.class-m-card:active {
  border-color: #e6d2b3;
}

.class-m-who {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.class-m-text {
  min-width: 0;
}

.class-m-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.class-m-chevron {
  color: #a8a29e;
  flex-shrink: 0;
  margin-top: 4px;
}

.class-m-card .m-card-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.class-m-card .m-card-head {
  margin-bottom: 0;
  align-items: flex-start;
}

.class-m-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.cm-chip {
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

.class-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 36px 20px !important;
  text-align: center;
}

.class-empty-ico {
  font-size: 28px;
  line-height: 1;
  filter: grayscale(0.15);
}

.class-empty strong {
  font-size: 15px;
  font-weight: 700;
  color: #44403c;
}

.class-empty em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
  line-height: 1.4;
  max-width: 260px;
}

.class-empty-cta {
  margin-top: 10px;
  min-height: 42px;
  border-radius: 12px;
  font-weight: 700;
}

/* ── WAP / Pad 班级列表 App 化 ── */
@media (max-width: 1199px) {
  .class-list-page {
    display: grid;
    gap: 10px;
  }

  .page-toolbar {
    margin: 0;
  }

  .page-toolbar.is-app-create {
    padding: 0;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .page-sub {
    display: none;
  }

  .class-entry-cta {
    display: flex;
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

  .mode-tabs {
    margin: 0 0 10px;
    padding: 4px;
    border-radius: 14px;
    border: 1px solid rgba(181, 145, 83, 0.2);
    background: #f3ebe0;
  }

  .mode-tabs :deep(.el-tabs__header) {
    margin: 0;
  }

  .mode-tabs :deep(.el-tabs__nav-wrap::after) {
    display: none;
  }

  .mode-tabs :deep(.el-tabs__active-bar) {
    display: none;
  }

  .mode-tabs :deep(.el-tabs__nav) {
    width: 100%;
    display: flex;
  }

  .mode-tabs :deep(.el-tabs__item) {
    flex: 1;
    height: 40px;
    line-height: 40px;
    padding: 0 12px !important;
    border-radius: 11px;
    justify-content: center;
    color: #78716c;
    font-weight: 650;
  }

  .mode-tabs :deep(.el-tabs__item.is-active) {
    color: #fffdf8 !important;
    background: linear-gradient(145deg, #c07a12, #a16207);
    box-shadow: 0 4px 12px rgba(161, 98, 7, 0.25);
  }

  .mode-tabs :deep(.tab-label) {
    justify-content: center;
  }

  .action-row {
    flex-direction: column;
    align-items: stretch;
  }

  .action-left {
    width: 100%;
  }

  .action-left .el-button {
    flex: 1;
    min-height: 40px;
  }

  .filter-panel .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-item,
  .filter-search,
  .filter-select,
  .query-btn {
    width: 100% !important;
  }

  .m-card-list {
    gap: 12px;
  }

  .class-m-card {
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

  .class-m-card .m-card-actions {
    display: grid !important;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(181, 145, 83, 0.14);
  }

  .class-m-card .m-card-actions .el-button {
    width: 100%;
    margin: 0;
    min-height: 42px;
    border-radius: 12px;
    font-weight: 700;
  }

  .class-m-card .m-card-actions .el-button:only-child {
    grid-column: 1 / -1;
  }

  .class-m-card .m-card-actions .el-button--primary.is-plain {
    background: linear-gradient(180deg, #fffefb, #faf3e6);
    border-color: rgba(161, 98, 7, 0.28);
    color: #a16207;
  }

  .name-avatar {
    width: 42px;
    height: 42px;
    border-radius: 13px;
    font-size: 16px;
    box-shadow: 0 4px 10px rgba(161, 98, 7, 0.16);
  }

  .assign-banner-actions .el-button {
    min-height: 40px;
    border-radius: 12px;
  }
}

.class-table {
  --el-table-border-color: #f0e9dc;
}

.class-table :deep(.el-table__row:hover > td.el-table__cell) {
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
}

.name-avatar.is-group {
  background: linear-gradient(145deg, #b88239, #a16207);
}

.name-avatar.is-oto {
  background: linear-gradient(145deg, #78716c, #57534e);
}

.name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-tag {
  flex-shrink: 0;
}

.cell-muted {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.cell-strong {
  color: var(--oc-ink, #44403c);
  font-weight: 600;
}

.cap-pill,
.schedule-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #f5f0e6;
  color: var(--oc-ink, #44403c);
  border: 1px solid #e8e0d0;
}

.schedule-pill {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #9a3412;
}

.hours-num {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.hours-remain {
  color: #16a34a;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.cat-tag {
  border-radius: 6px;
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

.create-tip {
  margin-bottom: 14px;
  border-radius: 10px;
}

.form-section {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin: 4px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.sec-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 3px rgba(161, 98, 7, 0.15);
}

.inline-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.field-hint {
  margin-left: 8px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.create-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

@media (max-width: 768px) {
  .filter-search,
  .filter-select {
    width: 100%;
  }

  .filter-item {
    width: 100%;
  }
}
</style>
