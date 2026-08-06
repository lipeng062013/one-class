<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadUserFile,
} from 'element-plus'
import {
  createMaterialApi,
  deleteMaterialApi,
  listMaterialsApi,
  patchMaterialApi,
  uploadMaterialFileApi,
  type Material,
} from '../../api/materials'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useListScrollRestore } from '../../composables/useListScrollRestore'

const LIST_STATE_KEY = 'oc-material-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const loading = ref(false)
const loadingMore = ref(false)
/** PC：当前页；WAP/Pad：已加载累计 */
const rows = ref<Material[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterExpanded = ref(false)
const sentinelRef = ref<HTMLElement | null>(null)
/** 供从详情返回时恢复「已展开条数」 */
const visibleCount = computed(() => rows.value.length)
let scrollObserver: IntersectionObserver | null = null

const filters = reactive({
  status: '',
  q: '',
  grade: '',
  subject: '',
})

const uploadDialog = ref(false)
const uploadFormRef = ref<FormInstance>()
const saving = ref(false)
const fileList = ref<UploadUserFile[]>([])

const uploadForm = reactive({
  title: '',
  grade: '',
  subject: '',
  pain_point: '',
  teacher_action: '',
  next_step: '',
  auth_status: 'authorized',
})

const uploadRules: FormRules = {
  title: [{ required: true, message: '请填写场景标题', trigger: 'blur' }],
  auth_status: [{ required: true, message: '请选择授权状态', trigger: 'change' }],
}

const statusLabel: Record<string, string> = {
  new: '新建',
  usable: '可用',
  used: '已用',
  archived: '归档',
}
const authLabel: Record<string, string> = {
  pending: '待授权',
  authorized: '已授权',
  denied: '拒绝',
  anonymized: '已脱敏',
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  if (status === 'usable') return 'success'
  if (status === 'new') return 'primary'
  if (status === 'used') return 'warning'
  return 'info'
}

function authTagType(auth: string): 'success' | 'warning' | 'info' | 'danger' {
  if (auth === 'authorized') return 'success'
  if (auth === 'pending') return 'warning'
  if (auth === 'denied') return 'danger'
  return 'info'
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.status) n += 1
  if (filters.q.trim()) n += 1
  if (filters.grade.trim()) n += 1
  if (filters.subject.trim()) n += 1
  return n
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value) || 1))
/** PC 表格：服务端当前页 */
const pagedRows = computed(() => rows.value)
/** WAP/Pad 卡片：累计已加载 */
const infiniteRows = computed(() => rows.value)
const hasMoreInfinite = computed(() => rows.value.length < total.value)

const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()
const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('materials', {
  visibleCount,
  enabled: isCompact,
  stateStorageKey: LIST_STATE_KEY,
})

function listQuery(pageNum: number, size: number) {
  return {
    page: pageNum,
    page_size: size,
    status: filters.status || undefined,
    grade: filters.grade.trim() || undefined,
    subject: filters.subject.trim() || undefined,
    q: filters.q.trim() || undefined,
  }
}

function goFirstPage() {
  page.value = 1
  saveListState()
  void load()
}

function goLastPage() {
  page.value = totalPages.value
  saveListState()
  void load()
}

function onPageChange() {
  saveListState()
  void load()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
  void load()
}

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
      filters.status = s.filters.status ?? ''
      filters.q = s.filters.q ?? ''
      filters.grade = s.filters.grade ?? ''
      filters.subject = s.filters.subject ?? ''
    }
    if (typeof s.page === 'number' && s.page > 0) page.value = s.page
    if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
      pageSize.value = s.pageSize
    }
  } catch {
    /* ignore */
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
    /* ignore */
  }
}

function runQuery() {
  clearSnapshot()
  collapseAll()
  page.value = 1
  filterExpanded.value = false
  saveListState()
  void load({ fromQuery: true })
}

function resetFilters() {
  clearSnapshot()
  collapseAll()
  filters.status = ''
  filters.q = ''
  filters.grade = ''
  filters.subject = ''
  page.value = 1
  filterExpanded.value = false
  saveListState()
  void load({ fromQuery: true })
}

function toggleFilterExpand() {
  filterExpanded.value = !filterExpanded.value
}

function resetUploadForm() {
  uploadForm.title = ''
  uploadForm.grade = ''
  uploadForm.subject = ''
  uploadForm.pain_point = ''
  uploadForm.teacher_action = ''
  uploadForm.next_step = ''
  uploadForm.auth_status = 'authorized'
  fileList.value = []
}

async function openUpload() {
  resetUploadForm()
  uploadDialog.value = true
  await nextTick()
  uploadFormRef.value?.clearValidate()
}

async function load(opts?: { fromQuery?: boolean; append?: boolean }) {
  const append = !!opts?.append && isCompact.value
  const snap = opts?.fromQuery || append ? null : takeSnapshotForLoad(route.path)
  if (opts?.fromQuery) clearSnapshot()

  if (append) loadingMore.value = true
  else loading.value = true
  try {
    if (isCompact.value) {
      // 移动端：按 chunk 拉取；append 时 page 已 +1
      if (!append) page.value = 1
      const res = await listMaterialsApi(listQuery(page.value, SCROLL_CHUNK))
      rows.value = append ? [...rows.value, ...res.items] : res.items
      total.value = res.total
      // 从详情返回：补拉到快照条数
      if (!append && snap?.visibleCount != null) {
        const need = Math.max(SCROLL_CHUNK, snap.visibleCount)
        while (rows.value.length < need && rows.value.length < total.value) {
          page.value += 1
          const more = await listMaterialsApi(listQuery(page.value, SCROLL_CHUNK))
          rows.value = [...rows.value, ...more.items]
          total.value = more.total
          if (!more.items.length) break
        }
      }
    } else {
      const res = await listMaterialsApi(listQuery(page.value, pageSize.value))
      rows.value = res.items
      total.value = res.total
      if (page.value > 1 && res.items.length === 0 && res.total > 0) {
        page.value = Math.max(1, Math.ceil(res.total / pageSize.value))
        const again = await listMaterialsApi(listQuery(page.value, pageSize.value))
        rows.value = again.items
        total.value = again.total
      }
    }
    saveListState()
  } finally {
    loading.value = false
    loadingMore.value = false
  }
  if (!append) void finishListEnter({ snap, forceTop: !!opts?.fromQuery })
}

async function loadMore() {
  if (!isCompact.value || loadingMore.value || loading.value || !hasMoreInfinite.value) return
  page.value += 1
  await load({ append: true })
}

function setupScrollObserver() {
  teardownScrollObserver()
  if (!isCompact.value) return
  const el = sentinelRef.value
  if (!el) return
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) void loadMore()
    },
    { root: null, rootMargin: '160px 0px', threshold: 0 },
  )
  scrollObserver.observe(el)
}

function teardownScrollObserver() {
  scrollObserver?.disconnect()
  scrollObserver = null
}

async function submitUpload() {
  const ok = await uploadFormRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const material = await createMaterialApi({ ...uploadForm })
    for (const item of fileList.value) {
      const raw = item.raw
      if (raw) {
        await uploadMaterialFileApi(material.id, raw as File)
      }
    }
    ElMessage.success('素材已上传')
    uploadDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    saving.value = false
  }
}

async function markUsable(row: Material) {
  await patchMaterialApi(row.id, { status: 'usable', auth_status: 'authorized' })
  ElMessage.success('已标为可用')
  await load()
}

async function onDelete(row: Material) {
  try {
    await ElMessageBox.confirm(`确定删除素材「${row.title}」？`, '删除确认', { type: 'warning' })
    await deleteMaterialApi(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}

watch(isCompact, async (compact, wasCompact) => {
  if (compact === wasCompact) return
  page.value = 1
  await load({ fromQuery: true })
  await nextTick()
  setupScrollObserver()
})

watch(sentinelRef, () => {
  if (isCompact.value) setupScrollObserver()
})

onMounted(async () => {
  restoreListState()
  await load()
  await nextTick()
  setupScrollObserver()
})

onUnmounted(() => teardownScrollObserver())
</script>

<template>
  <div class="material-page">
    <div class="page-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header class="is-title-only" content="素材管理" />
      <el-button class="tb-btn tb-btn--primary" type="primary" @click="openUpload">
        <el-icon><Plus /></el-icon>
        上传素材
      </el-button>
    </div>

    <!-- PC 筛选 -->
    <div class="mat-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">教学素材</span>
            <span class="pc-list-summary__count">
              共 <strong>{{ total }}</strong> 条
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
              <el-option v-for="(label, key) in statusLabel" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input
              v-model="filters.q"
              clearable
              placeholder="标题 / 痛点"
              style="width: 160px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item label="年级">
            <el-input v-model="filters.grade" clearable placeholder="年级" style="width: 110px" />
          </el-form-item>
          <el-form-item label="科目">
            <el-input v-model="filters.subject" clearable placeholder="科目" style="width: 110px" />
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="runQuery">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <!-- wap 筛选 -->
    <div class="mat-m m-filter">
      <div class="m-filter-search">
        <el-icon class="m-filter-search__icon"><Search /></el-icon>
        <input
          v-model="filters.q"
          class="m-filter-search__input"
          type="search"
          enterkeyhint="search"
          placeholder="搜索标题"
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
          :popper-options="{ strategy: 'fixed' }"
          popper-class="mat-m-select-popper"
        >
          <el-option v-for="(label, key) in statusLabel" :key="key" :label="label" :value="key" />
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
        <el-input v-model="filters.grade" clearable placeholder="年级" />
        <el-input v-model="filters.subject" clearable placeholder="科目" />
        <div class="m-filter-panel__actions">
          <button type="button" class="m-filter-link" @click="resetFilters">重置</button>
          <button type="button" class="m-filter-apply" @click="runQuery">完成</button>
        </div>
      </div>
    </div>

    <!-- 移动卡片（互斥折叠） -->
    <div v-loading="loading" class="mat-m mat-card-list">
      <div v-if="!total && !loading" class="mat-card mat-card--empty">暂无素材</div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="mat-card"
        :class="{ 'is-expanded': isExpanded(row.id) }"
      >
        <div class="mat-card__top" @click="toggleCard(row.id, $event)">
          <div class="mat-card__title">{{ row.title }}</div>
          <el-tag :type="statusTagType(row.status)" size="small" effect="plain" round>
            {{ statusLabel[row.status] || row.status }}
          </el-tag>
          <button
            type="button"
            class="m-card-acc-toggle"
            :aria-expanded="isExpanded(row.id)"
            @click.stop="toggleForce(row.id)"
          >
            <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(row.id) }">
              <ArrowDown />
            </el-icon>
          </button>
        </div>
        <div v-show="isExpanded(row.id)" class="m-card-acc-body">
          <div class="mat-card__meta">
            <span v-if="row.grade"><span class="k">年级</span>{{ row.grade }}</span>
            <span v-if="row.subject"><span class="k">科目</span>{{ row.subject }}</span>
            <span><span class="k">授权</span>{{ authLabel[row.auth_status] || row.auth_status }}</span>
            <span><span class="k">图片</span>{{ row.files?.length || 0 }}</span>
          </div>
          <div class="mat-card__actions">
            <el-button type="primary" size="small" @click="router.push(`/materials/${row.id}`)">
              详情
            </el-button>
            <el-button
              v-if="!auth.isTeacher && row.status === 'new'"
              size="small"
              type="success"
              plain
              @click="markUsable(row)"
            >
              标为可用
            </el-button>
            <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
          </div>
        </div>
      </div>
      <div v-if="total" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ total }} 条</span>
      </div>
    </div>

    <!-- PC 表格 -->
    <div class="mat-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <div class="table-scroll">
          <el-table
            :data="pagedRows"
            stripe
            class="pc-mat-table"
            style="width: 100%"
            empty-text="暂无素材"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-title-text">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="年级" width="100">
              <template #default="{ row }">
                <span class="pc-muted">{{ row.grade || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="subject" label="科目" width="100">
              <template #default="{ row }">
                <span class="pc-muted">{{ row.subject || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="授权" width="100">
              <template #default="{ row }">
                <el-tag :type="authTagType(row.auth_status)" size="small" effect="plain" round>
                  {{ authLabel[row.auth_status] || row.auth_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="92" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small" effect="plain" round>
                  {{ statusLabel[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="图片" width="72" align="center">
              <template #default="{ row }">
                <span class="pc-mono">{{ row.files?.length || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="router.push(`/materials/${row.id}`)">
                    详情
                  </el-button>
                  <el-button
                    v-if="!auth.isTeacher && row.status === 'new'"
                    link
                    type="success"
                    @click="markUsable(row)"
                  >
                    标为可用
                  </el-button>
                  <el-button link type="danger" @click="onDelete(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="!total && !loading" class="pc-table-empty">暂无素材，可点右上角「上传」</div>
      </el-card>

      <div v-if="total" class="pager-bar pc-pager">
        <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="total"
          :pager-count="5"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
        <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
      </div>
    </div>

    <el-dialog
      v-model="uploadDialog"
      title="上传素材"
      width="90%"
      class="mat-upload-dialog"
      align-center
      destroy-on-close
    >
      <el-form
        ref="uploadFormRef"
        class="mat-upload-form"
        :model="uploadForm"
        :rules="uploadRules"
        label-position="top"
      >
        <el-form-item label="场景标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="例如：课堂进步 / 试听反馈" />
        </el-form-item>
        <div class="mat-upload-row">
          <el-form-item label="年级">
            <el-input v-model="uploadForm.grade" placeholder="如 四年级" />
          </el-form-item>
          <el-form-item label="科目">
            <el-input v-model="uploadForm.subject" placeholder="如 数学" />
          </el-form-item>
        </div>
        <el-form-item label="家长痛点">
          <el-input v-model="uploadForm.pain_point" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="老师处理">
          <el-input v-model="uploadForm.teacher_action" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="下一步行动">
          <el-input v-model="uploadForm.next_step" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="家长授权" prop="auth_status">
          <el-select v-model="uploadForm.auth_status" style="width: 100%">
            <el-option label="已授权可发" value="authorized" />
            <el-option label="待确认" value="pending" />
            <el-option label="已脱敏" value="anonymized" />
            <el-option label="不可用" value="denied" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片（可多选）">
          <el-upload
            v-model:file-list="fileList"
            list-type="picture-card"
            :auto-upload="false"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitUpload">提交素材</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.material-page {
  min-width: 0;
}

.mat-pc {
  display: none;
}

.mat-m {
  display: block;
}

@media (min-width: 992px) {
  .mat-pc {
    display: block;
  }

  .mat-m {
    display: none !important;
  }
}

.page-toolbar.is-compact {
  gap: 10px;
}

/* wap 筛选 */
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

.m-filter-more .el-icon.is-open {
  transform: rotate(180deg);
}

.m-filter-panel {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-filter-panel__actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}

.m-filter-link {
  border: none;
  background: transparent;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  cursor: pointer;
}

.m-filter-apply {
  height: 32px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.mat-card-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mat-card {
  padding: 14px;
  border-radius: 14px;
  border: 2px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.mat-card--empty {
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  padding: 28px 14px;
  border-style: dashed;
}

.mat-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

.mat-card__title {
  flex: 1;
  min-width: 0;
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  cursor: pointer;
  word-break: break-word;
}

.mat-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #faf6ee;
  font-size: 13px;
  color: var(--oc-ink, #44403c);
}

.mat-card__meta .k {
  color: var(--oc-muted, #78716c);
  margin-right: 4px;
  font-size: 12px;
}

.mat-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.mat-card__actions .el-button {
  margin: 0;
  flex: 1 1 calc(33% - 6px);
  min-width: 0;
}

.scroll-sentinel {
  padding: 12px 0 4px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.pc-mat-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee !important;
}

@media (max-width: 991px) {
  .page-toolbar {
    flex-wrap: wrap;
  }

  .tb-btn--primary {
    width: 100%;
    height: 40px;
  }

  .mat-upload-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 10px;
  }

  .mat-upload-form :deep(.el-form-item) {
    margin-bottom: 12px;
  }

  .mat-upload-form :deep(.el-form-item__label) {
    margin-bottom: 4px;
  }
}

@media (min-width: 992px) {
  .mat-upload-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 12px;
  }
}
</style>

<!-- dialog 传送到 body，需非 scoped -->
<style>
.mat-upload-dialog.el-dialog {
  max-width: 560px;
  width: min(90vw, 560px);
}

@media (max-width: 991px) {
  /*
   * 素材上传字段多，pad 再压一档高度，避免贴底滚动时底部闪空白。
   * 全局 dialog 规则见 style.css；此处仅本弹窗更严。
   */
  .mat-upload-dialog.el-dialog {
    max-height: calc(100vh - 64px) !important;
    max-height: calc(100dvh - 64px) !important;
    max-height: calc(100svh - 64px) !important;
  }

  .mat-upload-dialog .el-dialog__body {
    overscroll-behavior: none;
    overscroll-behavior-y: none;
  }

  .mat-upload-dialog .el-upload--picture-card,
  .mat-upload-dialog .el-upload-list--picture-card .el-upload-list__item {
    width: 72px;
    height: 72px;
  }
}
</style>

<style>
.mat-m-select-popper {
  z-index: 5000 !important;
}
</style>
