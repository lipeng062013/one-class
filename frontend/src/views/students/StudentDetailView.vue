<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElDialog,
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadUserFile,
} from 'element-plus'
import {
  clearStudentPackageHoursApi,
  closeStudentCourseApi,
  createLearningApi,
  downloadGrowthReportApi,
  getStudentActivityApi,
  getStudentApi,
  getStudentClassRecordsApi,
  getStudentCoursePackagesApi,
  getStudentOrderLinesApi,
  getStudentOrdersApi,
  learningFileObjectUrl,
  listLearningApi,
  listManagersApi,
  patchStudentApi,
  patchStudentPackageApi,
  uploadLearningFileApi,
  type ManagerOption,
  type StudentStatus,
  type ClassStatus,
  type LearningRecord,
  type Student,
  type StudentActivityEvent,
  type StudentClassRecordRow,
  type StudentClassRecordsResult,
  type StudentClassRecordView,
  type StudentCoursePackageGroup,
  type StudentCoursePackagesResult,
  type StudentOrderLineItem,
  type StudentOrderItem,
  type StudentOrdersResult,
  type StudentPackageOrderRow,
} from '../../api/students'
import { createOrderApi, downloadOrderReceiptApi } from '../../api/finance'
import { getClassRecordApi, type ClassRecordDetail } from '../../api/academic'
import PcPagerBar from '../../components/PcPagerBar.vue'
import MobileActionBar from '../../components/MobileActionBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useListDetailStateCleanup } from '../../composables/useListScrollRestore'
import { usePageBack } from '../../composables/usePageBack'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import { asyncPool } from '../../utils/asyncPool'
import { toBusinessDateTimeIso } from '../../utils/datetime'
import {
  isValidOptionalPhone,
  PHONE_INPUT_MESSAGE,
  sanitizePhoneInput,
} from '../../utils/phone'
import AppSheet from '../../components/AppSheet.vue'

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/students')
useListDetailStateCleanup('students', 'oc-student-list-state')
const auth = useAuthStore()
const { isMobile, isApp } = useBreakpoint()
const { surface: financeSurface, surfaceProps: financeSurfaceProps } = useResponsiveSurface({
  dialogMaxWidth: '520px',
  compactSize: 'min(88%, 640px)',
  modalClass: 'student-finance-sheet',
  sheetProps: { forceBottom: true },
})

const loading = ref(false)
const student = ref<Student | null>(null)
const records = ref<LearningRecord[]>([])
const imageUrls = ref<Record<number, string>>({})

/** 详情下半区 Tab */
type DetailTab = 'courses' | 'orders' | 'classRecords' | 'learning' | 'activity'
const DETAIL_TAB_VALUES: DetailTab[] = [
  'courses',
  'orders',
  'classRecords',
  'learning',
  'activity',
]
const detailTabs: { value: DetailTab; label: string; compactLabel: string }[] = [
  { value: 'courses', label: '报读课程', compactLabel: '课程' },
  { value: 'orders', label: '消费记录', compactLabel: '消费' },
  { value: 'classRecords', label: '上课记录', compactLabel: '上课' },
  { value: 'learning', label: '学情时间线', compactLabel: '学情' },
  { value: 'activity', label: '学员动态', compactLabel: '动态' },
]

function tabFromQuery(raw: unknown): DetailTab | null {
  const v = Array.isArray(raw) ? raw[0] : raw
  if (typeof v !== 'string') return null
  return DETAIL_TAB_VALUES.includes(v as DetailTab) ? (v as DetailTab) : null
}

/** 默认学情；若 URL 带 tab=（如从选班调班返回）则恢复对应 Tab */
const detailTab = ref<DetailTab>(tabFromQuery(route.query.tab) || 'learning')
const tabLoading = ref(false)
/** 避免 tab ↔ query 同步互相触发 */
let syncingTabFromRoute = false
const responsiveSurface = computed(() => (isApp.value ? AppSheet : ElDialog))
const classRecordSurfaceProps = computed(() =>
  isApp.value
    ? {
        compactSize: isMobile.value ? '88%' : '72%',
        modalClass: 'student-record-sheet',
      }
    : { width: '90%', style: { maxWidth: '760px' } },
)
const reportSurfaceProps = computed(() =>
  isApp.value
    ? {
        compactSize: isMobile.value ? '82%' : '66%',
        modalClass: 'student-report-sheet',
      }
    : { width: '90%', style: { maxWidth: '520px' } },
)
const writeSurfaceProps = computed(() =>
  isApp.value
    ? {
        compactSize: isMobile.value ? '94%' : '82%',
        modalClass: 'student-learning-sheet',
      }
    : { width: '90%', style: { maxWidth: '560px' } },
)
const packagesData = ref<StudentCoursePackagesResult | null>(null)
const hideClosedCourses = ref(true)
const ordersData = ref<StudentOrdersResult | null>(null)
const orderLines = ref<StudentOrderLineItem[]>([])
const orderLinesTotal = ref(0)
const ordersSubTab = ref<'list' | 'lines'>('list')
const ordersPage = ref(1)
const ordersPageSize = ref(20)
const orderFilters = reactive({
  status: [] as string[],
  order_type: '',
  item_q: '',
})
const orderActionLoading = ref(false)
const printingOrderId = ref<number | null>(null)
const financeDialogVisible = ref(false)
const financeSaving = ref(false)
const financeForm = reactive({
  order_type: 'drop' as 'drop',
  item_summary: '',
  receivable: 0,
  received: 0,
  pay_method: '微信',
  course_id: null as number | null,
  course_name: '',
  clear_remain: true,
})
const activityItems = ref<StudentActivityEvent[]>([])
const activityFilter = ref('all')
const canManagePackages = computed(
  () => auth.hasPermission('students.write') || auth.isAdmin,
)
/** 编辑档案：与列表一致，有 students.write 或管理员 */
const canEditProfile = computed(
  () => auth.hasPermission('students.write') || auth.isAdmin,
)
const canFinanceWrite = computed(
  () => auth.hasPermission('finance.write') || auth.isAdmin,
)
/** 报名/续费：与后端 enrollments.manage 对齐 */
const canEnrollManage = computed(
  () => auth.hasPermission('enrollments.manage') || auth.isAdmin,
)
const classRecordView = ref<StudentClassRecordView>('completed')
const classRecordsData = ref<StudentClassRecordsResult | null>(null)
const classRecordPage = ref(1)
const classRecordPageSize = ref(20)
const classRecordRange = ref<[string, string] | null>(null)
const classRecordFilters = reactive({
  class_id: undefined as number | undefined,
  course_id: undefined as number | undefined,
  teacher_id: undefined as number | undefined,
  attendance_status: '',
  record_status: '',
})
const classRecordDetailVisible = ref(false)
const classRecordDetailLoading = ref(false)
const classRecordDetail = ref<ClassRecordDetail | null>(null)
const pendingRecordDetail = ref<StudentClassRecordRow | null>(null)

const writeVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const fileList = ref<UploadUserFile[]>([])
const form = reactive({
  class_date: new Date() as Date | null,
  class_status: 'attended' as ClassStatus,
  subject: '',
  learning_summary: '',
  homework_note: '',
  notes: '',
})

const canWrite = computed(() => auth.user?.role === 'admin' || auth.isCR)
const reportLoading = ref(false)
const reportVisible = ref(false)
/** all | range | records */
const reportMode = ref<'all' | 'range' | 'records'>('all')
/** 学情报告区间 YYYY-MM-DD */
const reportRange = ref<[string, string] | null>(null)
/** 指定学情记录 id */
const reportRecordIds = ref<number[]>([])

function openReportDialog() {
  reportMode.value = 'all'
  reportRange.value = null
  reportRecordIds.value = []
  reportVisible.value = true
}

function toDateParam(v: string | Date | null | undefined): string | undefined {
  if (v == null || v === '') return undefined
  if (typeof v === 'string') {
    const m = v.match(/^(\d{4}-\d{2}-\d{2})/)
    return m ? m[1] : undefined
  }
  if (v instanceof Date && !Number.isNaN(v.getTime())) {
    const y = v.getFullYear()
    const mo = String(v.getMonth() + 1).padStart(2, '0')
    const day = String(v.getDate()).padStart(2, '0')
    return `${y}-${mo}-${day}`
  }
  return undefined
}

function recordOptionLabel(r: LearningRecord): string {
  const when = r.class_date ? new Date(r.class_date).toLocaleString() : `#${r.id}`
  const st = classLabels[r.class_status] || r.class_status || ''
  const sub = r.subject ? ` · ${r.subject}` : ''
  const summary = (r.learning_summary || '').replace(/\s+/g, ' ').slice(0, 24)
  const tail = summary ? ` · ${summary}${summary.length >= 24 ? '…' : ''}` : ''
  return `${when}  ${st}${sub}${tail}`
}

async function submitReport() {
  if (!student.value) return
  if (reportMode.value === 'records' && !reportRecordIds.value.length) {
    ElMessage.warning('请至少勾选一条学情记录')
    return
  }
  if (reportMode.value === 'range' && !reportRange.value?.[0] && !reportRange.value?.[1]) {
    ElMessage.warning('请选择学情时间区间，或改选「全部学情」')
    return
  }
  reportLoading.value = true
  try {
    if (reportMode.value === 'records') {
      await downloadGrowthReportApi(student.value.id, student.value.name, {
        record_ids: [...reportRecordIds.value],
      })
      ElMessage.success(
        reportRecordIds.value.length === 1
          ? '成长档案已开始下载（指定 1 条学情）'
          : `成长档案已开始下载（指定 ${reportRecordIds.value.length} 条学情）`,
      )
    } else if (reportMode.value === 'range') {
      const from = toDateParam(reportRange.value?.[0])
      const to = toDateParam(reportRange.value?.[1])
      await downloadGrowthReportApi(student.value.id, student.value.name, {
        date_from: from,
        date_to: to,
      })
      ElMessage.success('成长档案已开始下载（按时间区间）')
    } else {
      await downloadGrowthReportApi(student.value.id, student.value.name)
      ElMessage.success('成长档案已开始下载（全部学情）')
    }
    reportVisible.value = false
  } catch {
    /* interceptor */
  } finally {
    reportLoading.value = false
  }
}

const editVisible = ref(false)
const editSaving = ref(false)
const editFormRef = ref<FormInstance>()
const managers = ref<ManagerOption[]>([])
const editOriginalPhone = ref('')
const editForm = reactive({
  name: '',
  grade: '',
  school: '',
  phone: '',
  parent_name: '',
  academic_manager_id: undefined as number | undefined,
  status: 'active' as StudentStatus,
  notes: '',
})
const gradeOptions = [
  '一年级',
  '二年级',
  '三年级',
  '四年级',
  '五年级',
  '六年级',
  '初一',
  '初二',
  '初三',
  '高一',
  '高二',
  '高三',
  '其他',
]
const activeManagers = computed(() => managers.value.filter((m) => m.is_active))

function validateEditedPhone(
  _rule: unknown,
  value: unknown,
  callback: (error?: Error) => void,
) {
  const phone = String(value ?? '')
  if (phone === editOriginalPhone.value && !isValidOptionalPhone(phone)) {
    callback()
    return
  }
  callback(isValidOptionalPhone(phone) ? undefined : new Error(PHONE_INPUT_MESSAGE))
}

const editRules = computed<FormRules>(() => ({
  name: [{ required: true, message: '请填写学生姓名', trigger: 'blur' }],
  grade: [{ required: true, message: '请填写年级', trigger: 'change' }],
  school: [{ required: true, message: '请填写学校', trigger: 'blur' }],
  academic_manager_id: [{ required: true, message: '请选择学管师', trigger: 'change' }],
  phone: [{ required: true, validator: validateEditedPhone, trigger: 'blur' }],
}))

const editSurfaceProps = computed(() =>
  isApp.value
    ? {
        compactSize: isMobile.value ? '90%' : '72%',
        modalClass: 'student-edit-sheet',
        forceBottom: true,
      }
    : { width: '90%', style: { maxWidth: '560px' }, destroyOnClose: true },
)

async function openEditProfile() {
  if (!student.value || !canEditProfile.value) return
  const row = student.value
  editForm.name = row.name
  editForm.grade = row.grade
  editForm.school = row.school || ''
  editForm.phone = row.phone || ''
  editOriginalPhone.value = row.phone || ''
  editForm.parent_name = row.parent_name || ''
  editForm.academic_manager_id = row.academic_manager_id ?? undefined
  editForm.status = (row.status as StudentStatus) || 'active'
  editForm.notes = row.notes || ''
  try {
    managers.value = await listManagersApi(true)
  } catch {
    managers.value = []
  }
  if (
    editForm.academic_manager_id != null &&
    !managers.value.some((m) => m.id === editForm.academic_manager_id)
  ) {
    editForm.academic_manager_id = undefined
  }
  editVisible.value = true
}

async function submitEditProfile() {
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok || !student.value) return
  editSaving.value = true
  try {
    const updated = await patchStudentApi(student.value.id, {
      name: editForm.name,
      grade: editForm.grade,
      school: editForm.school,
      ...(editForm.phone === editOriginalPhone.value ? {} : { phone: editForm.phone || null }),
      parent_name: editForm.parent_name || null,
      academic_manager_id: editForm.academic_manager_id ?? null,
      status: editForm.status,
      notes: editForm.notes,
    })
    student.value = updated
    editVisible.value = false
    ElMessage.success('学生信息已更新')
  } catch {
    /* interceptor */
  } finally {
    editSaving.value = false
  }
}

function managerOptionLabel(m: ManagerOption) {
  return `${m.display_name || m.username}${m.is_active ? '' : '（已停用）'}`
}

const statusLabels: Record<string, string> = {
  active: '在读',
  paused: '暂停',
  graduated: '结业',
  quit: '退学',
}
const classLabels: Record<string, string> = {
  attended: '已上课',
  absent: '缺勤',
  late: '迟到',
  leave: '请假',
  makeup: '补课',
}

const classTagType: Record<string, 'success' | 'danger' | 'warning' | 'info' | 'primary'> = {
  attended: 'success',
  absent: 'danger',
  late: 'warning',
  leave: 'info',
  makeup: 'primary',
}

const rules: FormRules = {
  learning_summary: [{ required: true, message: '请填写学习情况', trigger: 'blur' }],
  class_status: [{ required: true, message: '请选择上课状态', trigger: 'change' }],
}

const studentId = computed(() => Number(route.params.id))

/** 学情附件预览列表（仅已加载成功的 URL，保持与文件顺序一致） */
function recordPreviewList(rec: LearningRecord): string[] {
  return (rec.files || []).map((f) => imageUrls.value[f.id]).filter(Boolean) as string[]
}

/** 点击某张缩略图时，大图从该张开始（而不是总从第一张） */
function recordPreviewIndex(rec: LearningRecord, fileId: number): number {
  const list = recordPreviewList(rec)
  const url = imageUrls.value[fileId]
  if (!url) return 0
  const idx = list.indexOf(url)
  return idx >= 0 ? idx : 0
}

const IMAGE_CONCURRENCY = 4

async function loadImages(list: LearningRecord[]) {
  for (const key of Object.keys(imageUrls.value)) {
    URL.revokeObjectURL(imageUrls.value[Number(key)])
  }
  imageUrls.value = {}
  const files = list.flatMap((rec) => rec.files || [])
  await asyncPool(files, IMAGE_CONCURRENCY, async (f) => {
    try {
      imageUrls.value[f.id] = await learningFileObjectUrl(f.id, { thumb: true })
    } catch {
      /* ignore */
    }
  })
}

function formatMoney(n: number) {
  return Number(n || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

function hoursLabel(n: number) {
  const v = Number(n || 0)
  return `${v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}课时`
}

function validUntilLabel(v?: string | null) {
  if (!v) return '未设置有效期'
  const s = String(v).slice(0, 10)
  return s || '未设置有效期'
}

const visibleCourses = computed(() => {
  const list = packagesData.value?.courses || []
  if (!hideClosedCourses.value) return list
  return list.filter((c) => !c.is_closed)
})

const filteredActivity = computed(() => {
  const list = activityItems.value
  if (activityFilter.value === 'all') return list
  if (activityFilter.value === 'manager') return list.filter((e) => e.kind === 'manager')
  if (activityFilter.value === 'enroll')
    return list.filter((e) => e.kind === 'enroll' || e.kind === 'renew')
  if (activityFilter.value === 'learning') return list.filter((e) => e.kind === 'learning')
  return list
})

function classRecordParams(page = classRecordPage.value, pageSize = classRecordPageSize.value) {
  return {
    view: classRecordView.value,
    start: classRecordRange.value?.[0] || undefined,
    end: classRecordRange.value?.[1] || undefined,
    class_id: classRecordFilters.class_id,
    course_id: classRecordFilters.course_id,
    teacher_id: classRecordFilters.teacher_id,
    attendance_status:
      classRecordView.value === 'completed'
        ? classRecordFilters.attendance_status || undefined
        : undefined,
    record_status:
      classRecordView.value === 'completed' ? classRecordFilters.record_status || undefined : undefined,
    page,
    page_size: pageSize,
  }
}

async function loadClassRecords(resetPage = false) {
  if (!studentId.value) return
  if (resetPage) classRecordPage.value = 1
  tabLoading.value = true
  try {
    classRecordsData.value = await getStudentClassRecordsApi(
      studentId.value,
      classRecordParams(),
    )
  } catch {
    classRecordsData.value = null
  } finally {
    tabLoading.value = false
  }
}

function changeClassRecordView(value: string | number | boolean | undefined) {
  classRecordView.value = String(value) as StudentClassRecordView
  classRecordFilters.attendance_status = ''
  classRecordFilters.record_status = ''
  void loadClassRecords(true)
}

function resetClassRecordFilters() {
  classRecordRange.value = null
  classRecordFilters.class_id = undefined
  classRecordFilters.course_id = undefined
  classRecordFilters.teacher_id = undefined
  classRecordFilters.attendance_status = ''
  classRecordFilters.record_status = ''
  void loadClassRecords(true)
}

function classTimeLabel(row: StudentClassRecordRow) {
  const start = formatTime(row.class_start || row.roll_at)
  if (!row.class_end) return start
  const end = new Date(row.class_end)
  const endLabel = Number.isNaN(end.getTime())
    ? row.class_end
    : end.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${start} - ${endLabel}`
}

async function openClassRecordDetail(row: StudentClassRecordRow) {
  classRecordDetail.value = null
  pendingRecordDetail.value = row.row_type === 'pending' ? row : null
  classRecordDetailVisible.value = true
  if (row.row_type === 'pending') return
  classRecordDetailLoading.value = true
  try {
    classRecordDetail.value = await getClassRecordApi(row.id)
  } finally {
    classRecordDetailLoading.value = false
  }
}

function csvCell(value: unknown) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

async function exportClassRecords() {
  if (!student.value) return
  tabLoading.value = true
  try {
    const first = await getStudentClassRecordsApi(studentId.value, classRecordParams(1, 100))
    const rows = [...first.items]
    for (let page = 2; rows.length < first.total; page += 1) {
      const next = await getStudentClassRecordsApi(studentId.value, classRecordParams(page, 100))
      rows.push(...next.items)
      if (!next.items.length) break
    }
    if (!rows.length) {
      ElMessage.warning(
        classRecordView.value === 'completed'
          ? '暂无已上课记录可导出'
          : '暂无待上课记录可导出',
      )
      return
    }
    const headers = [
      '点名时间',
      '班级名称',
      '课程名称',
      '上课时间',
      '上课老师',
      '到课状态',
      '补课状态',
      '消耗方式',
      '扣除课时',
      '课消金额',
      '上课内容',
      '备注/教室',
    ]
    const lines = [
      headers.map(csvCell).join(','),
      ...rows.map((row) =>
        [
          formatTime(row.roll_at),
          row.class_name,
          row.course_name,
          classTimeLabel(row),
          row.teachers,
          row.attendance_status_label,
          row.makeup_status_label,
          row.consumption_type,
          row.hours_consumed,
          row.amount,
          row.content,
          row.notes,
        ]
          .map(csvCell)
          .join(','),
      ),
    ]
    const blob = new Blob([`\uFEFF${lines.join('\r\n')}`], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${student.value.name}-${classRecordView.value === 'completed' ? '已上课记录' : '待上课记录'}.csv`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${rows.length} 条上课记录`)
  } finally {
    tabLoading.value = false
  }
}

async function loadOrders(resetPage = false) {
  if (!studentId.value) return
  if (resetPage) ordersPage.value = 1
  tabLoading.value = true
  try {
    if (ordersSubTab.value === 'lines') {
      const res = await getStudentOrderLinesApi(studentId.value, {
        page: ordersPage.value,
        page_size: ordersPageSize.value,
        order_type: orderFilters.order_type || undefined,
        item_q: orderFilters.item_q.trim() || undefined,
      })
      orderLines.value = res.items || []
      orderLinesTotal.value = res.total || 0
    } else {
      const res = await getStudentOrdersApi(studentId.value, {
        page: ordersPage.value,
        page_size: ordersPageSize.value,
        status: orderFilters.status.length ? orderFilters.status.join(',') : undefined,
        order_type: orderFilters.order_type || undefined,
        item_q: orderFilters.item_q.trim() || undefined,
      })
      ordersData.value = res
    }
  } catch {
    if (ordersSubTab.value === 'lines') {
      orderLines.value = []
      orderLinesTotal.value = 0
    } else {
      ordersData.value = null
    }
  } finally {
    tabLoading.value = false
  }
}

function resetOrderFilters() {
  orderFilters.status = []
  orderFilters.order_type = ''
  orderFilters.item_q = ''
  void loadOrders(true)
}

function changeOrdersSubTab(name: string | number) {
  ordersSubTab.value = String(name) as 'list' | 'lines'
  void loadOrders(true)
}

async function loadTabData(tab: DetailTab) {
  if (!studentId.value) return
  tabLoading.value = true
  try {
    if (tab === 'courses') {
      packagesData.value = await getStudentCoursePackagesApi(studentId.value)
    } else if (tab === 'orders') {
      await loadOrders()
    } else if (tab === 'activity') {
      const res = await getStudentActivityApi(studentId.value, 80)
      activityItems.value = res.items || []
    } else if (tab === 'classRecords') {
      await loadClassRecords()
    } else if (tab === 'learning') {
      records.value = (
        await listLearningApi({ student_id: studentId.value, page: 1, page_size: 100 })
      ).items
      void loadImages(records.value)
    }
  } catch {
    if (tab === 'courses') packagesData.value = null
    if (tab === 'orders') {
      ordersData.value = null
      orderLines.value = []
      orderLinesTotal.value = 0
    }
    if (tab === 'activity') activityItems.value = []
    if (tab === 'classRecords') classRecordsData.value = null
  } finally {
    tabLoading.value = false
  }
}

function syncTabToRoute(tab: DetailTab) {
  if (syncingTabFromRoute) return
  const cur = tabFromQuery(route.query.tab)
  if (cur === tab) return
  void router.replace({
    path: route.path,
    query: {
      ...route.query,
      tab,
    },
  })
}

function onTabChange(name: string | number) {
  const tab = String(name) as DetailTab
  detailTab.value = tab
  syncTabToRoute(tab)
  void loadTabData(tab)
}

function selectDetailTab(tab: DetailTab) {
  if (detailTab.value === tab) return
  detailTab.value = tab
  onTabChange(tab)
}

watch(
  () => route.query.tab,
  (raw) => {
    const next = tabFromQuery(raw)
    if (!next || next === detailTab.value) return
    syncingTabFromRoute = true
    detailTab.value = next
    void loadTabData(next).finally(() => {
      syncingTabFromRoute = false
    })
  },
)

function goOrder(orderId?: number | null, orderNo?: string) {
  if (orderId) {
    void router.push(`/finance/orders/${orderId}`)
    return
  }
  if (orderNo && (auth.isAdmin || canFinanceWrite.value)) {
    void router.push({ path: '/finance/orders', query: { order_no: orderNo } })
  }
}

function goRenewal(courseId?: number | null) {
  if (!student.value) return
  const query: Record<string, string> = {
    student_id: String(student.value.id),
    kind: 'renew',
  }
  if (courseId) query.course_id = String(courseId)
  void router.push({ path: '/enrollments', query })
}

function goEnroll() {
  if (!student.value) return
  void router.push({
    path: '/enrollments',
    query: { student_id: String(student.value.id), kind: 'enroll' },
  })
}

async function goClassAssign(course?: StudentCoursePackageGroup | null) {
  if (!student.value) return
  // 先把当前详情 Tab 固化为报读课程，浏览器返回时恢复该 Tab
  detailTab.value = 'courses'
  if (tabFromQuery(route.query.tab) !== 'courses') {
    await router.replace({
      path: route.path,
      query: { ...route.query, tab: 'courses' },
    })
  }
  const query: Record<string, string> = {
    assign: '1',
    student_id: String(student.value.id),
    student_name: student.value.name,
  }
  if (course?.course_id) {
    query.course_id = String(course.course_id)
    query.course_name = course.course_name || ''
  }
  if (course?.class_id) query.from_class_id = String(course.class_id)
  if (course?.class_name) query.from_class_name = course.class_name
  if (course?.course_type === 'one_to_one') query.mode = 'one_to_one'
  else if (course?.course_type === 'group') query.mode = 'group'
  else if (course?.type_label?.includes('一对一')) query.mode = 'one_to_one'
  else query.mode = 'group'
  void router.push({ path: '/academic/classes', query })
}

function goCourseConsumptions(course?: StudentCoursePackageGroup | null) {
  if (!student.value) return
  const query: Record<string, string> = {
    student: student.value.name,
  }
  if (course?.course_id) query.course_id = String(course.course_id)
  void router.push({ path: '/finance/consumptions', query })
}

/** 转课：跳转报名页，预选学员 + 转出课程 */
function goTransfer(course?: StudentCoursePackageGroup | null) {
  if (!student.value) return
  const query: Record<string, string> = {
    student_id: String(student.value.id),
    kind: 'transfer',
  }
  if (course?.course_id) query.course_id = String(course.course_id)
  void router.push({ path: '/enrollments', query })
}

function openFinanceDialog(
  type: 'drop',
  course?: StudentCoursePackageGroup | null,
) {
  if (!student.value) return
  financeForm.order_type = type
  financeForm.course_id = course?.course_id ?? null
  financeForm.course_name = course?.course_name || ''
  financeForm.item_summary = `退课 · ${course?.course_name || student.value.name}`
  financeForm.receivable = 0
  financeForm.received = 0
  financeForm.pay_method = '微信'
  financeForm.clear_remain = true
  financeDialogVisible.value = true
}

async function submitFinanceOrder() {
  if (!student.value) return
  if (!financeForm.item_summary.trim()) {
    ElMessage.warning('请填写购买项目/摘要')
    return
  }
  financeSaving.value = true
  try {
    const order = await createOrderApi({
      student_id: student.value.id,
      order_type: financeForm.order_type,
      item_summary: financeForm.item_summary.trim(),
      receivable: financeForm.receivable,
      received: financeForm.received,
      pay_method: financeForm.pay_method,
    })
    if (
      financeForm.order_type === 'drop' &&
      financeForm.clear_remain &&
      financeForm.course_id &&
      canManagePackages.value
    ) {
      try {
        await closeStudentCourseApi(student.value.id, financeForm.course_id, true)
      } catch {
        /* 订单已建，结课失败单独提示 */
        ElMessage.warning('退课订单已创建，但课包清零失败，请手动结课/清零')
      }
    }
    ElMessage.success('退课订单已创建')
    financeDialogVisible.value = false
    if (detailTab.value === 'courses') {
      packagesData.value = await getStudentCoursePackagesApi(student.value.id)
    }
    void router.push(`/finance/orders/${order.id}`)
  } catch {
    /* interceptor */
  } finally {
    financeSaving.value = false
  }
}

async function onCloseCourse(course: StudentCoursePackageGroup) {
  if (!student.value || !course.course_id) return
  try {
    await ElMessageBox.confirm(
      `确定将「${course.course_name}」结课？结课后该课程在读课包将不可再扣课时。`,
      '结课确认',
      {
        type: 'warning',
        distinguishCancelAndClose: true,
        confirmButtonText: '结课',
        cancelButtonText: '取消',
        showCancelButton: true,
      },
    )
  } catch {
    return
  }
  let clearRemain = false
  if (Number(course.remain_hours || 0) > 0) {
    try {
      await ElMessageBox.confirm(
        `该课程仍有剩余 ${hoursLabel(course.remain_hours)}，是否同时清零剩余课时？`,
        '剩余课时处理',
        {
          type: 'warning',
          distinguishCancelAndClose: true,
          confirmButtonText: '清零并结课',
          cancelButtonText: '保留剩余',
        },
      )
      clearRemain = true
    } catch (e) {
      if (e === 'close') return
      clearRemain = false
    }
  }
  orderActionLoading.value = true
  try {
    const res = await closeStudentCourseApi(student.value.id, course.course_id, clearRemain)
    ElMessage.success(`已结课（${res.closed_count} 个课包）`)
    packagesData.value = await getStudentCoursePackagesApi(student.value.id)
  } catch {
    /* interceptor */
  } finally {
    orderActionLoading.value = false
  }
}

async function onClearPackageHours(row: StudentPackageOrderRow) {
  if (!student.value) return
  try {
    await ElMessageBox.confirm(
      `确定将订单「${row.order_no}」剩余 ${hoursLabel(row.remain_hours)} 清零？此操作不可撤销。`,
      '课时清零',
      { type: 'warning', confirmButtonText: '清零', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  orderActionLoading.value = true
  try {
    await clearStudentPackageHoursApi(student.value.id, row.package_id)
    ElMessage.success('课时已清零')
    packagesData.value = await getStudentCoursePackagesApi(student.value.id)
  } catch {
    /* interceptor */
  } finally {
    orderActionLoading.value = false
  }
}

async function onTogglePriority(row: StudentPackageOrderRow, value: boolean | string | number) {
  if (!student.value || !canManagePackages.value) return
  const next = Boolean(value)
  try {
    await patchStudentPackageApi(student.value.id, row.package_id, {
      priority_consume: next,
    })
    row.priority_consume = next
    ElMessage.success(next ? '已设为优先消耗' : '已取消优先消耗')
    // 刷新以同步同课程其他课包的优先状态
    packagesData.value = await getStudentCoursePackagesApi(student.value.id)
  } catch {
    /* interceptor */
  }
}

async function onEditValidUntil(row: StudentPackageOrderRow) {
  if (!student.value || !canManagePackages.value) return
  const current = row.valid_until ? String(row.valid_until).slice(0, 10) : ''
  try {
    const { value } = await ElMessageBox.prompt(
      '请输入课程有效期（YYYY-MM-DD），留空表示不设置有效期',
      '设置有效期',
      {
        inputValue: current,
        inputPlaceholder: 'YYYY-MM-DD 或留空',
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        inputPattern: /^$|^\d{4}-\d{2}-\d{2}$/,
        inputErrorMessage: '格式须为 YYYY-MM-DD',
      },
    )
    const raw = String(value || '').trim()
    if (!raw) {
      await patchStudentPackageApi(student.value.id, row.package_id, {
        clear_valid_until: true,
      })
      row.valid_until = null
    } else {
      await patchStudentPackageApi(student.value.id, row.package_id, {
        valid_until: raw,
      })
      row.valid_until = raw
    }
    ElMessage.success('有效期已更新')
  } catch {
    /* cancel */
  }
}

async function onPrintOrder(row: StudentOrderItem) {
  if (!row?.id) return
  printingOrderId.value = row.id
  try {
    await downloadOrderReceiptApi(row.id, {
      orderNo: row.order_no,
      studentName: student.value?.name,
    })
    ElMessage.success('收据 PDF 已开始下载')
  } catch {
    /* interceptor */
  } finally {
    printingOrderId.value = null
  }
}

async function load() {
  // 路由变化 / 浏览器返回时，按 URL tab 恢复
  const fromQuery = tabFromQuery(route.query.tab)
  if (fromQuery && fromQuery !== detailTab.value) {
    detailTab.value = fromQuery
  }
  loading.value = true
  try {
    student.value = await getStudentApi(studentId.value)
    records.value = (
      await listLearningApi({ student_id: studentId.value, page: 1, page_size: 100 })
    ).items
  } finally {
    loading.value = false
  }
  // 正文先出来，缩略图后台并发加载
  void loadImages(records.value)
  // 预加载当前 tab（默认学情已加载）；切换时再拉
  if (detailTab.value !== 'learning') {
    void loadTabData(detailTab.value)
  } else if (fromQuery === 'learning') {
    // 已在 load 中拉了学情列表
  }
}

function dialStudent() {
  const phone = student.value?.phone?.trim()
  if (!phone) return
  window.location.href = `tel:${phone}`
}

function openWrite() {
  form.class_date = new Date()
  form.class_status = 'attended'
  form.subject = ''
  form.learning_summary = ''
  form.homework_note = ''
  form.notes = ''
  fileList.value = []
  writeVisible.value = true
}

async function submitLearning() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const rec = await createLearningApi({
      student_id: studentId.value,
      class_date: toBusinessDateTimeIso(form.class_date),
      class_status: form.class_status,
      subject: form.subject || null,
      learning_summary: form.learning_summary,
      homework_note: form.homework_note,
      notes: form.notes,
    })
    for (const item of fileList.value) {
      if (item.raw) {
        await uploadLearningFileApi(rec.id, item.raw as File)
      }
    }
    ElMessage.success('学情已提交')
    writeVisible.value = false
    await load()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

watch(studentId, load)
onMounted(load)
onUnmounted(() => {
  for (const url of Object.values(imageUrls.value)) {
    URL.revokeObjectURL(url)
  }
})
</script>

<template>
  <div v-loading="loading" class="student-detail-page oc-page-shell">
    <div v-if="!isApp" class="page-toolbar">
      <el-page-header @back="goBack">
        <template #content>
          <span>学生详情{{ student ? ` · ${student.name}` : '' }}</span>
        </template>
      </el-page-header>
      <div class="toolbar-actions">
        <el-button
          v-if="canEnrollManage && student?.allocation_phase === 'pending_enroll'"
          type="success"
          @click="goEnroll"
        >
          去完成报名
        </el-button>
        <el-tag
          v-else-if="student?.allocation_phase === 'pending_enroll'"
          type="warning"
          effect="plain"
          round
          class="phase-tag"
        >
          待报名
        </el-tag>
        <el-tag
          v-if="student?.allocation_phase === 'pending_alloc' || student?.needs_allocation"
          type="danger"
          effect="dark"
          round
          class="phase-tag"
        >
          待调配学管
        </el-tag>
        <el-button v-if="canEditProfile" type="primary" plain @click="openEditProfile">编辑</el-button>
        <el-button type="primary" plain @click="openReportDialog">生成学情报告</el-button>
      </div>
    </div>

    <el-card v-if="student && !isApp" class="profile" shadow="never">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="姓名">{{ student.name }}</el-descriptions-item>
        <el-descriptions-item label="年级">{{ student.grade }}</el-descriptions-item>
        <el-descriptions-item label="学校">{{ student.school || '—' }}</el-descriptions-item>
        <el-descriptions-item label="学管师">
          {{ student.academic_manager_name || '—' }}
        </el-descriptions-item>
        <el-descriptions-item v-if="!auth.isTeacher" label="电话">{{ student.phone || '—' }}</el-descriptions-item>
        <el-descriptions-item label="家长">{{ student.parent_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag
            size="small"
            effect="light"
            :type="student.status === 'active' ? 'success' : student.status === 'paused' ? 'warning' : 'info'"
          >
            {{ statusLabels[student.status] || student.status }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ student.notes || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <section v-else-if="student" class="compact-profile" aria-label="学生基本信息">
      <div class="compact-profile__identity">
        <span class="compact-profile__avatar">{{ student.name.slice(0, 1) }}</span>
        <div class="compact-profile__name">
          <strong>{{ student.name }}</strong>
          <span>{{ student.grade || '未填年级' }} · {{ student.school || '未填学校' }}</span>
        </div>
        <div class="compact-profile__actions">
          <el-tag
            size="small"
            effect="plain"
            :type="student.status === 'active' ? 'success' : student.status === 'paused' ? 'warning' : 'info'"
          >
            {{ statusLabels[student.status] || student.status }}
          </el-tag>
          <button type="button" class="compact-report-button" @click="openReportDialog">
            <el-icon><Document /></el-icon>
            <span>报告</span>
          </button>
        </div>
      </div>
      <div class="compact-profile__facts">
        <div class="compact-profile__fact">
          <span>学管师</span>
          <strong>{{ student.academic_manager_name || '未分配' }}</strong>
        </div>
        <div v-if="!auth.isTeacher" class="compact-profile__fact">
          <span>联系电话</span>
          <a v-if="student.phone" :href="`tel:${student.phone}`">{{ student.phone }}</a>
          <strong v-else>未填写</strong>
        </div>
        <div class="compact-profile__fact">
          <span>家长</span>
          <strong>{{ student.parent_name || '未填写' }}</strong>
        </div>
      </div>
      <p v-if="student.notes" class="compact-profile__notes">
        <span>备注</span>
        {{ student.notes }}
      </p>
    </section>

    <el-card
      v-if="student"
      class="tabs-card"
      :class="{ 'is-compact': isApp }"
      shadow="never"
      v-loading="tabLoading"
    >
      <nav v-if="isApp" class="compact-detail-tabs" aria-label="学生详情分类">
        <button
          v-for="tab in detailTabs"
          :key="tab.value"
          type="button"
          :class="{ 'is-active': detailTab === tab.value }"
          @click="selectDetailTab(tab.value)"
        >
          {{ isMobile ? tab.compactLabel : tab.label }}
        </button>
      </nav>
      <el-tabs v-else v-model="detailTab" class="detail-tabs" @tab-change="onTabChange">
        <el-tab-pane label="报读课程" name="courses" />
        <el-tab-pane label="消费记录" name="orders" />
        <el-tab-pane label="上课记录" name="classRecords" />
        <el-tab-pane label="学情时间线" name="learning" />
        <el-tab-pane label="学员动态" name="activity" />
      </el-tabs>

      <!-- 报读课程 -->
      <div v-if="detailTab === 'courses'" class="tab-body">
        <div class="summary-bar">
          剩余课时数(课时)：
          <strong>{{ packagesData?.summary.remain_hours ?? 0 }}</strong>
          <span class="sum-gap">超上课时数(课时)：</span>
          <strong>{{ packagesData?.summary.overtime_hours ?? 0 }}</strong>
        </div>
        <div class="course-toolbar">
          <div class="course-toolbar-left">
            <el-button
              v-if="canManagePackages"
              type="warning"
              plain
              size="small"
              @click="goClassAssign()"
            >
              选班调班
            </el-button>
            <el-button
              v-if="canEnrollManage"
              type="primary"
              size="small"
              @click="goEnroll"
            >
              报名
            </el-button>
          </div>
          <el-checkbox v-model="hideClosedCourses">隐藏「已结课」课程</el-checkbox>
        </div>
        <el-empty
          v-if="!visibleCourses.length"
          :description="
            packagesData?.courses?.length
              ? '已隐藏结课课程，可取消勾选查看'
              : '暂无报读课程，可通过报名/续费关联课程'
          "
        />
        <div
          v-for="(c, idx) in visibleCourses"
          :key="c.course_id ?? idx"
          class="course-block"
          :class="{ 'is-closed': c.is_closed }"
        >
          <div class="course-block-head">
            <div class="course-block-title">
              <el-icon class="course-icon"><Reading /></el-icon>
              <span>{{ c.course_name }}</span>
              <el-tag v-if="c.type_label" size="small" effect="plain" type="warning">
                {{ c.type_label }}
              </el-tag>
              <el-tag v-if="c.is_closed" size="small" type="info" effect="plain">已结课</el-tag>
              <el-tag
                v-else-if="!c.has_available && c.packages?.length"
                size="small"
                type="info"
                effect="plain"
              >
                不可用
              </el-tag>
            </div>
            <div
              v-if="canEnrollManage && !c.from_link_only"
              class="course-block-actions"
            >
              <el-button
                v-if="canEnrollManage"
                link
                type="primary"
                @click="goRenewal(c.course_id)"
              >
                续费
              </el-button>
              <el-button
                v-if="canManagePackages || canFinanceWrite"
                link
                type="primary"
                @click="goTransfer(c)"
              >
                转课
              </el-button>
              <el-button
                v-if="canFinanceWrite"
                link
                type="warning"
                @click="openFinanceDialog('drop', c)"
              >
                退课
              </el-button>
              <el-button
                v-if="canManagePackages && c.can_close"
                link
                type="info"
                :loading="orderActionLoading"
                @click="onCloseCourse(c)"
              >
                结课
              </el-button>
            </div>
          </div>
          <div class="course-block-meta">
            <span>
              剩余课时：{{ hoursLabel(c.remain_hours) }}
              <button
                v-if="c.class_id"
                type="button"
                class="link-btn meta-link"
                @click="goClassAssign(c)"
              >
                去调班
              </button>
              <button
                v-else-if="canManagePackages"
                type="button"
                class="link-btn meta-link"
                @click="goClassAssign(c)"
              >
                去选班
              </button>
            </span>
            <span>
              消耗课时：{{ hoursLabel(c.consumed_hours) }}
              <button
                v-if="Number(c.consumed_hours) > 0"
                type="button"
                class="link-btn meta-link"
                @click="goCourseConsumptions(c)"
              >
                查看详情
              </button>
            </span>
            <span>合计购买课时：{{ hoursLabel(c.total_hours) }}</span>
          </div>
          <div class="course-block-meta">
            <span>
              所在班级：{{ c.class_name || '未选班' }}
              <button
                v-if="c.class_id"
                type="button"
                class="link-btn meta-link"
                @click="
                  router.push({
                    path: '/academic/classes',
                    query: { class_id: String(c.class_id) },
                  })
                "
              >
                查看
              </button>
            </span>
          </div>
          <el-table
            v-if="!isApp && c.packages?.length"
            :data="c.packages"
            size="small"
            border
            class="pkg-table"
            :header-cell-style="{
              background: '#f5f0e6',
              color: '#44403c',
              fontWeight: '600',
            }"
          >
            <el-table-column label="订单号" min-width="150">
              <template #default="{ row }">
                <button
                  v-if="row.order_id"
                  type="button"
                  class="link-btn"
                  @click="goOrder(row.order_id, row.order_no)"
                >
                  {{ row.order_no }}
                </button>
                <span v-else>{{ row.order_no }}</span>
              </template>
            </el-table-column>
            <el-table-column label="购买数量" width="96" align="center">
              <template #default="{ row }">{{ hoursLabel(row.purchase_hours) }}</template>
            </el-table-column>
            <el-table-column label="赠送数量" width="96" align="center">
              <template #default="{ row }">{{ hoursLabel(row.gift_hours) }}</template>
            </el-table-column>
            <el-table-column label="已消耗数量" width="100" align="center">
              <template #default="{ row }">{{ hoursLabel(row.consumed_hours) }}</template>
            </el-table-column>
            <el-table-column label="退转数量" width="90" align="center">
              <template #default="{ row }">{{ hoursLabel(row.refund_hours) }}</template>
            </el-table-column>
            <el-table-column label="剩余数量" width="96" align="center">
              <template #default="{ row }">
                <span :class="{ 'remain-warn': Number(row.remain_hours) <= 0 }">
                  {{ hoursLabel(row.remain_hours) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="课程有效期" min-width="140" align="center">
              <template #default="{ row }">
                <span class="valid-cell">
                  {{ validUntilLabel(row.valid_until) }}
                  <button
                    v-if="canManagePackages && row.status === 'active'"
                    type="button"
                    class="link-btn"
                    title="编辑有效期"
                    @click="onEditValidUntil(row)"
                  >
                    编辑
                  </button>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="优先消耗" width="90" align="center">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.priority_consume"
                  :disabled="!canManagePackages || row.status !== 'active'"
                  size="small"
                  @change="(v: string | number | boolean) => onTogglePriority(row, v)"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="canManagePackages && row.can_clear_hours"
                  link
                  type="danger"
                  :loading="orderActionLoading"
                  @click="onClearPackageHours(row)"
                >
                  课时清零
                </el-button>
                <span v-else class="op-dash">—</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-else-if="c.packages?.length" class="compact-data-grid pkg-app-grid">
            <div
              v-for="row in c.packages"
              :key="row.package_id || row.order_no"
              class="compact-data-card is-static pkg-app-card"
            >
              <button
                type="button"
                class="compact-data-head linkish"
                :disabled="!row.order_id"
                @click="row.order_id && goOrder(row.order_id, row.order_no)"
              >
                <strong>{{ row.order_no || '课包' }}</strong>
                <b class="pkg-remain" :class="{ 'is-warn': Number(row.remain_hours) <= 0 }">
                  余 {{ hoursLabel(row.remain_hours) }}
                </b>
              </button>
              <div class="oc-meta-chips pkg-app-chips">
                <span class="oc-meta-chip">购 {{ hoursLabel(row.purchase_hours) }}</span>
                <span class="oc-meta-chip">赠 {{ hoursLabel(row.gift_hours) }}</span>
                <span class="oc-meta-chip">已用 {{ hoursLabel(row.consumed_hours) }}</span>
                <span v-if="row.status_label" class="oc-meta-chip">{{ row.status_label }}</span>
              </div>
              <span class="compact-data-note">
                {{ validUntilLabel(row.valid_until) }}
              </span>
              <div v-if="canManagePackages && row.status === 'active'" class="compact-pkg-actions">
                <el-switch
                  :model-value="row.priority_consume"
                  size="small"
                  inline-prompt
                  active-text="优先"
                  inactive-text="普通"
                  @change="(v: string | number | boolean) => onTogglePriority(row, v)"
                />
                <el-button
                  v-if="row.can_clear_hours"
                  link
                  type="danger"
                  size="small"
                  @click="onClearPackageHours(row)"
                >
                  清零
                </el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无课包明细（仅关联课程档案）" :image-size="48" />
        </div>
      </div>

      <!-- 消费记录 -->
      <div v-else-if="detailTab === 'orders'" class="tab-body">
        <el-radio-group
          :model-value="ordersSubTab"
          class="orders-sub-tabs"
          @change="changeOrdersSubTab"
        >
          <el-radio-button value="list">订单记录</el-radio-button>
          <el-radio-button value="lines">订单明细</el-radio-button>
        </el-radio-group>

        <div class="orders-filters">
          <el-select
            v-if="ordersSubTab === 'list'"
            v-model="orderFilters.status"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            placeholder="订单状态"
            class="orders-filter-status"
          >
            <el-option label="已支付" value="paid" />
            <el-option label="部分支付" value="partial" />
            <el-option label="未支付" value="unpaid" />
            <el-option label="已作废" value="void" />
          </el-select>
          <el-select
            v-model="orderFilters.order_type"
            clearable
            placeholder="订单类型"
            class="orders-filter-type"
          >
            <el-option label="报名" value="enroll" />
            <el-option label="续费" value="renew" />
            <el-option label="转课" value="transfer" />
            <el-option label="退课" value="drop" />
            <el-option label="充值" value="recharge" />
            <el-option label="退款" value="refund" />
            <el-option label="其他" value="other" />
          </el-select>
          <el-input
            v-model="orderFilters.item_q"
            clearable
            placeholder="购买项目"
            class="orders-filter-item"
            @keyup.enter="loadOrders(true)"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button type="primary" @click="loadOrders(true)">查询</el-button>
          <el-button @click="resetOrderFilters">重置</el-button>
        </div>

        <div v-if="ordersSubTab === 'list'" class="summary-bar">
          订单总金额(元)
          <strong>{{ formatMoney(ordersData?.summary.order_amount ?? 0) }}</strong>
          <span class="sum-gap">实收金额(元)</span>
          <strong>{{ formatMoney(ordersData?.summary.received_amount ?? 0) }}</strong>
          <span class="sum-gap">欠费金额(元)</span>
          <strong>{{ formatMoney(ordersData?.summary.arrears_amount ?? 0) }}</strong>
        </div>

        <!-- 订单记录 -->
        <template v-if="ordersSubTab === 'list'">
          <el-table
            v-if="!isApp"
            :data="ordersData?.items || []"
            border
            stripe
            empty-text="暂无消费/订单记录"
            :header-cell-style="{
              background: '#f5f0e6',
              color: '#44403c',
              fontWeight: '600',
            }"
          >
            <el-table-column label="订单号" min-width="150">
              <template #default="{ row }">
                <button
                  v-if="row.id"
                  type="button"
                  class="link-btn"
                  @click="goOrder(row.id, row.order_no)"
                >
                  {{ row.order_no }}
                </button>
                <span v-else>{{ row.order_no }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="order_type_label" label="订单类型" width="90" align="center" />
            <el-table-column prop="item" label="购买项目" min-width="180" show-overflow-tooltip />
            <el-table-column label="应收/应退(元)" width="120" align="right">
              <template #default="{ row }">{{ formatMoney(row.receivable) }}</template>
            </el-table-column>
            <el-table-column label="实收/实退(元)" width="120" align="right">
              <template #default="{ row }">{{ formatMoney(row.received) }}</template>
            </el-table-column>
            <el-table-column prop="source" label="订单来源" width="100" />
            <el-table-column
              prop="performance_owner"
              label="业绩归属人"
              min-width="120"
              show-overflow-tooltip
            />
            <el-table-column prop="status_label" label="状态" width="90" align="center" />
            <el-table-column
              v-if="canFinanceWrite"
              label="操作"
              width="100"
              align="center"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  :loading="printingOrderId === row.id"
                  @click="onPrintOrder(row)"
                >
                  打印收据
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="compact-data-grid">
            <button
              v-for="row in ordersData?.items || []"
              :key="row.id"
              type="button"
              class="compact-data-card"
              @click="goOrder(row.id, row.order_no)"
            >
              <span class="compact-data-head">
                <strong>{{ row.item || row.order_no }}</strong>
                <b>{{ formatMoney(row.received) }}</b>
              </span>
              <span class="compact-data-meta">
                <span>{{ row.order_type_label }}</span>
                <span>应收 {{ formatMoney(row.receivable) }}</span>
                <span>{{ row.status_label }}</span>
              </span>
              <span class="compact-data-note">{{ row.order_no }}</span>
            </button>
            <p v-if="!ordersData?.items?.length" class="compact-data-empty">暂无消费/订单记录</p>
          </div>
          <div class="tab-foot orders-foot">
            <span>共 {{ ordersData?.total ?? 0 }} 条数据</span>
            <PcPagerBar
              v-if="(ordersData?.total ?? 0) > 0"
              v-model:page="ordersPage"
              v-model:page-size="ordersPageSize"
              :total="ordersData?.total ?? 0"
              @change="() => loadOrders(false)"
            />
          </div>
        </template>

        <!-- 订单明细 -->
        <template v-else>
          <el-table
            v-if="!isApp"
            :data="orderLines"
            border
            stripe
            empty-text="暂无订单明细"
            :header-cell-style="{
              background: '#f5f0e6',
              color: '#44403c',
              fontWeight: '600',
            }"
          >
            <el-table-column label="订单号" min-width="150">
              <template #default="{ row }">
                <button type="button" class="link-btn" @click="goOrder(row.order_id, row.order_no)">
                  {{ row.order_no }}
                </button>
              </template>
            </el-table-column>
            <el-table-column prop="order_type_label" label="订单类型" width="90" align="center" />
            <el-table-column prop="item_name" label="购买项目" min-width="160" show-overflow-tooltip />
            <el-table-column prop="quantity_label" label="数量" width="100" align="center" />
            <el-table-column label="应收(元)" width="110" align="right">
              <template #default="{ row }">{{ formatMoney(row.receivable) }}</template>
            </el-table-column>
            <el-table-column prop="class_name" label="班级" min-width="120" show-overflow-tooltip />
            <el-table-column prop="valid_until" label="有效期" width="120" align="center" />
          </el-table>
          <div v-else class="compact-data-grid">
            <button
              v-for="(row, i) in orderLines"
              :key="`${row.order_id}-${i}`"
              type="button"
              class="compact-data-card"
              @click="goOrder(row.order_id, row.order_no)"
            >
              <span class="compact-data-head">
                <strong>{{ row.item_name }}</strong>
                <b>{{ formatMoney(row.receivable) }}</b>
              </span>
              <span class="compact-data-meta">
                <span>{{ row.order_type_label }}</span>
                <span>{{ row.quantity_label }}</span>
              </span>
              <span class="compact-data-note">{{ row.order_no }}</span>
            </button>
            <p v-if="!orderLines.length" class="compact-data-empty">暂无订单明细</p>
          </div>
          <div class="tab-foot orders-foot">
            <span>共 {{ orderLinesTotal }} 条数据</span>
            <PcPagerBar
              v-if="orderLinesTotal > 0"
              v-model:page="ordersPage"
              v-model:page-size="ordersPageSize"
              :total="orderLinesTotal"
              @change="() => loadOrders(false)"
            />
          </div>
        </template>
      </div>

      <!-- 上课记录 -->
      <div v-else-if="detailTab === 'classRecords'" class="tab-body class-records-module">
        <div class="record-module-toolbar">
          <el-radio-group
            :model-value="classRecordView"
            class="record-view-switch"
            @change="changeClassRecordView"
          >
            <el-radio-button value="completed">已上课记录</el-radio-button>
            <el-radio-button value="pending">待上课记录</el-radio-button>
          </el-radio-group>
          <span class="record-total">共 {{ classRecordsData?.total ?? 0 }} 条</span>
        </div>

        <div class="class-record-filters">
          <div class="record-filter-item record-filter-date">
            <span class="record-filter-label">上课日期</span>
            <el-date-picker
              v-model="classRecordRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              clearable
            />
          </div>
          <div class="record-filter-item">
            <span class="record-filter-label">所在班级</span>
            <el-select v-model="classRecordFilters.class_id" clearable filterable placeholder="全部班级">
              <el-option
                v-for="item in classRecordsData?.filters.classes || []"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </div>
          <div class="record-filter-item">
            <span class="record-filter-label">上课老师</span>
            <el-select v-model="classRecordFilters.teacher_id" clearable filterable placeholder="全部老师">
              <el-option
                v-for="item in classRecordsData?.filters.teachers || []"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </div>
          <div class="record-filter-item">
            <span class="record-filter-label">报读课程</span>
            <el-select v-model="classRecordFilters.course_id" clearable filterable placeholder="全部课程">
              <el-option
                v-for="item in classRecordsData?.filters.courses || []"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
          </div>
          <div v-if="classRecordView === 'completed'" class="record-filter-item">
            <span class="record-filter-label">到课状态</span>
            <el-select v-model="classRecordFilters.attendance_status" clearable placeholder="全部状态">
              <el-option label="到课" value="present" />
              <el-option label="迟到" value="late" />
              <el-option label="请假" value="leave" />
              <el-option label="缺勤" value="absent" />
            </el-select>
          </div>
          <div v-if="classRecordView === 'completed'" class="record-filter-item">
            <span class="record-filter-label">记录状态</span>
            <el-select v-model="classRecordFilters.record_status" clearable placeholder="全部状态">
              <el-option label="正常" value="normal" />
              <el-option label="已撤销" value="void" />
            </el-select>
          </div>
        </div>

        <div class="record-result-toolbar">
          <div v-if="classRecordView === 'completed'" class="record-summary" aria-label="到课统计">
            <span class="record-summary-item is-present">
              <i></i>到课 <strong>{{ classRecordsData?.summary.present ?? 0 }}</strong> 次
            </span>
            <span class="record-summary-item is-late">
              <i></i>迟到 <strong>{{ classRecordsData?.summary.late ?? 0 }}</strong> 次
            </span>
            <span class="record-summary-item is-leave">
              <i></i>请假 <strong>{{ classRecordsData?.summary.leave ?? 0 }}</strong> 次
            </span>
            <span class="record-summary-item is-absent">
              <i></i>缺勤 <strong>{{ classRecordsData?.summary.absent ?? 0 }}</strong> 次
            </span>
          </div>
          <div v-else class="record-pending-hint">待上课 {{ classRecordsData?.total ?? 0 }} 节</div>
          <div class="record-filter-actions">
            <el-button type="primary" @click="loadClassRecords(true)">
              <el-icon><Search /></el-icon>
              查询
            </el-button>
            <el-button @click="resetClassRecordFilters">
              <el-icon><RefreshLeft /></el-icon>
              重置
            </el-button>
            <el-tooltip
              :disabled="!!classRecordsData?.total"
              content="暂无上课记录可导出"
              placement="top"
            >
              <span class="export-btn-wrap">
                <el-button :disabled="!classRecordsData?.total" @click="exportClassRecords">
                  <el-icon><Download /></el-icon>
                  导出
                </el-button>
              </span>
            </el-tooltip>
          </div>
        </div>

        <el-table
          v-if="!isApp"
          :data="classRecordsData?.items || []"
          border
          stripe
          class="class-record-table"
          :empty-text="classRecordView === 'completed' ? '暂无已上课记录' : '暂无待上课记录'"
          :header-cell-style="{
            background: '#f5f0e6',
            color: '#44403c',
            fontWeight: '600',
          }"
        >
          <el-table-column v-if="classRecordView === 'completed'" label="点名时间" min-width="155">
            <template #default="{ row }">{{ formatTime(row.roll_at) }}</template>
          </el-table-column>
          <el-table-column prop="class_name" label="班级名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="course_name" label="课程名称" min-width="150" show-overflow-tooltip />
          <el-table-column label="上课时间" min-width="205">
            <template #default="{ row }">{{ classTimeLabel(row) }}</template>
          </el-table-column>
          <el-table-column prop="teachers" label="上课老师" min-width="130" show-overflow-tooltip />
          <el-table-column label="到课状态" width="95" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                :type="
                  row.attendance_status === 'present'
                    ? 'success'
                    : row.attendance_status === 'late'
                      ? 'warning'
                      : row.attendance_status === 'pending'
                        ? 'info'
                        : 'danger'
                "
              >
                {{ row.attendance_status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="classRecordView === 'completed'" label="补课状态" width="95" align="center">
            <template #default="{ row }">
              <span :class="['makeup-status', { 'is-pending': row.makeup_status_label === '待补课' }]">
                {{ row.makeup_status_label }}
              </span>
            </template>
          </el-table-column>
          <el-table-column v-if="classRecordView === 'completed'" prop="consumption_type" label="消耗方式" width="90" align="center" />
          <el-table-column v-if="classRecordView === 'completed'" label="扣除额度" width="100" align="right">
            <template #default="{ row }">{{ hoursLabel(row.hours_consumed) }}</template>
          </el-table-column>
          <el-table-column v-if="classRecordView === 'completed'" label="课消金额" width="105" align="right">
            <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="content" label="上课内容" min-width="160" show-overflow-tooltip />
          <el-table-column prop="notes" label="备注/教室" min-width="110" show-overflow-tooltip />
          <el-table-column fixed="right" label="操作" width="110" align="center">
            <template #default="{ row }">
              <el-button link type="primary" @click="openClassRecordDetail(row)">
                <el-icon><View /></el-icon>
                {{ row.row_type === 'completed' ? '点名详情' : '查看排课' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-else class="compact-data-grid">
          <button
            v-for="row in classRecordsData?.items || []"
            :key="`${row.row_type}-${row.id}`"
            type="button"
            class="compact-data-card"
            @click="openClassRecordDetail(row)"
          >
            <span class="compact-data-head">
              <strong>{{ row.class_name || row.course_name }}</strong>
              <el-tag size="small" effect="plain">{{ row.attendance_status_label }}</el-tag>
            </span>
            <span class="compact-data-meta">
              <span>{{ classTimeLabel(row) }}</span>
              <span>{{ row.teachers || '未填老师' }}</span>
              <span v-if="row.hours_consumed != null">扣 {{ hoursLabel(row.hours_consumed) }}</span>
            </span>
            <span v-if="row.content" class="compact-data-note">{{ row.content }}</span>
          </button>
          <p v-if="!classRecordsData?.items?.length" class="compact-data-empty">
            {{ classRecordView === 'completed' ? '暂无已上课记录' : '暂无待上课记录' }}
          </p>
        </div>

        <PcPagerBar
          v-model:page="classRecordPage"
          v-model:page-size="classRecordPageSize"
          :total="classRecordsData?.total ?? 0"
          @change="loadClassRecords()"
        />
      </div>

      <!-- 学情时间线 -->
      <div v-else-if="detailTab === 'learning'" class="tab-body">
        <div class="section-row in-tab">
          <h3 class="section-title">学情时间线</h3>
          <el-button v-if="canWrite && !isApp" type="primary" @click="openWrite">编写学情</el-button>
        </div>
        <div v-if="!records.length && isApp" class="oc-app-empty compact-empty-state">
          <strong>暂无学情记录</strong>
          <em>记录课堂掌握点、作业与下次建议，方便家校同步</em>
          <el-button v-if="canWrite" type="primary" @click="openWrite">录学情</el-button>
        </div>
        <el-empty v-else-if="!records.length" description="暂无学情，点击「编写学情」开始记录" />
        <el-timeline v-else class="learning-timeline">
          <el-timeline-item
            v-for="r in records"
            :key="r.id"
            :timestamp="formatTime(r.class_date)"
            placement="top"
          >
            <el-card shadow="hover" class="rec-card">
              <div class="rec-head">
                <el-tag
                  size="small"
                  effect="dark"
                  :type="classTagType[r.class_status] || 'info'"
                  class="tag-status"
                >
                  {{ classLabels[r.class_status] || r.class_status }}
                </el-tag>
                <el-tag
                  v-if="r.subject"
                  size="small"
                  effect="plain"
                  type="warning"
                  class="tag-subject"
                >
                  {{ r.subject }}
                </el-tag>
                <el-tag
                  v-if="r.teacher_name"
                  size="small"
                  effect="plain"
                  type="info"
                  class="tag-author"
                >
                  填写人 · {{ r.teacher_name }}
                </el-tag>
              </div>

              <div class="rec-fields">
                <div class="rec-field">
                  <div class="rec-field-title">学习情况</div>
                  <div class="rec-field-content">{{ r.learning_summary || '—' }}</div>
                </div>

                <div v-if="r.homework_note" class="rec-field">
                  <div class="rec-field-title">作业 / 下次</div>
                  <div class="rec-field-content">{{ r.homework_note }}</div>
                </div>

                <div v-if="r.notes" class="rec-field">
                  <div class="rec-field-title">内部备注</div>
                  <div class="rec-field-content">{{ r.notes }}</div>
                </div>

                <div v-if="r.files?.length" class="rec-field rec-field-imgs">
                  <div class="rec-field-title">
                    附件图片
                    <span class="rec-field-count">{{ r.files.length }}</span>
                  </div>
                  <div class="imgs">
                    <el-image
                      v-for="f in r.files"
                      :key="f.id"
                      :src="imageUrls[f.id]"
                      :preview-src-list="recordPreviewList(r)"
                      :initial-index="recordPreviewIndex(r, f.id)"
                      preview-teleported
                      lazy
                      fit="cover"
                      class="thumb"
                    />
                  </div>
                </div>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>

      <!-- 学员动态 -->
      <div v-else class="tab-body">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="展示报名、学情、跟进人等关键动态记录"
          class="activity-tip"
        />
        <div class="activity-filters">
          <el-radio-group v-model="activityFilter" size="small">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="manager">跟进人变动</el-radio-button>
            <el-radio-button value="enroll">报名记录</el-radio-button>
            <el-radio-button value="learning">学情记录</el-radio-button>
          </el-radio-group>
        </div>
        <el-empty v-if="!filteredActivity.length" description="暂无动态" />
        <el-timeline v-else class="activity-timeline">
          <el-timeline-item
            v-for="e in filteredActivity"
            :key="e.id"
            :timestamp="formatTime(e.at)"
            placement="top"
          >
            <el-card shadow="never" class="act-card">
              <div class="act-head">
                <el-tag size="small" effect="plain" type="warning">{{ e.kind_label }}</el-tag>
                <span class="act-title">{{ e.title }}</span>
              </div>
              <div v-for="(line, i) in e.lines" :key="i" class="act-line">
                <template v-if="line.startsWith('订单号:') && e.order_id">
                  订单号：
                  <button type="button" class="link-btn" @click="goOrder(e.order_id, e.order_no)">
                    {{ e.order_no || line.replace('订单号:', '') }}
                  </button>
                </template>
                <template v-else>{{ line }}</template>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <div class="tab-foot">共 {{ filteredActivity.length }} 条数据</div>
      </div>
    </el-card>

    <component
      :is="responsiveSurface"
      v-model="classRecordDetailVisible"
      :title="pendingRecordDetail ? '待上课排课详情' : '点名详情'"
      v-bind="classRecordSurfaceProps"
      destroy-on-close
    >
      <div v-loading="classRecordDetailLoading">
        <el-descriptions v-if="pendingRecordDetail && !isApp" :column="2" border>
          <el-descriptions-item label="班级">{{ pendingRecordDetail.class_name }}</el-descriptions-item>
          <el-descriptions-item label="课程">{{ pendingRecordDetail.course_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="上课时间">{{ classTimeLabel(pendingRecordDetail) }}</el-descriptions-item>
          <el-descriptions-item label="老师">{{ pendingRecordDetail.teachers || '—' }}</el-descriptions-item>
          <el-descriptions-item label="教室">{{ pendingRecordDetail.notes || '—' }}</el-descriptions-item>
          <el-descriptions-item label="上课内容">{{ pendingRecordDetail.content || '—' }}</el-descriptions-item>
        </el-descriptions>

        <section v-else-if="pendingRecordDetail" class="record-sheet-summary">
          <div class="record-sheet-summary__head">
            <strong>{{ pendingRecordDetail.class_name }}</strong>
            <el-tag size="small" type="warning" effect="plain">待上课</el-tag>
          </div>
          <div class="record-sheet-summary__facts">
            <span><em>课程</em><b>{{ pendingRecordDetail.course_name || '未关联' }}</b></span>
            <span><em>时间</em><b>{{ classTimeLabel(pendingRecordDetail) }}</b></span>
            <span><em>老师</em><b>{{ pendingRecordDetail.teachers || '未填写' }}</b></span>
            <span><em>教室</em><b>{{ pendingRecordDetail.notes || '未填写' }}</b></span>
          </div>
          <p v-if="pendingRecordDetail.content">{{ pendingRecordDetail.content }}</p>
        </section>

        <template v-else-if="classRecordDetail">
          <el-descriptions v-if="!isApp" :column="2" border class="record-detail-descriptions">
            <el-descriptions-item label="班级">{{ classRecordDetail.class_name }}</el-descriptions-item>
            <el-descriptions-item label="课程">{{ classRecordDetail.course_name || '—' }}</el-descriptions-item>
            <el-descriptions-item label="上课时间">
              {{ formatTime(classRecordDetail.class_start || classRecordDetail.roll_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="上课老师">{{ classRecordDetail.teachers || '—' }}</el-descriptions-item>
            <el-descriptions-item label="教室">{{ classRecordDetail.room || '—' }}</el-descriptions-item>
            <el-descriptions-item label="记录状态">{{ classRecordDetail.status_label }}</el-descriptions-item>
            <el-descriptions-item label="上课内容" :span="2">{{ classRecordDetail.content || '—' }}</el-descriptions-item>
          </el-descriptions>
          <section v-else class="record-sheet-summary">
            <div class="record-sheet-summary__head">
              <strong>{{ classRecordDetail.class_name }}</strong>
              <el-tag size="small" effect="plain">{{ classRecordDetail.status_label }}</el-tag>
            </div>
            <div class="record-sheet-summary__facts">
              <span><em>课程</em><b>{{ classRecordDetail.course_name || '未关联' }}</b></span>
              <span><em>时间</em><b>{{ formatTime(classRecordDetail.class_start || classRecordDetail.roll_at) }}</b></span>
              <span><em>老师</em><b>{{ classRecordDetail.teachers || '未填写' }}</b></span>
              <span><em>教室</em><b>{{ classRecordDetail.room || '未填写' }}</b></span>
            </div>
            <p v-if="classRecordDetail.content">{{ classRecordDetail.content }}</p>
          </section>
          <el-table v-if="!isApp" :data="classRecordDetail.attendances || []" border class="record-detail-table">
            <el-table-column prop="student_name" label="学员" min-width="120" />
            <el-table-column prop="status_label" label="到课状态" width="100" align="center" />
            <el-table-column label="扣除课时" width="105" align="right">
              <template #default="{ row }">{{ hoursLabel(row.hours_consumed) }}</template>
            </el-table-column>
            <el-table-column label="超上课时" width="105" align="right">
              <template #default="{ row }">{{ hoursLabel(row.uncovered_hours) }}</template>
            </el-table-column>
            <el-table-column label="课消金额" width="115" align="right">
              <template #default="{ row }">¥ {{ formatMoney(row.amount) }}</template>
            </el-table-column>
          </el-table>
          <div v-else class="record-attendance-cards">
            <article v-for="row in classRecordDetail.attendances || []" :key="row.student_id || row.student_name" class="record-attendance-card">
              <div class="record-attendance-card__head"><strong>{{ row.student_name }}</strong><el-tag size="small" effect="plain">{{ row.status_label }}</el-tag></div>
              <div class="record-attendance-card__meta">
                <span>扣除 {{ hoursLabel(row.hours_consumed) }}</span>
                <span>超上 {{ hoursLabel(row.uncovered_hours) }}</span>
                <span>课消 ¥ {{ formatMoney(row.amount) }}</span>
              </div>
            </article>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="classRecordDetailVisible = false">关闭</el-button>
      </template>
    </component>

    <component
      :is="responsiveSurface"
      v-model="reportVisible"
      title="生成学情报告"
      v-bind="reportSurfaceProps"
      destroy-on-close
    >
      <p class="report-hint">
        可导出全部学情、按上课日期区间，或勾选指定的某一次/几次学情。PDF 正文不展示筛选条件。
      </p>
      <el-form label-position="top">
        <el-form-item label="导出范围">
          <el-radio-group v-model="reportMode" class="report-mode">
            <el-radio-button value="all">全部学情</el-radio-button>
            <el-radio-button value="range">时间区间</el-radio-button>
            <el-radio-button value="records">指定学情</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="reportMode === 'range'" label="学情上课日期">
          <el-date-picker
            v-model="reportRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            style="width: 100%"
            clearable
          />
        </el-form-item>

        <el-form-item v-if="reportMode === 'records'" label="选择学情记录">
          <el-empty v-if="!records.length" description="暂无学情可选" :image-size="64" />
          <el-checkbox-group v-else v-model="reportRecordIds" class="report-record-list">
            <el-checkbox
              v-for="r in records"
              :key="r.id"
              :value="r.id"
              :label="r.id"
              class="report-record-item"
            >
              {{ recordOptionLabel(r) }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportVisible = false">取消</el-button>
        <el-button type="primary" :loading="reportLoading" @click="submitReport">
          生成 PDF
        </el-button>
      </template>
    </component>

    <component
      :is="responsiveSurface"
      v-model="writeVisible"
      title="编写学情"
      v-bind="writeSurfaceProps"
      destroy-on-close
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="student-learning-form"
        :class="{ 'is-compact': isApp }"
      >
        <el-form-item label="上课日期">
          <el-date-picker v-model="form.class_date" type="datetime" style="width: 100%" />
        </el-form-item>
        <el-form-item label="科目">
          <el-input v-model="form.subject" placeholder="可选" />
        </el-form-item>
        <el-form-item class="student-learning-form__full" label="上课状态" prop="class_status">
          <el-radio-group v-model="form.class_status" class="status-group">
            <el-radio-button v-for="(label, key) in classLabels" :key="key" :value="key">
              {{ label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item class="student-learning-form__full" label="学习情况" prop="learning_summary">
          <el-input v-model="form.learning_summary" type="textarea" :rows="4" placeholder="今日掌握点、问题、亮点…" />
        </el-form-item>
        <el-form-item class="student-learning-form__full" label="作业 / 下次建议">
          <el-input v-model="form.homework_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item class="student-learning-form__full" label="内部备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item class="student-learning-form__full" label="图片">
          <el-upload
            v-model:file-list="fileList"
            list-type="picture-card"
            :auto-upload="false"
            accept="image/*"
            multiple
            aria-label="添加学情图片"
          >
            <el-icon><Plus /></el-icon>
            <span class="oc-visually-hidden">添加学情图片</span>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="writeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitLearning">提交</el-button>
      </template>
    </component>

    <!-- 编辑学生档案（不要求关联课程） -->
    <component
      :is="responsiveSurface"
      v-model="editVisible"
      title="编辑学生"
      v-bind="editSurfaceProps"
      destroy-on-close
      append-to-body
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editRules"
        label-position="top"
        class="student-edit-form"
      >
        <el-form-item label="学生姓名" prop="name">
          <el-input v-model="editForm.name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-select v-model="editForm.grade" filterable allow-create style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="学校" prop="school">
          <el-input v-model="editForm.school" placeholder="就读学校" />
        </el-form-item>
        <el-form-item label="学管师（班主任）" prop="academic_manager_id">
          <el-select
            v-model="editForm.academic_manager_id"
            placeholder="选择学管师"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="m in activeManagers"
              :key="m.id"
              :label="managerOptionLabel(m)"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话" prop="phone">
          <el-input
            v-model="editForm.phone"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="11"
            placeholder="请输入11位手机号"
            @input="editForm.phone = sanitizePhoneInput(editForm.phone)"
          />
        </el-form-item>
        <el-form-item label="家长称呼">
          <el-input v-model="editForm.parent_name" placeholder="如：张妈妈" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEditProfile">保存</el-button>
      </template>
    </component>

    <component
      :is="financeSurface"
      v-model="financeDialogVisible"
      title="退课"
      v-bind="financeSurfaceProps"
      destroy-on-close
      append-to-body
    >
      <p class="finance-dialog-hint">
        创建退课财务订单。可选择同步清零该课程剩余课时并结课。
      </p>
      <el-form label-position="top">
        <el-form-item label="学员">
          <el-input :model-value="student?.name || ''" disabled />
        </el-form-item>
        <el-form-item v-if="financeForm.course_name" label="关联课程">
          <el-input :model-value="financeForm.course_name" disabled />
        </el-form-item>
        <el-form-item label="购买项目 / 摘要" required>
          <el-input v-model="financeForm.item_summary" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="应退金额(元)">
          <el-input-number v-model="financeForm.receivable" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="实退金额(元)">
          <el-input-number v-model="financeForm.received" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="支付方式">
          <el-select v-model="financeForm.pay_method" style="width: 100%">
            <el-option label="微信" value="微信" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="现金" value="现金" />
            <el-option label="银行卡" value="银行卡" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="financeForm.course_id">
          <el-checkbox v-model="financeForm.clear_remain">
            同步清零该课程剩余课时并结课
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="financeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="financeSaving" @click="submitFinanceOrder">
          确认退课
        </el-button>
      </template>
    </component>

    <MobileActionBar :visible="isApp && Boolean(student)">
      <el-button
        v-if="!auth.isTeacher && student?.phone"
        plain
        @click="dialStudent"
      >
        联系
      </el-button>
      <el-button
        v-else-if="canWrite && canEnrollManage"
        plain
        @click="goEnroll"
      >
        报名
      </el-button>
      <!-- 待报名：运营主操作去完成报名 -->
      <el-button
        v-if="canEnrollManage && student?.allocation_phase === 'pending_enroll'"
        type="primary"
        @click="goEnroll"
      >
        去完成报名
      </el-button>
      <el-button v-else-if="canWrite" type="primary" @click="openWrite">录学情</el-button>
      <el-button
        v-else-if="canEnrollManage"
        type="primary"
        @click="goEnroll"
      >
        报名
      </el-button>
      <el-button
        v-else-if="canEditProfile"
        type="primary"
        plain
        @click="openEditProfile"
      >
        编辑
      </el-button>
    </MobileActionBar>
  </div>
</template>

<style scoped>
.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.phase-tag {
  margin-right: 2px;
}

.export-btn-wrap {
  display: inline-flex;
  vertical-align: middle;
}

.export-btn-wrap .el-button {
  margin: 0;
}

.student-edit-form {
  display: grid;
  gap: 2px;
}

.compact-report-button {
  appearance: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 44px;
  border: 0;
  background: transparent;
  color: var(--oc-ink, #44403c);
  cursor: pointer;
}

.compact-report-button {
  min-height: 36px;
  gap: 5px;
  padding: 0 8px;
  border-radius: 6px;
  background: rgba(161, 98, 7, 0.08);
  color: #8b5406;
  font-size: 13px;
  font-weight: 650;
}

.compact-profile__actions {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.compact-profile {
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid #e1cfad;
  border-radius: 8px;
  background: linear-gradient(135deg, #fffdf8 0%, #faf6ee 48%, #f5e6c8 120%);
  box-shadow: 0 6px 18px rgba(88, 60, 24, 0.08);
}

.compact-profile__identity {
  display: flex;
  align-items: center;
  gap: 10px;
}

.compact-profile__avatar {
  flex: 0 0 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: 1px solid #d0a75f;
  border-radius: 8px;
  background: linear-gradient(145deg, #d5ad6f, #b7791f);
  color: #fffdf8;
  font-size: 17px;
  font-weight: 750;
}

.compact-profile__name {
  min-width: 0;
  flex: 1;
}

.compact-profile__name strong,
.compact-profile__name span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-profile__name strong {
  color: #3f3a34;
  font-size: 17px;
  line-height: 1.3;
}

.compact-profile__name span {
  margin-top: 3px;
  color: #78716c;
  font-size: 12px;
}

.compact-profile__facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.compact-profile__fact {
  min-width: 0;
  min-height: 58px;
  padding: 9px 10px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.62);
}

.compact-profile__fact span,
.compact-profile__fact strong,
.compact-profile__fact a {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-profile__fact span {
  color: #8b8278;
  font-size: 11px;
}

.compact-profile__fact strong,
.compact-profile__fact a {
  margin-top: 3px;
  color: #44403c;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.compact-profile__fact a {
  color: #8b5406;
}

.compact-profile__notes {
  margin: 11px 0 0;
  padding: 9px 10px;
  border-left: 3px solid #d4a853;
  border-radius: 0 6px 6px 0;
  background: rgba(255, 253, 248, 0.72);
  color: #6f675e;
  font-size: 12px;
  line-height: 1.5;
}

.compact-profile__notes span {
  margin-right: 8px;
  color: #8b5406;
  font-weight: 650;
}

.compact-detail-tabs {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  border: 1px solid #dde2e8;
  border-radius: 8px;
  background: #f1f3f5;
}

.compact-detail-tabs button {
  position: relative;
  min-width: 0;
  height: 40px;
  padding: 0 4px;
  border: 0;
  background: transparent;
  border-radius: 6px;
  color: #69717d;
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;
}

.compact-detail-tabs button::after {
  display: none;
}

.compact-detail-tabs button.is-active {
  background: #fff;
  color: #8b5406;
  font-weight: 700;
  box-shadow: 0 1px 4px rgba(31, 35, 40, 0.1);
}

.compact-detail-tabs button.is-active::after {
  background: var(--oc-primary, #a16207);
}

.compact-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 132px;
  margin-top: 10px;
  border: 1px dashed #cfd5dc;
  border-radius: 8px;
  background: #f8f9fa;
  color: #69717d;
  font-size: 13px;
}

.compact-empty-state .el-icon {
  font-size: 28px;
  color: #a7afb9;
}

.record-sheet-summary {
  padding-bottom: 12px;
}

.record-sheet-summary__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.record-sheet-summary__head strong {
  min-width: 0;
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 16px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-sheet-summary__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 14px;
  margin-top: 12px;
}

.record-sheet-summary__facts span,
.record-sheet-summary__facts em,
.record-sheet-summary__facts b {
  display: block;
  min-width: 0;
}

.record-sheet-summary__facts em {
  color: #a8a29e;
  font-size: 11px;
  font-style: normal;
}

.record-sheet-summary__facts b {
  margin-top: 3px;
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.record-sheet-summary > p {
  margin: 12px 0 0;
  padding: 9px 10px;
  background: #faf6ee;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  line-height: 1.5;
}

.student-learning-form.is-compact {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.student-learning-form__full {
  grid-column: 1 / -1;
}

.student-learning-form.is-compact :deep(.el-form-item) {
  min-width: 0;
  margin-bottom: 14px;
}

.profile {
  margin-bottom: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-top: 3px solid var(--oc-primary, #a16207);
  background: var(--oc-card, #fffdf8);
  box-shadow: var(--oc-shadow, 0 8px 24px rgba(41, 37, 36, 0.06));
}

.profile :deep(.el-card__body) {
  padding: 16px;
}

.profile :deep(.el-descriptions__label.el-descriptions__cell) {
  width: 108px;
  background: #f5f0e6;
  color: var(--oc-ink, #44403c);
  font-weight: 650;
}

.profile :deep(.el-descriptions__content.el-descriptions__cell) {
  background: var(--oc-card, #fffdf8);
  color: var(--oc-ink, #44403c);
}

.tabs-card {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: var(--oc-card, #fffdf8);
  margin-bottom: 20px;
  box-shadow: var(--oc-shadow, 0 8px 24px rgba(41, 37, 36, 0.06));
}

.tabs-card :deep(.el-card__body) {
  padding: 8px 18px 18px;
}

.tabs-card.is-compact {
  margin-bottom: 10px;
  border: 1px solid #dde2e8;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(31, 35, 40, 0.06);
}

.tabs-card.is-compact :deep(.el-card__body) {
  padding: 10px;
}

.tabs-card.is-compact .tab-body {
  min-height: 0;
  padding-top: 12px;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.detail-tabs :deep(.el-tabs__item) {
  height: 44px;
  padding: 0 20px;
  color: var(--oc-muted, #78716c);
}

.detail-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--oc-border, #e8e0d0);
}

.detail-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--oc-primary, #a16207);
}

.tab-body {
  min-height: 120px;
  padding-top: 4px;
}

.summary-bar {
  background: #faf3e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 14px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 6px;
}

.summary-bar strong {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  margin-right: 8px;
}

.sum-gap {
  margin-left: 12px;
}

.course-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.course-toolbar-left {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.course-block {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
  padding: 12px 14px 14px;
  margin-bottom: 14px;
  background: #fffdfb;
}

.course-block.is-closed {
  opacity: 0.78;
  background: #fafafa;
}

.course-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.course-block-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  font-size: 15px;
  flex-wrap: wrap;
}

.course-block-actions {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 2px 4px;
}

.course-icon {
  color: var(--oc-primary, #a16207);
}

.course-block-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 8px;
}

.meta-link {
  margin-left: 6px;
  font-weight: 500;
  font-size: 12px;
}

.pkg-table {
  margin-top: 8px;
  width: 100%;
}

.valid-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
}

.remain-warn {
  color: #a8a29e;
}

.op-dash {
  color: #c4b5a0;
}

.compact-data-card.is-static {
  cursor: default;
  text-align: left;
}

.compact-data-card .linkish {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  width: 100%;
  cursor: pointer;
  font: inherit;
  text-align: left;
}

.compact-data-card .linkish:disabled {
  cursor: default;
}

.compact-pkg-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
}

.pkg-app-grid {
  gap: 10px;
}

.pkg-app-card {
  padding: 12px 12px 10px;
  border-radius: 14px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background: linear-gradient(160deg, #fffefb, #faf6ee);
}

.pkg-app-card .pkg-remain {
  color: var(--oc-primary, #a16207);
  font-weight: 750;
}

.pkg-app-card .pkg-remain.is-warn {
  color: #b91c1c;
}

.pkg-app-chips {
  margin: 8px 0 4px;
}

.orders-sub-tabs {
  margin-bottom: 12px;
}

.orders-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  align-items: center;
}

.orders-filter-status {
  min-width: 160px;
  width: 180px;
}

.orders-filter-type {
  min-width: 120px;
  width: 140px;
}

.orders-filter-item {
  min-width: 160px;
  width: 200px;
  flex: 1 1 180px;
}

.orders-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.finance-dialog-hint {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #faf3e6;
  color: #78716c;
  font-size: 13px;
  line-height: 1.5;
}

.link-btn {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font: inherit;
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.link-btn:hover {
  text-decoration: underline;
}

.tab-foot {
  margin-top: 10px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.activity-tip {
  margin-bottom: 12px;
}

.activity-filters {
  margin-bottom: 14px;
}

.act-card {
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fff;
}

.act-card :deep(.el-card__body) {
  padding: 12px 14px;
}

.act-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.act-title {
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
}

.act-line {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  line-height: 1.6;
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 12px;
  flex-wrap: wrap;
}

.section-row.in-tab {
  margin-top: 0;
}

.section-title {
  margin: 0;
  font-size: 1.05rem;
  color: var(--oc-ink, #44403c);
}

.status-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.status-group :deep(.el-radio-button) {
  margin: 0;
}

@media (max-width: 767px) {
  .section-row .el-button {
    width: auto;
  }

  .thumb {
    width: 96px;
    height: 96px;
  }
}

.rec-card {
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
}

.rec-card :deep(.el-card__body) {
  padding: 14px 16px 16px;
}

/* 顶部：上课状态 / 科目 / 填写人 — 不同色标签 */
.rec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--oc-border, #f0e9dc);
}

.tag-status {
  font-weight: 650;
}

.tag-subject {
  --el-tag-border-color: #e8c98a;
  --el-tag-text-color: #92400e;
  --el-tag-bg-color: #fff7ed;
  font-weight: 600;
}

.tag-author {
  --el-tag-border-color: #c4b5a0;
  --el-tag-text-color: #57534e;
  --el-tag-bg-color: #f5f0e6;
}

/* 字段区：左标题右内容，一眼区分 */
.rec-fields {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.rec-field {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px 14px;
  padding: 12px 0;
  border-bottom: 1px dashed #efe8db;
  align-items: start;
}

.rec-field:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.rec-field:first-child {
  padding-top: 0;
}

.rec-field-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  line-height: 1.5;
  padding-top: 1px;
  display: flex;
  align-items: center;
  gap: 6px;
  /* 左侧色条强调「这是标题」 */
  border-left: 3px solid var(--oc-primary, #a16207);
  padding-left: 8px;
}

.rec-field-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  background: #f5e6c8;
  color: var(--oc-primary, #a16207);
}

.rec-field-content {
  margin: 0;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.6;
  color: #57534e;
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
}

.rec-field-imgs .rec-field-content,
.rec-field-imgs .imgs {
  grid-column: 2;
}

.report-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  line-height: 1.5;
}

.report-mode {
  display: flex;
  flex-wrap: wrap;
}

.report-record-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
  width: 100%;
  padding: 4px 0;
}

.report-record-item {
  margin: 0 !important;
  height: auto;
  align-items: flex-start;
  white-space: normal;
  line-height: 1.45;
  padding: 8px 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fffdf8;
}

.report-record-item :deep(.el-checkbox__label) {
  white-space: normal;
  font-size: 13px;
  color: var(--oc-ink, #44403c);
}

.imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.thumb {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

/* 窄屏：标题在上、内容在下，仍保持标题加粗 + 色条 */
@media (max-width: 767px) {
  .rec-field {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .rec-field-imgs .imgs {
    grid-column: 1;
  }

  .thumb {
    width: 88px;
    height: 88px;
  }
}

/*
 * EP 默认 is-start 左内边距 40px + wrapper 28px，PC 也偏宽。
 * 统一收紧：节点/竖线左移，内容区更贴左。
 */
.learning-timeline {
  padding-left: 12px !important;
  padding-right: 0 !important;
}

.learning-timeline :deep(.el-timeline-item__wrapper) {
  padding-left: 16px !important;
}

.learning-timeline :deep(.el-timeline-item__tail) {
  left: 2px;
}

.learning-timeline :deep(.el-timeline-item__node) {
  left: 0;
}

.learning-timeline :deep(.el-timeline-item__timestamp) {
  font-size: 12px;
}

.learning-timeline :deep(.el-timeline-item__timestamp.is-top) {
  margin-bottom: 6px;
}

@media (max-width: 1199px) {
  .learning-timeline {
    padding-left: 10px !important;
  }

  .learning-timeline :deep(.el-timeline-item__wrapper) {
    padding-left: 14px !important;
  }

  .rec-card :deep(.el-card__body) {
    padding: 12px;
  }
}

@media (max-width: 767px) {
  .learning-timeline {
    padding-left: 8px !important;
  }

  .learning-timeline :deep(.el-timeline-item__wrapper) {
    padding-left: 12px !important;
  }

  .learning-timeline :deep(.el-timeline-item) {
    padding-bottom: 14px;
  }
}

.record-module-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 2px 0 14px;
}

.record-view-switch {
  padding: 3px;
  border-radius: 7px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #f5f0e6;
}

.record-view-switch :deep(.el-radio-button__inner) {
  min-width: 112px;
  height: 34px;
  padding: 8px 16px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--oc-muted, #78716c);
  box-shadow: none;
  font-weight: 600;
}

.record-view-switch :deep(.el-radio-button:first-child .el-radio-button__inner),
.record-view-switch :deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 5px;
}

.record-view-switch :deep(.el-radio-button.is-active .el-radio-button__inner),
.record-view-switch :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(145deg, #b7791f 0%, var(--oc-primary, #a16207) 72%);
  color: #fffdf8;
  box-shadow: 0 3px 9px rgba(161, 98, 7, 0.25);
}

.record-total {
  padding: 5px 10px;
  border: 1px solid #e6d2b3;
  border-radius: 999px;
  background: #faf3e6;
  color: var(--oc-primary, #a16207);
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.class-record-filters {
  display: grid;
  grid-template-columns: repeat(3, minmax(240px, 1fr));
  gap: 14px 22px;
  padding: 18px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 7px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
  box-shadow: inset 3px 0 0 rgba(161, 98, 7, 0.72);
}

.record-filter-item {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.record-filter-item :deep(.el-select),
.record-filter-item :deep(.el-date-editor) {
  width: 100%;
}

.record-filter-item :deep(.el-select__wrapper),
.record-filter-item :deep(.el-input__wrapper),
.record-filter-item :deep(.el-range-editor.el-input__wrapper) {
  min-height: 36px;
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 0 0 1px var(--oc-border, #e8e0d0) inset;
}

.record-filter-item :deep(.el-select__wrapper:hover),
.record-filter-item :deep(.el-input__wrapper:hover),
.record-filter-item :deep(.el-range-editor.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #c9a066 inset;
}

.record-filter-label {
  color: var(--oc-ink, #44403c);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.record-result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 52px;
  margin: 12px 0;
  padding: 9px 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 7px;
  background: linear-gradient(90deg, rgba(245, 230, 200, 0.42) 0%, rgba(255, 253, 248, 0.92) 58%);
}

.record-filter-actions {
  display: flex;
  flex: 0 0 auto;
  flex-wrap: wrap;
  gap: 8px;
}

.record-filter-actions .el-button + .el-button {
  margin-left: 0;
}

.record-filter-actions :deep(.el-button) {
  min-width: 84px;
  font-weight: 600;
}

.record-filter-actions :deep(.el-button--primary) {
  box-shadow: 0 3px 9px rgba(161, 98, 7, 0.22);
}

.record-filter-actions :deep(.el-button:not(.el-button--primary)) {
  border-color: #dbbf94;
  background: #fffdf8;
  color: #6b4f25;
}

.record-summary {
  display: flex;
  align-items: center;
  min-width: 0;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.record-summary-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 0 18px;
  border-right: 1px solid #e6d2b3;
  white-space: nowrap;
}

.record-summary-item:first-child {
  padding-left: 2px;
}

.record-summary-item:last-child {
  border-right: 0;
}

.record-summary-item i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #a8a29e;
}

.record-summary-item strong {
  color: var(--oc-ink, #44403c);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.record-summary-item.is-present i {
  background: #3f8f61;
}

.record-summary-item.is-late i {
  background: #d08a17;
}

.record-summary-item.is-leave i {
  background: #8b7658;
}

.record-summary-item.is-absent i {
  background: #c74f4f;
}

.record-pending-hint {
  color: var(--oc-primary, #a16207);
  font-size: 13px;
  font-weight: 600;
}

.class-record-table {
  width: 100%;
  border-radius: 6px;
  font-size: 13px;
}

.class-record-table :deep(.el-table__header th.el-table__cell) {
  height: 44px;
  padding: 0;
  border-bottom-color: #dbbf94;
}

.class-record-table :deep(.el-table__body td.el-table__cell) {
  height: 48px;
  padding: 7px 0;
  color: var(--oc-ink, #44403c);
}

.class-record-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee;
}

.class-record-table :deep(.el-tag) {
  min-width: 48px;
  justify-content: center;
  border-radius: 4px;
  font-weight: 600;
}

.class-record-table :deep(.el-button.is-link) {
  gap: 4px;
  font-weight: 600;
}

.makeup-status {
  color: var(--oc-muted, #78716c);
}

.makeup-status.is-pending {
  color: #b33f3f;
  font-weight: 600;
}

.class-records-module :deep(.pc-pager) {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #f0e9dc;
}

.record-detail-descriptions {
  margin-bottom: 14px;
}

.record-detail-table {
  width: 100%;
}

.record-attendance-cards {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.record-attendance-card {
  padding: 10px 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: var(--oc-card, #fffdf8);
}

.record-attendance-card__head,
.record-attendance-card__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px 12px;
}

.record-attendance-card__meta {
  flex-wrap: wrap;
  margin-top: 8px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

@media (max-width: 1180px) {
  .class-record-filters {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }

  .record-result-toolbar {
    align-items: flex-start;
    flex-direction: column;
    padding-bottom: 12px;
  }
}

@media (max-width: 767px) {
  .student-learning-form.is-compact {
    grid-template-columns: 1fr;
  }

  .student-learning-form__full {
    grid-column: auto;
  }

  .compact-profile__facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .compact-profile__fact:nth-child(3):last-child {
    grid-column: 1 / -1;
  }

  .compact-detail-tabs button {
    font-size: 12px;
  }

  .compact-detail-tabs button::after {
    right: 8px;
    left: 8px;
  }

  .profile :deep(.el-card__body) {
    padding: 12px;
  }

  .profile :deep(.el-descriptions__label.el-descriptions__cell) {
    width: 72px;
  }

  .tabs-card :deep(.el-card__body) {
    padding: 6px 12px 14px;
  }

  .detail-tabs :deep(.el-tabs__item) {
    padding: 0 14px;
  }

  .tabs-card.is-compact .section-row {
    min-height: 44px;
    margin-bottom: 6px;
  }

  .tabs-card.is-compact .section-title {
    font-size: 15px;
  }

  .tabs-card.is-compact .section-row .el-button {
    height: 40px;
    padding: 0 14px;
  }

  .record-module-toolbar {
    align-items: flex-start;
    flex-direction: column;
    gap: 8px;
  }

  .record-view-switch {
    width: 100%;
  }

  .record-view-switch :deep(.el-radio-button) {
    width: 50%;
  }

  .record-view-switch :deep(.el-radio-button__inner) {
    width: 100%;
    min-width: 0;
  }

  .class-record-filters {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    padding: 10px;
  }

  .record-filter-date {
    grid-column: 1 / -1;
  }

  .record-filter-item {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .record-result-toolbar {
    gap: 12px;
  }

  .record-summary {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
    row-gap: 10px;
  }

  .record-summary-item,
  .record-summary-item:first-child {
    justify-content: flex-start;
    padding: 0;
    border-right: 0;
  }

  .record-filter-actions {
    width: 100%;
  }

  .record-filter-actions .el-button {
    flex: 1 1 88px;
  }
}

.compact-data-grid {
  display: grid;
  gap: 8px;
}

.compact-data-card {
  appearance: none;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #dde2e8;
  border-left: 3px solid #b7791f;
  border-radius: 8px;
  background: #fff;
  color: inherit;
  text-align: left;
  box-shadow: 0 1px 4px rgba(31, 35, 40, 0.05);
}

.compact-data-card:disabled {
  cursor: default;
}

.compact-data-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.compact-data-head strong {
  min-width: 0;
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-data-head b {
  flex-shrink: 0;
  color: var(--oc-primary, #a16207);
  font-size: 14px;
}

.compact-data-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 6px;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
}

.compact-data-note {
  display: block;
  margin-top: 6px;
  overflow: hidden;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-data-empty {
  grid-column: 1 / -1;
  margin: 18px 0;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  text-align: center;
}

@media (min-width: 768px) and (max-width: 1199px) {
  .compact-data-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
