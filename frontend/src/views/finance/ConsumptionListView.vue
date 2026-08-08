<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getConsumptionDetailApi,
  listConsumptionsApi,
  type CourseConsumption,
  type CourseConsumptionDetail,
} from '../../api/finance'
import {
  listAcademicTeachersApi,
  listClassesApi,
  listCoursesApi,
  type ClassRoom,
  type Course,
  type TeacherManage,
} from '../../api/academic'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import { SCROLL_CHUNK } from '../../composables/useServerPagedList'

const { isApp } = useBreakpoint()
const { surface: detailSurface, surfaceProps: detailSurfaceProps } = useResponsiveSurface({
  dialogWidth: '760px',
  dialogMaxWidth: '760px',
  compactSize: '92%',
  modalClass: 'consume-detail-sheet',
  size: '520px',
})
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const loadingMore = ref(false)
const optionLoading = ref(false)
const exporting = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const rows = ref<CourseConsumption[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalAmount = ref(0)
const sentinelRef = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null
const hasMore = computed(() => rows.value.length < total.value)
const classes = ref<ClassRoom[]>([])
const courses = ref<Course[]>([])
const teachers = ref<TeacherManage[]>([])
const detail = ref<CourseConsumptionDetail | null>(null)
const filterVisible = ref(false)

const filters = reactive({
  student: '',
  class_id: undefined as number | undefined,
  course_id: undefined as number | undefined,
  course_type: '',
  teacher_id: undefined as number | undefined,
  consume_type: '',
  source: '',
  status: '',
  hide_void: true,
  date_range: [] as string[],
  grade: '',
  subject: '',
  term: '',
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const grades = computed(() => uniqueOptions(courses.value.map((item) => item.grade)))
const subjects = computed(() => uniqueOptions(courses.value.map((item) => item.subject)))
const terms = computed(() => uniqueOptions(courses.value.map((item) => item.term)))
const activeFilterCount = computed(() =>
  Number(Boolean(filters.student.trim())) +
  Number(Boolean(filters.date_range.length)) +
  Number(Boolean(filters.class_id)) +
  Number(Boolean(filters.course_id)) +
  Number(Boolean(filters.course_type)) +
  Number(Boolean(filters.teacher_id)) +
  Number(Boolean(filters.consume_type)) +
  Number(Boolean(filters.source)) +
  Number(Boolean(filters.status)) +
  Number(Boolean(filters.grade)) +
  Number(Boolean(filters.subject)) +
  Number(Boolean(filters.term)),
)

function uniqueOptions(values: Array<string | undefined | null>) {
  return Array.from(new Set(values.map((v) => (v || '').trim()).filter(Boolean)))
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return String(v)
  }
}

function formatShortTime(v?: string | null) {
  if (!v) return '—'
  try {
    const d = new Date(v)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return String(v)
  }
}

function formatMoney(n?: number | null) {
  return Number(n || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatHours(n?: number | null) {
  return `${Number(n || 0).toLocaleString('zh-CN', { maximumFractionDigits: 4 })}课时`
}

function classTime(row: CourseConsumptionDetail | null) {
  if (!row?.class_start && !row?.class_end) return '—'
  if (!row.class_end) return formatShortTime(row.class_start)
  return `${formatShortTime(row.class_start)} ~ ${formatShortTime(row.class_end)}`
}

async function loadOptions() {
  optionLoading.value = true
  try {
    // 筛选项：无教务权时静默失败，不弹「无权限」（主列表靠 finance.read）
    const silent = { skipErrorToast: true }
    const [classRes, courseRes, teacherRes] = await Promise.all([
      listClassesApi({ page: 1, page_size: 100 }, silent).catch(() => ({
        items: [] as ClassRoom[],
      })),
      listCoursesApi({ enabled: true, page: 1, page_size: 100 }, silent).catch(() => ({
        items: [] as Course[],
      })),
      listAcademicTeachersApi({ page: 1, page_size: 100 }, silent).catch(() => ({
        items: [] as TeacherManage[],
      })),
    ])
    classes.value = classRes.items
    courses.value = courseRes.items
    teachers.value = teacherRes.items
  } finally {
    optionLoading.value = false
  }
}

function listParams(pageNum: number, size: number) {
  const [startDate, endDate] = filters.date_range || []
  return {
    student_q: filters.student.trim() || undefined,
    class_id: filters.class_id,
    course_id: filters.course_id,
    course_type: filters.course_type || undefined,
    teacher_id: filters.teacher_id,
    consume_type: filters.consume_type || undefined,
    source: filters.source || undefined,
    status: filters.status || undefined,
    hide_void: filters.hide_void,
    start_date: startDate || undefined,
    end_date: endDate || undefined,
    grade: filters.grade || undefined,
    subject: filters.subject || undefined,
    term: filters.term || undefined,
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
    const res = await listConsumptionsApi(listParams(page.value, size))
    rows.value = append ? [...rows.value, ...res.items] : res.items
    total.value = res.total
    if (!append) totalAmount.value = res.summary?.amount ?? 0
  } catch {
    if (append) page.value = Math.max(1, page.value - 1)
    else {
      rows.value = []
      total.value = 0
      totalAmount.value = 0
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

function csvCell(value: unknown) {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

function exportFileName() {
  const [startDate, endDate] = filters.date_range || []
  const stamp = new Date()
  const y = stamp.getFullYear()
  const m = String(stamp.getMonth() + 1).padStart(2, '0')
  const d = String(stamp.getDate()).padStart(2, '0')
  if (startDate && endDate) return `课消记录_${startDate}_${endDate}.csv`
  return `课消记录_${y}${m}${d}.csv`
}

async function exportList() {
  exporting.value = true
  try {
    const items: CourseConsumption[] = []
    let current = 1
    let count = 0
    do {
      const res = await listConsumptionsApi(listParams(current, 100))
      items.push(...res.items)
      count = res.total
      current += 1
    } while (items.length < count)

    if (!items.length) {
      ElMessage.warning('当前筛选条件下暂无可导出数据')
      return
    }

    const csvRows = [
      [
        '课消时间',
        '学员姓名',
        '所在班级',
        '课程名称',
        '上课老师',
        '课消类型',
        '课消来源',
        '消耗额度',
        '欠课时',
        '课消金额(元)',
        '状态',
        '创建时间',
      ],
      ...items.map((row) => [
        formatTime(row.consumed_at),
        row.student || '',
        row.class_name || '',
        row.course_name || '',
        row.teacher || '',
        row.consume_type || '',
        row.source || '',
        row.hours_label || formatHours(row.hours),
        row.uncovered_hours || 0,
        Number(row.amount || 0).toFixed(2),
        row.status_label || row.status || '',
        formatTime(row.created_at),
      ]),
    ]
    const csv = `\uFEFF${csvRows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = exportFileName()
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出${items.length} 条课消记录`)
  } catch {
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

function runQuery() {
  page.value = 1
  void load()
}

function resetFilters() {
  filters.student = ''
  filters.class_id = undefined
  filters.course_id = undefined
  filters.course_type = ''
  filters.teacher_id = undefined
  filters.consume_type = ''
  filters.source = ''
  filters.status = ''
  filters.hide_void = true
  filters.date_range = []
  filters.grade = ''
  filters.subject = ''
  filters.term = ''
  runQuery()
}

async function openDetail(row: CourseConsumption) {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getConsumptionDetailApi(row.id)
  } finally {
    detailLoading.value = false
  }
}

function goOrder(orderId?: number | null) {
  if (orderId) void router.push(`/finance/orders/${orderId}`)
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
  const studentQ = String(route.query.student || route.query.student_q || '').trim()
  if (studentQ) filters.student = studentQ
  const courseId = Number(route.query.course_id)
  if (Number.isFinite(courseId) && courseId > 0) filters.course_id = courseId
  void loadOptions()
  await load()
  await nextTick()
  if (isApp.value) setupScrollObserver()
})

onUnmounted(() => teardownScrollObserver())
</script>

<template>
  <div class="consume-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="课消记录" />
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading || optionLoading">
      <div v-if="!isApp" class="filter-grid">
        <label class="filter-item">
          <span>搜索学员</span>
          <el-input
            v-model="filters.student"
            clearable
            placeholder="请输入学员姓名手机号"
            @keyup.enter="runQuery"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </label>
        <label class="filter-item">
          <span>课消日期</span>
          <el-date-picker
            v-model="filters.date_range"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="~"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            clearable
          />
        </label>
        <label class="filter-item">
          <span>班级名称</span>
          <el-select v-model="filters.class_id" clearable filterable placeholder="请选择班级">
            <el-option v-for="item in classes" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>报名课程</span>
          <el-select v-model="filters.course_id" clearable filterable placeholder="请选择课程">
            <el-option v-for="item in courses" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课程类型</span>
          <el-select v-model="filters.course_type" clearable placeholder="请选择类型">
            <el-option label="班课" value="group" />
            <el-option label="一对一" value="one_to_one" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>上课老师</span>
          <el-select v-model="filters.teacher_id" clearable filterable placeholder="请选择老师">
            <el-option v-for="item in teachers" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课消类型</span>
          <el-select v-model="filters.consume_type" clearable placeholder="请选择类型">
            <el-option label="课时课消" value="课时课消" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课消来源</span>
          <el-select v-model="filters.source" clearable placeholder="请选择课消来源">
            <el-option label="点名" value="点名" />
            <el-option label="手动" value="手动" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课消状态：</span>
          <el-select v-model="filters.status" clearable placeholder="请选择状态">
            <el-option label="正常" value="normal" />
            <el-option label="已作废" value="void" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>年级</span>
          <el-select v-model="filters.grade" clearable filterable placeholder="请选择年级">
            <el-option v-for="item in grades" :key="item" :label="item" :value="item" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>科目</span>
          <el-select v-model="filters.subject" clearable filterable placeholder="请选择科目">
            <el-option v-for="item in subjects" :key="item" :label="item" :value="item" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>学期</span>
          <el-select v-model="filters.term" clearable filterable placeholder="请选择学期">
            <el-option v-for="item in terms" :key="item" :label="item" :value="item" />
          </el-select>
        </label>
      </div>

      <div v-if="!isApp" class="filter-actions">
        <el-checkbox v-model="filters.hide_void" @change="runQuery">过滤已作废</el-checkbox>
        <el-button :icon="'RefreshLeft'" @click="resetFilters">重置</el-button>
        <el-button type="primary" :icon="'Search'" @click="runQuery">查询</el-button>
        <el-button :icon="'Download'" :loading="exporting" @click="exportList">导出</el-button>
      </div>

      <CompactFilterBar v-if="isApp" :active-count="activeFilterCount" :total="total" label="条课消" @open="filterVisible = true" />
      <MobileFilterSheet v-model="filterVisible" :active-count="activeFilterCount" @apply="runQuery" @reset="resetFilters">
        <el-form label-position="top">
          <el-form-item label="搜索学员"><el-input v-model="filters.student" clearable placeholder="姓名 / 手机号" /></el-form-item>
          <el-form-item label="课消日期"><el-date-picker v-model="filters.date_range" type="daterange" value-format="YYYY-MM-DD" range-separator="~" start-placeholder="开始日期" end-placeholder="结束日期" clearable /></el-form-item>
          <el-form-item label="班级"><el-select v-model="filters.class_id" clearable filterable placeholder="全部班级"><el-option v-for="item in classes" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="课程"><el-select v-model="filters.course_id" clearable filterable placeholder="全部课程"><el-option v-for="item in courses" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="课程类型"><el-select v-model="filters.course_type" clearable placeholder="全部类型"><el-option label="班课" value="group" /><el-option label="一对一" value="one_to_one" /></el-select></el-form-item>
          <el-form-item label="上课老师"><el-select v-model="filters.teacher_id" clearable filterable placeholder="全部老师"><el-option v-for="item in teachers" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="课消来源"><el-select v-model="filters.source" clearable placeholder="全部来源"><el-option label="点名" value="点名" /><el-option label="手动" value="手动" /></el-select></el-form-item>
          <el-form-item label="课消状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option label="正常" value="normal" /><el-option label="已作废" value="void" /></el-select></el-form-item>
          <el-form-item label="年级"><el-select v-model="filters.grade" clearable filterable placeholder="全部年级"><el-option v-for="item in grades" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="科目"><el-select v-model="filters.subject" clearable filterable placeholder="全部科目"><el-option v-for="item in subjects" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item label="学期"><el-select v-model="filters.term" clearable filterable placeholder="全部学期"><el-option v-for="item in terms" :key="item" :label="item" :value="item" /></el-select></el-form-item>
          <el-form-item><el-checkbox v-model="filters.hide_void">过滤已作废</el-checkbox></el-form-item>
        </el-form>
      </MobileFilterSheet>

      <div class="summary-bar">
        课消金额(元)
        <strong>{{ formatMoney(totalAmount) }}</strong>
      </div>

      <div v-if="isApp" class="m-card-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty oc-app-empty">
          <span class="consume-empty-ico" aria-hidden="true">📚</span>
          <strong>暂无课消记录</strong>
          <em>{{ activeFilterCount ? '当前筛选没有匹配课消，可清空条件后重试' : '点名扣课后会出现在这里' }}</em>
        </div>
        <button v-for="row in rows" :key="row.id" type="button" class="m-card consume-card" @click="openDetail(row)">
          <div class="m-card-head">
            <div class="consume-who">
              <span class="name-avatar">{{ (row.student || '?').slice(0, 1) }}</span>
              <div>
                <div class="m-card-title">{{ row.student || '—' }}</div>
                <div class="consume-sub">{{ formatTime(row.consumed_at) }}</div>
              </div>
            </div>
            <span class="pc-mono">¥ {{ formatMoney(row.amount) }}</span>
          </div>
          <div class="oc-meta-chips consume-chips">
            <span v-if="row.class_name" class="oc-meta-chip">{{ row.class_name }}</span>
            <span v-if="row.course_name" class="oc-meta-chip">{{ row.course_name }}</span>
            <span v-if="row.teacher" class="oc-meta-chip">老师 {{ row.teacher }}</span>
            <span class="oc-meta-chip is-gold">{{ row.hours_label || formatHours(row.hours) }}</span>
            <span v-if="row.source" class="oc-meta-chip">{{ row.source }}</span>
            <span v-if="row.uncovered_hours > 0" class="oc-meta-chip is-danger">欠 {{ row.uncovered_hours }} 课时</span>
          </div>
        </button>
        <div ref="sentinelRef" class="list-load-sentinel"><ListLoadStatus :has-more="hasMore"
          :loading="loadingMore"
          :loaded="rows.length"
          :total="total"
          @more="loadMore"
          @retry="loadMore"
        /></div>
      </div>

      <div v-else class="oc-compact-table-wrap">
        <el-table :data="rows" row-key="id" stripe border :header-cell-style="pcHeaderStyle">
          <el-table-column label="课消时间" width="160">
            <template #default="{ row }">{{ formatTime(row.consumed_at) }}</template>
          </el-table-column>
          <el-table-column prop="student" label="学员姓名" width="120" />
          <el-table-column prop="class_name" label="所在班级" min-width="150" show-overflow-tooltip />
          <el-table-column prop="course_name" label="课程名称" min-width="150" show-overflow-tooltip />
          <el-table-column prop="teacher" label="上课老师" min-width="180" show-overflow-tooltip />
          <el-table-column prop="consume_type" label="课消类型" width="110" />
          <el-table-column prop="source" label="课消来源" width="100" align="center" />
          <el-table-column prop="hours_label" label="消耗额度" width="120" />
          <el-table-column label="欠课时" width="90" align="right">
            <template #default="{ row }">
              <span :class="{ shortage: row.uncovered_hours > 0 }">{{ row.uncovered_hours || 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="课消金额(元)" width="130" align="right">
            <template #default="{ row }">
              <span class="pc-mono">{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right" align="center">
            <template #default="{ row }">
              <el-button type="primary" link @click="openDetail(row)">查看详情</el-button>
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
      :is="detailSurface"
      v-model="detailVisible"
      v-bind="detailSurfaceProps"
      title="课消详情"
    >
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="detail-hero">
            <div class="detail-hero-main">
              <strong>{{ detail.student || '—' }}</strong>
              <span>{{ detail.course_name || '未关联课程' }}</span>
            </div>
            <span class="detail-hero-amt">¥ {{ formatMoney(detail.amount) }}</span>
          </div>
          <div class="oc-meta-chips detail-chips">
            <span class="oc-meta-chip">来源 {{ detail.source || '—' }}</span>
            <span class="oc-meta-chip is-gold">{{ formatHours(detail.hours) }}</span>
            <span v-if="detail.class_name" class="oc-meta-chip">{{ detail.class_name }}</span>
            <span v-if="detail.teacher" class="oc-meta-chip">老师 {{ detail.teacher }}</span>
          </div>
          <div class="detail-panel">
            <div class="detail-grid">
              <div><span>上课时间</span>{{ classTime(detail) }}</div>
              <div><span>到课状态</span>{{ detail.attendance_status_label || detail.status_label || detail.status || '—' }}</div>
              <div><span>操作人</span>{{ detail.operator || '—' }}</div>
              <div><span>课消时间</span>{{ formatTime(detail.consumed_at) }}</div>
              <div><span>操作时间</span>{{ formatTime(detail.operation_time || detail.created_at) }}</div>
            </div>
          </div>

          <div class="detail-section-title">消耗订单</div>
          <el-table
            v-if="!isApp"
            :data="detail.orders"
            border
            :header-cell-style="pcHeaderStyle"
            empty-text="暂无消耗订单"
          >
            <el-table-column prop="order_no" label="订单号" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">
                <button
                  v-if="row.order_id && row.order_no"
                  type="button"
                  class="link-btn order-no"
                  @click.stop="goOrder(row.order_id)"
                >
                  {{ row.order_no }}
                </button>
                <span v-else class="order-no">{{ row.order_no || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="course_name" label="购买课程" min-width="150" show-overflow-tooltip />
            <el-table-column label="单价" width="110" align="right">
              <template #default="{ row }">{{ formatMoney(row.unit_price) }} 元/课时</template>
            </el-table-column>
            <el-table-column label="消耗购买数量" width="130" align="center">
              <template #default="{ row }">{{ formatHours(row.hours) }}</template>
            </el-table-column>
            <el-table-column label="消耗赠送数量" width="130" align="center">
              <template #default="{ row }">{{ formatHours(row.gift_hours) }}</template>
            </el-table-column>
            <el-table-column label="课消金额(元)" width="130" align="right">
              <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
            </el-table-column>
          </el-table>
          <div v-else class="detail-order-list">
            <article v-for="(row, idx) in detail.orders || []" :key="idx" class="detail-order-card">
              <div class="detail-order-head">
                <button
                  v-if="row.order_id && row.order_no"
                  type="button"
                  class="link-btn order-no"
                  @click.stop="goOrder(row.order_id)"
                >
                  {{ row.order_no }}
                </button>
                <strong v-else class="order-no">{{ row.order_no || '—' }}</strong>
                <span class="pc-mono">¥ {{ formatMoney(row.amount) }}</span>
              </div>
              <div class="oc-meta-chips">
                <span v-if="row.course_name" class="oc-meta-chip">{{ row.course_name }}</span>
                <span class="oc-meta-chip">{{ formatMoney(row.unit_price) }} 元/课时</span>
                <span class="oc-meta-chip">购买 {{ formatHours(row.hours) }}</span>
                <span v-if="row.gift_hours" class="oc-meta-chip">赠送 {{ formatHours(row.gift_hours) }}</span>
              </div>
            </article>
            <div v-if="!detail.orders?.length" class="oc-app-empty detail-order-empty">
              <strong>暂无消耗订单</strong>
              <em>本条课消未关联订单明细</em>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button type="primary" @click="detailVisible = false">关闭</el-button>
      </template>
    </component>
  </div>
</template>

<style scoped>
.shortage {
  color: var(--el-color-danger);
  font-weight: 600;
}

.consume-page {
  width: 100%;
}

.module-card {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.module-card :deep(.el-card__body) {
  padding: 12px 16px 8px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(260px, 1fr));
  gap: 12px 28px;
  margin-bottom: 12px;
}

.filter-item {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  color: #57534e;
  font-size: 13px;
}

.filter-item :deep(.el-date-editor),
.filter-item :deep(.el-select) {
  width: 100%;
}

.filter-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
}

.summary-bar {
  background: #faf3e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 12px;
}

.summary-bar strong {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  font-size: 15px;
}

.consume-card {
  display: block;
  width: 100%;
  border: 1px solid var(--oc-border, #e8e0d0);
  text-align: left;
  cursor: pointer;
  background: var(--oc-card, #fffdf8);
}

.consume-who {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.name-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.consume-sub {
  margin-top: 2px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.consume-chips {
  margin-top: 10px;
}

.consume-empty-ico {
  font-size: 28px;
  line-height: 1;
}

.detail-body {
  min-height: 220px;
}

.detail-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.detail-hero-main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.detail-hero-main strong {
  color: var(--oc-ink, #44403c);
  font-size: 17px;
}

.detail-hero-main span {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.detail-hero-amt {
  flex-shrink: 0;
  color: var(--oc-primary, #a16207);
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.detail-chips {
  margin-bottom: 12px;
}

.detail-panel {
  border: 1px solid rgba(181, 145, 83, 0.22);
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 16px;
  background: #faf6ee;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 28px;
  font-size: 13px;
  color: #292524;
}

.detail-grid span {
  display: block;
  margin-bottom: 2px;
  color: #78716c;
  font-size: 12px;
}

.detail-section-title {
  margin: 6px 0 10px;
  font-weight: 700;
  color: #44403c;
}

.detail-order-list {
  display: grid;
  gap: 8px;
}

.detail-order-card {
  padding: 12px;
  border: 1px solid rgba(181, 145, 83, 0.2);
  border-radius: 14px;
  background: #fffdf8;
}

.detail-order-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.detail-order-empty {
  padding: 24px 12px;
}

.order-no {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.link-btn {
  appearance: none;
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
}

@media (max-width: 1200px) {
  .filter-grid {
    grid-template-columns: repeat(2, minmax(240px, 1fr));
  }
}

@media (max-width: 1199px) {
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

  .summary-bar {
    border-radius: 14px;
  }

  .filter-grid {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .filter-item {
    grid-template-columns: 80px minmax(0, 1fr);
  }

  .filter-actions {
    justify-content: stretch;
    flex-wrap: wrap;
  }

  .filter-actions .el-button {
    flex: 1;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */
</style>
