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
  listManagersApi,
  listStudentsApi,
  type ManagerOption,
  type Student,
} from '../../api/students'
import { listUsersApi, type UserRow } from '../../api/users'
import { listAcademicTeachersApi, listCoursesApi, type Course } from '../../api/academic'
import AppSheet from '../../components/AppSheet.vue'
import { useAuthStore } from '../../stores/auth'
import { sanitizePhoneInput, validateRequiredPhone } from '../../utils/phone'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const searchQ = ref('')
const searching = ref(false)
const searchResults = ref<Student[]>([])
const selected = ref<Student | null>(null)
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
  /** 新建学生须关联课程 */
  course_ids: [] as number[],
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
  course_ids: [
    {
      type: 'array',
      required: true,
      min: 1,
      message: '请至少选择一门关联课程',
      trigger: 'change',
    },
  ],
}

type AttrRow = { key: string; user_id?: number; amount: number }
type PurchaseMeta = {
  hours: number
  gift_hours: number
  price_standard: string
  discount_type: 'reduce' | 'rate'
  discount_value: number
}

const enrollForm = reactive({
  kind: 'enroll' as EnrollmentKind,
  handled_at: '' as string,
  /** 选中的课程 id 列表（多选） */
  course_ids: [] as number[],
  course_details: {} as Record<number, PurchaseMeta>,
  /** 支付方式多选 */
  pay_methods: [] as PayMethodOption[],
  pay_amounts: {} as Partial<Record<PayMethodOption, number>>,
  pay_other: '',
  attributions: [] as AttrRow[],
  internal_notes: '',
  external_notes: '',
})

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
    return {
      course,
      detail,
      total,
      discount,
      subtotal: Math.max(0, total - discount),
    }
  }),
)
const createSelectedCourses = computed(() =>
  courseOptions.value.filter((c) => createForm.course_ids.includes(c.id)),
)
const showPayOther = computed(() => enrollForm.pay_methods.includes('其他'))
const receivableTotal = computed(() =>
  purchaseRows.value.reduce((sum, row) => sum + row.subtotal, 0),
)
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

const canSubmit = computed(
  () =>
    !!selected.value &&
    enrollForm.course_ids.length > 0 &&
    enrollForm.pay_methods.length > 0 &&
    receivedTotal.value <= receivableTotal.value &&
    attributionComplete.value &&
    (!showPayOther.value || !!enrollForm.pay_other.trim()),
)

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
  }
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

function onDiscountTypeChange(detail: PurchaseMeta) {
  detail.discount_value = detail.discount_type === 'rate' ? 10 : 0
}

function normalizePurchaseNumber(detail: PurchaseMeta, key: 'hours' | 'gift_hours') {
  const min = key === 'hours' ? 0.01 : 0
  const value = Number(detail[key])
  detail[key] = Number.isFinite(value)
    ? Math.max(min, Math.round(value * 100) / 100)
    : min
}

function changePurchaseHours(detail: PurchaseMeta, key: 'hours' | 'gift_hours', delta: -0.25 | 0.25) {
  normalizePurchaseNumber(detail, key)
  const min = key === 'hours' ? 0.01 : 0
  detail[key] = Math.max(min, Math.round((detail[key] + delta) * 100) / 100)
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
  revokePreviews()
  imagePaths.value = []
  imagePreviews.value = []
}

function mapLinkedCourseIds(student: Student): number[] {
  const links = student.linked_courses || []
  const ids: number[] = []
  for (const c of links) {
    if (c.id != null && courseOptions.value.some((o) => o.id === c.id)) {
      ids.push(c.id)
    } else {
      const hit = courseOptions.value.find((o) => o.name === c.name)
      if (hit) ids.push(hit.id)
    }
  }
  return [...new Set(ids)]
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
  pickStudent(item)
}

function pickStudent(
  s: Student,
  opts?: { preferEnroll?: boolean; kind?: EnrollmentKind; courseIds?: number[] },
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
  const fromOpt = opts?.courseIds !== undefined ? opts.courseIds : mapLinkedCourseIds(s)
  if (fromOpt.length) {
    enrollForm.course_ids = [...fromOpt]
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

  pickStudent(student, {
    kind: kindValue === 'enroll' ? 'enroll' : 'renew',
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
  createForm.course_ids = []
  await loadManagers()
  createDrawer.value = true
}

async function submitCreateStudent() {
  const ok = await createFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!createForm.course_ids.length) {
    ElMessage.warning('请至少选择一门关联课程')
    return
  }
  createSaving.value = true
  try {
    const courses = createSelectedCourses.value.map((c) => ({
      id: c.id,
      name: c.name,
      type: c.type_label,
      price_label: c.price_label,
      unit_price: c.unit_price,
      hours: 10,
    }))
    const student = await createStudentApi({
      name: createForm.name.trim(),
      grade: createForm.grade,
      school: createForm.school.trim(),
      phone: createForm.phone.trim() || null,
      parent_name: createForm.parent_name.trim() || null,
      academic_manager_id: createForm.academic_manager_id ?? null,
      status: 'active',
      notes: createForm.notes.trim(),
      courses,
    })
    ElMessage.success('学生已创建')
    createDrawer.value = false
    // 新建后进入报名，并带上刚选的课程
    pickStudent(student, {
      preferEnroll: true,
      courseIds: [...createForm.course_ids],
    })
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
    ElMessage.warning('请选择关联课程')
    return
  }
  if (!enrollForm.pay_methods.length) {
    ElMessage.warning('请选择支付方式')
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
    const courses = purchaseRows.value.map(({ course, detail, discount, subtotal }) => ({
      id: course.id,
      name: course.name,
      type: course.type_label,
      price_label: course.price_label,
      unit_price: course.unit_price,
      hours: detail.hours,
      gift_hours: detail.gift_hours,
      price_standard: detail.price_standard,
      discount_type: detail.discount_type,
      discount_value: detail.discount_value,
      discount,
      subtotal,
    }))
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
    })
    const orderNo = record.order_no || ''
    lastOrderNo.value = orderNo
    lastOrderId.value = record.order_id || null
    ElMessage.success(
      orderNo
        ? `${enrollForm.kind === 'enroll' ? '报名' : '续费'}已登记，订单号 ${orderNo}`
        : enrollForm.kind === 'enroll'
          ? '报名已登记'
          : '续费已登记',
    )
    clearSelected()
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

watch(() => [...enrollForm.course_ids], syncCourseDetails)
watch(receivableTotal, () => distributeAttributions())

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
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="报名 / 续费" />
      <p class="page-desc">搜索在读学员办理报名或续费；新学员可先「新建学生」建档并关联课程。</p>
    </div>

    <!-- 搜索条 -->
    <section class="search-bar panel">
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

    <div class="work-area">
      <!-- 左侧：选中学员 + 表单 / 空态 -->
      <section class="panel main-panel">
        <template v-if="!selected">
          <div class="empty-stage">
            <div class="empty-icon" aria-hidden="true">
              <el-icon :size="42"><UserFilled /></el-icon>
            </div>
            <h2 class="empty-title">请先查找学员</h2>
            <p class="empty-desc">
              在上方输入姓名或手机号搜索在册学员；若为新客，点击「新建学生」建档并关联课程后再办理报名。
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
          <div class="student-banner">
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
                <h3>购买内容</h3>
                <el-radio-group v-model="enrollForm.kind" size="small">
                  <el-radio-button value="enroll">报名</el-radio-button>
                  <el-radio-button value="renew">续费</el-radio-button>
                </el-radio-group>
              </div>

              <el-form-item label="关联课程" required>
                <div class="course-block">
                  <el-select
                    v-model="enrollForm.course_ids"
                    multiple
                    filterable
                    collapse-tags
                    collapse-tags-tooltip
                    placeholder="请选择课程（可多选）"
                    style="width: 100%; max-width: 560px"
                  >
                    <el-option
                      v-for="c in courseOptions"
                      :key="c.id"
                      :label="`${c.name}（${c.type_label} · ${c.price_label}）`"
                      :value="c.id"
                    />
                  </el-select>
                  <p class="form-hint">课程目录与「教务中心 · 课程管理」一致。</p>
                </div>
              </el-form-item>

              <div v-if="purchaseRows.length" class="purchase-table-wrap">
                <el-table :data="purchaseRows" border size="small" class="purchase-table">
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
                        />
                        <span>{{ row.detail.discount_type === 'rate' ? '折' : '元' }}</span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="小计" width="110" align="right">
                    <template #default="{ row }"><strong>¥{{ row.subtotal.toFixed(2) }}</strong></template>
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
              </div>
              <el-empty v-else description="请选择报名课程" :image-size="52" />
              <div class="section-total">应收合计 <strong>¥{{ receivableTotal.toFixed(2) }}</strong></div>
            </section>

            <section class="form-section">
              <div class="form-section-head"><h3>支付信息</h3></div>
              <div class="amount-summary">
                <div><span>应收金额</span><strong>¥{{ receivableTotal.toFixed(2) }}</strong></div>
                <div><span>实收金额</span><strong>¥{{ receivedTotal.toFixed(2) }}</strong></div>
                <div :class="{ 'has-arrears': arrearsTotal > 0 }"><span>欠费金额</span><strong>¥{{ arrearsTotal.toFixed(2) }}</strong></div>
              </div>
              <el-form-item label="收款方式" required>
                <div class="pay-block">
                  <el-checkbox-group v-model="enrollForm.pay_methods" class="pay-method-grid">
                    <div v-for="m in PAY_METHOD_OPTIONS" :key="m" class="pay-method-item">
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
                  <p class="form-hint">可组合收款；未收部分会作为欠费同步到财务订单。</p>
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

            <el-form-item>
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
                :type="row.kind === 'enroll' ? 'success' : 'warning'"
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
            <div v-if="row.pay_methods?.length" class="recent-pay">
              支付
              {{
                row.pay_methods.join('、') +
                (row.pay_other ? `（${row.pay_other}）` : '')
              }}
            </div>
            <div v-if="courseSummary(row)" class="recent-courses" :title="courseSummary(row)">
              课程 {{ courseSummary(row) }}
            </div>
            <div v-if="row.attributions?.length" class="recent-attr">
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
        <div class="drawer-section-title">关联课程</div>
        <el-form-item label="选择课程" prop="course_ids">
          <el-select
            v-model="createForm.course_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="请选择课程（可多选，至少一门）"
            style="width: 100%"
          >
            <el-option
              v-for="c in courseOptions"
              :key="c.id"
              :label="`${c.name}（${c.type_label} · ${c.price_label}）`"
              :value="c.id"
            />
          </el-select>
          <p class="form-hint">新学员在此建档，须关联至少一门课程；建档后可在学生信息中查看与编辑。</p>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="createForm.notes"
            type="textarea"
            :rows="2"
            placeholder="选填"
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
  grid-template-columns: 72px 112px 18px;
  align-items: center;
  gap: 5px;
}

.discount-control :deep(.el-input-number) {
  width: 112px;
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

  .student-banner {
    flex-direction: column;
    align-items: flex-start;
  }

  .form-section-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .amount-summary,
  .pay-method-grid {
    grid-template-columns: 1fr;
  }
}
</style>
