<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createClassApi,
  deleteClassApi,
  listAcademicTeachersApi,
  listClassesApi,
  listCourseEligibleStudentsApi,
  listCoursesApi,
  listRoomsApi,
  updateClassApi,
  type ClassMode,
  type ClassRoom,
  type Course,
  type CourseEligibleStudent,
  type TeacherManage,
} from '../../api/academic'
import AppSheet from '../../components/AppSheet.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { isCompact } = useBreakpoint()

/** 班级管理写操作：与负责人一致（学管师默认有 academic.write） */
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
const rows = ref<ClassRoom[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const selectedIds = ref<number[]>([])

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

async function load() {
  loading.value = true
  try {
    const res = await listClassesApi({
      mode: mode.value,
      q: keyword.value.trim() || undefined,
      course_id: courseFilter.value,
      teacher_id: teacherFilter.value,
      only_mine: onlyMine.value,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
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
    await ElMessageBox.confirm(`确定将选中的 ${selectedIds.value.length} 个班级设为结业？`, '批量结业', {
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
    await ElMessageBox.confirm(`确定删除/归档选中的 ${selectedIds.value.length} 个班级？`, '批量删除', {
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

watch(mode, (next, prev) => {
  page.value = 1
  selectedIds.value = []
  if (prev !== undefined) syncModeToRoute(next)
  void load()
})

// 从详情返回或带 ?mode= 进入时，恢复对应 Tab
watch(
  () => route.query.mode,
  (m) => {
    const next = modeFromQuery(m)
    if (mode.value !== next) mode.value = next
  },
)

onMounted(async () => {
  // 确保地址栏带上当前 mode，便于返回恢复
  if (route.query.mode !== mode.value) {
    syncModeToRoute(mode.value)
  }
  await loadMeta()
  await load()
})
</script>

<template>
  <div class="class-list-page">
    <div class="page-toolbar">
      <div class="toolbar-title-block">
        <el-page-header class="is-title-only" content="班级管理" />
        <p class="page-sub">管理班课与一对一班级 · 排课 / 学员 / 点名</p>
      </div>
      <div class="toolbar-right">
        <el-checkbox v-model="onlyMine" class="mine-check" @change="runQuery">只看我的班级</el-checkbox>
        <el-button class="tb-btn" plain @click="load">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
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

      <div class="filter-panel">
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

      <div class="action-row">
        <div class="action-left">
          <template v-if="mode === 'group'">
            <el-button
              v-if="canManageClass"
              type="primary"
              class="tb-btn tb-btn--primary"
              @click="openCreate"
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
              @click="openCreate"
            >
              <el-icon><Plus /></el-icon>
              新建一对一
            </el-button>
            <el-button v-if="canManageClass" class="tb-btn" plain @click="batchDelete">批量删除</el-button>
          </template>
          <span v-if="selectedIds.length" class="selected-pill">已选 {{ selectedIds.length }}</span>
        </div>
        <div class="summary-chip">
          共 <b>{{ total }}</b> 个{{ mode === 'group' ? '班课' : '一对一' }}班级
        </div>
      </div>

      <!-- wap/pad 卡片 -->
      <div v-if="isCompact" class="m-card-list class-m-list" v-loading="loading">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无班级数据</div>
        <div
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
          <div class="m-card-meta">
            <span><span class="k">老师</span>{{ row.teachers || '待分配' }}</span>
            <span v-if="mode === 'group'">
              <span class="k">人数</span>{{ row.capacity_label }}
            </span>
            <span><span class="k">课次</span>{{ row.scheduled_label }}</span>
            <span><span class="k">已授</span>{{ row.taught_hours }}课时</span>
            <span v-if="mode === 'one_to_one'">
              <span class="k">剩余</span>{{ row.remain_hours }}课时
            </span>
          </div>
          <div class="m-card-actions" @click.stop>
            <el-button v-if="mode === 'group'" size="small" @click="goDetail(row, 'students')">
              学员
            </el-button>
            <el-button size="small" type="primary" plain @click="goRoll(row)">点名</el-button>
            <el-button size="small" @click="goDetail(row)">详情</el-button>
          </div>
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
          <el-table-column label="操作" :width="mode === 'group' ? 210 : 150" fixed="right" align="right">
            <template #default="{ row }">
              <div class="pc-ops">
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

    <AppSheet
      v-model="drawerVisible"
      :title="drawerTitle"
      size="460px"
      modal-class="class-create-drawer"
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
          <el-input v-model="form.category" placeholder="如 培优 / 不指定" />
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
    </AppSheet>
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

.mine-check {
  color: var(--oc-ink, #44403c);
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
}

@media (max-width: 991px) {
  .action-row {
    flex-direction: column;
    align-items: stretch;
  }

  .action-left {
    width: 100%;
  }

  .action-left .el-button {
    flex: 1;
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
