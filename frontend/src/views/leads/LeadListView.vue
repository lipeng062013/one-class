<script setup lang="ts">
import { computed, nextTick, onActivated, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  type FormInstance,
  type FormRules,
  type UploadFile,
  type UploadUserFile,
} from 'element-plus'
import {
  createLead,
  downloadLeadImportTemplate,
  importLeadWorkbook,
  listLeads,
  patchLead,
  peekLeadListCache,
  type Lead,
  type LeadListParams,
  type LeadImportResult,
  type LeadSource,
  type LeadStatus,
} from '../../api/leads'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useListScrollRestore } from '../../composables/useListScrollRestore'
import { useServerPagedList } from '../../composables/useServerPagedList'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import { sanitizePhoneInput, validateRequiredPhone } from '../../utils/phone'
import { toBusinessDateTimeIso } from '../../utils/datetime'

const LIST_STATE_KEY = 'oc-lead-list-state'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isApp } = useBreakpoint()
const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()
const { surface: createSurface, surfaceProps: createSurfaceProps } = useResponsiveSurface({
  dialogMaxWidth: '520px',
  compactSize: 'min(92%, 720px)',
  modalClass: 'lead-create-sheet',
})
const { surface: importSurface, surfaceProps: importSurfaceProps } = useResponsiveSurface({
  dialogMaxWidth: '720px',
  compactSize: 'min(94%, 860px)',
  modalClass: 'lead-import-sheet',
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const createVisible = ref(false)
const formRef = ref<FormInstance>()
const saving = ref(false)
const filterExpanded = ref(false)
const importVisible = ref(false)
const importing = ref(false)
const importProgress = ref(0)
const importFile = ref<File | null>(null)
const importFileList = ref<UploadUserFile[]>([])
const importResult = ref<LeadImportResult | null>(null)
const canImport = computed(() => auth.hasPermission('leads.write'))

const filters = reactive({
  source: '',
  status: '',
  name: '',
  phone: '',
})

function buildListParams(p: number, size: number): LeadListParams {
  return {
    source: filters.source || undefined,
    status: filters.status || undefined,
    name: filters.name.trim() || undefined,
    phone: filters.phone.trim() || undefined,
    page: p,
    page_size: size,
  }
}

const {
  page,
  pageSize,
  total,
  rows,
  loading,
  loadingMore,
  hasMore: hasMoreInfinite,
  PAGE_SIZES,
  sentinelRef,
  load: loadPage,
  loadMore,
  onPageChange,
  onPageSizeChange,
  setupScrollObserver,
} = useServerPagedList<Lead>({
  isCompact: isApp,
  getId: (r) => r.id,
  fetchPage: (p, size) => listLeads(buildListParams(p, size)),
})

/** 保持服务端 id 倒序；当前分页内二次排序会导致编辑后跳位且跨页顺序不一致。*/
const pagedRows = computed(() => rows.value)
/** wap/pad 卡片直接用已 append 的 rows（服务端追加），不再二次内存切片 */
const infiniteRows = computed(() => pagedRows.value)
const visibleCount = computed(() => rows.value.length)

const form = reactive({
  student_or_parent_name: '',
  phone: '',
  source: 'referral' as LeadSource,
  referrer_name: '',
  need: '',
  notes: '',
  next_follow_at: null as Date | null,
})

const rules: FormRules = {
  student_or_parent_name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  source: [{ required: true, message: '请选择来源', trigger: 'change' }],
  phone: [{ required: true, validator: validateRequiredPhone, trigger: 'blur' }],
}

const sourceLabels: Record<string, string> = {
  referral: '老带新',
  dianping: '大众点评',
  wechat: '微信',
  walkin: '到店',
  other: '其他',
}
const statusLabels: Record<string, string> = {
  new: '新建',
  contacted: '已联系',
  visited: '已到访',
  enrolled: '已报名',
  lost: '已流失',
}
const statusOptions: LeadStatus[] = ['new', 'contacted', 'visited', 'enrolled', 'lost']

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  switch (status) {
    case 'enrolled':
      return 'success'
    case 'visited':
      return 'warning'
    case 'contacted':
      return 'primary'
    case 'lost':
      return 'info'
    case 'new':
    default:
      return 'danger'
  }
}

function isToday(value?: string | null) {
  if (!value) return false
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return false
  const now = new Date()
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  )
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

function teamLabel(row: Lead) {
  const owner = row.owner_name?.trim()
  const n = row.collaborator_count || 0
  if (owner && n > 0) return `${owner} · 协作 ${n}`
  if (owner) return owner
  if (n > 0) return `协作 ${n} 人`
  return '未指定主责'
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.source) n += 1
  if (filters.status) n += 1
  if (filters.name.trim()) n += 1
  if (filters.phone.trim()) n += 1
  return n
})

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('leads', {
  visibleCount,
  enabled: isApp,
  stateStorageKey: LIST_STATE_KEY,
})

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY)
    if (!raw) return
    const s = JSON.parse(raw) as {
      filters?: Partial<typeof filters>
      page?: number
      pageSize?: number
    }
    if (s.filters) {
      filters.source = s.filters.source ?? ''
      filters.status = s.filters.status ?? ''
      filters.name = s.filters.name ?? ''
      filters.phone = s.filters.phone ?? ''
    }
    // 仍PC 恢复页码；紧凑端始终从第 1 页滚动加载
        if (!isApp.value) {
      if (typeof s.page === 'number' && s.page > 0) page.value = s.page
      if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
        pageSize.value = s.pageSize
      }
    }
  } catch {
    /* ignore */
  }
}

function hasStoredListState() {
  try {
    return sessionStorage.getItem(LIST_STATE_KEY) != null
  } catch {
    return false
  }
}

function clearFilterValues() {
  filters.source = ''
  filters.status = ''
  filters.name = ''
  filters.phone = ''
}

function seedCachedRows() {
  const cached = peekLeadListCache(
    buildListParams(isApp.value ? 1 : page.value, isApp.value ? 10 : pageSize.value),
  )
  if (!cached) return false
  rows.value = cached.items
  total.value = cached.total
  return true
}

function saveListState() {
  try {
    sessionStorage.setItem(
      LIST_STATE_KEY,
      JSON.stringify({
        filters: { ...filters },
        page: page.value,
        pageSize: pageSize.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

async function load(opts?: { resetPage?: boolean; preserveRows?: boolean }) {
  const snap = opts?.resetPage ? null : takeSnapshotForLoad(route.path)
  if (opts?.resetPage) {
    clearSnapshot()
    if (!opts.preserveRows) {
      rows.value = []
      total.value = 0
    }
  }
  await loadPage(opts?.resetPage ? { reset: true } : undefined)
  saveListState()
  void finishListEnter({ snap, forceTop: !!opts?.resetPage })
}

function resetFilters() {
  clearFilterValues()
  collapseAll()
  void load({ resetPage: true })
}

function runQuery() {
  if (isApp.value) filterExpanded.value = false
  collapseAll()
  void load({ resetPage: true })
}

function onPcPageChange() {
  onPageChange()
  saveListState()
}

function onPcPageSizeChange() {
  onPageSizeChange()
  saveListState()
}

function goDetail(row: Lead) {
  void router.push(`/leads/${row.id}`)
}

function openCreate() {
  form.student_or_parent_name = ''
  form.phone = ''
  form.source = 'referral'
  form.referrer_name = ''
  form.need = ''
  form.notes = ''
  form.next_follow_at = null
  createVisible.value = true
}

function openImport() {
  importFile.value = null
  importFileList.value = []
  importResult.value = null
  importProgress.value = 0
  importVisible.value = true
}

function onImportFileChange(file: UploadFile) {
  const raw = file.raw
  if (!raw) return
  const extension = raw.name.slice(raw.name.lastIndexOf('.')).toLowerCase()
  if (!['.xls', '.xlsx'].includes(extension)) {
    ElMessage.warning('请选择 .xls 戍.xlsx 文件')
    importFile.value = null
    importFileList.value = []
    return
  }
  if (raw.size > 5 * 1024 * 1024) {
    ElMessage.warning('文件大小不能超过 5 MB')
    importFile.value = null
    importFileList.value = []
    return
  }
  importFile.value = raw
  importResult.value = null
  importProgress.value = 0
}

function onImportFileRemove() {
  importFile.value = null
  importResult.value = null
  importProgress.value = 0
}

async function downloadImportTemplate() {
  try {
    await downloadLeadImportTemplate()
    ElMessage.success('导入模板已开始下载')
  } catch {
    /* interceptor */
  }
}

async function submitImport() {
  if (!importFile.value) {
    ElMessage.warning('请先选择 Excel 文件')
    return
  }
  importing.value = true
  importProgress.value = 0
  try {
    importResult.value = await importLeadWorkbook(importFile.value, (percent) => {
      importProgress.value = percent
    })
    const result = importResult.value
    if (result.imported_count > 0) {
      ElMessage.success(`成功导入 ${result.imported_count} 条线索`)
      await load({ resetPage: true })
    } else {
      ElMessage.info('文件处理完成，没有新增线索')
    }
  } catch {
    importProgress.value = 0
  } finally {
    importing.value = false
  }
}

function importStatusLabel(status: string) {
  return {
    imported: '成功',
    duplicate: '重复',
    failed: '失败',
    warning: '警告',
  }[status] || status
}

function importStatusType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'imported') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'warning') return 'warning'
  return 'info'
}

async function submitCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const created = await createLead({
      student_or_parent_name: form.student_or_parent_name,
      phone: form.phone || null,
      source: form.source,
      referrer_name: form.referrer_name || null,
      need: form.need,
      notes: form.notes,
      next_follow_at: toBusinessDateTimeIso(form.next_follow_at),
    })
    ElMessage.success('线索已创建')
    createVisible.value = false
    // 新建后进入详情，便于立刻写跟进/ 指定主责
    void router.push(`/leads/${created.id}`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}

function isLeadStatusLocked(row: Lead) {
  return row.status === 'enrolled' && !auth.isAdmin
}

function canGoEnrollAfterConvert() {
  return auth.hasPermission('enrollments.manage') || auth.isAdmin
}

async function changeStatus(row: Lead, status: LeadStatus) {
  if (row.status === 'enrolled' && !auth.isAdmin) {
    ElMessage.warning('已报名线索不可再改状态，如需调整请联系负责人')
    return
  }
  const wasEnrolled = row.status === 'enrolled'
  try {
    const updated = await patchLead(row.id, { status })
    const studentId = updated.converted_student_id
    const conversion = updated.conversion_status

    if (status === 'enrolled' && !wasEnrolled) {
      if (conversion === 'incomplete') {
        ElMessage.warning(updated.conversion_message || '已标记已报名，但信息不全未能建档')
      } else if (studentId && canGoEnrollAfterConvert()) {
        ElMessage.success('已建档，请完成报名')
        await load()
        await router.push({
          path: '/enrollments',
          query: {
            student_id: String(studentId),
            kind: 'enroll',
            from_lead: String(row.id),
          },
        })
        return
      } else if (studentId) {
        ElMessage.success(`已建档学员 #${studentId}，请联系有报名权限的同事办理报名`)
      } else {
        ElMessage.success('状态已更新为已报名')
      }
    } else {
      ElMessage.success('状态已更新')
    }
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '状态更新失败')
    await load()
  }
}

function onPcStatusChange(row: Lead, event: Event) {
  const value = (event.target as HTMLSelectElement).value as LeadStatus
  if (value === row.status) return
  void changeStatus(row, value)
}

onMounted(async () => {
  restoreListState()
  const hasCachedRows = seedCachedRows()
  await load({ resetPage: isApp.value, preserveRows: hasCachedRows })
  await nextTick()
  if (sentinelRef.value) setupScrollObserver()
})

let activationCount = 0
onActivated(() => {
  activationCount += 1
  if (activationCount === 1) return

  if (hasStoredListState()) {
    restoreListState()
  } else {
    clearFilterValues()
    page.value = 1
    pageSize.value = 20
    collapseAll()
  }

  const hasCachedRows = seedCachedRows()
  if (!hasCachedRows) {
    rows.value = []
    total.value = 0
  }
  void load({ resetPage: isApp.value, preserveRows: hasCachedRows })
})
</script>

<template>
  <div class="lead-page">
    <div class="page-toolbar lead-toolbar" :class="{ 'is-compact': isApp }">
      <el-page-header class="is-title-only" content="线索管理" />
      <div class="lead-toolbar-actions">
        <el-button v-if="canImport" class="import-btn" plain @click="openImport">
          <el-icon><Upload /></el-icon>
          导入
        </el-button>
        <el-button class="create-btn tb-btn tb-btn--primary" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新建线索
        </el-button>
      </div>
    </div>

    <!-- PC 筛选：与学生信息列表同一套米金筛选卡 -->
    <div v-if="!isApp" class="lead-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">获客线索</span>
            <span class="pc-list-summary__count">共 <strong>{{ total }}</strong> 条

            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="来源">
            <el-select v-model="filters.source" clearable placeholder="全部" style="width: 120px">
              <el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
              <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model="filters.name" clearable placeholder="搜索姓名" style="width: 130px" />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="filters.phone" clearable placeholder="搜索电话" style="width: 130px" />
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="runQuery">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <div v-if="isApp" class="lead-m">
      <CompactFilterBar :active-count="activeFilterCount" :total="total" label="条线索" @open="filterExpanded = true" />
      <MobileFilterSheet
        v-model="filterExpanded"
        :active-count="activeFilterCount"
        @reset="resetFilters"
        @apply="runQuery"
      >
        <el-form label-position="top" @submit.prevent="runQuery">
          <el-form-item label="姓名"><el-input v-model="filters.name" clearable placeholder="搜索姓名" /></el-form-item>
          <el-form-item label="电话"><el-input v-model="filters.phone" clearable placeholder="搜索电话" /></el-form-item>
          <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
          <el-form-item label="来源"><el-select v-model="filters.source" clearable placeholder="全部来源"><el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
        </el-form>
      </MobileFilterSheet>
    </div>

    <!-- 移动卡片（手机 / Pad App 模式）-->
    <div v-if="isApp" v-loading="loading && !rows.length" class="lead-m lead-card-list">
      <div v-if="!total && !loading" class="oc-app-empty lead-card--empty">
        <strong>暂无线索</strong>
        <em>新建或导入线索后，可在这里跟进与写动态</em>
        <el-button type="primary" class="tb-btn tb-btn--primary" @click="openCreate">
          新建线索
        </el-button>
      </div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="lead-card"
        :class="{
          'is-today': isToday(row.next_follow_at),
          'is-expanded': isExpanded(row.id),
        }"
      >
        <div class="lead-card__top" @click="toggleCard(row.id, $event)">
          <div class="lead-card__avatar">{{ (row.student_or_parent_name || '?').slice(0, 1) }}</div>
          <div class="lead-card__who">
            <div class="lead-card__name">{{ row.student_or_parent_name }}</div>
            <div class="lead-card__sub">
              <span>{{ sourceLabels[row.source] || row.source }}</span>
              <span v-if="row.phone"> · {{ row.phone }}</span>
            </div>
          </div>
          <div class="lead-card__badges">
            <el-tag v-if="isToday(row.next_follow_at)" type="danger" size="small" effect="dark" round>
              今日
            </el-tag>
            <el-tag :type="statusTagType(row.status)" size="small" effect="plain" round>
              {{ statusLabels[row.status] || row.status }}
            </el-tag>
            <el-tag
              v-if="(row.collaborator_count || 0) > 0"
              type="warning"
              size="small"
              effect="plain"
              round
            >
              协作 {{ row.collaborator_count }}
            </el-tag>
          </div>
          <button
            type="button"
            class="m-card-acc-toggle"
            :aria-expanded="isExpanded(row.id)"
            :aria-label="isExpanded(row.id) ? '收起' : '展开'"
            @click.stop="toggleForce(row.id)"
          >
            <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(row.id) }">
              <ArrowDown />
            </el-icon>
          </button>
        </div>

        <div class="oc-meta-chips lead-card__chips">
          <span v-if="row.owner_name" class="oc-meta-chip">{{ row.owner_name }}</span>
          <span
            v-if="row.next_follow_at"
            class="oc-meta-chip"
            :class="{ 'is-warn': isToday(row.next_follow_at) }"
          >
            下次 {{ formatTime(row.next_follow_at) }}
          </span>
          <span v-else class="oc-meta-chip">下次跟进 暂无</span>
          <span v-if="row.school || row.grade" class="oc-meta-chip">
            {{ [row.school, row.grade].filter(Boolean).join(' · ') }}
          </span>
        </div>

        <div v-if="isExpanded(row.id)" class="m-card-acc-body">
          <div v-if="row.need || row.notes" class="lead-card__body">
            <p v-if="row.need" class="lead-card__need">
              <span class="k">需求</span>{{ row.need }}
            </p>
            <p v-if="row.notes" class="lead-card__notes">
              <span class="k">备注</span>{{ row.notes }}
            </p>
          </div>

          <div class="lead-card__meta">
            <div v-if="row.campus || row.external_code" class="lead-meta-item">
              <span class="lead-meta-k">校区编号</span>
              <span class="lead-meta-v">
                {{ [row.campus, row.external_code].filter(Boolean).join(' · ') || '—' }}
              </span>
            </div>
            <div class="lead-meta-item">
              <span class="lead-meta-k">主责</span>
              <span class="lead-meta-v">{{ teamLabel(row) }}</span>
            </div>
            <div class="lead-meta-item lead-meta-item--full">
              <span class="lead-meta-k">最近联系</span>
              <span class="lead-meta-v">
                <template v-if="row.last_contact_at">
                  {{ formatTime(row.last_contact_at) }}
                  <template v-if="row.last_contact_by_name"> · {{ row.last_contact_by_name }}</template>
                </template>
                <template v-else>暂无</template>
              </span>
            </div>
          </div>

          <div class="lead-card__controls">
            <div class="ctrl">
              <span class="ctrl-label">状态</span>
              <el-tag
                v-if="isLeadStatusLocked(row)"
                :type="statusTagType(row.status)"
                size="small"
                effect="plain"
                round
              >
                {{ statusLabels[row.status] || row.status }} · 已锁定
              </el-tag>
              <el-select
                v-else
                :model-value="row.status"
                class="ctrl-select"
                teleported
                placement="bottom-start"
                :fit-input-width="true"
                :popper-options="{ strategy: 'fixed' }"
                popper-class="lead-m-select-popper"
                @change="(v: LeadStatus) => changeStatus(row, v)"
              >
                <el-option v-for="s in statusOptions" :key="s" :label="statusLabels[s]" :value="s" />
              </el-select>
            </div>
          </div>

          <div class="lead-card__actions">
            <el-button type="primary" size="small" @click="goDetail(row)">
              {{ row.status === 'enrolled' ? '查看详情' : '详情 / 写跟进' }}
            </el-button>
            <el-button
              v-if="row.status === 'enrolled' && row.converted_student_id && canGoEnrollAfterConvert()"
              size="small"
              type="success"
              plain
              @click="
                router.push({
                  path: '/enrollments',
                  query: {
                    student_id: String(row.converted_student_id),
                    kind: 'enroll',
                    from_lead: String(row.id),
                  },
                })
              "
            >
              去报名
            </el-button>
          </div>
        </div>
      </div>
      <div ref="sentinelRef" class="list-load-sentinel"><ListLoadStatus :has-more="hasMoreInfinite"
        :loading="loadingMore"
        :loaded="rows.length"
        :total="total"
        @more="loadMore"
        @retry="loadMore"
      /></div>
    </div>

    <!-- PC 表格：与学生信息列表同一套表格气质-->
    <div v-if="!isApp" class="lead-pc">
      <el-card class="pc-table-card" v-loading="loading && !rows.length" shadow="never">
        <div class="table-scroll">
          <el-table
            :data="pagedRows"
            stripe
            class="pc-lead-table"
            style="width: 100%"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="student_or_parent_name" label="姓名" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <button type="button" class="pc-name-cell" @click="goDetail(row)">
                  <span class="pc-avatar">{{ (row.student_or_parent_name || '?').slice(0, 1) }}</span>
                  <span class="pc-name-text">{{ row.student_or_parent_name }}</span>
                </button>
              </template>
            </el-table-column>
            <el-table-column prop="phone" label="电话" width="128">
              <template #default="{ row }">
                <span class="pc-mono">{{ row.phone || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="108">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" round type="info">
                  {{ sourceLabels[row.source] || row.source }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="school" label="学校" min-width="130" show-overflow-tooltip>
              <template #default="{ row }">{{ row.school || '—' }}</template>
            </el-table-column>
            <el-table-column prop="grade" label="年级" width="90">
              <template #default="{ row }">{{ row.grade || '—' }}</template>
            </el-table-column>
            <el-table-column prop="campus" label="校区" min-width="110" show-overflow-tooltip>
              <template #default="{ row }">{{ row.campus || '—' }}</template>
            </el-table-column>
            <el-table-column prop="external_code" label="编号" min-width="110" show-overflow-tooltip>
              <template #default="{ row }">{{ row.external_code || '—' }}</template>
            </el-table-column>
            <el-table-column prop="need" label="需求" min-width="120" show-overflow-tooltip />
            <el-table-column label="主责" min-width="110" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-owner">{{ row.owner_name || '—' }}</span>
                <span v-if="(row.collaborator_count || 0) > 0" class="pc-collab">
                  · 协作 {{ row.collaborator_count }}
                </span>
              </template>
            </el-table-column>
            <!-- 加宽状态列，避免 select 被挤出「.」省略 -->
            <el-table-column label="状态" width="148" class-name="col-status">
              <template #default="{ row }">
                <el-tag
                  v-if="isLeadStatusLocked(row)"
                  :type="statusTagType(row.status)"
                  size="small"
                  effect="plain"
                  round
                >
                  {{ statusLabels[row.status] || row.status }}
                </el-tag>
                <select
                  v-else
                  class="status-native"
                  :value="row.status"
                  aria-label="修改线索状态"
                  @change="onPcStatusChange(row, $event)"
                >
                  <option v-for="s in statusOptions" :key="s" :value="s">
                    {{ statusLabels[s] }}
                  </option>
                </select>
              </template>
            </el-table-column>
            <el-table-column label="下次跟进" min-width="190" class-name="col-follow">
              <template #default="{ row }">
                <div class="follow-cell">
                  <span class="follow-readonly" :class="{ 'is-empty': !row.next_follow_at }">
                    {{ row.next_follow_at ? formatTime(row.next_follow_at) : '暂无' }}
                  </span>
                  <el-tag
                    v-if="isToday(row.next_follow_at)"
                    type="danger"
                    size="small"
                    effect="dark"
                    round
                    class="follow-today-tag"
                  >
                    今日
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="最近联系" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-notes" :class="{ 'is-empty': !row.last_contact_at }">
                  {{ row.last_contact_at ? formatTime(row.last_contact_at) : '—' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="notes" label="备注" min-width="100" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-notes">{{ row.notes || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="88" fixed="right" align="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="goDetail(row)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <!-- 仍PC 显示底部分页；wap/pad 用服务端上拉追加 -->
      <PcPagerBar
        v-if="!isApp"
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        @change="onPcPageChange"
        @size-change="onPcPageSizeChange"
      />
    </div>

    <component
      :is="importSurface"
      v-model="importVisible"
      title="导入线索"
      v-bind="importSurfaceProps"
      :close-on-click-modal="!importing"
      :close-on-press-escape="!importing"
      :show-close="!importing"
      :class="isApp ? undefined : 'lead-import-dialog'"
    >
      <div class="import-heading-row">
        <span class="import-limit">支持 .xls/.xlsx，最多 5 MB，最多 1000 条</span>
        <el-button link type="primary" :disabled="importing" @click="downloadImportTemplate">
          <el-icon><Download /></el-icon>
          下载导入模板
        </el-button>
      </div>
      <el-upload
        v-model:file-list="importFileList"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".xls,.xlsx"
        :disabled="importing"
        :on-change="onImportFileChange"
        :on-remove="onImportFileRemove"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖放 Excel 文件到此处，或 <em>点击选择</em></div>
      </el-upload>
      <el-progress
        v-if="importing || importProgress > 0"
        class="import-progress"
        :percentage="importProgress"
        :status="importProgress === 100 ? 'success' : undefined"
      />
      <template v-if="importResult">
        <div class="import-summary">
          <div class="import-summary-item is-success"><strong>{{ importResult.imported_count }}</strong><span>成功</span></div>
          <div class="import-summary-item is-duplicate"><strong>{{ importResult.duplicate_count }}</strong><span>重复</span></div>
          <div class="import-summary-item is-failed"><strong>{{ importResult.failed_count }}</strong><span>失败</span></div>
          <div class="import-summary-item is-warning"><strong>{{ importResult.warning_count }}</strong><span>警告</span></div>
        </div>
        <el-table :data="importResult.details" size="small" max-height="260" class="import-details">
          <el-table-column prop="row" label="行号" width="70" />
          <el-table-column label="结果" width="82">
            <template #default="{ row }">
              <el-tag :type="importStatusType(row.status)" size="small" effect="plain">
                {{ importStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="260" show-overflow-tooltip />
        </el-table>
      </template>
      <template #footer>
        <el-button :disabled="importing" @click="importVisible = false">
          {{ importResult ? '完成' : '取消' }}
        </el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="submitImport">
          开始导入
        </el-button>
      </template>
    </component>

    <component
      :is="createSurface"
      v-model="createVisible"
      title="新建线索"
      v-bind="createSurfaceProps"
      destroy-on-close
      :class="isApp ? undefined : 'lead-create-dialog'"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="学生/家长姓名" prop="student_or_parent_name">
          <el-input v-model="form.student_or_parent_name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="电话" prop="phone">
          <el-input
            v-model="form.phone"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="11"
            placeholder="请输入1位手机号"
            @input="form.phone = sanitizePhoneInput(form.phone)"
          />
        </el-form-item>
        <el-form-item label="来源" prop="source">
          <el-select v-model="form.source" style="width: 100%">
            <el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="介绍人">
          <el-input v-model="form.referrer_name" placeholder="老带新可填" />
        </el-form-item>
        <el-form-item label="需求">
          <el-input v-model="form.need" type="textarea" :rows="2" placeholder="如：一对一、英语口语" />
        </el-form-item>
        <el-form-item label="下次跟进时间">
          <el-date-picker
            v-model="form.next_follow_at"
            type="datetime"
            placeholder="选择日期时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">保存</el-button>
      </template>
    </component>
  </div>
</template>

<style scoped>
.lead-page {
  min-width: 0;
}

.lead-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.import-btn {
  height: 36px;
}

.import-heading-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.import-limit {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.import-progress {
  margin-top: 14px;
}

.import-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.import-summary-item {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
  min-height: 54px;
  padding: 10px 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fafafa;
}

.import-summary-item strong {
  font-size: 22px;
  line-height: 1;
}

.import-summary-item span {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.import-summary-item.is-success strong { color: #2f855a; }
.import-summary-item.is-duplicate strong { color: #64748b; }
.import-summary-item.is-failed strong { color: #c2413b; }
.import-summary-item.is-warning strong { color: #b7791f; }

.import-details {
  margin-top: 12px;
}

/* Element Plus 的全局移动端规则将 body 设为 flex-basis: 0；导入区需要按内容撑开，结果表再独立滚动。*/
:global(.lead-import-dialog.el-dialog) {
  overflow: hidden;
}

:global(.lead-import-dialog .el-dialog__body) {
  flex: 0 1 auto;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

/* App 模式覆盖手机不Pad；桌面宽度才切换为PC 表格 */
.lead-pc {
  display: none;
}

.lead-m {
  display: block;
}

@media (min-width: 1200px) {
  .lead-pc {
    display: block;
  }

  .lead-m {
    display: none !important;
  }
}

.lead-toolbar.is-compact {
  gap: 10px;
}

.create-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.filters {
  margin-top: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  border-radius: 12px;
}

/* 与学生信息PC 筛选卡一致*/
.pc-filters {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
}

.pc-filters :deep(.el-card__body) {
  padding: 14px 16px 8px;
}

.pc-filters-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  margin-bottom: 10px;
}

.pc-filters-head-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pc-filters-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.pc-filters-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(161, 98, 7, 0.1);
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.pc-list-summary {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.9);
  border: 1px solid var(--oc-border, #e8e0d0);
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.pc-list-summary__label {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.pc-list-summary strong {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
}

.pc-filter-form :deep(.el-form-item) {
  margin-bottom: 10px;
  margin-right: 14px;
}

.pc-filter-form :deep(.el-form-item__label) {
  color: var(--oc-muted, #78716c);
  font-weight: 500;
}

.tb-btn--primary {
  height: 36px;
  border-radius: 9px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.22);
}

/* ── wap 筛选── */
.m-filter {
  position: relative;
  z-index: 20;
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  overflow: visible;
}

.m-filter-search {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 4px 0 12px;
  background: #f5f0e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
}

.m-filter-search__icon {
  color: #a8a29e;
  font-size: 16px;
  flex-shrink: 0;
}

.m-filter-search__input {
  flex: 1;
  min-width: 0;
  height: 100%;
  margin: 0 8px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
  appearance: none;
}

.m-filter-search__input::-webkit-search-cancel-button {
  -webkit-appearance: none;
}

.m-filter-search__input::placeholder {
  color: #a8a29e;
}

.m-filter-search__btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.m-filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  overflow: visible;
}

.m-filter-select {
  flex: 1 1 0;
  min-width: 0;
}

.m-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 8px;
  background: #faf6ef !important;
  box-shadow: 0 0 0 1px var(--oc-border, #e8e0d0) inset !important;
}

.m-filter-more {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fffdf8;
  color: var(--oc-ink, #44403c);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.m-filter-more.is-active {
  border-color: #d4b483;
  color: var(--oc-primary, #a16207);
  background: #faf3e6;
}

.m-filter-more .el-icon {
  transition: transform 0.15s ease;
}

.m-filter-more .el-icon.is-open {
  transform: rotate(180deg);
}

.m-filter-panel {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
}

.m-filter-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  align-items: center;
}

.m-filter-link {
  border: none;
  background: none;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  cursor: pointer;
}

.m-filter-apply {
  height: 30px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

:global(.lead-m-select-popper.el-popper) {
  z-index: 5000 !important;
}

/* ── 移动卡片 ── */
.lead-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
  padding-bottom: 8px;
}

@media (min-width: 768px) and (max-width: 1199px) {
  .lead-card-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  .lead-card--empty,
  .infinite-sentinel {
    grid-column: 1 / -1;
  }
}

.lead-card {
  background: var(--oc-card, #fffdf8);
  border: 2px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  padding: 14px;
  transition: border-color 0.15s ease;
}

.lead-card.is-today {
  border-color: #f0b4b4;
  background: linear-gradient(180deg, #fff8f8 0%, #fffdf8 40%);
}

.lead-card--empty {
  margin-top: 4px;
}

.lead-card--empty .el-button {
  margin-top: 10px;
}

.lead-card__chips {
  margin-top: 10px;
}

.lead-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
}

.lead-card__avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.18);
}

.lead-card__who {
  flex: 1;
  min-width: 0;
}

.lead-card__name {
  font-size: 16px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lead-card__sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lead-card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.lead-card__body {
  margin-top: 12px;
  padding: 10px 12px;
  background: #f7f2e9;
  border-radius: 10px;
}

.lead-card__need,
.lead-card__notes {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-ink, #44403c);
}

.lead-card__notes {
  margin-top: 4px;
  color: var(--oc-muted, #78716c);
}

.lead-card__need .k,
.lead-card__notes .k {
  color: #a8a29e;
  margin-right: 6px;
}

.lead-card__meta {
  display: grid;
  grid-template-columns: 1fr;
  gap: 6px;
  margin-top: 10px;
}

.lead-meta-item {
  display: flex;
  gap: 8px;
  font-size: 12px;
  line-height: 1.45;
  min-width: 0;
}

.lead-meta-k {
  flex-shrink: 0;
  color: #a8a29e;
  min-width: 3.5em;
}

.lead-meta-v {
  min-width: 0;
  color: var(--oc-ink, #44403c);
  word-break: break-word;
}

.lead-card__controls {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.lead-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.ctrl-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.ctrl-select {
  width: 100%;
}

/* ── PC 表格（对齐学生列表） ── */
.pc-table-card {
  margin-top: 14px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  overflow: hidden;
  min-height: 160px;
}

.pc-table-card :deep(.el-card__body) {
  padding: 0;
}

.pc-lead-table {
  --el-table-border-color: var(--oc-border, #e8e0d0);
  --el-table-row-hover-bg-color: #faf6ee;
}

.pc-lead-table :deep(.el-table__header th) {
  border-bottom-color: var(--oc-border, #e8e0d0);
}

.pc-lead-table :deep(.el-table__row td) {
  padding: 12px 0;
}

.pc-lead-table :deep(.col-status .cell),
.pc-lead-table :deep(.col-follow .cell) {
  overflow: visible;
}

.pc-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.pc-name-cell:hover .pc-name-text {
  color: var(--oc-primary, #a16207);
}

.pc-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.pc-name-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  color: var(--oc-ink, #44403c);
  transition: color 0.15s ease;
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  color: var(--oc-ink, #44403c);
}

.pc-owner {
  color: var(--oc-ink, #44403c);
  font-weight: 500;
}

.pc-collab {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.pc-notes {
  color: var(--oc-muted, #78716c);
}

.pc-notes.is-empty {
  color: #a8a29e;
}

/* 状态列：给足宽度，去掉被挤出的「.」。*/
.status-native {
  width: 120px;
  max-width: 100%;
  height: 28px;
  padding: 0 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 6px;
  background: #fffdf8;
  color: var(--oc-ink, #44403c);
  font: inherit;
  cursor: pointer;
}

.status-native:focus-visible {
  border-color: var(--oc-primary, #a16207);
  outline: 2px solid rgba(161, 98, 7, 0.15);
  outline-offset: 1px;
}

.follow-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  min-width: 0;
}

.follow-readonly {
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
}

.follow-readonly.is-empty {
  color: #a8a29e;
}

.follow-today-tag {
  flex-shrink: 0;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */

@media (max-width: 1199px) {
  .lead-toolbar {
    flex-wrap: wrap;
    gap: 10px;
  }

  .lead-toolbar-actions {
    width: auto;
  }

  .create-btn,
  .import-btn {
    flex: 1 1 0;
    height: 40px;
    border-radius: 10px;
    font-weight: 600;
  }

  .import-heading-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .import-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

</style>
