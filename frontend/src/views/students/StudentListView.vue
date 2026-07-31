<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  bulkDeleteStudentsApi,
  createStudentApi,
  deleteStudentApi,
  listManagersApi,
  listStudentsApi,
  patchStudentApi,
  reassignStudentsApi,
  type ManagerOption,
  type Student,
  type StudentStatus,
} from '../../api/students'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'

const LIST_STATE_KEY = 'oc-student-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const rows = ref<Student[]>([])
const managers = ref<ManagerOption[]>([])
const selectedIds = ref<number[]>([])
const page = ref(1)
const pageSize = ref(20)
const tableRef = ref<{ clearSelection?: () => void } | null>(null)

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  ensureVisible,
} = useInfiniteScroll(rows, { chunk: SCROLL_CHUNK, enabled: isCompact, sentinelRef })

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('students', {
  visibleCount,
  enabled: isCompact,
})

const filters = reactive({
  grade: '',
  name: '',
  phone: '',
  school: '',
  status: 'active',
  academic_manager_id: undefined as number | undefined,
})

/** wap/pad：筛选默认收起，避免占满首屏 */
const filterExpanded = ref(false)

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.grade) n += 1
  if (filters.status && filters.status !== 'active') n += 1
  if (filters.academic_manager_id != null) n += 1
  if (filters.name.trim()) n += 1
  if (filters.phone.trim()) n += 1
  if (filters.school.trim()) n += 1
  return n
})

const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const saving = ref(false)
const form = reactive({
  name: '',
  grade: '',
  school: '',
  phone: '',
  parent_name: '',
  academic_manager_id: undefined as number | undefined,
  status: 'active' as StudentStatus,
  notes: '',
})

const reassignVisible = ref(false)
const reassignSaving = ref(false)
const reassign = reactive({
  from_manager_id: undefined as number | undefined,
  to_manager_id: undefined as number | undefined,
  student_ids: [] as number[],
})

const statusLabels: Record<string, string> = {
  active: '在读',
  paused: '暂停',
  graduated: '结业',
  quit: '退学',
}

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

const rules: FormRules = {
  name: [{ required: true, message: '请填写学生姓名', trigger: 'blur' }],
  grade: [{ required: true, message: '请填写年级', trigger: 'change' }],
  school: [{ required: true, message: '请填写学校', trigger: 'blur' }],
  academic_manager_id: [{ required: true, message: '请选择学管师', trigger: 'change' }],
}

const canReassign = computed(() => auth.isAdmin)
const canDelete = computed(() => auth.isAdmin)
const reassignStudentQuery = ref('')

const activeManagers = computed(() => managers.value.filter((m) => m.is_active))
const allManagers = computed(() => managers.value)

const studentsForReassign = computed(() => {
  let list = rows.value
  if (reassign.from_manager_id) {
    list = list.filter((s) => s.academic_manager_id === reassign.from_manager_id)
  }
  const q = reassignStudentQuery.value.trim().toLowerCase()
  if (!q) return list
  return list.filter((s) => {
    const hay = `${s.name} ${s.grade} ${s.school} ${s.phone || ''} ${s.parent_name || ''}`.toLowerCase()
    return hay.includes(q)
  })
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
      filters.grade = s.filters.grade ?? ''
      filters.name = s.filters.name ?? ''
      filters.phone = s.filters.phone ?? ''
      filters.school = s.filters.school ?? ''
      filters.status = s.filters.status ?? 'active'
      filters.academic_manager_id = s.filters.academic_manager_id
    }
    if (typeof s.page === 'number' && s.page > 0) page.value = s.page
    if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
      pageSize.value = s.pageSize
    }
  } catch {
    /* ignore corrupt state */
  }
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
    /* quota / private mode */
  }
}

const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

function clampPage() {
  if (page.value > totalPages.value) page.value = totalPages.value
  if (page.value < 1) page.value = 1
}

function goFirstPage() {
  page.value = 1
  saveListState()
}

function goLastPage() {
  page.value = totalPages.value
  saveListState()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
}

function onPageChange() {
  saveListState()
}

async function loadManagers() {
  managers.value = await listManagersApi(true)
}

async function load(opts?: { resetPage?: boolean }) {
  const snap = opts?.resetPage ? null : takeSnapshotForLoad(route.path)
  if (opts?.resetPage) {
    clearSnapshot()
    page.value = 1
    resetInfinite()
  }
  loading.value = true
  try {
    const params: Record<string, string | number> = {}
    if (filters.grade) params.grade = filters.grade
    if (filters.name) params.name = filters.name
    if (filters.phone) params.phone = filters.phone
    if (filters.school) params.school = filters.school
    if (filters.status) params.status = filters.status
    if (filters.academic_manager_id != null) {
      params.academic_manager_id = filters.academic_manager_id
    }
    rows.value = await listStudentsApi(params)
    if (opts?.resetPage) {
      resetInfinite()
    } else if (snap?.visibleCount != null && isCompact.value) {
      ensureVisible(snap.visibleCount)
    } else if (isCompact.value) {
      resetInfinite()
    }
    clampPage()
    saveListState()
  } finally {
    loading.value = false
  }
  void finishListEnter({ snap, forceTop: !!opts?.resetPage })
}

watch(pageSize, () => {
  clampPage()
})

function resetForm() {
  form.name = ''
  form.grade = ''
  form.school = ''
  form.phone = ''
  form.parent_name = ''
  form.academic_manager_id = undefined
  form.status = 'active'
  form.notes = ''
  editingId.value = null
}

function openCreate() {
  formMode.value = 'create'
  resetForm()
  formVisible.value = true
}

function openEdit(row: Student) {
  formMode.value = 'edit'
  editingId.value = row.id
  form.name = row.name
  form.grade = row.grade
  form.school = row.school
  form.phone = row.phone || ''
  form.parent_name = row.parent_name || ''
  form.academic_manager_id = row.academic_manager_id ?? undefined
  form.status = (row.status as StudentStatus) || 'active'
  form.notes = row.notes || ''
  formVisible.value = true
}

async function submitForm() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload = {
      name: form.name,
      grade: form.grade,
      school: form.school,
      phone: form.phone || null,
      parent_name: form.parent_name || null,
      academic_manager_id: form.academic_manager_id ?? null,
      status: form.status,
      notes: form.notes,
    }
    if (formMode.value === 'create') {
      await createStudentApi(payload)
      ElMessage.success('学生已创建')
    } else if (editingId.value != null) {
      await patchStudentApi(editingId.value, payload)
      ElMessage.success('学生已更新')
    }
    formVisible.value = false
    await load()
    await loadManagers()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

async function onDelete(row: Student) {
  try {
    await ElMessageBox.confirm(`确定删除学生「${row.name}」？学情记录将一并删除。`, '删除确认', {
      type: 'warning',
    })
    await deleteStudentApi(row.id)
    ElMessage.success('已删除')
    selectedIds.value = selectedIds.value.filter((id) => id !== row.id)
    await load()
    await loadManagers()
  } catch {
    /* cancel or error */
  }
}

async function onBulkDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要删除的学生')
    return
  }
  const names = rows.value
    .filter((s) => selectedIds.value.includes(s.id))
    .map((s) => s.name)
  const preview =
    names.length <= 5 ? names.join('、') : `${names.slice(0, 5).join('、')} 等 ${names.length} 人`
  try {
    await ElMessageBox.confirm(
      `确定批量删除 ${selectedIds.value.length} 名学生（${preview}）？学情记录将一并删除，且不可恢复。`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    const result = await bulkDeleteStudentsApi(selectedIds.value)
    ElMessage.success(`已删除 ${result.deleted_count} 名学生`)
    selectedIds.value = []
    await load()
    await loadManagers()
  } catch {
    /* cancel or error */
  }
}

function openReassign(preselect?: number[]) {
  reassign.from_manager_id = undefined
  reassign.to_manager_id = undefined
  reassign.student_ids = preselect?.length ? [...preselect] : [...selectedIds.value]
  reassignStudentQuery.value = ''
  reassignVisible.value = true
}

function onFromManagerChange() {
  // 切换原学管师时，默认勾选其名下当前列表中的学生
  if (reassign.from_manager_id) {
    reassign.student_ids = studentsForReassign.value.map((s) => s.id)
  }
}

async function submitReassign() {
  if (!reassign.to_manager_id) {
    ElMessage.warning('请选择目标学管师')
    return
  }
  if (!reassign.student_ids.length) {
    ElMessage.warning('请至少选择一名学生')
    return
  }
  reassignSaving.value = true
  try {
    const result = await reassignStudentsApi({
      student_ids: reassign.student_ids,
      to_manager_id: reassign.to_manager_id,
      from_manager_id: reassign.from_manager_id ?? null,
    })
    ElMessage.success(`已转交 ${result.updated_count} 名学生给「${result.to_manager_name}」`)
    reassignVisible.value = false
    selectedIds.value = []
    await load()
    await loadManagers()
  } catch {
    /* interceptor */
  } finally {
    reassignSaving.value = false
  }
}

function onSelectionChange(selection: Student[]) {
  selectedIds.value = selection.map((s) => s.id)
}

function toggleCardSelect(id: number, checked: boolean | string | number) {
  const on = checked === true || checked === 'true'
  if (on) {
    if (!selectedIds.value.includes(id)) selectedIds.value = [...selectedIds.value, id]
  } else {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }
}

function goDetail(row: Student) {
  router.push(`/students/${row.id}`)
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function statusTagType(status?: string): 'success' | 'warning' | 'info' | 'danger' {
  if (status === 'active') return 'success'
  if (status === 'paused') return 'warning'
  if (status === 'quit') return 'danger'
  return 'info'
}

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#78716c',
  fontWeight: '600',
  fontSize: '13px',
}

function clearSelection() {
  selectedIds.value = []
  tableRef.value?.clearSelection?.()
}

function managerLabel(m: ManagerOption) {
  return m.is_active ? m.display_name : `${m.display_name}（已停用）`
}

function managerOptionLabel(m: ManagerOption) {
  return `${m.display_name}${m.is_active ? '' : '（已停用）'} · ${m.student_count} 人`
}

function activeManagerLabel(m: ManagerOption) {
  return `${m.display_name}（${m.username}）`
}

function studentOptionLabel(s: Student) {
  return `${s.name} · ${s.grade} · ${s.school || '未填学校'}`
}

function resetFilters() {
  filters.grade = ''
  filters.name = ''
  filters.phone = ''
  filters.school = ''
  filters.status = 'active'
  filters.academic_manager_id = undefined
  load({ resetPage: true })
}

function runQuery() {
  if (isCompact.value) filterExpanded.value = false
  load({ resetPage: true })
}

function toggleFilterExpand() {
  filterExpanded.value = !filterExpanded.value
}

onMounted(async () => {
  restoreListState()
  await loadManagers()
  await load()
})
</script>

<template>
  <div class="student-list-page">
    <div class="page-toolbar student-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header content="学生信息" />
      <div class="toolbar-right">
        <el-button
          v-if="canDelete"
          class="tb-btn"
          type="danger"
          plain
          :disabled="!selectedIds.length"
          @click="onBulkDelete"
        >
          删除{{ selectedIds.length ? ` ${selectedIds.length}` : '' }}
        </el-button>
        <el-button v-if="canReassign" class="tb-btn" plain @click="openReassign()">
          转交{{ selectedIds.length ? ` ${selectedIds.length}` : '' }}
        </el-button>
        <el-button class="tb-btn tb-btn--primary" type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>
          新建
        </el-button>
      </div>
    </div>

    <!-- PC 筛选 + 列表摘要（档案说明放在这里，不挤在标题下） -->
    <el-card v-if="!isCompact" class="filters pc-filters" shadow="never">
      <div class="pc-filters-head">
        <div class="pc-filters-head-main">
          <span class="pc-filters-title">筛选条件</span>
          <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
        </div>
        <div class="pc-list-summary">
          <span class="pc-list-summary__label">在读学员档案</span>
          <span class="pc-list-summary__count">
            共 <strong>{{ rows.length }}</strong> 人
          </span>
          <span v-if="selectedIds.length" class="pc-list-summary__sel">
            已选 <strong>{{ selectedIds.length }}</strong>
          </span>
        </div>
      </div>
      <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
        <el-form-item label="年级">
          <el-select v-model="filters.grade" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
            <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="学管师">
          <el-select
            v-model="filters.academic_manager_id"
            clearable
            filterable
            placeholder="全部"
            style="width: 150px"
          >
            <el-option
              v-for="m in allManagers"
              :key="m.id"
              :label="managerLabel(m)"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="filters.name" clearable placeholder="搜索姓名" style="width: 130px" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="filters.phone" clearable placeholder="搜索电话" style="width: 140px" />
        </el-form-item>
        <el-form-item label="学校">
          <el-input v-model="filters.school" clearable placeholder="搜索学校" style="width: 150px" />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="runQuery">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- wap/pad 筛选 -->
    <div v-else class="m-filter">
      <div class="m-filter-search">
        <el-icon class="m-filter-search__icon"><Search /></el-icon>
        <input
          v-model="filters.name"
          class="m-filter-search__input"
          type="search"
          enterkeyhint="search"
          placeholder="搜索学生姓名"
          @keyup.enter="runQuery"
        />
        <button type="button" class="m-filter-search__btn" @click="runQuery">查询</button>
      </div>
      <div class="m-filter-row">
        <el-select
          v-model="filters.status"
          class="m-filter-select"
          clearable
          placeholder="状态"
          teleported
          placement="bottom-start"
          :fit-input-width="true"
          :popper-options="{ strategy: 'fixed' }"
          popper-class="student-m-select-popper"
        >
          <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select
          v-model="filters.grade"
          class="m-filter-select"
          clearable
          placeholder="年级"
          teleported
          placement="bottom-start"
          :fit-input-width="true"
          :popper-options="{ strategy: 'fixed' }"
          popper-class="student-m-select-popper"
        >
          <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
        </el-select>
        <button
          type="button"
          class="m-filter-more"
          :class="{ 'is-active': filterExpanded || activeFilterCount > 0 }"
          @click="toggleFilterExpand"
        >
          更多{{ activeFilterCount ? ` · ${activeFilterCount}` : '' }}
          <el-icon :class="{ 'is-open': filterExpanded }"><ArrowDown /></el-icon>
        </button>
      </div>
      <div v-show="filterExpanded" class="m-filter-panel">
        <el-select
          v-model="filters.academic_manager_id"
          class="m-filter-panel__full"
          clearable
          placeholder="学管师"
          teleported
          placement="bottom-start"
          :fit-input-width="true"
          :popper-options="{ strategy: 'fixed' }"
          popper-class="student-m-select-popper"
        >
          <el-option
            v-for="m in allManagers"
            :key="m.id"
            :label="managerLabel(m)"
            :value="m.id"
          />
        </el-select>
        <el-input v-model="filters.phone" class="m-filter-panel__half" clearable placeholder="电话" />
        <el-input v-model="filters.school" class="m-filter-panel__half" clearable placeholder="学校" />
        <div class="m-filter-panel__actions">
          <button type="button" class="m-filter-link" @click="resetFilters">重置</button>
          <button type="button" class="m-filter-apply" @click="runQuery">完成</button>
        </div>
      </div>
    </div>

    <!-- 平板 / 手机：学生卡片 -->
    <div v-if="isCompact" v-loading="loading" class="stu-card-list">
      <div v-if="!rows.length && !loading" class="stu-card stu-card--empty">暂无学生，可点「新建」</div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="stu-card"
        :class="{ 'is-selected': selectedIds.includes(row.id) }"
      >
        <div class="stu-card__top">
          <el-checkbox
            v-if="canDelete || canReassign"
            class="stu-card__check"
            :model-value="selectedIds.includes(row.id)"
            @change="(v: boolean | string | number) => toggleCardSelect(row.id, v)"
            @click.stop
          />
          <div class="stu-card__identity" @click="goDetail(row)">
            <div class="stu-card__avatar">{{ (row.name || '?').slice(0, 1) }}</div>
            <div class="stu-card__who">
              <div class="stu-card__name">{{ row.name }}</div>
              <div class="stu-card__sub">
                {{ row.grade || '未填年级' }}
                <span v-if="row.school"> · {{ row.school }}</span>
              </div>
            </div>
          </div>
          <el-tag
            size="small"
            effect="plain"
            round
            :type="row.status === 'active' ? 'success' : row.status === 'quit' ? 'danger' : 'info'"
          >
            {{ statusLabels[row.status] || row.status }}
          </el-tag>
        </div>

        <div class="stu-card__meta">
          <div class="stu-meta-item">
            <span class="stu-meta-k">学管</span>
            <span class="stu-meta-v">{{ row.academic_manager_name || '—' }}</span>
          </div>
          <div v-if="row.phone" class="stu-meta-item">
            <span class="stu-meta-k">电话</span>
            <span class="stu-meta-v">{{ row.phone }}</span>
          </div>
          <div v-if="row.parent_name" class="stu-meta-item">
            <span class="stu-meta-k">家长</span>
            <span class="stu-meta-v">{{ row.parent_name }}</span>
          </div>
          <div v-if="row.latest_learning_at" class="stu-meta-item stu-meta-item--full">
            <span class="stu-meta-k">学情</span>
            <span class="stu-meta-v">{{ formatTime(row.latest_learning_at) }}</span>
          </div>
        </div>

        <p v-if="row.notes" class="stu-card__notes">{{ row.notes }}</p>

        <div class="stu-card__actions">
          <el-button type="primary" size="small" @click="goDetail(row)">详情</el-button>
          <el-button size="small" plain @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canReassign" size="small" plain @click="openReassign([row.id])">转交</el-button>
          <el-button v-if="canDelete" size="small" type="danger" plain @click="onDelete(row)">
            删除
          </el-button>
        </div>
      </div>
      <div v-if="rows.length" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ rows.length }} 条</span>
      </div>
    </div>

    <!-- 桌面：表格 -->
    <el-card v-else v-loading="loading" class="pc-table-card" shadow="never">
      <div v-if="selectedIds.length" class="pc-selection-bar">
        <span>
          已选择
          <strong>{{ selectedIds.length }}</strong>
          名学生
        </span>
        <div class="pc-selection-actions">
          <el-button v-if="canReassign" size="small" type="primary" plain @click="openReassign()">
            批量转交
          </el-button>
          <el-button v-if="canDelete" size="small" type="danger" plain @click="onBulkDelete">
            批量删除
          </el-button>
          <el-button size="small" text @click="clearSelection">取消选择</el-button>
        </div>
      </div>
      <div class="table-scroll">
        <el-table
          ref="tableRef"
          class="pc-student-table"
          :data="pagedRows"
          stripe
          style="width: 100%"
          row-key="id"
          :header-cell-style="pcHeaderStyle"
          @selection-change="onSelectionChange"
        >
          <el-table-column v-if="canDelete || canReassign" type="selection" width="48" />
          <el-table-column label="姓名" min-width="130">
            <template #default="{ row }">
              <button type="button" class="pc-name-cell" @click="goDetail(row)">
                <span class="pc-avatar">{{ (row.name || '?').slice(0, 1) }}</span>
                <span class="pc-name-text">{{ row.name }}</span>
              </button>
            </template>
          </el-table-column>
          <el-table-column prop="grade" label="年级" width="88">
            <template #default="{ row }">
              <span class="pc-muted">{{ row.grade || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="school" label="学校" min-width="120" show-overflow-tooltip />
          <el-table-column prop="phone" label="电话" width="124">
            <template #default="{ row }">
              <span class="pc-mono">{{ row.phone || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="parent_name" label="家长" width="90">
            <template #default="{ row }">
              <span class="pc-muted">{{ row.parent_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="学管师" min-width="110">
            <template #default="{ row }">
              <span class="pc-manager">{{ row.academic_manager_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="92" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                round
                :type="statusTagType(row.status)"
              >
                {{ statusLabels[row.status] || row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="pc-notes">{{ row.notes || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="最近学情" min-width="148">
            <template #default="{ row }">
              <span
                class="pc-learning"
                :class="{ 'is-empty': !row.latest_learning_at }"
              >
                {{ formatTime(row.latest_learning_at) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="210" fixed="right" align="right">
            <template #default="{ row }">
              <div class="pc-ops">
                <el-button link type="primary" @click="goDetail(row)">详情</el-button>
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button v-if="canReassign" link type="primary" @click="openReassign([row.id])">
                  转交
                </el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-if="!rows.length && !loading" class="pc-table-empty">暂无学生，可点右上角「新建」</div>
    </el-card>

    <!-- 仅 PC 显示底部分页；wap/pad 用滚动加载 -->
    <div v-if="!isCompact && rows.length" class="pager-bar pc-pager">
      <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZES"
        :total="rows.length"
        :pager-count="5"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
      <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
    </div>

    <!-- 新建 / 编辑 -->
    <el-dialog
      v-model="formVisible"
      :title="formMode === 'create' ? '新建学生' : '编辑学生'"
      width="90%"
      style="max-width: 560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="学生姓名" prop="name">
          <el-input v-model="form.name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-select v-model="form.grade" filterable allow-create style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="学校" prop="school">
          <el-input v-model="form.school" placeholder="就读学校" />
        </el-form-item>
        <el-form-item label="学管师（班主任）" prop="academic_manager_id">
          <el-select
            v-model="form.academic_manager_id"
            placeholder="选择老师账号"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="m in activeManagers"
              :key="m.id"
              :label="activeManagerLabel(m)"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" placeholder="多为家长手机" />
        </el-form-item>
        <el-form-item label="家长称呼">
          <el-input v-model="form.parent_name" placeholder="如：张妈妈" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- 批量转交 -->
    <el-dialog
      v-model="reassignVisible"
      title="批量转交学管师"
      width="90%"
      style="max-width: 640px"
      destroy-on-close
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="适用于学管师离职或调班：先选原学管师（可选），再勾选学生，最后指定新学管师。"
        style="margin-bottom: 16px"
      />
      <el-form label-position="top">
        <el-form-item label="原学管师（可选，用于筛选其名下学生）">
          <el-select
            v-model="reassign.from_manager_id"
            clearable
            placeholder="不限 / 选择离职或调出老师"
            style="width: 100%"
            @change="onFromManagerChange"
          >
            <el-option
              v-for="m in allManagers"
              :key="m.id"
              :label="managerOptionLabel(m)"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="选择学生">
          <el-input
            v-model="reassignStudentQuery"
            clearable
            placeholder="搜索姓名 / 年级 / 学校 / 电话"
            style="margin-bottom: 8px"
          />
          <el-select
            v-model="reassign.student_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="手动勾选要转交的学生"
            style="width: 100%"
          >
            <el-option
              v-for="s in studentsForReassign"
              :key="s.id"
              :label="studentOptionLabel(s)"
              :value="s.id"
            />
          </el-select>
          <div class="hint">当前可选 {{ studentsForReassign.length }} 人（受列表筛选影响时可先「查询」放宽条件）</div>
        </el-form-item>
        <el-form-item label="目标学管师（在职老师）" required>
          <el-select
            v-model="reassign.to_manager_id"
            placeholder="转交给谁"
            style="width: 100%"
            filterable
          >
            <el-option
              v-for="m in activeManagers"
              :key="m.id"
              :label="activeManagerLabel(m)"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" :loading="reassignSaving" @click="submitReassign">确认转交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.student-list-page {
  width: 100%;
}

.filters {
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
}

/* ── PC 顶栏 ── */
.student-toolbar.is-compact {
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}

.toolbar-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* ── PC 筛选 ── */
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

/* 列表摘要：放在筛选卡片右上，不占标题下方 */
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

.pc-list-summary__sel strong {
  color: var(--oc-primary, #a16207);
}

.pc-filter-form :deep(.el-form-item) {
  margin-bottom: 10px;
  margin-right: 14px;
}

.pc-filter-form :deep(.el-form-item__label) {
  color: var(--oc-muted, #78716c);
  font-weight: 500;
}

/* ── PC 表格卡片 ── */
.pc-table-card {
  margin-top: 14px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  overflow: hidden;
}

.pc-table-card :deep(.el-card__body) {
  padding: 0;
}

.pc-selection-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 16px;
  background: linear-gradient(90deg, #faf3e6, #f5f0e6);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  font-size: 13px;
  color: var(--oc-ink, #44403c);
}

.pc-selection-bar strong {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  margin: 0 2px;
}

.pc-selection-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pc-student-table {
  --el-table-border-color: var(--oc-border, #e8e0d0);
  --el-table-row-hover-bg-color: #faf6ee;
}

.pc-student-table :deep(.el-table__header th) {
  border-bottom-color: var(--oc-border, #e8e0d0);
}

.pc-student-table :deep(.el-table__row td) {
  padding: 12px 0;
}

.pc-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  max-width: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
  color: inherit;
}

.pc-name-cell:hover .pc-name-text {
  color: var(--oc-primary, #a16207);
}

.pc-avatar {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.18);
}

.pc-name-text {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.15s;
}

.pc-muted {
  color: var(--oc-muted, #78716c);
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  color: var(--oc-ink, #44403c);
}

.pc-manager {
  font-weight: 500;
  color: var(--oc-ink, #44403c);
}

.pc-notes {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.pc-learning {
  font-size: 12px;
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
}

.pc-learning.is-empty {
  color: #a8a29e;
}

.pc-ops {
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  padding-right: 8px;
}

.pc-table-empty {
  padding: 48px 16px;
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 14px;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */

.student-toolbar.is-compact .toolbar-right {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.student-toolbar.is-compact .tb-btn--primary {
  grid-column: 1 / -1;
}

.tb-btn {
  height: 36px;
  margin: 0 !important;
  border-radius: 9px;
  font-weight: 500;
}

.student-toolbar.is-compact .tb-btn {
  width: 100%;
}

.tb-btn--primary :deep(span) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

/* ── wap/pad 筛选壳（勿 overflow:hidden，否则下拉可能被裁） ── */
.m-filter {
  position: relative;
  z-index: 20;
  margin-top: 4px;
  margin-bottom: 8px;
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
  flex-shrink: 0;
  color: #a8a29e;
  font-size: 16px;
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
  /* 去掉 type=search 的默认清除按钮占位异常 */
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
  margin: 0;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.m-filter-search__btn:active {
  background: var(--oc-primary-hover, #86530a);
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

/* 下拉挂 body + fixed，避免被 main overflow 裁切/错位 */
:global(.student-m-select-popper.el-popper) {
  z-index: 5000 !important;
}

:global(.student-m-select-popper .el-select-dropdown__item) {
  padding: 0 14px;
  height: 36px;
  line-height: 36px;
  font-size: 14px;
}

:global(.student-m-select-popper .el-select-dropdown__item.is-selected) {
  color: var(--oc-primary, #a16207);
  font-weight: 600;
  background: #faf3e6;
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
  font-size: 12px;
  transition: transform 0.15s ease;
}

.m-filter-more .el-icon.is-open {
  transform: rotate(180deg);
}

.m-filter-panel {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
  overflow: visible;
}

.m-filter-panel__full {
  grid-column: 1 / -1;
  width: 100%;
}

.m-filter-panel__half {
  width: 100%;
  min-width: 0;
}

.m-filter-panel__actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  padding-top: 2px;
}

.m-filter-link {
  border: none;
  background: none;
  padding: 0;
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

.hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

/* ── wap/pad 学生卡片 ── */
.stu-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
  padding-bottom: 8px;
}

.stu-card {
  background: var(--oc-card, #fffdf8);
  border: 2px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  padding: 14px;
  box-shadow: none;
  transition: border-color 0.15s ease;
}

.stu-card.is-selected {
  border-color: var(--oc-primary, #a16207);
  background: #fffcf6;
}

.stu-card--empty {
  text-align: center;
  color: var(--oc-muted, #78716c);
  padding: 36px 16px;
  border-style: dashed;
  box-shadow: none;
}

.stu-card__top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stu-card__check {
  flex-shrink: 0;
  height: 20px;
  margin: 0;
}

.stu-card__check :deep(.el-checkbox__label) {
  display: none;
}

.stu-card__check :deep(.el-checkbox__inner) {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(120, 113, 108, 0.85);
  background-color: transparent !important;
  background-image: none !important;
  box-shadow: none;
}

.stu-card__check :deep(.el-checkbox__input.is-checked .el-checkbox__inner),
.stu-card__check :deep(.el-checkbox__input.is-indeterminate .el-checkbox__inner) {
  background-color: var(--oc-primary, #a16207) !important;
  border-color: var(--oc-primary, #a16207);
}

.stu-card__check :deep(.el-checkbox__inner::after) {
  box-sizing: content-box;
  content: '';
  border: 2px solid #fff;
  border-left: 0;
  border-top: 0;
  height: 8px;
  width: 4px;
  left: 6px;
  top: 2px;
  position: absolute;
  transform: rotate(45deg) scaleY(1);
  transform-origin: center;
}

.stu-card__check :deep(.el-checkbox__input.is-focus .el-checkbox__inner),
.stu-card__check :deep(.el-checkbox:focus-within .el-checkbox__inner) {
  box-shadow: none !important;
  outline: none;
}

.stu-card__identity {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.stu-card__avatar {
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
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.2);
}

.stu-card__who {
  min-width: 0;
  flex: 1;
}

.stu-card__name {
  font-size: 16px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stu-card__sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stu-card__meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 10px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #f7f2e9;
  border-radius: 10px;
}

.stu-meta-item {
  min-width: 0;
  display: flex;
  gap: 6px;
  font-size: 12px;
  line-height: 1.4;
}

.stu-meta-item--full {
  grid-column: 1 / -1;
}

.stu-meta-k {
  flex-shrink: 0;
  color: #a8a29e;
}

.stu-meta-v {
  min-width: 0;
  color: var(--oc-ink, #44403c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stu-card__notes {
  margin: 10px 0 0;
  padding: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--oc-muted, #78716c);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.stu-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.stu-card__actions .el-button {
  margin: 0;
  flex: 1 1 calc(50% - 4px);
  min-width: 0;
  height: 34px;
  border-radius: 8px;
  font-weight: 500;
}

.scroll-sentinel {
  padding: 16px 8px 28px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}
</style>
