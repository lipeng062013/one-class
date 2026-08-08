<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules, type UploadRawFile } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import {
  createEnrollmentApi,
  enrollmentNoteImageObjectUrl,
  listEnrollmentsApi,
  PAY_METHOD_OPTIONS,
  uploadEnrollmentNoteImageApi,
  type EnrollmentKind,
  type EnrollmentRecord,
  type PayMethodOption,
} from '../../api/enrollments'
import {
  createStudentApi,
  getStudentApi,
  getStudentCoursePackagesApi,
  listManagersApi,
  listStudentsApi,
  type ManagerOption,
  type Student,
  type StudentCoursePackageGroup,
  type StudentPackageOrderRow,
} from '../../api/students'
import { listUsersApi, type UserRow } from '../../api/users'
import { listAcademicTeachersApi, listCoursesApi, type Course } from '../../api/academic'
import AppSheet from '../../components/AppSheet.vue'
import MobileActionBar from '../../components/MobileActionBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useAuthStore } from '../../stores/auth'
import { sanitizePhoneInput, validateRequiredPhone } from '../../utils/phone'

const auth = useAuthStore()
const { isApp } = useBreakpoint()
const route = useRoute()
const router = useRouter()

const searchQ = ref('')
const searching = ref(false)
const searchResults = ref<Student[]>([])
const selected = ref<Student | null>(null)
const searchVisible = ref(false)
let studentSuggestionRequest = 0
const recent = ref<EnrollmentRecord[]>([])
const recentTotal = ref(0)
const loadingRecent = ref(false)
/** 最近一次提交成功的订单号（提示用） */
const lastOrderNo = ref('')
const lastOrderId = ref<number | null>(null)

const staff = ref<UserRow[]>([])
const managers = ref<ManagerOption[]>([])
/** 可选课程（教务课程库 · 已启用） */
const courseOptions = ref<Course[]>([])

const createDrawer = ref(false)
const createSaving = ref(false)
const createFormRef = ref<FormInstance>()
const createForm = reactive({
  name: '',
  grade: '',
  school: '',
  phone: '',
  parent_name: '',
  academic_manager_id: undefined as number | undefined,
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

const createRules: FormRules = {
  name: [{ required: true, message: '请填写学生姓名', trigger: 'blur' }],
  grade: [{ required: true, message: '请选择年级', trigger: 'change' }],
  school: [{ required: true, message: '请填写学校', trigger: 'blur' }],
  academic_manager_id: [{ required: true, message: '请选择学管师', trigger: 'change' }],
  phone: [{ required: true, validator: validateRequiredPhone, trigger: 'blur' }],
}

type AttrRow = { key: string; user_id?: number; amount: number }
type PurchaseMeta = {
  hours: number
  gift_hours: number
  price_standard: string
  discount_type: 'reduce' | 'rate'
  discount_value: number
  /** 手动覆盖小计；null 表示按 总价-优惠 自动计算 */
  subtotal_override: number | null
}

type TransferOutRow = {
  package_id: number
  order_no: string
  unit_price: number
  remain_hours: number
  purchase_hours: number
  gift_hours: number
  transfer_hours: number
  transfer_gift_hours: number
  fee: number
  /** 手动覆盖转出金额；null 表示按单价×转出购买课时 */
  transfer_amount_override: number | null
}

const enrollForm = reactive({
  kind: 'enroll' as EnrollmentKind,
  handled_at: '' as string,
  /** 选中的课程 id 列表（多选）— 报名/续费/转入 */
  course_ids: [] as number[],
  course_details: {} as Record<number, PurchaseMeta>,
  /** 支付方式多选 */
  pay_methods: [] as PayMethodOption[],
  pay_amounts: {} as Partial<Record<PayMethodOption, number>>,
  pay_other: '',
  attributions: [] as AttrRow[],
  internal_notes: '',
  external_notes: '',
  /** 转课：course=转给其他课程；student=转课给其他学员 */
  transfer_mode: 'course' as 'course' | 'student',
  transfer_out_course_id: undefined as number | undefined,
})
const expandedPurchaseId = ref<number | null>(null)
const studentPackages = ref<StudentCoursePackageGroup[]>([])
const packagesLoading = ref(false)
const transferOutRows = ref<TransferOutRow[]>([])
/** 转课给其他学员时的目标学员 */
const transferToStudent = ref<Student | null>(null)
const transferToSearchQ = ref('')
const transferToSearching = ref(false)
const transferToResults = ref<Student[]>([])
let transferToSuggestionRequest = 0

const isTransfer = computed(() => enrollForm.kind === 'transfer')
const isTransferToStudent = computed(
  () => isTransfer.value && enrollForm.transfer_mode === 'student',
)

const transferOutCourseOptions = computed(() =>
  studentPackages.value.filter(
    (c) => c.course_id && !c.is_closed && Number(c.remain_hours || 0) > 0,
  ),
)

const selectedCourses = computed(() =>
  courseOptions.value.filter((c) => enrollForm.course_ids.includes(c.id)),
)
const purchaseRows = computed(() =>
  selectedCourses.value.map((course) => {
    const detail = enrollForm.course_details[course.id] || defaultPurchaseMeta(course)
    const total = Number(detail.hours || 0) * Number(course.unit_price || 0)
    const discount =
      detail.discount_type === 'rate'
        ? total * (1 - Math.min(10, Math.max(0, Number(detail.discount_value || 0))) / 10)
        : Math.min(total, Math.max(0, Number(detail.discount_value || 0)))
    const autoSubtotal = Math.max(0, total - discount)
    const subtotal =
      detail.subtotal_override != null && Number.isFinite(detail.subtotal_override)
        ? Math.max(0, Number(detail.subtotal_override))
        : autoSubtotal
    return {
      course,
      detail,
      total,
      discount,
      autoSubtotal,
      subtotal,
      subtotalEdited:
        detail.subtotal_override != null &&
        Number.isFinite(detail.subtotal_override) &&
        Math.abs(Number(detail.subtotal_override) - autoSubtotal) >= 0.01,
    }
  }),
)
const showPayOther = computed(() => enrollForm.pay_methods.includes('其他'))

const transferOutTotal = computed(() =>
  transferOutRows.value.reduce((sum, row) => {
    if (row.transfer_amount_override != null && Number.isFinite(row.transfer_amount_override)) {
      return sum + Math.max(0, Number(row.transfer_amount_override))
    }
    return sum + Math.max(0, Number(row.unit_price || 0) * Number(row.transfer_hours || 0))
  }, 0),
)
const transferFeeTotal = computed(() =>
  transferOutRows.value.reduce((sum, row) => sum + Math.max(0, Number(row.fee || 0)), 0),
)
const transferInTotal = computed(() =>
  purchaseRows.value.reduce((sum, row) => sum + row.subtotal, 0),
)
/** 报名/续费=购买合计；转课=max(0, 转入-转出+手续费) */
const receivableTotal = computed(() => {
  if (!isTransfer.value) {
    return purchaseRows.value.reduce((sum, row) => sum + row.subtotal, 0)
  }
  return Math.max(0, transferInTotal.value - transferOutTotal.value + transferFeeTotal.value)
})
const receivedTotal = computed(() =>
  enrollForm.pay_methods.reduce(
    (sum, method) => sum + Number(enrollForm.pay_amounts[method] || 0),
    0,
  ),
)
const arrearsTotal = computed(() => Math.max(0, receivableTotal.value - receivedTotal.value))

const imagePaths = ref<string[]>([])
const imagePreviews = ref<{ path: string; url: string }[]>([])
const uploadingImage = ref(false)
const submitting = ref(false)

const kindLabels: Record<string, string> = {
  enroll: '报名',
  renew: '续费',
  transfer: '转课',
}

const statusLabels: Record<string, string> = {
  active: '在读',
  paused: '暂停',
  graduated: '结业',
  quit: '退学',
}

const attrTotal = computed(() =>
  enrollForm.attributions.reduce((s, a) => s + (Number(a.amount) || 0), 0),
)
const attributionComplete = computed(
  () =>
    enrollForm.attributions.length > 0 &&
    enrollForm.attributions.every((a) => a.user_id != null) &&
    Math.abs(attrTotal.value - receivableTotal.value) < 0.01,
)

const transferOutValid = computed(() => {
  if (!isTransfer.value) return true
  if (!enrollForm.transfer_out_course_id) return false
  const active = transferOutRows.value.filter(
    (r) => Number(r.transfer_hours) > 0 || Number(r.transfer_gift_hours) > 0,
  )
  if (!active.length) return false
  return active.every((r) => {
    const take = Number(r.transfer_hours || 0) + Number(r.transfer_gift_hours || 0)
    return take > 0 && take <= Number(r.remain_hours || 0) + 1e-9
  })
})

const transferOutHoursTotal = computed(() =>
  transferOutRows.value.reduce(
    (sum, r) => sum + Number(r.transfer_hours || 0) + Number(r.transfer_gift_hours || 0),
    0,
  ),
)

/** 报名/续费：有应收时必须实收 > 0，禁止零支付提交 */
const enrollRenewRequiresPayment = computed(
  () => !isTransfer.value && receivableTotal.value > 0,
)

const canSubmit = computed(() => {
  if (!selected.value) return false
  if (enrollForm.course_ids.length <= 0) return false
  if (isTransfer.value && !transferOutValid.value) return false
  if (isTransferToStudent.value) {
    if (!transferToStudent.value) return false
    if (transferToStudent.value.id === selected.value.id) return false
  }
  if (receivableTotal.value > 0 && enrollForm.pay_methods.length <= 0) return false
  if (enrollRenewRequiresPayment.value && receivedTotal.value <= 0) return false
  if (receivedTotal.value > receivableTotal.value) return false
  if (!attributionComplete.value) return false
  if (showPayOther.value && !enrollForm.pay_other.trim()) return false
  return true
})

/** App 步骤：选学员 → 填内容 → 可提交 */
const enrollStep = computed(() => {
  if (!selected.value) return 1
  if (!canSubmit.value) return 2
  return 3
})

const confirmCourseLabel = computed(() => {
  const names = purchaseRows.value.map((r) => r.course.name).filter(Boolean)
  if (!names.length) return isTransfer.value ? '未选转入课程' : '未选课程'
  if (names.length <= 2) return names.join('、')
  return `${names.slice(0, 2).join('、')} 等${names.length}门`
})

const confirmPayLabel = computed(() => {
  if (!enrollForm.pay_methods.length) {
    return receivableTotal.value > 0 ? '未选支付方式' : '无需收款'
  }
  return enrollForm.pay_methods.join('、') + (showPayOther.value && enrollForm.pay_other ? `（${enrollForm.pay_other}）` : '')
})

function todayStr() {
  const d = new Date()
  const m = `${d.getMonth() + 1}`.padStart(2, '0')
  const day = `${d.getDate()}`.padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

function defaultPurchaseMeta(course?: Course): PurchaseMeta {
  return {
    hours: 1,
    gift_hours: 0,
    price_standard: course?.price_label || '单价',
    discount_type: 'reduce',
    discount_value: 0,
    subtotal_override: null,
  }
}

/** 清除手动小计，恢复按课时/优惠自动计算 */
function clearSubtotalOverride(detail: PurchaseMeta) {
  detail.subtotal_override = null
}

/**
 * 学管/负责人直接改行小计。
 * 不联动直减/折扣；改优惠时会 clearSubtotalOverride 再按总价-优惠重算小计。
 */
function setPurchaseSubtotal(courseId: number, _catalogTotal: number, value: number | string | undefined) {
  const detail = enrollForm.course_details[courseId]
  if (!detail) return
  const raw = typeof value === 'string' ? value.trim() : value
  const num = raw === '' || raw == null ? 0 : Number(raw)
  const v = Number.isFinite(num) ? Math.max(0, Math.round(num * 100) / 100) : 0
  detail.subtotal_override = v
}

function onSubtotalBlur(courseId: number, catalogTotal: number, event: Event) {
  const target = event.target as HTMLInputElement | null
  setPurchaseSubtotal(courseId, catalogTotal, target?.value)
}

function syncCourseDetails() {
  const next: Record<number, PurchaseMeta> = {}
  for (const id of enrollForm.course_ids) {
    next[id] =
      enrollForm.course_details[id] ||
      defaultPurchaseMeta(courseOptions.value.find((course) => course.id === id))
  }
  enrollForm.course_details = next
}

function removePurchase(courseId: number) {
  enrollForm.course_ids = enrollForm.course_ids.filter((id) => id !== courseId)
}

function togglePurchaseCard(courseId: number) {
  expandedPurchaseId.value = expandedPurchaseId.value === courseId ? null : courseId
}

function onDiscountTypeChange(detail: PurchaseMeta) {
  clearSubtotalOverride(detail)
  detail.discount_value = detail.discount_type === 'rate' ? 10 : 0
}

function onDiscountValueChange(detail: PurchaseMeta) {
  // 改优惠后以优惠为准，取消手动小计
  clearSubtotalOverride(detail)
}

function normalizePurchaseNumber(detail: PurchaseMeta, key: 'hours' | 'gift_hours') {
  const min = key === 'hours' ? 0.01 : 0
  const value = Number(detail[key])
  detail[key] = Number.isFinite(value)
    ? Math.max(min, Math.round(value * 100) / 100)
    : min
  clearSubtotalOverride(detail)
}

function changePurchaseHours(detail: PurchaseMeta, key: 'hours' | 'gift_hours', delta: -0.25 | 0.25) {
  normalizePurchaseNumber(detail, key)
  const min = key === 'hours' ? 0.01 : 0
  detail[key] = Math.max(min, Math.round((detail[key] + delta) * 100) / 100)
  clearSubtotalOverride(detail)
}

function resetEnrollForm() {
  enrollForm.kind = 'enroll'
  enrollForm.handled_at = todayStr()
  enrollForm.course_ids = []
  enrollForm.course_details = {}
  enrollForm.pay_methods = []
  enrollForm.pay_amounts = {}
  enrollForm.pay_other = ''
  enrollForm.attributions = []
  enrollForm.internal_notes = ''
  enrollForm.external_notes = ''
  enrollForm.transfer_mode = 'course'
  enrollForm.transfer_out_course_id = undefined
  transferOutRows.value = []
  transferToStudent.value = null
  transferToSearchQ.value = ''
  transferToResults.value = []
  expandedPurchaseId.value = null
  revokePreviews()
  imagePaths.value = []
  imagePreviews.value = []
}

/** 转课给其他学员时：按转出课时自动带入同课程作为转入（可改） */
function suggestTransferInFromOut() {
  if (!isTransferToStudent.value) return
  const outId = enrollForm.transfer_out_course_id
  if (!outId) return
  const course = courseOptions.value.find((c) => c.id === outId)
  if (!course) return
  const hours = Math.max(0.01, Math.round(transferOutHoursTotal.value * 100) / 100)
  if (!enrollForm.course_ids.includes(outId)) {
    enrollForm.course_ids = [outId]
  }
  syncCourseDetails()
  const detail = enrollForm.course_details[outId] || defaultPurchaseMeta(course)
  detail.hours = hours
  detail.gift_hours = 0
  detail.discount_type = 'reduce'
  // 按转出金额对齐小计，避免同课转学员时出现虚假补差
  const outAmt = Math.round(transferOutTotal.value * 100) / 100
  const catalogTotal = hours * Number(course.unit_price || 0)
  detail.subtotal_override = outAmt
  detail.discount_value = Math.max(0, Math.round((catalogTotal - outAmt) * 100) / 100)
  enrollForm.course_details[outId] = detail
}

function packageToTransferRow(pkg: StudentPackageOrderRow): TransferOutRow {
  const remain = Number(pkg.remain_hours || 0)
  return {
    package_id: pkg.package_id,
    order_no: pkg.order_no,
    unit_price: Number(pkg.unit_price || 0),
    remain_hours: remain,
    purchase_hours: Number(pkg.purchase_hours || 0),
    gift_hours: Number(pkg.gift_hours || 0),
    transfer_hours: remain > 0 ? remain : 0,
    transfer_gift_hours: 0,
    fee: 0,
    transfer_amount_override: null,
  }
}

function transferLineAmount(row: TransferOutRow) {
  if (row.transfer_amount_override != null && Number.isFinite(row.transfer_amount_override)) {
    return Math.max(0, Number(row.transfer_amount_override))
  }
  return Math.max(0, Number(row.unit_price || 0) * Number(row.transfer_hours || 0))
}

function rebuildTransferOutRows(courseId?: number) {
  const cid = courseId ?? enrollForm.transfer_out_course_id
  if (!cid) {
    transferOutRows.value = []
    return
  }
  const group = studentPackages.value.find((c) => c.course_id === cid)
  const pkgs = (group?.packages || []).filter(
    (p) => p.status === 'active' && Number(p.remain_hours || 0) > 0,
  )
  transferOutRows.value = pkgs.map(packageToTransferRow)
}

async function loadStudentPackages(studentId: number) {
  packagesLoading.value = true
  try {
    const res = await getStudentCoursePackagesApi(studentId)
    studentPackages.value = res.courses || []
  } catch {
    studentPackages.value = []
  } finally {
    packagesLoading.value = false
  }
}

async function queryTransferToSuggestions(
  query: string,
  callback: (items: Array<Student & { value: string; label: string }>) => void,
) {
  const keyword = query.trim()
  if (!keyword) {
    transferToSuggestionRequest += 1
    callback([])
    return
  }
  const request = ++transferToSuggestionRequest
  const page = await listStudentsApi({ q: keyword, page: 1, page_size: 20 }).catch(() => ({
    items: [] as Student[],
  }))
  if (request !== transferToSuggestionRequest) return
  const sourceId = selected.value?.id
  callback(
    page.items
      .filter((s) => s.id !== sourceId && studentMatchesSearch(s, keyword))
      .map((s) => ({
        ...s,
        value: `${s.name}${s.phone ? ` · ${s.phone}` : ''}`,
        label: `${s.name}${s.phone ? ` · ${s.phone}` : ''}`,
      })),
  )
}

function pickTransferToStudent(s: Student) {
  if (selected.value && s.id === selected.value.id) {
    ElMessage.warning('转入学员不能与转出学员相同')
    return
  }
  transferToStudent.value = s
  transferToSearchQ.value = ''
  transferToResults.value = []
  suggestTransferInFromOut()
}

function clearTransferToStudent() {
  transferToStudent.value = null
  transferToSearchQ.value = ''
  transferToResults.value = []
}

async function runTransferToSearch() {
  const q = transferToSearchQ.value.trim()
  if (!q) {
    transferToResults.value = []
    ElMessage.warning('请输入转入学员姓名或手机号')
    return
  }
  transferToSearching.value = true
  try {
    const page = await listStudentsApi({ q, page: 1, page_size: 20 })
    const sourceId = selected.value?.id
    transferToResults.value = page.items.filter(
      (s) => s.id !== sourceId && studentMatchesSearch(s, q),
    )
    if (!transferToResults.value.length) {
      ElMessage.info('未找到可转入的学员')
    }
  } finally {
    transferToSearching.value = false
  }
}

function revokePreviews() {
  for (const p of imagePreviews.value) {
    URL.revokeObjectURL(p.url)
  }
}

function clearSelected() {
  selected.value = null
  resetEnrollForm()
}

async function loadStaff() {
  // 业绩归属下拉：负责人走用户列表；学管师无 users.manage，改用学管+老师列表，避免弹「无权限」
  if (auth.hasPermission('users.manage')) {
    const page = await listUsersApi({ is_active: true, page: 1, page_size: 100 }).catch(() => null)
    staff.value = page?.items ?? []
    return
  }
  const [mgrs, teachersPage] = await Promise.all([
    listManagersApi(false).catch(() => [] as ManagerOption[]),
    listAcademicTeachersApi({ page: 1, page_size: 100 }).catch(() => ({
      items: [] as { id: number; name: string; username: string }[],
    })),
  ])
  const byId = new Map<number, UserRow>()
  for (const m of mgrs) {
    if (!m.is_active) continue
    byId.set(m.id, {
      id: m.id,
      username: m.username,
      display_name: m.display_name,
      role: 'cr',
      is_active: true,
    })
  }
  for (const t of teachersPage.items || []) {
    if (byId.has(t.id)) continue
    byId.set(t.id, {
      id: t.id,
      username: t.username || '',
      display_name: t.name,
      role: 'teacher',
      is_active: true,
    })
  }
  // 确保当前登录人可选
  if (auth.user && !byId.has(auth.user.id)) {
    byId.set(auth.user.id, {
      id: auth.user.id,
      username: auth.user.username,
      display_name: auth.user.display_name,
      role: auth.user.role,
      is_active: true,
    })
  }
  staff.value = [...byId.values()]
}

async function loadManagers() {
  managers.value = await listManagersApi(false).catch(() => [])
}

async function loadCourses() {
  const page = await listCoursesApi({ enabled: true, page: 1, page_size: 100 }).catch(() => ({
    items: [] as Course[],
  }))
  courseOptions.value = page.items
}

async function loadRecent() {
  loadingRecent.value = true
  try {
    const page = await listEnrollmentsApi({ page: 1, page_size: 2 })
    recent.value = page.items
    recentTotal.value = page.total
  } catch {
    recent.value = []
    recentTotal.value = 0
  } finally {
    loadingRecent.value = false
  }
}

function showAllEnrollments() {
  void router.push('/enrollments/records')
}

async function runSearch() {
  const q = searchQ.value.trim()
  if (!q) {
    searchResults.value = []
    ElMessage.warning('请输入学员姓名或手机号')
    return
  }
  searching.value = true
  try {
    const page = await listStudentsApi({ q, page: 1, page_size: 20 })
    searchResults.value = page.items.filter((s) => studentMatchesSearch(s, q))
    if (!searchResults.value.length) {
      ElMessage.info('未找到学员，可点「新建学生」建档')
    }
  } finally {
    searching.value = false
  }
}

function studentMatchesSearch(s: Student, query = searchQ.value.trim()) {
  return s.name.includes(query) || (s.phone || '').includes(query)
}

async function queryStudentSuggestions(
  query: string,
  callback: (items: Array<Student & { value: string; label: string }>) => void,
) {
  const keyword = query.trim()
  if (!keyword) {
    studentSuggestionRequest += 1
    callback([])
    return
  }
  const request = ++studentSuggestionRequest
  const page = await listStudentsApi({ q: keyword, page: 1, page_size: 20 }).catch(() => ({
    items: [] as Student[],
  }))
  if (request !== studentSuggestionRequest) return
  callback(
    page.items.filter((s) => studentMatchesSearch(s, keyword)).map((s) => ({
      ...s,
      value: `${s.name}${s.phone ? ` · ${s.phone}` : ''}`,
      label: `${s.name}${s.phone ? ` · ${s.phone}` : ''}`,
    })),
  )
}

function pickStudentSuggestion(item: Student & { value: string; label: string }) {
  void pickStudent(item)
}

async function pickStudent(
  s: Student,
  opts?: {
    preferEnroll?: boolean
    kind?: EnrollmentKind
    courseIds?: number[]
    /** 转课：预填转出课程 */
    transferOutCourseId?: number
  },
) {
  selected.value = s
  searchResults.value = []
  searchQ.value = ''
  resetEnrollForm()
  // 续费倾向：已有在读学员默认续费；新建/暂停等默认报名
  if (opts?.kind) {
    enrollForm.kind = opts.kind
  } else if (opts?.preferEnroll || s.status !== 'active') {
    enrollForm.kind = 'enroll'
  } else {
    enrollForm.kind = 'renew'
  }

  if (enrollForm.kind === 'transfer') {
    await loadStudentPackages(s.id)
    const outId =
      opts?.transferOutCourseId &&
      transferOutCourseOptions.value.some((c) => c.course_id === opts.transferOutCourseId)
        ? opts.transferOutCourseId
        : transferOutCourseOptions.value[0]?.course_id || undefined
    enrollForm.transfer_out_course_id = outId
    rebuildTransferOutRows(outId)
    // 转入课程由经办人选择，不预填转出课
    enrollForm.course_ids = []
  } else if (opts?.courseIds?.length) {
    // 仅路由显式传入 course_id 时预填（如从学员详情跳转续某门课）
    enrollForm.course_ids = [...opts.courseIds]
    syncCourseDetails()
  }

  enrollForm.attributions = [
    {
      key: `${Date.now()}-default`,
      user_id: auth.user?.id,
      amount: receivableTotal.value,
    },
  ]
}

function routeQueryValues(value: unknown): string[] {
  const values = Array.isArray(value) ? value : [value]
  return values.flatMap((item) => (typeof item === 'string' && item.trim() ? [item.trim()] : []))
}

function parseKind(value?: string): EnrollmentKind {
  if (value === 'enroll' || value === 'renew' || value === 'transfer') return value
  return 'renew'
}

async function applyRoutePrefill() {
  const [studentValue] = routeQueryValues(route.query.student_id)
  const studentId = Number(studentValue)
  if (!Number.isInteger(studentId) || studentId <= 0) return

  const student = await getStudentApi(studentId).catch(() => null)
  if (!student) return

  const courseQueryPresent = route.query.course_id != null
  const requestedCourseIds = routeQueryValues(route.query.course_id)
    .map(Number)
    .filter((id) => Number.isInteger(id) && id > 0)
  const availableCourseIds = requestedCourseIds.filter((id) =>
    courseOptions.value.some((course) => course.id === id),
  )
  const [kindValue] = routeQueryValues(route.query.kind)
  const kind = parseKind(kindValue)

  if (kind === 'transfer') {
    await pickStudent(student, {
      kind: 'transfer',
      transferOutCourseId: requestedCourseIds[0],
    })
    if (requestedCourseIds.length && !enrollForm.transfer_out_course_id) {
      ElMessage.warning('该课程无可转出课时，请另选转出课程')
    }
    return
  }

  await pickStudent(student, {
    kind: kind === 'enroll' ? 'enroll' : 'renew',
    courseIds: courseQueryPresent ? availableCourseIds : undefined,
  })

  if (requestedCourseIds.length && !availableCourseIds.length) {
    ElMessage.warning('该课程已停用或不存在，请重新选择课程')
  }
}

async function openCreateDrawer() {
  createForm.name = ''
  createForm.grade = ''
  createForm.school = ''
  const phoneCandidate = sanitizePhoneInput(searchQ.value)
  createForm.phone = phoneCandidate.length >= 7 ? phoneCandidate : ''
  createForm.parent_name = ''
  // 学管师新建学员默认绑到自己名下
  createForm.academic_manager_id =
    auth.isCR && auth.user?.id ? auth.user.id : undefined
  createForm.notes = ''
  await loadManagers()
  createDrawer.value = true
}

async function submitCreateStudent() {
  const ok = await createFormRef.value?.validate().catch(() => false)
  if (!ok) return
  createSaving.value = true
  try {
    const student = await createStudentApi({
      name: createForm.name.trim(),
      grade: createForm.grade,
      school: createForm.school.trim(),
      phone: createForm.phone.trim() || null,
      parent_name: createForm.parent_name.trim() || null,
      academic_manager_id: createForm.academic_manager_id ?? null,
      status: 'active',
      notes: createForm.notes.trim(),
    })
    ElMessage.success('学生已创建，请选择课程完成报名')
    createDrawer.value = false
    // 新建后进入报名表单，课程由经办人当场选择（不预填）
    await pickStudent(student, { preferEnroll: true })
  } catch {
    /* interceptor */
  } finally {
    createSaving.value = false
  }
}

function addAttribution() {
  if (enrollForm.attributions.length >= 10) {
    ElMessage.warning('最多添加 10 位业绩归属人')
    return
  }
  enrollForm.attributions.push({
    key: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    user_id: undefined,
    amount: 0,
  })
  distributeAttributions()
}

function removeAttribution(idx: number) {
  enrollForm.attributions.splice(idx, 1)
  distributeAttributions()
}

function distributeAttributions() {
  const rows = enrollForm.attributions
  if (!rows.length) return
  const totalCents = Math.round(receivableTotal.value * 100)
  const share = Math.floor(totalCents / rows.length)
  rows.forEach((row, index) => {
    row.amount = (index === rows.length - 1 ? totalCents - share * index : share) / 100
  })
}

function balanceAttributions(changedIndex: number) {
  const rows = enrollForm.attributions
  if (!rows.length) return
  if (rows.length === 1) {
    rows[0].amount = receivableTotal.value
    return
  }
  const balanceIndex = changedIndex === rows.length - 1 ? 0 : rows.length - 1
  const fixed = rows.reduce(
    (sum, row, index) =>
      index === changedIndex || index === balanceIndex ? sum : sum + Number(row.amount || 0),
    0,
  )
  const available = Math.max(0, receivableTotal.value - fixed)
  rows[changedIndex].amount = Math.min(available, Math.max(0, Number(rows[changedIndex].amount || 0)))
  rows[balanceIndex].amount = Math.max(0, receivableTotal.value - fixed - rows[changedIndex].amount)
}

async function onPickImage(raw: UploadRawFile) {
  if (imagePaths.value.length >= 3) {
    ElMessage.warning('最多上传 3 张图片')
    return false
  }
  const okType = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'].includes(raw.type)
  if (!okType) {
    ElMessage.warning('仅支持 jpg / png / webp')
    return false
  }
  if (raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('单张图片不能超过 20MB')
    return false
  }
  uploadingImage.value = true
  try {
    const { path } = await uploadEnrollmentNoteImageApi(raw)
    const url = await enrollmentNoteImageObjectUrl(path)
    imagePaths.value = [...imagePaths.value, path]
    imagePreviews.value = [...imagePreviews.value, { path, url }]
  } catch {
    /* interceptor */
  } finally {
    uploadingImage.value = false
  }
  return false
}

function removeImage(path: string) {
  const hit = imagePreviews.value.find((p) => p.path === path)
  if (hit) URL.revokeObjectURL(hit.url)
  imagePaths.value = imagePaths.value.filter((p) => p !== path)
  imagePreviews.value = imagePreviews.value.filter((p) => p.path !== path)
}

async function submitEnrollment() {
  if (!selected.value) {
    ElMessage.warning('请先搜索并选择学员')
    return
  }
  if (!enrollForm.course_ids.length) {
    ElMessage.warning(isTransfer.value ? '请选择转入课程' : '请选择关联课程')
    return
  }
  if (isTransfer.value) {
    if (!enrollForm.transfer_out_course_id) {
      ElMessage.warning('请选择转出课程')
      return
    }
    if (!transferOutValid.value) {
      ElMessage.warning('请填写有效的转出课时')
      return
    }
    if (isTransferToStudent.value) {
      if (!transferToStudent.value) {
        ElMessage.warning('请选择转入学员')
        return
      }
      if (transferToStudent.value.id === selected.value.id) {
        ElMessage.warning('转入学员不能与转出学员相同')
        return
      }
    }
  }
  if (receivableTotal.value > 0 && !enrollForm.pay_methods.length) {
    ElMessage.warning('请选择支付方式')
    return
  }
  if (!isTransfer.value && receivableTotal.value > 0 && receivedTotal.value <= 0) {
    ElMessage.warning('报名/续费须填写实收金额，不能零支付提交')
    return
  }
  if (receivedTotal.value > receivableTotal.value) {
    ElMessage.warning('实收金额不能大于应收金额')
    return
  }
  if (showPayOther.value && !enrollForm.pay_other.trim()) {
    ElMessage.warning('选择「其他」时请填写支付说明')
    return
  }
  const badAttr = enrollForm.attributions.some((a) => !a.user_id)
  if (badAttr) {
    ElMessage.warning('请完善业绩归属人')
    return
  }
  if (!enrollForm.attributions.length) {
    ElMessage.warning('请添加业绩归属人')
    return
  }
  if (Math.abs(attrTotal.value - receivableTotal.value) >= 0.01) {
    ElMessage.warning('销售业绩合计必须等于应收金额')
    return
  }
  submitting.value = true
  try {
    const outAvgUnit = (() => {
      const rows = transferOutRows.value.filter(
        (r) => Number(r.transfer_hours) > 0 || Number(r.transfer_gift_hours) > 0,
      )
      if (!rows.length) return 0
      return rows.reduce((s, r) => s + Number(r.unit_price || 0), 0) / rows.length
    })()
    const courses = purchaseRows.value.map(({ course, detail, discount, subtotal, total }) => {
      let unitPrice = Number(course.unit_price || 0)
      let lineSubtotal = subtotal
      let lineDiscount = discount
      let catalogTotal = total
      // 转给其他学员且同课程：优先用转出课包单价，保证等量转移无虚假差额
      if (
        isTransferToStudent.value &&
        course.id === enrollForm.transfer_out_course_id &&
        outAvgUnit > 0 &&
        detail.subtotal_override == null
      ) {
        unitPrice = outAvgUnit
        catalogTotal = Number(detail.hours || 0) * unitPrice
        lineDiscount =
          detail.discount_type === 'rate'
            ? catalogTotal * (1 - Math.min(10, Math.max(0, Number(detail.discount_value || 0))) / 10)
            : Math.min(catalogTotal, Math.max(0, Number(detail.discount_value || 0)))
        lineSubtotal = Math.max(0, catalogTotal - lineDiscount)
      }
      // 手动小计优先，不改写直减/折扣；高于目录价时仅反推课包单价
      if (detail.subtotal_override != null && Number.isFinite(detail.subtotal_override)) {
        lineSubtotal = Math.max(0, Number(detail.subtotal_override))
        if (lineSubtotal > catalogTotal + 0.009 && Number(detail.hours || 0) > 0) {
          unitPrice = lineSubtotal / Number(detail.hours)
        }
      }
      return {
        id: course.id,
        name: course.name,
        type: course.type_label,
        price_label: course.price_label,
        unit_price: unitPrice,
        hours: detail.hours,
        gift_hours: detail.gift_hours,
        price_standard: detail.price_standard,
        discount_type: detail.discount_type,
        discount_value: detail.discount_value,
        discount: lineDiscount,
        subtotal: lineSubtotal,
      }
    })
    const transferOutItems = isTransfer.value
      ? transferOutRows.value
          .filter(
            (r) => Number(r.transfer_hours) > 0 || Number(r.transfer_gift_hours) > 0,
          )
          .map((r) => ({
            package_id: r.package_id,
            transfer_hours: Number(r.transfer_hours || 0),
            transfer_gift_hours: Number(r.transfer_gift_hours || 0),
            fee: Number(r.fee || 0),
            transfer_amount: transferLineAmount(r),
          }))
      : undefined
    const record = await createEnrollmentApi({
      student_id: selected.value.id,
      kind: enrollForm.kind,
      handled_at: enrollForm.handled_at
        ? `${enrollForm.handled_at}T12:00:00`
        : null,
      amount: receivableTotal.value,
      courses,
      pay_methods: [...enrollForm.pay_methods],
      pay_other: showPayOther.value ? enrollForm.pay_other.trim() : '',
      payments: enrollForm.pay_methods.map((method) => ({
        method,
        amount: Number(enrollForm.pay_amounts[method] || 0),
      })),
      attributions: enrollForm.attributions
        .filter((a) => a.user_id != null)
        .map((a) => ({ user_id: a.user_id as number, amount: Number(a.amount) || 0 })),
      internal_notes: enrollForm.internal_notes.trim(),
      external_notes: enrollForm.external_notes.trim(),
      internal_images: [...imagePaths.value],
      transfer_mode: isTransfer.value ? enrollForm.transfer_mode : undefined,
      transfer_out_course_id: isTransfer.value ? enrollForm.transfer_out_course_id : undefined,
      transfer_out_items: transferOutItems,
      transfer_to_student_id:
        isTransferToStudent.value && transferToStudent.value
          ? transferToStudent.value.id
          : undefined,
    })
    const orderNo = record.order_no || ''
    lastOrderNo.value = orderNo
    lastOrderId.value = record.order_id || null
    const kindLabel = kindLabels[enrollForm.kind] || '登记'
    const toHint =
      isTransferToStudent.value && transferToStudent.value
        ? `，已转入「${transferToStudent.value.name}」`
        : ''
    const allocHint =
      enrollForm.kind === 'enroll' ? '；线索转入学员将通知负责人分配学管' : ''
    ElMessage.success(
      orderNo
        ? `${kindLabel}已登记，订单号 ${orderNo}${toHint}${allocHint}`
        : `${kindLabel}已登记${toHint}${allocHint}`,
    )
    clearSelected()
    studentPackages.value = []
    transferToStudent.value = null
    await loadRecent()
  } catch {
    /* interceptor */
  } finally {
    submitting.value = false
  }
}

function courseSummary(row: EnrollmentRecord) {
  const list = row.courses || []
  if (!list.length) return ''
  return list.map((c) => c.name).join('、')
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function staffLabel(u: UserRow) {
  const role =
    u.role === 'admin'
      ? '负责人'
      : u.role === 'cr' || u.role === 'academic_manager'
        ? 'CR（班主任，学管师）'
        : u.role === 'teacher'
          ? '老师'
          : u.role === 'operator'
            ? '运营'
            : u.role
  return `${u.display_name || u.username}（${role}）`
}

watch(
  () => [...enrollForm.course_ids],
  (ids, previousIds = []) => {
    syncCourseDetails()
    const addedId = ids.find((id) => !previousIds.includes(id))
    if (addedId != null) {
      expandedPurchaseId.value = addedId
    } else if (expandedPurchaseId.value != null && !ids.includes(expandedPurchaseId.value)) {
      expandedPurchaseId.value = ids.at(-1) ?? null
    }
  },
)
watch(receivableTotal, () => distributeAttributions())

watch(
  () => enrollForm.kind,
  async (kind, prev) => {
    if (kind === prev) return
    if (kind === 'transfer' && selected.value) {
      enrollForm.course_ids = []
      await loadStudentPackages(selected.value.id)
      if (
        !enrollForm.transfer_out_course_id ||
        !transferOutCourseOptions.value.some((c) => c.course_id === enrollForm.transfer_out_course_id)
      ) {
        enrollForm.transfer_out_course_id = transferOutCourseOptions.value[0]?.course_id ?? undefined
      }
      rebuildTransferOutRows()
    } else if (prev === 'transfer') {
      enrollForm.transfer_out_course_id = undefined
      transferOutRows.value = []
    }
  },
)

watch(
  () => enrollForm.transfer_out_course_id,
  (cid) => {
    if (isTransfer.value) {
      rebuildTransferOutRows(cid)
      if (isTransferToStudent.value) suggestTransferInFromOut()
    }
  },
)

watch(
  () => enrollForm.transfer_mode,
  (mode) => {
    if (mode !== 'student') {
      transferToStudent.value = null
      transferToSearchQ.value = ''
      transferToResults.value = []
    } else {
      suggestTransferInFromOut()
    }
  },
)

watch(transferOutHoursTotal, () => {
  if (isTransferToStudent.value && enrollForm.course_ids.length <= 1) {
    suggestTransferInFromOut()
  }
})

onMounted(async () => {
  resetEnrollForm()
  await Promise.all([loadStaff(), loadManagers(), loadCourses(), loadRecent()])
  await applyRoutePrefill()
})

onUnmounted(() => {
  revokePreviews()
})
</script>

<template>
  <div class="enroll-page oc-page-shell">
    <div v-if="!isApp" class="page-toolbar">
      <el-page-header class="is-title-only" :content="isTransfer ? '转课' : '报名 / 续费'" />
      <p class="page-desc">
        {{
          isTransfer
            ? '选择学员后，指定转出课包课时并选择转入课程，确认差额收款完成转课。'
            : '搜索在读学员办理报名或续费；新学员可先「新建学生」建档，再选择课程完成登记。'
        }}
      </p>
    </div>

    <!-- App 步骤指示 -->
    <nav v-if="isApp" class="enroll-steps" aria-label="办理步骤">
      <div class="enroll-step" :class="{ 'is-active': enrollStep === 1, 'is-done': enrollStep > 1 }">
        <span class="enroll-step__n">1</span>
        <span class="enroll-step__t">选学员</span>
      </div>
      <span class="enroll-step__line" :class="{ 'is-on': enrollStep > 1 }" />
      <div class="enroll-step" :class="{ 'is-active': enrollStep === 2, 'is-done': enrollStep > 2 }">
        <span class="enroll-step__n">2</span>
        <span class="enroll-step__t">填内容</span>
      </div>
      <span class="enroll-step__line" :class="{ 'is-on': enrollStep > 2 }" />
      <div class="enroll-step" :class="{ 'is-active': enrollStep === 3, 'is-done': enrollStep >= 3 }">
        <span class="enroll-step__n">3</span>
        <span class="enroll-step__t">确认提交</span>
      </div>
    </nav>

    <!-- 搜索条 -->
    <section v-if="!isApp" class="search-bar panel">
      <div class="search-row">
        <el-autocomplete
          v-model="searchQ"
          clearable
          size="large"
          class="search-input"
          placeholder="输入学员姓名 / 手机号快速查找"
          value-key="label"
          :fetch-suggestions="queryStudentSuggestions"
          :trigger-on-focus="false"
          popper-class="student-search-popper"
          @select="pickStudentSuggestion"
          @keyup.enter.stop="runSearch"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
          <template #default="{ item }">
            <div class="student-suggestion">
              <span class="student-suggestion-name">{{ item.name }}</span>
              <span class="student-suggestion-meta">
                {{ item.grade || '未填年级' }}
                <template v-if="item.phone"> · {{ item.phone }}</template>
                <template v-if="item.school"> · {{ item.school }}</template>
              </span>
            </div>
          </template>
        </el-autocomplete>
        <el-button type="primary" size="large" :loading="searching" @click="runSearch">
          查找
        </el-button>
        <el-button size="large" class="create-btn" @click="openCreateDrawer">
          <el-icon><Plus /></el-icon>
          新建学生
        </el-button>
      </div>

      <div v-if="searchResults.length" class="search-hits">
        <button
          v-for="s in searchResults"
          :key="s.id"
          type="button"
          class="hit-card"
          @click="pickStudent(s)"
        >
          <span class="hit-avatar">{{ (s.name || '?').slice(0, 1) }}</span>
          <span class="hit-main">
            <span class="hit-name">{{ s.name }}</span>
            <span class="hit-meta">
              {{ s.grade || '未填年级' }}
              <template v-if="s.phone"> · {{ s.phone }}</template>
              <template v-if="s.school"> · {{ s.school }}</template>
            </span>
          </span>
          <el-tag size="small" effect="plain" round>
            {{ statusLabels[s.status] || s.status }}
          </el-tag>
        </button>
      </div>
    </section>

    <section v-if="isApp" class="student-picker" :class="{ 'has-student': selected }">
      <button type="button" class="student-picker-main" @click="searchVisible = true">
        <span class="student-picker-icon" aria-hidden="true">
          <span v-if="selected">{{ (selected.name || '?').slice(0, 1) }}</span>
          <el-icon v-else><Search /></el-icon>
        </span>
        <span class="student-picker-copy">
          <span class="student-picker-label">办理学员</span>
          <strong>{{ selected ? selected.name : '选择学员' }}</strong>
          <span class="student-picker-meta">
            <template v-if="selected">
              {{ selected.grade || '未填年级' }}<template v-if="selected.phone"> · {{ selected.phone }}</template>
            </template>
            <template v-else>按姓名或手机号查找在册学员</template>
          </span>
        </span>
        <span class="student-picker-action">
          {{ selected ? '更换' : '选择' }}
          <el-icon><ArrowRight /></el-icon>
        </span>
      </button>
      <button v-if="!selected" type="button" class="student-create-action" @click="openCreateDrawer">
        <el-icon><Plus /></el-icon>
        新建学员
      </button>
    </section>
    <MobileFilterSheet
      v-model="searchVisible"
      title="选择办理学员"
      apply-text="显示匹配学员"
      reset-text="清空"
      compact-size="420px"
      :active-count="Number(Boolean(searchQ.trim()))"
      @apply="runSearch"
      @reset="searchQ = ''; searchResults = []"
    >
      <el-form label-position="top" @submit.prevent="runSearch">
        <el-form-item label="姓名或手机号">
          <el-autocomplete
            v-model="searchQ"
            clearable
            placeholder="输入学员姓名 / 手机号"
            value-key="label"
            :fetch-suggestions="queryStudentSuggestions"
            :trigger-on-focus="false"
            popper-class="student-search-popper"
            @select="pickStudentSuggestion"
          />
        </el-form-item>
      </el-form>
    </MobileFilterSheet>
    <section v-if="isApp && searchResults.length" class="compact-search-results">
      <div class="compact-search-title">搜索结果 · {{ searchResults.length }} 位</div>
      <div class="search-hits compact-search-hits">
        <button v-for="s in searchResults" :key="s.id" type="button" class="hit-card" @click="pickStudent(s)">
          <span class="hit-avatar">{{ (s.name || '?').slice(0, 1) }}</span>
          <span class="hit-main">
            <span class="hit-name">{{ s.name }}</span>
            <span class="hit-meta">{{ s.grade || '未填年级' }}<template v-if="s.phone"> · {{ s.phone }}</template></span>
          </span>
          <el-tag size="small" effect="plain" round>{{ statusLabels[s.status] || s.status }}</el-tag>
        </button>
      </div>
    </section>

    <div class="work-area">
      <!-- 左侧：选中学员 + 表单 / 空态 -->
      <section class="panel main-panel">
        <template v-if="!selected">
          <div class="empty-stage">
            <div class="empty-icon" aria-hidden="true">
              <el-icon :size="42"><UserFilled /></el-icon>
            </div>
            <h2 class="empty-title">请选择学员</h2>
            <p class="empty-desc">
              选择在册学员后可办理报名、续费或转课；新学员需先建档，再在本页选择课程。
            </p>
            <p v-if="lastOrderNo" class="last-order-hint">
              上一笔订单号：
              <button
                v-if="lastOrderId"
                type="button"
                class="link-btn"
                @click="router.push(`/finance/orders/${lastOrderId}`)"
              >
                <strong>{{ lastOrderNo }}</strong>
              </button>
              <strong v-else>{{ lastOrderNo }}</strong>
            </p>
          </div>
        </template>

        <template v-else>
          <div v-if="!isApp" class="student-banner">
            <div class="student-banner-left">
              <span class="student-avatar">{{ (selected.name || '?').slice(0, 1) }}</span>
              <div>
                <div class="student-name">{{ selected.name }}</div>
                <div class="student-meta">
                  {{ selected.grade || '未填年级' }}
                  <template v-if="selected.school"> · {{ selected.school }}</template>
                  <template v-if="selected.phone"> · {{ selected.phone }}</template>
                  <template v-if="selected.academic_manager_name">
                    · 学管 {{ selected.academic_manager_name }}
                  </template>
                </div>
              </div>
            </div>
            <el-button text type="primary" @click="clearSelected">更换学员</el-button>
          </div>

          <el-form class="enroll-form" label-width="96px" @submit.prevent>
            <section class="form-section">
              <div class="form-section-head">
                <h3>{{ isTransfer ? '业务类型' : '购买内容' }}</h3>
                <el-radio-group v-model="enrollForm.kind" size="small">
                  <el-radio-button value="enroll">报名</el-radio-button>
                  <el-radio-button value="renew">续费</el-radio-button>
                  <el-radio-button value="transfer">转课</el-radio-button>
                </el-radio-group>
              </div>

              <!-- 转课：转出信息 -->
              <template v-if="isTransfer">
                <div class="form-section-head sub-head">
                  <h3>转课方式</h3>
                </div>
                <el-form-item label="方式">
                  <el-radio-group v-model="enrollForm.transfer_mode">
                    <el-radio value="course">转给其他课程</el-radio>
                    <el-radio value="student">转课给其他学员</el-radio>
                  </el-radio-group>
                </el-form-item>

                <!-- 转课给其他学员：选择目标学员 -->
                <template v-if="isTransferToStudent">
                  <div class="form-section-head sub-head">
                    <h3>转入学员</h3>
                  </div>
                  <el-form-item label="目标学员" required>
                    <div v-if="transferToStudent" class="transfer-to-banner">
                      <span class="transfer-to-avatar">
                        {{ (transferToStudent.name || '?').slice(0, 1) }}
                      </span>
                      <div class="transfer-to-main">
                        <strong>{{ transferToStudent.name }}</strong>
                        <span>
                          {{ transferToStudent.grade || '未填年级' }}
                          <template v-if="transferToStudent.phone">
                            · {{ transferToStudent.phone }}
                          </template>
                          <template v-if="transferToStudent.school">
                            · {{ transferToStudent.school }}
                          </template>
                        </span>
                      </div>
                      <el-button text type="primary" @click="clearTransferToStudent">更换</el-button>
                    </div>
                    <div v-else class="transfer-to-search">
                      <el-autocomplete
                        v-model="transferToSearchQ"
                        clearable
                        class="transfer-to-input"
                        placeholder="输入转入学员姓名 / 手机号"
                        value-key="label"
                        :fetch-suggestions="queryTransferToSuggestions"
                        :trigger-on-focus="false"
                        popper-class="student-search-popper"
                        @select="(item: Student & { label: string }) => pickTransferToStudent(item)"
                        @keyup.enter.stop="runTransferToSearch"
                      >
                        <template #prefix>
                          <el-icon><Search /></el-icon>
                        </template>
                        <template #default="{ item }">
                          <div class="student-suggestion">
                            <span class="student-suggestion-name">{{ item.name }}</span>
                            <span class="student-suggestion-meta">
                              {{ item.grade || '未填年级' }}
                              <template v-if="item.phone"> · {{ item.phone }}</template>
                            </span>
                          </div>
                        </template>
                      </el-autocomplete>
                      <el-button
                        type="primary"
                        plain
                        :loading="transferToSearching"
                        @click="runTransferToSearch"
                      >
                        查找
                      </el-button>
                    </div>
                    <div v-if="transferToResults.length" class="transfer-to-hits">
                      <button
                        v-for="s in transferToResults"
                        :key="s.id"
                        type="button"
                        class="hit-card"
                        @click="pickTransferToStudent(s)"
                      >
                        <span class="hit-avatar">{{ (s.name || '?').slice(0, 1) }}</span>
                        <span class="hit-main">
                          <span class="hit-name">{{ s.name }}</span>
                          <span class="hit-meta">
                            {{ s.grade || '未填年级' }}
                            <template v-if="s.phone"> · {{ s.phone }}</template>
                          </span>
                        </span>
                      </button>
                    </div>
                    <p class="form-hint">
                      转出学员为上方已选学员；课时将从本学员扣减，并写入目标学员课包。
                    </p>
                  </el-form-item>
                </template>

                <div class="form-section-head sub-head">
                  <h3>转出信息</h3>
                </div>
                <el-form-item label="转出课程" required>
                  <el-select
                    v-model="enrollForm.transfer_out_course_id"
                    filterable
                    clearable
                    placeholder="选择该学员可转出的课程"
                    style="width: 100%; max-width: 420px"
                    :loading="packagesLoading"
                  >
                    <el-option
                      v-for="c in transferOutCourseOptions"
                      :key="c.course_id!"
                      :label="`${c.course_name}（剩余 ${Number(c.remain_hours || 0)} 课时）`"
                      :value="c.course_id!"
                    />
                  </el-select>
                  <p v-if="!packagesLoading && !transferOutCourseOptions.length" class="form-hint form-error">
                    该学员暂无可转出课时的课程
                  </p>
                </el-form-item>

                <div v-if="transferOutRows.length" class="purchase-table-wrap transfer-out-wrap">
                  <el-table
                    v-if="!isApp"
                    :data="transferOutRows"
                    border
                    size="small"
                    class="purchase-table transfer-out-table"
                  >
                    <el-table-column label="订单号" min-width="140">
                      <template #default="{ row }">{{ row.order_no }}</template>
                    </el-table-column>
                    <el-table-column label="单价" width="110" align="right">
                      <template #default="{ row }">
                        {{ Number(row.unit_price).toFixed(2) }}元/课时
                      </template>
                    </el-table-column>
                    <el-table-column label="剩余课时" width="100" align="center">
                      <template #default="{ row }">{{ row.remain_hours }}课时</template>
                    </el-table-column>
                    <el-table-column label="转出购买" width="130" align="center">
                      <template #default="{ row }">
                        <el-input-number
                          v-model="row.transfer_hours"
                          :min="0"
                          :max="row.remain_hours"
                          :precision="2"
                          :step="0.5"
                          :controls="false"
                          style="width: 100%"
                        />
                      </template>
                    </el-table-column>
                    <el-table-column label="转出赠送" width="120" align="center">
                      <template #default="{ row }">
                        <el-input-number
                          v-model="row.transfer_gift_hours"
                          :min="0"
                          :max="Math.max(0, row.remain_hours - Number(row.transfer_hours || 0))"
                          :precision="2"
                          :step="0.5"
                          :controls="false"
                          style="width: 100%"
                        />
                      </template>
                    </el-table-column>
                    <el-table-column label="转出金额" width="120" align="right">
                      <template #default="{ row }">
                        <el-input-number
                          :model-value="transferLineAmount(row)"
                          :min="0"
                          :precision="2"
                          :controls="false"
                          style="width: 100%"
                          @update:model-value="(v: number | undefined) => (row.transfer_amount_override = Number(v || 0))"
                        />
                      </template>
                    </el-table-column>
                    <el-table-column label="手续费" width="100" align="right">
                      <template #default="{ row }">
                        <el-input-number
                          v-model="row.fee"
                          :min="0"
                          :precision="2"
                          :controls="false"
                          style="width: 100%"
                        />
                      </template>
                    </el-table-column>
                  </el-table>
                  <div v-else class="transfer-out-mobile">
                    <section v-for="row in transferOutRows" :key="row.package_id" class="purchase-mobile-card">
                      <header class="purchase-mobile-head">
                        <strong>{{ row.order_no }}</strong>
                        <span>剩余 {{ row.remain_hours }}课时</span>
                      </header>
                      <div class="purchase-mobile-body">
                        <label>
                          <span>转出购买课时</span>
                          <el-input-number
                            v-model="row.transfer_hours"
                            :min="0"
                            :max="row.remain_hours"
                            :precision="2"
                            :controls="false"
                          />
                        </label>
                        <label>
                          <span>转出金额</span>
                          <el-input-number
                            :model-value="transferLineAmount(row)"
                            :min="0"
                            :precision="2"
                            :controls="false"
                            @update:model-value="(v: number | undefined) => (row.transfer_amount_override = Number(v || 0))"
                          />
                        </label>
                      </div>
                    </section>
                  </div>
                  <div class="section-total transfer-out-sum">
                    转出合计
                    <strong>¥{{ transferOutTotal.toFixed(2) }}</strong>
                    <span v-if="transferFeeTotal > 0" class="sum-fee">
                      · 手续费 ¥{{ transferFeeTotal.toFixed(2) }}
                    </span>
                  </div>
                </div>
                <el-empty
                  v-else-if="enrollForm.transfer_out_course_id"
                  description="该课程下暂无可转出课包"
                  :image-size="48"
                />

                <div class="form-section-head sub-head">
                  <h3>
                    {{ isTransferToStudent ? '转入信息（写入目标学员）' : '转入信息' }}
                  </h3>
                </div>
              </template>

              <el-form-item :label="isTransfer ? '转入课程' : '关联课程'" required>
                <div class="course-block">
                  <el-select
                    v-model="enrollForm.course_ids"
                    multiple
                    filterable
                    collapse-tags
                    collapse-tags-tooltip
                    :placeholder="isTransfer ? '请选择转入课程（可多选）' : '请选择课程（可多选）'"
                    style="width: 100%; max-width: 560px"
                  >
                    <el-option
                      v-for="c in courseOptions"
                      :key="c.id"
                      :label="`${c.name}（${c.type_label} · ${c.price_label}）`"
                      :value="c.id"
                    />
                  </el-select>
                  <p class="form-hint">
                    <template v-if="isTransferToStudent">
                      转入课程与课时将写入
                      <strong>{{ transferToStudent?.name || '目标学员' }}</strong>
                      的课包；默认按转出课时带入同课程，可修改。
                    </template>
                    <template v-else-if="isTransfer">
                      转入课程将写入本学员新课包；转出课时从原课包扣减。
                    </template>
                    <template v-else>
                      课程目录与「教务中心 · 课程管理」一致。
                    </template>
                  </p>
                </div>
              </el-form-item>

              <div v-if="purchaseRows.length" class="purchase-table-wrap">
                <el-table v-if="!isApp" :data="purchaseRows" border size="small" class="purchase-table">
                  <el-table-column label="购买项目" min-width="168">
                    <template #default="{ row }">
                      <div class="purchase-name">{{ row.course.name }}</div>
                      <span class="purchase-type">{{ row.course.type_label }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="定价标准" width="210">
                    <template #default="{ row }">
                      <el-select v-model="row.detail.price_standard">
                        <el-option :label="row.course.price_label" :value="row.course.price_label" />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="购买课时" width="146">
                    <template #default="{ row }">
                      <div class="course-stepper">
                        <button
                          type="button"
                          aria-label="购买课时减0.25"
                          :disabled="row.detail.hours <= 0.01"
                          @click="changePurchaseHours(row.detail, 'hours', -0.25)"
                        >
                          <el-icon><Minus /></el-icon>
                        </button>
                        <el-input
                          v-model.number="row.detail.hours"
                          inputmode="decimal"
                          aria-label="购买课时"
                          @blur="normalizePurchaseNumber(row.detail, 'hours')"
                        />
                        <button
                          type="button"
                          aria-label="购买课时加0.25"
                          @click="changePurchaseHours(row.detail, 'hours', 0.25)"
                        >
                          <el-icon><Plus /></el-icon>
                        </button>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="总价" width="112" align="right">
                    <template #default="{ row }">¥{{ row.total.toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column label="赠送课时" width="146">
                    <template #default="{ row }">
                      <div class="course-stepper">
                        <button
                          type="button"
                          aria-label="赠送课时减0.25"
                          :disabled="row.detail.gift_hours <= 0"
                          @click="changePurchaseHours(row.detail, 'gift_hours', -0.25)"
                        >
                          <el-icon><Minus /></el-icon>
                        </button>
                        <el-input
                          v-model.number="row.detail.gift_hours"
                          inputmode="decimal"
                          aria-label="赠送课时"
                          @blur="normalizePurchaseNumber(row.detail, 'gift_hours')"
                        />
                        <button
                          type="button"
                          aria-label="赠送课时加0.25"
                          @click="changePurchaseHours(row.detail, 'gift_hours', 0.25)"
                        >
                          <el-icon><Plus /></el-icon>
                        </button>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="直减/折扣" width="220">
                    <template #default="{ row }">
                      <div class="discount-control">
                        <el-select
                          v-model="row.detail.discount_type"
                          @change="onDiscountTypeChange(row.detail)"
                        >
                          <el-option label="直减" value="reduce" />
                          <el-option label="折扣" value="rate" />
                        </el-select>
                        <el-input-number
                          v-model="row.detail.discount_value"
                          :min="0"
                          :max="row.detail.discount_type === 'rate' ? 10 : row.total"
                          :precision="row.detail.discount_type === 'rate' ? 1 : 2"
                          :step="row.detail.discount_type === 'rate' ? 0.1 : 50"
                          :controls="false"
                          @change="onDiscountValueChange(row.detail)"
                        />
                        <span>{{ row.detail.discount_type === 'rate' ? '折' : '元' }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="小计" width="128" align="right">
                    <template #default="{ row }">
                      <div class="subtotal-edit" :class="{ 'is-manual': row.subtotalEdited }">
                        <span class="subtotal-edit__yen">¥</span>
                        <el-input
                          :model-value="
                            row.detail.subtotal_override != null
                              ? row.subtotal
                              : row.subtotal.toFixed(2)
                          "
                          inputmode="decimal"
                          class="subtotal-edit__input"
                          aria-label="小计金额，可编辑"
                          @update:model-value="
                            (v: string) => setPurchaseSubtotal(row.course.id, row.total, v)
                          "
                          @blur="(e: FocusEvent) => onSubtotalBlur(row.course.id, row.total, e)"
                        />
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="72" align="center">
                    <template #default="{ row }">
                      <el-tooltip content="移除课程" placement="top">
                        <el-button link type="danger" aria-label="移除课程" @click="removePurchase(row.course.id)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </el-tooltip>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else class="purchase-mobile-list">
                  <section
                    v-for="row in purchaseRows"
                    :key="row.course.id"
                    class="purchase-mobile-card"
                    :class="{ 'is-expanded': expandedPurchaseId === row.course.id }"
                  >
                    <header class="purchase-mobile-head">
                      <button
                        type="button"
                        class="purchase-mobile-summary"
                        :aria-expanded="expandedPurchaseId === row.course.id"
                        :aria-label="`${expandedPurchaseId === row.course.id ? '收起' : '编辑'}${row.course.name}`"
                        @click="togglePurchaseCard(row.course.id)"
                      >
                        <span class="purchase-mobile-title">
                          <strong>{{ row.course.name }}</strong>
                          <span>
                            {{ row.course.type_label }} · 购买 {{ row.detail.hours }} 课时
                            <template v-if="row.detail.gift_hours"> · 赠 {{ row.detail.gift_hours }}</template>
                          </span>
                        </span>
                        <span
                          class="purchase-mobile-subtotal"
                          :class="{ 'is-manual': row.subtotalEdited }"
                        >
                          小计 ¥{{ row.subtotal.toFixed(2) }}
                        </span>
                        <el-icon class="purchase-mobile-chevron"><ArrowDown /></el-icon>
                      </button>
                      <el-button
                        class="purchase-mobile-remove"
                        link
                        type="danger"
                        aria-label="移除课程"
                        @click.stop="removePurchase(row.course.id)"
                      >
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </header>
                    <div v-show="expandedPurchaseId === row.course.id" class="purchase-mobile-body">
                      <label class="purchase-mobile-field purchase-mobile-price-standard">
                        <span>定价标准</span>
                        <el-select v-model="row.detail.price_standard">
                          <el-option :label="row.course.price_label" :value="row.course.price_label" />
                        </el-select>
                      </label>
                      <div class="purchase-mobile-grid">
                        <div class="purchase-mobile-field">
                          <span>购买课时</span>
                          <div class="course-stepper">
                            <button type="button" aria-label="购买课时减0.25" :disabled="row.detail.hours <= 0.01" @click="changePurchaseHours(row.detail, 'hours', -0.25)"><el-icon><Minus /></el-icon></button>
                            <el-input v-model.number="row.detail.hours" inputmode="decimal" aria-label="购买课时" @blur="normalizePurchaseNumber(row.detail, 'hours')" />
                            <button type="button" aria-label="购买课时加0.25" @click="changePurchaseHours(row.detail, 'hours', 0.25)"><el-icon><Plus /></el-icon></button>
                          </div>
                        </div>
                        <div class="purchase-mobile-field">
                          <span>赠送课时</span>
                          <div class="course-stepper">
                            <button type="button" aria-label="赠送课时减0.25" :disabled="row.detail.gift_hours <= 0" @click="changePurchaseHours(row.detail, 'gift_hours', -0.25)"><el-icon><Minus /></el-icon></button>
                            <el-input v-model.number="row.detail.gift_hours" inputmode="decimal" aria-label="赠送课时" @blur="normalizePurchaseNumber(row.detail, 'gift_hours')" />
                            <button type="button" aria-label="赠送课时加0.25" @click="changePurchaseHours(row.detail, 'gift_hours', 0.25)"><el-icon><Plus /></el-icon></button>
                          </div>
                        </div>
                      </div>
                      <div class="purchase-mobile-field">
                        <span>优惠调整</span>
                        <div class="discount-control">
                          <el-select v-model="row.detail.discount_type" @change="onDiscountTypeChange(row.detail)">
                            <el-option label="直减" value="reduce" />
                            <el-option label="折扣" value="rate" />
                          </el-select>
                          <el-input-number
                            v-model="row.detail.discount_value"
                            :min="0"
                            :max="row.detail.discount_type === 'rate' ? 10 : row.total"
                            :precision="row.detail.discount_type === 'rate' ? 1 : 2"
                            :step="row.detail.discount_type === 'rate' ? 0.1 : 50"
                            :controls="false"
                            @change="onDiscountValueChange(row.detail)"
                          />
                          <span>{{ row.detail.discount_type === 'rate' ? '折' : '元' }}</span>
                        </div>
                      </div>
                      <div class="purchase-mobile-field purchase-mobile-subtotal-field">
                        <span>
                          小计（可改）
                          <em v-if="row.subtotalEdited" class="subtotal-manual-tag">已改价</em>
                        </span>
                        <div class="subtotal-edit is-mobile" :class="{ 'is-manual': row.subtotalEdited }">
                          <span class="subtotal-edit__yen">¥</span>
                          <el-input
                            :model-value="
                              row.detail.subtotal_override != null
                                ? row.subtotal
                                : row.subtotal.toFixed(2)
                            "
                            inputmode="decimal"
                            class="subtotal-edit__input"
                            aria-label="小计金额，可编辑"
                            @update:model-value="
                              (v: string) => setPurchaseSubtotal(row.course.id, row.total, v)
                            "
                            @blur="(e: FocusEvent) => onSubtotalBlur(row.course.id, row.total, e)"
                          />
                        </div>
                        <p class="form-hint">
                          原价 ¥{{ row.total.toFixed(2) }}；改小计不联动优惠，改优惠会重算小计
                        </p>
                      </div>
                    </div>
                  </section>
                </div>
              </div>
              <el-empty
                v-else
                :description="isTransfer ? '请选择转入课程' : '请选择报名课程'"
                :image-size="52"
              />
              <div v-if="isTransfer" class="section-total transfer-calc">
                <span>转入合计 <b>¥{{ transferInTotal.toFixed(2) }}</b></span>
                <span>转出合计 <b>¥{{ transferOutTotal.toFixed(2) }}</b></span>
                <span v-if="transferFeeTotal > 0">手续费 <b>¥{{ transferFeeTotal.toFixed(2) }}</b></span>
                <span class="recv">
                  应收金额
                  <strong>¥{{ receivableTotal.toFixed(2) }}</strong>
                </span>
              </div>
              <div v-else class="section-total">
                应收合计 <strong>¥{{ receivableTotal.toFixed(2) }}</strong>
              </div>
            </section>

            <section class="form-section">
              <div class="form-section-head"><h3>支付信息</h3></div>
              <div class="amount-summary">
                <div><span>应收金额</span><strong>¥{{ receivableTotal.toFixed(2) }}</strong></div>
                <div><span>实收金额</span><strong>¥{{ receivedTotal.toFixed(2) }}</strong></div>
                <div :class="{ 'has-arrears': arrearsTotal > 0 }"><span>欠费金额</span><strong>¥{{ arrearsTotal.toFixed(2) }}</strong></div>
              </div>
              <el-form-item
                :label="receivableTotal > 0 ? '收款方式' : '收款方式（可选）'"
                :required="receivableTotal > 0"
              >
                <div class="pay-block">
                  <el-checkbox-group v-model="enrollForm.pay_methods" class="pay-method-grid">
                    <div
                      v-for="m in PAY_METHOD_OPTIONS"
                      :key="m"
                      class="pay-method-item"
                      :class="{ 'is-selected': enrollForm.pay_methods.includes(m) }"
                    >
                      <el-checkbox :value="m">{{ m }}</el-checkbox>
                      <el-input-number
                        v-if="enrollForm.pay_methods.includes(m)"
                        v-model="enrollForm.pay_amounts[m]"
                        :min="0"
                        :precision="2"
                        :step="100"
                        :controls="false"
                        placeholder="实收"
                      />
                      <span v-else class="pay-amount-empty" aria-hidden="true" />
                    </div>
                  </el-checkbox-group>
                  <el-input
                    v-if="showPayOther"
                    v-model="enrollForm.pay_other"
                    class="pay-other-input"
                    maxlength="64"
                    show-word-limit
                    placeholder="请填写其他支付方式说明"
                  />
                  <p v-if="receivedTotal > receivableTotal" class="form-error">实收金额不能大于应收金额</p>
                  <p
                    v-else-if="!isTransfer && receivableTotal > 0 && receivedTotal <= 0"
                    class="form-error"
                  >
                    报名/续费须填写实收金额，不能零支付提交
                  </p>
                  <p class="form-hint">
                    {{
                      isTransfer && receivableTotal <= 0
                        ? '转出金额已覆盖转入，无需补差价；可直接确认转课。'
                        : !isTransfer
                          ? '报名/续费须至少有一笔实收；可组合收款，未收部分记为欠费。'
                          : '可组合收款；未收部分会作为欠费同步到财务订单。'
                    }}
                  </p>
                </div>
              </el-form-item>
            </section>

            <section class="form-section">
              <div class="form-section-head"><h3>其他信息</h3></div>
              <el-form-item label="经办日期" required>
                <el-date-picker
                  v-model="enrollForm.handled_at"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择日期"
                  style="width: 220px"
                />
              </el-form-item>

              <el-form-item label="业绩归属">
              <div class="attr-block">
                <el-table
                  v-if="enrollForm.attributions.length"
                  v-show="!isApp"
                  :data="enrollForm.attributions"
                  size="small"
                  border
                  class="attr-table"
                >
                  <el-table-column label="归属人" min-width="160">
                    <template #default="{ row }">
                      <el-select
                        v-model="row.user_id"
                        filterable
                        placeholder="选择同事"
                        style="width: 100%"
                      >
                        <el-option
                          v-for="u in staff"
                          :key="u.id"
                          :label="staffLabel(u)"
                          :value="u.id"
                          :disabled="enrollForm.attributions.some((a) => a !== row && a.user_id === u.id)"
                        />
                      </el-select>
                    </template>
                  </el-table-column>
                  <el-table-column label="销售业绩（元）" width="150">
                    <template #default="{ row, $index }">
                      <el-input-number
                        v-model="row.amount"
                        :min="0"
                        :max="receivableTotal"
                        :precision="2"
                        :step="50"
                        :controls="false"
                        style="width: 100%"
                        @change="balanceAttributions($index)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="72" align="center">
                    <template #default="{ $index }">
                      <el-button link type="danger" @click="removeAttribution($index)">
                        移除
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-if="isApp && enrollForm.attributions.length" class="attr-mobile-list">
                  <section v-for="(row, index) in enrollForm.attributions" :key="row.key" class="attr-mobile-card">
                    <label>
                      <span>归属人</span>
                      <el-select v-model="row.user_id" filterable placeholder="选择同事">
                        <el-option v-for="u in staff" :key="u.id" :label="staffLabel(u)" :value="u.id" :disabled="enrollForm.attributions.some((a) => a !== row && a.user_id === u.id)" />
                      </el-select>
                    </label>
                    <label>
                      <span>销售业绩（元）</span>
                      <el-input-number v-model="row.amount" :min="0" :max="receivableTotal" :precision="2" :step="50" :controls="false" @change="balanceAttributions(index)" />
                    </label>
                    <el-button plain type="danger" @click="removeAttribution(index)">移除</el-button>
                  </section>
                </div>
                <div class="attr-foot">
                  <el-button plain size="small" @click="addAttribution">
                    <el-icon><Plus /></el-icon>
                    添加（{{ enrollForm.attributions.length }}/10）
                  </el-button>
                  <span v-if="enrollForm.attributions.length" class="attr-sum">
                    归属合计 ¥{{ attrTotal.toFixed(2) }} / 应收 ¥{{ receivableTotal.toFixed(2) }}
                  </span>
                </div>
                <p v-if="enrollForm.attributions.length && !attributionComplete" class="form-error">
                  销售业绩合计必须等于应收金额
                </p>
              </div>
              </el-form-item>

              <el-form-item label="对内备注">
              <div class="notes-block">
                <div class="image-row">
                  <el-upload
                    :show-file-list="false"
                    accept="image/jpeg,image/png,image/webp,image/jpg"
                    :http-request="() => undefined"
                    :before-upload="onPickImage"
                    :disabled="imagePaths.length >= 3 || uploadingImage"
                  >
                    <el-button plain size="small" :loading="uploadingImage">
                      <el-icon><Upload /></el-icon>
                      上传图片
                    </el-button>
                  </el-upload>
                  <span class="form-hint">jpg / png / webp，最多 3 张，单张 ≤20MB</span>
                </div>
                <div v-if="imagePreviews.length" class="preview-row">
                  <div v-for="img in imagePreviews" :key="img.path" class="preview-item">
                    <img :src="img.url" alt="" />
                    <button type="button" class="preview-remove" @click="removeImage(img.path)">
                      <el-icon><Close /></el-icon>
                    </button>
                  </div>
                </div>
                <el-input
                  v-model="enrollForm.internal_notes"
                  type="textarea"
                  :rows="3"
                  maxlength="1000"
                  show-word-limit
                  placeholder="内部可见备注，可选"
                />
              </div>
              </el-form-item>

              <el-form-item label="对外备注">
              <el-input
                v-model="enrollForm.external_notes"
                type="textarea"
                :rows="2"
                maxlength="500"
                show-word-limit
                placeholder="可给家长看的说明，可选"
              />
              </el-form-item>
            </section>

            <!-- 提交前确认摘要 -->
            <section class="confirm-summary" :class="{ 'is-ready': canSubmit }">
              <div class="confirm-summary__accent" aria-hidden="true" />
              <div class="confirm-summary__head">
                <div class="confirm-summary__title-wrap">
                  <span class="confirm-summary__kicker">提交前核对</span>
                  <strong class="confirm-summary__title">确认摘要</strong>
                </div>
                <el-tag
                  size="small"
                  effect="dark"
                  round
                  :type="canSubmit ? 'success' : 'warning'"
                  class="confirm-summary__badge"
                >
                  {{ canSubmit ? '可提交' : '待完善' }}
                </el-tag>
              </div>

              <div class="confirm-summary__identity">
                <div class="confirm-summary__avatar" aria-hidden="true">
                  {{ (selected.name || '?').slice(0, 1) }}
                </div>
                <div class="confirm-summary__who">
                  <div class="confirm-summary__name">{{ selected.name }}</div>
                  <div class="confirm-summary__meta">
                    <el-tag size="small" effect="plain" round type="warning">
                      {{ kindLabels[enrollForm.kind] || enrollForm.kind }}
                    </el-tag>
                    <span class="confirm-summary__course" :title="confirmCourseLabel">
                      {{ isTransfer ? '转入' : '课程' }} · {{ confirmCourseLabel }}
                    </span>
                  </div>
                </div>
              </div>

              <div class="confirm-summary__money">
                <div class="confirm-money-pill">
                  <span class="confirm-money-pill__label">应收</span>
                  <strong class="confirm-money-pill__value">¥{{ receivableTotal.toFixed(2) }}</strong>
                </div>
                <div class="confirm-money-pill is-received">
                  <span class="confirm-money-pill__label">实收</span>
                  <strong class="confirm-money-pill__value">¥{{ receivedTotal.toFixed(2) }}</strong>
                </div>
                <div v-if="arrearsTotal > 0" class="confirm-money-pill is-arrears">
                  <span class="confirm-money-pill__label">欠费</span>
                  <strong class="confirm-money-pill__value">¥{{ arrearsTotal.toFixed(2) }}</strong>
                </div>
              </div>

              <div class="confirm-summary__pay">
                <span class="confirm-summary__pay-label">支付方式</span>
                <strong class="confirm-summary__pay-value">{{ confirmPayLabel }}</strong>
              </div>

              <p v-if="!canSubmit" class="confirm-summary__hint">
                请完善课程、支付与业绩归属后再提交
              </p>
              <p v-else class="confirm-summary__hint is-ok">
                信息已齐全，确认无误后提交{{ kindLabels[enrollForm.kind] || '登记' }}
              </p>
            </section>

            <el-form-item v-if="!isApp">
              <div class="form-actions">
                <el-button @click="clearSelected">取消</el-button>
                <el-button
                  type="primary"
                  :loading="submitting"
                  :disabled="!canSubmit"
                  @click="submitEnrollment"
                >
                  确认{{ kindLabels[enrollForm.kind] }}
                </el-button>
              </div>
            </el-form-item>
            <MobileActionBar v-else>
              <el-button @click="clearSelected">取消</el-button>
              <el-button
                type="primary"
                :loading="submitting"
                :disabled="!canSubmit"
                @click="submitEnrollment"
              >
                确认{{ kindLabels[enrollForm.kind] }}
              </el-button>
            </MobileActionBar>
          </el-form>
        </template>
      </section>

      <!-- 右侧：最近记录 -->
      <aside class="panel recent-panel" v-loading="loadingRecent">
        <div class="panel-head">
          <h2 class="panel-title">最近登记</h2>
          <el-button link type="primary" @click="loadRecent">刷新</el-button>
        </div>
        <el-empty
          v-if="!recent.length && !loadingRecent"
          description="暂无报名/续费记录"
          :image-size="64"
        />
        <ul v-else class="recent-list">
          <li v-for="row in recent" :key="row.id" class="recent-item">
            <div class="recent-top">
              <span class="recent-name">{{ row.student_name || `学员#${row.student_id}` }}</span>
              <el-tag
                size="small"
                effect="plain"
                round
                :type="row.kind === 'enroll' ? 'success' : row.kind === 'transfer' ? 'primary' : 'warning'"
              >
                {{ kindLabels[row.kind] || row.kind }}
              </el-tag>
            </div>
            <div class="recent-meta">
              <span>{{ formatTime(row.handled_at) }}</span>
              <span v-if="row.amount">¥{{ Number(row.amount).toFixed(2) }}</span>
            </div>
            <div v-if="row.order_no" class="recent-order">
              订单
              <button
                v-if="row.order_id"
                type="button"
                class="link-btn"
                @click="router.push(`/finance/orders/${row.order_id}`)"
              >
                {{ row.order_no }}
              </button>
              <span v-else>{{ row.order_no }}</span>
            </div>
            <div v-if="!isApp && row.pay_methods?.length" class="recent-pay">
              支付
              {{
                row.pay_methods.join('、') +
                (row.pay_other ? `（${row.pay_other}）` : '')
              }}
            </div>
            <div v-if="!isApp && courseSummary(row)" class="recent-courses" :title="courseSummary(row)">
              课程 {{ courseSummary(row) }}
            </div>
            <div v-if="!isApp && row.attributions?.length" class="recent-attr">
              归属
              {{
                row.attributions
                  .map((a) => a.display_name || `#${a.user_id}`)
                  .join('、')
              }}
            </div>
          </li>
        </ul>
        <el-button
          v-if="recentTotal > 2"
          class="recent-more"
          plain
          @click="showAllEnrollments"
        >
          查看更多
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </aside>
    </div>

    <!-- 新建学生：PC 右侧 / wap 底部面板 -->
    <AppSheet
      v-model="createDrawer"
      title="新建学生"
      size="440px"
      modal-class="create-student-drawer"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-position="top"
        class="create-form"
      >
        <div class="drawer-section-title">基本信息</div>
        <el-form-item label="学生姓名" prop="name">
          <el-input v-model="createForm.name" placeholder="必填" maxlength="64" />
        </el-form-item>
        <el-form-item label="手机号码" prop="phone">
          <el-input
            v-model="createForm.phone"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="11"
            placeholder="请输入11位手机号"
            @input="createForm.phone = sanitizePhoneInput(createForm.phone)"
          />
        </el-form-item>
        <el-form-item label="家长称呼">
          <el-input v-model="createForm.parent_name" placeholder="如：张妈妈" maxlength="64" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-select v-model="createForm.grade" filterable allow-create style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="就读学校" prop="school">
          <el-input v-model="createForm.school" placeholder="必填" maxlength="128" />
        </el-form-item>
        <el-form-item label="学管师" prop="academic_manager_id">
          <el-select
            v-model="createForm.academic_manager_id"
            filterable
            placeholder="选择班主任 / 学管"
            style="width: 100%"
          >
            <el-option
              v-for="m in managers.filter((x) => x.is_active)"
              :key="m.id"
              :label="`${m.display_name}（${m.username}）`"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="createForm.notes"
            type="textarea"
            :rows="2"
            placeholder="选填；课程请在建档后的报名表单中选择"
            maxlength="500"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDrawer = false">取消</el-button>
        <el-button type="primary" :loading="createSaving" @click="submitCreateStudent">
          保存并选用
        </el-button>
      </template>
    </AppSheet>
  </div>
</template>

<style scoped>
.enroll-page {
  padding-bottom: 16px;
}

.page-toolbar {
  margin-bottom: 14px;
}

.enroll-steps {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 16px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background: linear-gradient(180deg, #fffefb, #faf3e6);
}

.enroll-step {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  color: #8a8178;
  font-size: 12px;
  font-weight: 650;
}

.enroll-step__n {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 750;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(181, 145, 83, 0.28);
  color: #78716c;
  flex-shrink: 0;
}

.enroll-step.is-active {
  color: #a16207;
}

.enroll-step.is-active .enroll-step__n {
  color: #fffdf8;
  background: linear-gradient(145deg, #c07a12, #a16207);
  border-color: transparent;
  box-shadow: 0 3px 8px rgba(161, 98, 7, 0.25);
}

.enroll-step.is-done .enroll-step__n {
  color: #15803d;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.enroll-step__line {
  flex: 1;
  height: 2px;
  min-width: 12px;
  border-radius: 999px;
  background: rgba(181, 145, 83, 0.2);
}

.enroll-step__line.is-on {
  background: linear-gradient(90deg, #d97706, #a16207);
}

.confirm-summary {
  position: relative;
  margin: 8px 0 18px;
  padding: 16px 16px 14px;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid rgba(181, 145, 83, 0.32);
  background:
    linear-gradient(125deg, #ffffff 0%, #fffdf8 42%, #faf3e6 100%);
  box-shadow:
    0 12px 28px rgba(88, 60, 24, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.confirm-summary__accent {
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 4px;
  border-radius: 0 6px 6px 0;
  background: linear-gradient(180deg, #d4b483, #a16207);
}

.confirm-summary.is-ready {
  border-color: rgba(22, 163, 74, 0.32);
  background:
    linear-gradient(125deg, #ffffff 0%, #f7fbf5 45%, #eef8ea 100%);
  box-shadow:
    0 12px 28px rgba(22, 101, 52, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.confirm-summary.is-ready .confirm-summary__accent {
  background: linear-gradient(180deg, #86efac, #16a34a);
}

.confirm-summary__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding-left: 8px;
}

.confirm-summary__title-wrap {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.confirm-summary__kicker {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.06em;
  color: #a16207;
}

.confirm-summary.is-ready .confirm-summary__kicker {
  color: #15803d;
}

.confirm-summary__title {
  font-size: 16px;
  font-weight: 750;
  color: #3f3a34;
  line-height: 1.3;
}

.confirm-summary__badge {
  flex-shrink: 0;
  font-weight: 700;
}

.confirm-summary__identity {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 0 12px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(181, 145, 83, 0.2);
  background: rgba(255, 253, 248, 0.85);
}

.confirm-summary.is-ready .confirm-summary__identity {
  border-color: rgba(22, 163, 74, 0.18);
  background: rgba(255, 255, 255, 0.72);
}

.confirm-summary__avatar {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 750;
  color: #fffdf8;
  background: linear-gradient(145deg, #c98718, #a16207);
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.22);
}

.confirm-summary__who {
  flex: 1;
  min-width: 0;
}

.confirm-summary__name {
  font-size: 15px;
  font-weight: 720;
  color: #44403c;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.confirm-summary__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.confirm-summary__course {
  min-width: 0;
  font-size: 12px;
  line-height: 1.4;
  color: #78716c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.confirm-summary__money {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
  padding-left: 2px;
}

.confirm-money-pill {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
  text-align: left;
}

.confirm-money-pill.is-received {
  border-color: rgba(161, 98, 7, 0.28);
  background: linear-gradient(180deg, #fff8e8, #f5e6c8);
}

.confirm-money-pill.is-arrears {
  border-color: rgba(180, 83, 9, 0.28);
  background: linear-gradient(180deg, #fff7ed, #ffedd5);
}

.confirm-money-pill__label {
  display: block;
  font-size: 11px;
  font-weight: 650;
  color: #8a8178;
  letter-spacing: 0.04em;
}

.confirm-money-pill__value {
  display: block;
  margin-top: 4px;
  font-size: 16px;
  font-weight: 750;
  color: #a16207;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.confirm-money-pill.is-arrears .confirm-money-pill__value {
  color: #c2410c;
}

.confirm-summary__pay {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 0 2px;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px dashed rgba(181, 145, 83, 0.28);
}

.confirm-summary__pay-label {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 650;
  color: #8a8178;
}

.confirm-summary__pay-value {
  min-width: 0;
  text-align: right;
  font-size: 13px;
  font-weight: 700;
  color: #44403c;
  word-break: break-word;
}

.confirm-summary__hint {
  margin: 12px 2px 0;
  padding: 8px 10px;
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.45;
  color: #92400e;
  background: rgba(254, 243, 199, 0.55);
  border: 1px solid rgba(245, 158, 11, 0.22);
}

.confirm-summary__hint.is-ok {
  color: #166534;
  background: rgba(220, 252, 231, 0.55);
  border-color: rgba(34, 197, 94, 0.22);
}

.page-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  min-width: 0;
}

.search-bar {
  padding: 14px 16px;
  margin-bottom: 14px;
}

.student-picker {
  margin-bottom: 12px;
  overflow: hidden;
  border: 1px solid #e4d5b8;
  border-radius: 8px;
  background: linear-gradient(135deg, #fffdf8 0%, #f8f0e1 100%);
  box-shadow: 0 3px 10px rgba(83, 61, 28, 0.05);
}

.student-picker-main {
  width: 100%;
  min-height: 78px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.student-picker-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #ead9b8;
  border-radius: 8px;
  background: #fff;
  color: var(--oc-primary, #a16207);
  font-size: 18px;
  font-weight: 700;
}

.student-picker-copy {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 2px;
}

.student-picker-label {
  color: #8a7150;
  font-size: 11px;
}

.student-picker-copy strong {
  color: var(--oc-ink, #44403c);
  font-size: 16px;
}

.student-picker-meta {
  overflow: hidden;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.student-picker-action {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--oc-primary, #a16207);
  font-size: 13px;
  font-weight: 600;
}

.student-create-action {
  width: 100%;
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 0;
  border-top: 1px solid #eadfc9;
  background: rgba(255, 255, 255, 0.58);
  color: #6f5a3c;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

.compact-search-results {
  margin-bottom: 12px;
  padding: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fff;
}

.compact-search-title {
  margin-bottom: 8px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  font-weight: 600;
}

.compact-search-hits {
  margin-top: 0;
}

.search-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.search-input {
  flex: 1 1 240px;
  min-width: 0;
  max-width: 480px;
}

.student-suggestion {
  min-width: 0;
  padding: 4px 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.student-suggestion-name {
  color: var(--oc-ink, #44403c);
  font-weight: 600;
}

.student-suggestion-meta {
  overflow: hidden;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.create-btn {
  border-color: var(--el-color-primary-light-5);
  color: var(--oc-primary, #a16207);
  background: #faf6ee;
}

.create-btn:hover {
  border-color: var(--oc-primary, #a16207);
  background: #f5e6c8;
  color: var(--oc-primary, #a16207);
}

.search-hits {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.hit-card {
  appearance: none;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: #fff;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.hit-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 6px 16px rgba(41, 37, 36, 0.06);
  transform: translateY(-1px);
}

.hit-avatar,
.student-avatar {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #f5e6c8, #f2e8d6);
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  flex-shrink: 0;
}

.hit-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hit-name,
.student-name {
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.hit-meta,
.student-meta {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.work-area {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  align-items: start;
}

@media (min-width: 1100px) {
  .work-area {
    grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.55fr);
  }
}

.main-panel {
  padding: 18px 20px 12px;
  min-height: 360px;
}

.empty-stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 56px 20px;
  min-height: 320px;
}

.empty-icon {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #faf6ee, #f5e6c8);
  color: var(--oc-primary, #a16207);
  margin-bottom: 16px;
  box-shadow: 0 0 0 8px rgba(161, 98, 7, 0.06);
}

.empty-title {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
}

.empty-desc {
  margin: 0;
  max-width: 420px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--oc-muted, #78716c);
}

.last-order-hint {
  margin: 14px 0 0;
  font-size: 13px;
  color: var(--oc-primary, #a16207);
}

.pay-block {
  width: 100%;
  max-width: 720px;
}

.pay-method-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(220px, 1fr));
  gap: 10px;
}

.pay-method-item {
  min-width: 0;
  min-height: 46px;
  padding: 6px 8px 6px 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  display: grid;
  grid-template-columns: minmax(76px, 1fr) 132px;
  align-items: center;
  gap: 8px;
  background: #fff;
}

.pay-method-item.is-selected {
  border-color: #d4ad65;
  background: #fffaf0;
}

.pay-method-item :deep(.el-checkbox) {
  margin-right: 0;
}

.pay-method-item :deep(.el-input-number) {
  width: 132px;
}

.pay-amount-empty {
  width: 132px;
  height: 32px;
}

.pay-other-input {
  margin-top: 10px;
  max-width: 360px;
}

.form-error {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-color-danger, #c45656);
}

.student-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 18px;
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(135deg, #fffdf8, #faf6ee);
}

.student-banner-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.enroll-form {
  width: 100%;
}

.form-section {
  padding: 0 0 18px;
  margin-bottom: 18px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.form-section:last-of-type {
  margin-bottom: 6px;
}

.form-section-head {
  min-height: 32px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.form-section-head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--oc-ink, #44403c);
}

.purchase-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.purchase-mobile-list,
.attr-mobile-list {
  display: grid;
  gap: 12px;
}

.attr-mobile-card {
  display: grid;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fff;
}

.purchase-mobile-card {
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fff;
}

.purchase-mobile-card.is-expanded {
  border-color: #ddc89e;
  box-shadow: 0 3px 10px rgba(83, 61, 28, 0.05);
}

.purchase-mobile-head,
.purchase-mobile-total {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.purchase-mobile-head {
  min-height: 68px;
  padding: 0 8px 0 12px;
  background: #fff;
}

.purchase-mobile-card.is-expanded .purchase-mobile-head {
  background: #fffaf0;
}

.purchase-mobile-summary {
  min-width: 0;
  min-height: 68px;
  flex: 1;
  padding: 9px 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 20px;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.purchase-mobile-summary:focus-visible {
  border-radius: 6px;
  outline: 2px solid #d4ad65;
  outline-offset: -2px;
}

.purchase-mobile-title {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.purchase-mobile-title strong {
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.purchase-mobile-title > span {
  overflow: hidden;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.purchase-mobile-subtotal {
  color: var(--oc-primary, #a16207);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.purchase-mobile-subtotal.is-manual {
  color: #b45309;
}

.subtotal-edit {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
  min-width: 0;
  max-width: 100%;
}

.subtotal-edit.is-mobile {
  width: 100%;
  justify-content: stretch;
}

.subtotal-edit__yen {
  flex: 0 0 auto;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  font-weight: 600;
}

.subtotal-edit__input {
  width: 100px;
}

.subtotal-edit.is-mobile .subtotal-edit__input {
  flex: 1 1 auto;
  width: auto;
}

.subtotal-edit :deep(.el-input__wrapper) {
  padding-left: 8px;
  padding-right: 8px;
}

.subtotal-edit :deep(.el-input__inner) {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 650;
}

.subtotal-edit.is-manual :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px rgba(180, 83, 9, 0.35) inset;
  background: #fffbeb;
}

.subtotal-manual-tag {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
  font-size: 11px;
  font-style: normal;
  font-weight: 650;
}

.purchase-mobile-subtotal-field .form-hint {
  margin: 0;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  line-height: 1.4;
}

.purchase-mobile-chevron {
  color: #8a7150;
  transition: transform 0.16s ease;
}

.purchase-mobile-card.is-expanded .purchase-mobile-chevron {
  transform: rotate(180deg);
}

.purchase-mobile-remove {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  margin: 0 !important;
}

.purchase-mobile-body {
  padding: 11px 12px 12px;
  display: grid;
  gap: 11px;
  border-top: 1px solid #eadfc9;
  background: #fff;
}

.purchase-mobile-field,
.attr-mobile-card label {
  display: grid;
  gap: 7px;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.purchase-mobile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.purchase-mobile-grid .course-stepper {
  width: 100%;
}

.purchase-mobile-body .discount-control {
  grid-template-columns: 88px minmax(0, 1fr) 18px;
  width: 100%;
}

.purchase-mobile-body .discount-control :deep(.el-input-number) {
  width: 100%;
}

.purchase-mobile-total {
  min-height: 36px;
  padding-top: 9px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.purchase-mobile-total strong {
  color: var(--oc-primary, #a16207);
  font-size: 14px;
}

.attr-mobile-card :deep(.el-input-number),
.attr-mobile-card :deep(.el-select) {
  width: 100%;
}

.purchase-table {
  min-width: 1160px;
}

.purchase-table :deep(.el-input-number) {
  width: 112px;
}

.course-stepper {
  width: 128px;
  height: 32px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) 34px;
  overflow: hidden;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 4px;
  background: #fff;
}

.course-stepper button {
  appearance: none;
  border: 0;
  background: #f8f6f1;
  color: var(--oc-ink, #44403c);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.course-stepper button:first-child {
  border-right: 1px solid var(--el-border-color, #dcdfe6);
}

.course-stepper button:last-child {
  border-left: 1px solid var(--el-border-color, #dcdfe6);
}

.course-stepper button:hover:not(:disabled) {
  background: #f5e6c8;
  color: var(--oc-primary, #a16207);
}

.course-stepper button:disabled {
  color: var(--el-text-color-disabled, #c0c4cc);
  cursor: not-allowed;
}

.course-stepper :deep(.el-input__wrapper) {
  padding: 0 6px;
  border-radius: 0;
  box-shadow: none;
}

.course-stepper :deep(.el-input__inner) {
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.discount-control {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 18px;
  align-items: center;
  gap: 5px;
  min-width: 0;
  max-width: 100%;
}

.discount-control :deep(.el-input-number) {
  width: 100%;
  min-width: 0;
}

.discount-control > span {
  text-align: center;
  white-space: nowrap;
}

.purchase-name {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.purchase-type {
  display: inline-block;
  margin-top: 3px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.section-total {
  margin-top: 10px;
  text-align: right;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.section-total strong {
  margin-left: 10px;
  color: var(--oc-primary, #a16207);
  font-size: 18px;
}

.form-section-head.sub-head {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
}

.transfer-out-wrap {
  margin-bottom: 8px;
}

.transfer-out-sum .sum-fee {
  margin-left: 10px;
  color: #a16207;
}

.transfer-calc {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px 16px;
  align-items: baseline;
}

.transfer-calc b {
  color: var(--oc-ink, #44403c);
  font-weight: 650;
}

.transfer-calc .recv strong {
  font-size: 16px;
}

.transfer-out-mobile {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.transfer-to-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  max-width: 520px;
  padding: 10px 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
  background: #fffdf8;
}

.transfer-to-avatar {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(161, 98, 7, 0.12);
  color: #8b5406;
  font-weight: 700;
}

.transfer-to-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.transfer-to-main strong {
  color: var(--oc-ink, #44403c);
  font-size: 14px;
}

.transfer-to-main span {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.transfer-to-search {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
  max-width: 560px;
}

.transfer-to-input {
  flex: 1 1 220px;
  min-width: 0;
}

.transfer-to-hits {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  max-width: 560px;
  margin-top: 8px;
}

.amount-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin-bottom: 18px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-border, #e8e0d0);
  overflow: hidden;
}

.amount-summary > div {
  min-height: 70px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  background: #fff;
}

.amount-summary span {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.amount-summary strong {
  font-size: 18px;
  color: var(--oc-ink, #44403c);
}

.amount-summary .has-arrears strong {
  color: var(--el-color-warning-dark-2, #b45309);
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.course-block {
  width: 100%;
}

.course-block .form-hint {
  display: block;
  margin: 8px 0 0;
}

.course-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.course-chip-meta {
  margin-left: 4px;
  opacity: 0.7;
}

.attr-block {
  width: 100%;
}

.attr-table {
  width: 100%;
  margin-bottom: 8px;
}

.attr-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.attr-sum {
  font-size: 13px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
}

.notes-block {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.image-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.preview-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.preview-item {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.preview-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.preview-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: rgba(41, 37, 36, 0.65);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  width: 100%;
  padding-top: 4px;
}

.recent-panel {
  padding: 14px 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
}

.recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recent-item {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 11px;
  background: #fff;
  padding: 10px 12px;
}

.recent-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.recent-order {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-primary, #a16207);
  font-variant-numeric: tabular-nums;
  word-break: break-all;
}

.link-btn {
  appearance: none;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
}

.recent-pay {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.recent-name {
  font-weight: 650;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
}

.recent-meta {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.recent-courses,
.recent-attr {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-courses {
  color: var(--oc-primary, #a16207);
  font-weight: 500;
}

.recent-more {
  width: 100%;
  margin-top: 12px;
}

.drawer-section-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
  margin-bottom: 12px;
  letter-spacing: 0.04em;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.create-form {
  padding: 0 4px;
}

@media (max-width: 640px) {
  .search-row {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input {
    max-width: none;
  }

  .form-hint {
    display: block;
    margin: 6px 0 0;
  }

  .student-banner-left > div {
    min-width: 0;
  }

  .student-meta {
    white-space: normal;
    overflow-wrap: anywhere;
    line-height: 1.55;
  }
}

@media (max-width: 1199px) {
  .enroll-page {
    padding-bottom: 0;
  }

  .work-area {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .panel {
    border-radius: 8px;
    box-shadow: none;
  }

  .main-panel {
    min-height: 0;
    padding: 14px;
    border: 0;
    background: transparent;
    box-shadow: none;
  }

  .confirm-summary {
    margin-bottom: 12px;
    border-radius: 18px;
    padding: 14px 12px 12px;
  }

  .confirm-summary__head {
    padding-left: 6px;
  }

  .confirm-summary__money {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .confirm-summary__money:has(.is-arrears) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .confirm-money-pill__value {
    font-size: 15px;
  }

  .form-section-head h3 {
    font-weight: 720;
  }

  .form-section-head h3::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 12px;
    margin-right: 8px;
    border-radius: 999px;
    background: linear-gradient(180deg, #d97706, #a16207);
    vertical-align: -1px;
  }

  .empty-stage {
    min-height: 190px;
    padding: 28px 12px 32px;
  }

  .empty-icon {
    width: 62px;
    height: 62px;
    margin-bottom: 12px;
    box-shadow: 0 0 0 6px rgba(161, 98, 7, 0.05);
  }

  .enroll-form :deep(.el-form-item) {
    display: block;
    margin-bottom: 14px;
  }

  .enroll-form :deep(.el-form-item__label) {
    width: auto !important;
    height: auto;
    margin-bottom: 6px;
    justify-content: flex-start;
    line-height: 20px;
  }

  .enroll-form :deep(.el-form-item__content) {
    margin-left: 0 !important;
  }

  .form-section {
    margin-bottom: 14px;
    padding-bottom: 14px;
  }

  .form-section-head {
    min-height: 28px;
    margin-bottom: 12px;
    flex-flow: row wrap;
    align-items: center;
  }

  .purchase-mobile-list,
  .attr-mobile-list {
    gap: 8px;
  }

  .attr-mobile-card {
    gap: 10px;
    padding: 11px;
  }

  .purchase-mobile-grid {
    gap: 8px;
  }

  .amount-summary {
    margin-bottom: 14px;
  }

  .amount-summary > div {
    min-height: 58px;
    padding: 9px 10px;
  }

  .amount-summary strong {
    font-size: 15px;
  }

  .pay-method-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .pay-method-item {
    min-height: 76px;
    padding: 7px 8px;
    grid-template-columns: 1fr;
    grid-template-rows: 26px 32px;
    gap: 4px;
  }

  .pay-method-item :deep(.el-input-number),
  .pay-amount-empty {
    width: 100%;
  }

  .attr-mobile-card {
    grid-template-columns: minmax(0, 1.35fr) minmax(112px, 0.8fr);
    align-items: end;
  }

  .attr-mobile-card > .el-button {
    grid-column: 1 / -1;
    min-height: 30px;
    margin-top: -2px;
  }

  .recent-panel {
    padding: 12px;
  }

  .recent-item {
    padding: 9px 10px;
    border-radius: 7px;
  }

  .recent-meta {
    margin-top: 3px;
  }

  .recent-order {
    overflow: hidden;
    margin-top: 3px;
    text-overflow: ellipsis;
    white-space: nowrap;
    word-break: normal;
  }

  .recent-more {
    min-height: 40px;
    margin-top: 10px;
  }
}

@media (max-width: 640px) {
  .student-picker-main {
    min-height: 74px;
    padding: 10px 12px;
  }

  .student-picker-meta {
    max-width: 205px;
  }

  .search-hits {
    grid-template-columns: 1fr;
  }

  .amount-summary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .amount-summary > div {
    padding-inline: 7px;
  }

  .amount-summary strong {
    font-size: 14px;
  }

  .pay-method-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 360px) {
  .purchase-mobile-grid,
  .attr-mobile-card {
    grid-template-columns: 1fr;
  }
}
</style>
