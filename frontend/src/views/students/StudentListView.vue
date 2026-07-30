<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
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

const LIST_STATE_KEY = 'oc-student-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const router = useRouter()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const rows = ref<Student[]>([])
const managers = ref<ManagerOption[]>([])
const selectedIds = ref<number[]>([])
const page = ref(1)
const pageSize = ref(20)

const {
  sentinelRef,
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  resetVisible: resetInfinite,
} = useInfiniteScroll(rows, { chunk: SCROLL_CHUNK, enabled: isCompact })

const filters = reactive({
  grade: '',
  name: '',
  phone: '',
  school: '',
  status: 'active',
  academic_manager_id: undefined as number | undefined,
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
  if (opts?.resetPage) {
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
    if (opts?.resetPage || isCompact.value) resetInfinite()
    clampPage()
    saveListState()
  } finally {
    loading.value = false
  }
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
  load({ resetPage: true })
}

onMounted(async () => {
  restoreListState()
  await loadManagers()
  await load()
})
</script>

<template>
  <div class="student-list-page">
    <div class="page-toolbar">
      <el-page-header content="学生信息" />
      <el-space wrap class="toolbar-actions">
        <el-button
          v-if="canDelete"
          type="danger"
          plain
          :disabled="!selectedIds.length"
          @click="onBulkDelete"
        >
          批量删除{{ selectedIds.length ? `（${selectedIds.length}）` : '' }}
        </el-button>
        <el-button v-if="canReassign" @click="openReassign()">
          批量转交{{ selectedIds.length ? `（${selectedIds.length}）` : '' }}
        </el-button>
        <el-button type="primary" @click="openCreate">新建学生</el-button>
      </el-space>
    </div>

    <el-card class="filters" shadow="never">
      <el-form class="filter-form" :inline="true" @submit.prevent="runQuery">
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
            placeholder="全部"
            style="width: 140px"
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
          <el-input v-model="filters.name" clearable placeholder="搜索姓名" style="width: 120px" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="filters.phone" clearable placeholder="搜索电话" style="width: 130px" />
        </el-form-item>
        <el-form-item label="学校">
          <el-input v-model="filters.school" clearable placeholder="搜索学校" style="width: 140px" />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="runQuery">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 平板 / 手机：卡片 + 滚动加载（每 10 条） -->
    <div v-if="isCompact" v-loading="loading" class="m-card-list" style="margin-top: 12px">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无学生，可点「新建学生」</div>
      <div v-for="row in infiniteRows" :key="row.id" class="m-card">
        <div v-if="canDelete || canReassign" class="m-select-row">
          <el-checkbox
            :model-value="selectedIds.includes(row.id)"
            @change="(v: boolean | string | number) => toggleCardSelect(row.id, v)"
          />
          <span class="pick-hint">勾选后可批量删除 / 转交</span>
        </div>
        <div class="m-card-head">
          <div class="m-card-title" @click="goDetail(row)">{{ row.name }}</div>
          <el-tag size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
        </div>
        <div class="m-card-meta">
          <span><span class="k">年级</span> {{ row.grade || '—' }}</span>
          <span><span class="k">学校</span> {{ row.school || '—' }}</span>
          <span><span class="k">学管</span> {{ row.academic_manager_name || '—' }}</span>
          <span v-if="row.phone"><span class="k">电话</span> {{ row.phone }}</span>
          <span v-if="row.parent_name"><span class="k">家长</span> {{ row.parent_name }}</span>
          <span v-if="row.latest_learning_at">
            <span class="k">最近学情</span> {{ formatTime(row.latest_learning_at) }}
          </span>
        </div>
        <div v-if="row.notes" class="m-card-notes">{{ row.notes }}</div>
        <div class="m-card-actions">
          <el-button type="primary" size="small" @click="goDetail(row)">详情</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canReassign" size="small" @click="openReassign([row.id])">转交</el-button>
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
    <el-card v-else v-loading="loading" style="margin-top: 12px">
      <div class="table-scroll">
        <el-table :data="pagedRows" stripe style="width: 100%" @selection-change="onSelectionChange">
          <el-table-column v-if="canDelete || canReassign" type="selection" width="48" />
          <el-table-column prop="name" label="姓名" min-width="100" />
          <el-table-column prop="grade" label="年级" width="90" />
          <el-table-column prop="school" label="学校" min-width="120" show-overflow-tooltip />
          <el-table-column prop="phone" label="电话" width="120" />
          <el-table-column prop="parent_name" label="家长" width="90" />
          <el-table-column label="学管师" min-width="110">
            <template #default="{ row }">
              {{ row.academic_manager_name || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="140" show-overflow-tooltip />
          <el-table-column label="最近学情" min-width="150">
            <template #default="{ row }">{{ formatTime(row.latest_learning_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="goDetail(row)">详情</el-button>
              <el-button link @click="openEdit(row)">编辑</el-button>
              <el-button v-if="canReassign" link @click="openReassign([row.id])">转交</el-button>
              <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- 仅 PC 显示底部分页；wap/pad 用滚动加载 -->
    <div v-if="!isCompact && rows.length" class="pager-bar">
      <el-button size="small" :disabled="page <= 1" @click="goFirstPage">首页</el-button>
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
      <el-button size="small" :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
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
.filters {
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
}

.hint {
  margin-top: 6px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.pick-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.m-card-title {
  cursor: pointer;
}

.m-card-notes {
  margin-top: 6px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.m-card-actions .el-button {
  min-height: 32px;
}

.pager-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
  padding: 4px 0 8px;
}

.pager-bar :deep(.el-pagination) {
  flex-wrap: wrap;
  justify-content: flex-end;
  row-gap: 8px;
}

@media (max-width: 767px) {
  .pager-bar {
    justify-content: center;
  }
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
