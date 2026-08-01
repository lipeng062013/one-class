<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  createLead,
  listLeads,
  patchLead,
  type Lead,
  type LeadSource,
  type LeadStatus,
} from '../../api/leads'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'

const LIST_STATE_KEY = 'oc-lead-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const route = useRoute()
const { isCompact } = useBreakpoint()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const loading = ref(false)
const rows = ref<Lead[]>([])
const createVisible = ref(false)
const formRef = ref<FormInstance>()
const saving = ref(false)
const page = ref(1)
const pageSize = ref(20)
const filterExpanded = ref(false)

const filters = reactive({
  source: '',
  status: '',
  name: '',
  phone: '',
})

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

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.source) n += 1
  if (filters.status) n += 1
  if (filters.name.trim()) n += 1
  if (filters.phone.trim()) n += 1
  return n
})

const sorted = computed(() =>
  [...rows.value].sort((a, b) => {
    const aToday = isToday(a.next_follow_at) || a.status === 'new' ? 1 : 0
    const bToday = isToday(b.next_follow_at) || b.status === 'new' ? 1 : 0
    if (aToday !== bToday) return bToday - aToday
    return (b.id || 0) - (a.id || 0)
  }),
)

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  ensureVisible,
} = useInfiniteScroll(sorted, {
  chunk: SCROLL_CHUNK,
  // 与 CSS 断点一致：≤991 启用滚动加载（不依赖首帧 isCompact 误判）
  enabled: isCompact,
  sentinelRef,
})

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('leads', {
  visibleCount,
  enabled: isCompact,
})

const totalPages = computed(() => Math.max(1, Math.ceil(sorted.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return sorted.value.slice(start, start + pageSize.value)
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

async function load(opts?: { resetPage?: boolean }) {
  const snap = opts?.resetPage ? null : takeSnapshotForLoad(route.path)
  if (opts?.resetPage) {
    clearSnapshot()
    page.value = 1
    resetInfinite()
  }
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.source) params.source = filters.source
    if (filters.status) params.status = filters.status
    if (filters.name) params.name = filters.name
    if (filters.phone) params.phone = filters.phone
    rows.value = await listLeads(params)
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

function resetFilters() {
  filters.source = ''
  filters.status = ''
  filters.name = ''
  filters.phone = ''
  load({ resetPage: true })
}

function runQuery() {
  if (isCompact.value) filterExpanded.value = false
  load({ resetPage: true })
}

function toggleFilterExpand() {
  filterExpanded.value = !filterExpanded.value
}

watch(pageSize, () => clampPage())

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

function toIso(value: Date | string | null | undefined): string | null {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

async function submitCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createLead({
      student_or_parent_name: form.student_or_parent_name,
      phone: form.phone || null,
      source: form.source,
      referrer_name: form.referrer_name || null,
      need: form.need,
      notes: form.notes,
      next_follow_at: toIso(form.next_follow_at),
    })
    ElMessage.success('线索已创建')
    createVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}

async function changeStatus(row: Lead, status: LeadStatus) {
  await patchLead(row.id, { status })
  ElMessage.success('状态已更新')
  await load()
}

async function patchFollow(row: Lead, value: Date | null) {
  await patchLead(row.id, { next_follow_at: toIso(value) })
  ElMessage.success('跟进时间已更新')
  await load()
}

onMounted(() => {
  restoreListState()
  load()
})
</script>

<template>
  <div class="lead-page">
    <div class="page-toolbar lead-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header class="is-title-only" content="线索管理" />
      <el-button class="create-btn tb-btn tb-btn--primary" type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新建线索
      </el-button>
    </div>

    <!-- PC 筛选：与学生信息列表同一套米金筛选卡 -->
    <div class="lead-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">获客线索</span>
            <span class="pc-list-summary__count">
              共 <strong>{{ sorted.length }}</strong> 条
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

    <!-- wap/pad 筛选 -->
    <div class="lead-m m-filter">
      <div class="m-filter-search">
        <el-icon class="m-filter-search__icon"><Search /></el-icon>
        <input
          v-model="filters.name"
          class="m-filter-search__input"
          type="search"
          enterkeyhint="search"
          placeholder="搜索姓名"
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
          popper-class="lead-m-select-popper"
        >
          <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select
          v-model="filters.source"
          class="m-filter-select"
          clearable
          placeholder="来源"
          teleported
          placement="bottom-start"
          :fit-input-width="true"
          :popper-options="{ strategy: 'fixed' }"
          popper-class="lead-m-select-popper"
        >
          <el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" />
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
        <el-input v-model="filters.phone" clearable placeholder="电话" />
        <div class="m-filter-panel__actions">
          <button type="button" class="m-filter-link" @click="resetFilters">重置</button>
          <button type="button" class="m-filter-apply" @click="runQuery">完成</button>
        </div>
      </div>
    </div>

    <!-- 移动卡片（CSS 控制显隐，不依赖 isCompact 首帧） -->
    <div v-loading="loading" class="lead-m lead-card-list">
      <div v-if="!sorted.length && !loading" class="lead-card lead-card--empty">暂无线索</div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="lead-card"
        :class="{ 'is-today': isToday(row.next_follow_at) }"
      >
        <div class="lead-card__top">
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
          </div>
        </div>

        <div v-if="row.need || row.notes" class="lead-card__body">
          <p v-if="row.need" class="lead-card__need">
            <span class="k">需求</span>{{ row.need }}
          </p>
          <p v-if="row.notes" class="lead-card__notes">
            <span class="k">备注</span>{{ row.notes }}
          </p>
        </div>

        <div class="lead-card__controls">
          <div class="ctrl">
            <span class="ctrl-label">状态</span>
            <el-select
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
          <div class="ctrl">
            <span class="ctrl-label">下次跟进</span>
            <el-date-picker
              :model-value="row.next_follow_at ? new Date(row.next_follow_at) : null"
              type="datetime"
              placeholder="设置跟进"
              class="ctrl-date"
              teleported
              @update:model-value="(v: Date | null) => patchFollow(row, v)"
            />
          </div>
        </div>
      </div>
      <div v-if="sorted.length" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ sorted.length }} 条</span>
      </div>
    </div>

    <!-- PC 表格：与学生信息列表同一套表格气质 -->
    <div class="lead-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
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
                <div class="pc-name-cell">
                  <span class="pc-avatar">{{ (row.student_or_parent_name || '?').slice(0, 1) }}</span>
                  <span class="pc-name-text">{{ row.student_or_parent_name }}</span>
                </div>
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
            <el-table-column prop="need" label="需求" min-width="120" show-overflow-tooltip />
            <!-- 加宽状态列，避免 select 被挤出「..」省略 -->
            <el-table-column label="状态" width="148" class-name="col-status">
              <template #default="{ row }">
                <el-select
                  :model-value="row.status"
                  size="small"
                  class="status-select"
                  teleported
                  :fit-input-width="true"
                  @change="(v: LeadStatus) => changeStatus(row, v)"
                >
                  <el-option v-for="s in statusOptions" :key="s" :label="statusLabels[s]" :value="s" />
                </el-select>
              </template>
            </el-table-column>
            <!-- 时间选择在前，今日标签在后 -->
            <el-table-column label="下次跟进" min-width="248" class-name="col-follow">
              <template #default="{ row }">
                <div class="follow-cell">
                  <el-date-picker
                    :model-value="row.next_follow_at ? new Date(row.next_follow_at) : null"
                    type="datetime"
                    size="small"
                    placeholder="设置跟进"
                    class="follow-picker"
                    teleported
                    @update:model-value="(v: Date | null) => patchFollow(row, v)"
                  />
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
            <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-notes">{{ row.notes || '—' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <div v-if="sorted.length" class="pager-bar pc-pager">
        <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="sorted.length"
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
      v-model="createVisible"
      title="新建线索"
      width="90%"
      style="max-width: 520px"
      destroy-on-close
      class="lead-create-dialog"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="学生/家长姓名" prop="student_or_parent_name">
          <el-input v-model="form.student_or_parent_name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="选填" />
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
    </el-dialog>
  </div>
</template>

<style scoped>
.lead-page {
  min-width: 0;
}

/* ≤991：只显示移动布局；≥992：只显示 PC */
.lead-pc {
  display: none;
}

.lead-m {
  display: block;
}

@media (min-width: 992px) {
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

/* 与学生信息 PC 筛选卡一致 */
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

/* ── wap 筛选 ── */
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
  text-align: center;
  color: var(--oc-muted, #78716c);
  padding: 40px 16px;
  border-style: dashed;
}

.lead-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
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

.lead-card__controls {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.ctrl-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.ctrl-select,
.ctrl-date {
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
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  color: var(--oc-ink, #44403c);
}

.pc-notes {
  color: var(--oc-muted, #78716c);
}

/* 状态列：给足宽度，去掉被挤出的「..」 */
.status-select {
  width: 120px;
  max-width: 100%;
}

.status-select :deep(.el-select__wrapper) {
  min-height: 28px;
}

.follow-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  min-width: 0;
}

.follow-picker {
  width: 178px;
  flex-shrink: 0;
}

.follow-today-tag {
  flex-shrink: 0;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */

@media (max-width: 991px) {
  .lead-toolbar {
    flex-wrap: wrap;
    gap: 10px;
  }

  .create-btn {
    width: 100%;
    height: 40px;
    border-radius: 10px;
    font-weight: 600;
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
