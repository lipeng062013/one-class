<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bulkDeleteCopies, deleteCopy, listCopies, type GeneratedCopy } from '../../api/copies'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'

const LIST_STATE_KEY = 'oc-copy-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const MODE_LABELS: Record<string, string> = {
  template: '仅模板',
  template_then_llm: '模板+润色',
  llm: '直接大模型',
}

const PLATFORM_LABELS: Record<string, string> = {
  xhs: '小红书',
  douyin: '抖音',
  wechat: '微信',
  moments: '朋友圈',
  video: '视频号',
}

const route = useRoute()
const router = useRouter()
const { isCompact } = useBreakpoint()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const loading = ref(false)
const bulkLoading = ref(false)
const rows = ref<GeneratedCopy[]>([])
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref<number[]>([])
const filterExpanded = ref(false)
const tableRef = ref<{ clearSelection?: () => void } | null>(null)

const filters = reactive({
  q: '',
  mode: '',
  platform: '',
})

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.q.trim()) n += 1
  if (filters.mode) n += 1
  if (filters.platform) n += 1
  return n
})

const filtered = computed(() => {
  const q = filters.q.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (filters.mode && r.mode !== filters.mode) return false
    if (filters.platform && r.platform !== filters.platform) return false
    if (!q) return true
    const hay = `${r.title || ''} ${r.body || ''}`.toLowerCase()
    return hay.includes(q)
  })
})

function modeLabel(mode?: string | null) {
  if (!mode) return '—'
  return MODE_LABELS[mode] || mode
}

function platformLabel(platform?: string | null) {
  if (!platform) return '—'
  return PLATFORM_LABELS[platform] || platform
}

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  ensureVisible,
} = useInfiniteScroll(filtered, { chunk: SCROLL_CHUNK, enabled: isCompact, sentinelRef })

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('copies', {
  visibleCount,
  enabled: isCompact,
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const selectedCount = computed(() => selectedIds.value.length)

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
      filters.q = s.filters.q ?? ''
      filters.mode = s.filters.mode ?? ''
      filters.platform = s.filters.platform ?? ''
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

function runQuery() {
  clearSnapshot()
  page.value = 1
  filterExpanded.value = false
  resetInfinite()
  clampPage()
  saveListState()
}

function resetFilters() {
  clearSnapshot()
  filters.q = ''
  filters.mode = ''
  filters.platform = ''
  page.value = 1
  filterExpanded.value = false
  resetInfinite()
  saveListState()
}

function toggleFilterExpand() {
  filterExpanded.value = !filterExpanded.value
}

function onSelectionChange(selection: GeneratedCopy[]) {
  selectedIds.value = selection.map((s) => s.id)
}

function clearSelection() {
  selectedIds.value = []
  tableRef.value?.clearSelection?.()
}

function toggleCardSelect(id: number, checked: boolean | string | number) {
  const on = checked === true || checked === 'true'
  if (on) {
    if (!selectedIds.value.includes(id)) selectedIds.value = [...selectedIds.value, id]
  } else {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }
}

function isSelected(id: number) {
  return selectedIds.value.includes(id)
}

async function load(opts?: { fromQuery?: boolean }) {
  const snap = opts?.fromQuery ? null : takeSnapshotForLoad(route.path)
  if (opts?.fromQuery) clearSnapshot()

  loading.value = true
  try {
    rows.value = await listCopies()
    selectedIds.value = selectedIds.value.filter((id) => rows.value.some((r) => r.id === id))
    if (snap?.visibleCount != null && isCompact.value) {
      ensureVisible(snap.visibleCount)
    } else {
      resetInfinite()
    }
    clampPage()
    saveListState()
  } finally {
    loading.value = false
  }
  // 有快照才恢复；否则强制回顶（.main 跨路由不卸，切换模块会带着旧 scroll）
  void finishListEnter({ snap, forceTop: !!opts?.fromQuery })
}

function goDetail(row: GeneratedCopy) {
  router.push(`/copies/${row.id}`)
}

async function copyBody(row: GeneratedCopy) {
  try {
    await navigator.clipboard.writeText(`${row.title}\n\n${row.body}`)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function onDelete(row: GeneratedCopy) {
  try {
    await ElMessageBox.confirm(`删除文案「${row.title || row.id}」？`, '确认', { type: 'warning' })
    await deleteCopy(row.id)
    ElMessage.success('已删除')
    selectedIds.value = selectedIds.value.filter((id) => id !== row.id)
    await load()
  } catch {
    /* cancel */
  }
}

async function onBulkDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要删除的文案')
    return
  }
  const titles = rows.value
    .filter((r) => selectedIds.value.includes(r.id))
    .map((r) => r.title || `#${r.id}`)
  const preview =
    titles.length <= 5
      ? titles.join('、')
      : `${titles.slice(0, 5).join('、')} 等 ${titles.length} 条`
  try {
    await ElMessageBox.confirm(
      `确定批量删除 ${selectedIds.value.length} 条文案（${preview}）？不可恢复。`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    bulkLoading.value = true
    const result = await bulkDeleteCopies(selectedIds.value)
    ElMessage.success(`已删除 ${result.deleted_count} 条文案`)
    selectedIds.value = []
    await load()
  } catch {
    /* cancel */
  } finally {
    bulkLoading.value = false
  }
}

watch(filtered, () => clampPage())
watch(pageSize, () => clampPage())

onMounted(() => {
  restoreListState()
  load()
})
</script>

<template>
  <div class="copy-page">
    <div class="page-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header class="is-title-only" content="文案列表" />
      <div class="toolbar-right">
        <el-button
          class="tb-btn"
          type="danger"
          plain
          :disabled="!selectedCount"
          :loading="bulkLoading"
          @click="onBulkDelete"
        >
          删除所选{{ selectedCount ? ` ${selectedCount}` : '' }}
        </el-button>
        <el-button
          class="tb-btn tb-btn--primary"
          type="primary"
          @click="router.push('/copies/generate')"
        >
          <el-icon><Plus /></el-icon>
          生成文案
        </el-button>
      </div>
    </div>

    <div class="copy-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">生成文案</span>
            <span class="pc-list-summary__count">
              共 <strong>{{ filtered.length }}</strong> 条
            </span>
            <span v-if="selectedCount" class="pc-list-summary__sel">
              已选 <strong>{{ selectedCount }}</strong>
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="关键词">
            <el-input
              v-model="filters.q"
              clearable
              placeholder="标题 / 正文"
              style="width: 160px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item label="模式">
            <el-select v-model="filters.mode" clearable placeholder="全部" style="width: 130px">
              <el-option v-for="(label, key) in MODE_LABELS" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="平台">
            <el-select v-model="filters.platform" clearable placeholder="全部" style="width: 120px">
              <el-option
                v-for="(label, key) in PLATFORM_LABELS"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="runQuery">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <div class="copy-m m-filter">
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
          v-model="filters.mode"
          class="m-filter-select"
          clearable
          placeholder="模式"
          teleported
          :popper-options="{ strategy: 'fixed' }"
          popper-class="copy-m-select-popper"
        >
          <el-option v-for="(label, key) in MODE_LABELS" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select
          v-model="filters.platform"
          class="m-filter-select"
          clearable
          placeholder="平台"
          teleported
          :popper-options="{ strategy: 'fixed' }"
          popper-class="copy-m-select-popper"
        >
          <el-option
            v-for="(label, key) in PLATFORM_LABELS"
            :key="key"
            :label="label"
            :value="key"
          />
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
        <div class="m-filter-panel__actions">
          <button type="button" class="m-filter-link" @click="resetFilters">重置</button>
          <button type="button" class="m-filter-apply" @click="runQuery">完成</button>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="copy-m copy-card-list">
      <div v-if="!filtered.length && !loading" class="copy-card copy-card--empty">暂无文案</div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="copy-card"
        :class="{ 'is-selected': isSelected(row.id) }"
      >
        <div class="copy-card__top">
          <el-checkbox
            class="copy-card__check"
            :model-value="isSelected(row.id)"
            @click.stop
            @update:model-value="(v: boolean | string | number) => toggleCardSelect(row.id, v)"
          />
          <button type="button" class="copy-card__title copy-card__title--link" @click="goDetail(row)">
            {{ row.title || `文案 #${row.id}` }}
          </button>
          <el-tag v-if="row.banned_hits?.length" type="danger" size="small" effect="plain" round>
            禁用词 {{ row.banned_hits.length }}
          </el-tag>
        </div>
        <div class="copy-card__meta" @click="goDetail(row)">
          <span><span class="k">模式</span>{{ modeLabel(row.mode) }}</span>
          <span><span class="k">平台</span>{{ platformLabel(row.platform) }}</span>
        </div>
        <p v-if="row.body" class="copy-card__excerpt" @click="goDetail(row)">
          {{ row.body }}
        </p>
        <div class="copy-card__actions">
          <el-button type="primary" size="small" @click="goDetail(row)">详情</el-button>
          <el-button size="small" @click="copyBody(row)">复制</el-button>
          <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
        </div>
      </div>
      <div v-if="filtered.length" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ filtered.length }} 条</span>
      </div>
    </div>

    <div class="copy-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <div v-if="selectedCount" class="pc-selection-bar">
          <span>
            已选择 <strong>{{ selectedCount }}</strong> 条文案
          </span>
          <div class="pc-selection-actions">
            <el-button size="small" type="danger" plain :loading="bulkLoading" @click="onBulkDelete">
              批量删除
            </el-button>
            <el-button size="small" text @click="clearSelection">取消选择</el-button>
          </div>
        </div>
        <div class="table-scroll">
          <el-table
            ref="tableRef"
            :data="pagedRows"
            stripe
            class="pc-copy-table"
            row-key="id"
            empty-text="暂无文案"
            :header-cell-style="pcHeaderStyle"
            @selection-change="onSelectionChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <button type="button" class="pc-title-link" @click="goDetail(row)">
                  {{ row.title || `文案 #${row.id}` }}
                </button>
              </template>
            </el-table-column>
            <el-table-column label="模式" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" round type="info">
                  {{ modeLabel(row.mode) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="平台" width="100">
              <template #default="{ row }">
                <span class="pc-muted">{{ platformLabel(row.platform) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="禁用词" width="100" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.banned_hits?.length" type="danger" size="small" effect="plain" round>
                  {{ row.banned_hits.length }}
                </el-tag>
                <span v-else class="pc-muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="goDetail(row)">详情</el-button>
                  <el-button link type="primary" @click="copyBody(row)">复制</el-button>
                  <el-button link type="danger" @click="onDelete(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="!filtered.length && !loading" class="pc-table-empty">暂无文案，可点「生成文案」</div>
      </el-card>

      <div v-if="filtered.length" class="pager-bar pc-pager">
        <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="filtered.length"
          :pager-count="5"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
        <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.copy-page {
  min-width: 0;
}

.copy-pc {
  display: none;
}

.copy-m {
  display: block;
}

@media (min-width: 992px) {
  .copy-pc {
    display: block;
  }

  .copy-m {
    display: none !important;
  }
}

.toolbar-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.m-filter {
  position: relative;
  z-index: 20;
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
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
  font-size: 12px;
  cursor: pointer;
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
}

.m-filter-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.m-filter-link {
  border: none;
  background: transparent;
  color: var(--oc-muted, #78716c);
  cursor: pointer;
}

.m-filter-apply {
  height: 32px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

.copy-card-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.copy-card {
  padding: 14px;
  border-radius: 14px;
  border: 2px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.copy-card.is-selected {
  border-color: var(--oc-primary, #a16207);
}

.copy-card--empty {
  text-align: center;
  color: var(--oc-muted, #78716c);
  padding: 28px 14px;
  border-style: dashed;
}

.copy-card__top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.copy-card__check {
  flex-shrink: 0;
}

.copy-card__title {
  flex: 1;
  min-width: 0;
  font-weight: 650;
  font-size: 15px;
  color: var(--oc-ink, #44403c);
  word-break: break-word;
  text-align: left;
}

.copy-card__title--link {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font: inherit;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.copy-card__title--link:hover {
  color: var(--oc-primary, #a16207);
}

.copy-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #faf6ee;
  font-size: 13px;
  cursor: pointer;
}

.copy-card__meta .k {
  color: var(--oc-muted, #78716c);
  margin-right: 4px;
  font-size: 12px;
}

.copy-card__excerpt {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--oc-muted, #78716c);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  cursor: pointer;
}

.copy-card__actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.copy-card__actions .el-button {
  margin: 0;
  width: 100%;
}

.pc-title-link {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  text-align: left;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pc-title-link:hover {
  color: var(--oc-primary, #a16207);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.pc-ops {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  flex-wrap: wrap;
}

.scroll-sentinel {
  padding: 12px 0 4px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.pc-copy-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee !important;
}

@media (max-width: 991px) {
  .toolbar-right {
    width: 100%;
  }

  .toolbar-right .tb-btn {
    flex: 1;
  }

  .toolbar-right .tb-btn--primary {
    flex: 1 1 100%;
  }
}
</style>

<style>
.copy-m-select-popper {
  z-index: 5000 !important;
}
</style>
