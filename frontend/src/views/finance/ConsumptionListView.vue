<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
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
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'

const { isCompact } = useBreakpoint()
const router = useRouter()
const loading = ref(false)
const optionLoading = ref(false)
const exporting = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const rows = ref<CourseConsumption[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const totalAmount = ref(0)
const classes = ref<ClassRoom[]>([])
const courses = ref<Course[]>([])
const teachers = ref<TeacherManage[]>([])
const detail = ref<CourseConsumptionDetail | null>(null)

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
    const [classRes, courseRes, teacherRes] = await Promise.all([
      listClassesApi({ page: 1, page_size: 100 }).catch(() => ({ items: [] as ClassRoom[] })),
      listCoursesApi({ enabled: true, page: 1, page_size: 100 }).catch(() => ({ items: [] as Course[] })),
      listAcademicTeachersApi({ page: 1, page_size: 100 }).catch(() => ({ items: [] as TeacherManage[] })),
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

async function load() {
  loading.value = true
  try {
    const res = await listConsumptionsApi(listParams(page.value, pageSize.value))
    rows.value = res.items
    total.value = res.total
    totalAmount.value = res.summary?.amount ?? 0
  } catch {
    rows.value = []
    total.value = 0
    totalAmount.value = 0
  } finally {
    loading.value = false
  }
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
    ElMessage.success(`已导出 ${items.length} 条课消记录`)
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

onMounted(() => {
  void loadOptions()
  void load()
})
</script>

<template>
  <div class="consume-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="课消记录" />
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading || optionLoading">
      <div class="filter-grid">
        <label class="filter-item">
          <span>搜索学员：</span>
          <el-input
            v-model="filters.student"
            clearable
            placeholder="请输入学员姓名/手机号"
            @keyup.enter="runQuery"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </label>
        <label class="filter-item">
          <span>课消日期：</span>
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
          <span>班级名称：</span>
          <el-select v-model="filters.class_id" clearable filterable placeholder="请选择班级">
            <el-option v-for="item in classes" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>报名课程：</span>
          <el-select v-model="filters.course_id" clearable filterable placeholder="请选择课程">
            <el-option v-for="item in courses" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课程类型：</span>
          <el-select v-model="filters.course_type" clearable placeholder="请选择类型">
            <el-option label="班课" value="group" />
            <el-option label="一对一" value="one_to_one" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>上课老师：</span>
          <el-select v-model="filters.teacher_id" clearable filterable placeholder="请选择老师">
            <el-option v-for="item in teachers" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课消类型：</span>
          <el-select v-model="filters.consume_type" clearable placeholder="请选择类型">
            <el-option label="课时课消" value="课时课消" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>课消来源：</span>
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
          <span>年级：</span>
          <el-select v-model="filters.grade" clearable filterable placeholder="请选择年级">
            <el-option v-for="item in grades" :key="item" :label="item" :value="item" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>科目：</span>
          <el-select v-model="filters.subject" clearable filterable placeholder="请选择科目">
            <el-option v-for="item in subjects" :key="item" :label="item" :value="item" />
          </el-select>
        </label>
        <label class="filter-item">
          <span>学期：</span>
          <el-select v-model="filters.term" clearable filterable placeholder="请选择学期">
            <el-option v-for="item in terms" :key="item" :label="item" :value="item" />
          </el-select>
        </label>
      </div>

      <div class="filter-actions">
        <el-checkbox v-model="filters.hide_void" @change="runQuery">过滤已作废</el-checkbox>
        <el-button :icon="'RefreshLeft'" @click="resetFilters">重置</el-button>
        <el-button type="primary" :icon="'Search'" @click="runQuery">查询</el-button>
        <el-button :icon="'Download'" :loading="exporting" @click="exportList">导出</el-button>
      </div>

      <div class="summary-bar">
        课消金额(元)：
        <strong>{{ formatMoney(totalAmount) }}</strong>
      </div>

      <div v-if="isCompact" class="m-card-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无课消记录</div>
        <button v-for="row in rows" :key="row.id" type="button" class="m-card consume-card" @click="openDetail(row)">
          <div class="m-card-head">
            <div class="m-card-title">{{ row.student || '—' }}</div>
            <span class="pc-mono">¥ {{ formatMoney(row.amount) }}</span>
          </div>
          <div class="m-card-meta">
            <span><span class="k">时间</span>{{ formatTime(row.consumed_at) }}</span>
            <span><span class="k">班级</span>{{ row.class_name || '—' }}</span>
            <span><span class="k">课程</span>{{ row.course_name || '—' }}</span>
            <span><span class="k">老师</span>{{ row.teacher || '—' }}</span>
            <span><span class="k">额度</span>{{ row.hours_label || '—' }}</span>
            <span v-if="row.uncovered_hours > 0" class="shortage"><span class="k">欠课时</span>{{ row.uncovered_hours }}</span>
          </div>
        </button>
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

    <el-dialog v-model="detailVisible" title="查看详情" width="760px" class="consume-detail-dialog">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="detail-source">课消来源：{{ detail.source || '—' }}</div>
          <div class="detail-panel">
            <div class="detail-grid">
              <div><span>学员姓名：</span>{{ detail.student || '—' }}</div>
              <div><span>上课班级：</span>{{ detail.class_name || '—' }}</div>
              <div><span>课程名称：</span>{{ detail.course_name || '—' }}</div>
              <div><span>上课时间：</span>{{ classTime(detail) }}</div>
              <div><span>到课状态：</span>{{ detail.attendance_status_label || detail.status_label || detail.status || '—' }}</div>
              <div><span>上课老师：</span>{{ detail.teacher || '—' }}</div>
              <div><span>课时变更：</span>{{ formatHours(detail.hours) }}</div>
              <div><span>操作人：</span>{{ detail.operator || '—' }}</div>
              <div><span>课消时间：</span>{{ formatTime(detail.consumed_at) }}</div>
              <div><span>操作时间：</span>{{ formatTime(detail.operation_time || detail.created_at) }}</div>
            </div>
          </div>

          <div class="detail-section-title">消耗订单</div>
          <el-table :data="detail.orders" border :header-cell-style="pcHeaderStyle" empty-text="暂无消耗订单">
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
              <template #default="{ row }">{{ formatMoney(row.unit_price) }}元/课时</template>
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
        </template>
      </div>
    </el-dialog>
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
}

.detail-body {
  min-height: 260px;
}

.detail-source {
  margin-bottom: 10px;
  color: #57534e;
  font-size: 13px;
}

.detail-panel {
  border: 1px solid #ebe3d4;
  border-radius: 4px;
  padding: 12px 14px;
  margin-bottom: 18px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 28px;
  font-size: 13px;
  color: #292524;
}

.detail-grid span {
  color: #78716c;
}

.detail-section-title {
  margin: 6px 0 10px;
  font-weight: 650;
  color: #44403c;
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

@media (max-width: 991px) {
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
