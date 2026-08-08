<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createKnowledge,
  deleteKnowledge,
  listKnowledge,
  updateKnowledge,
  type KnowledgeEntry,
} from '../../api/knowledge'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'

const LIST_STATE_KEY = 'oc-knowledge-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { isApp } = useBreakpoint()
const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()
const { surface: knowSurface, surfaceProps: knowSurfaceProps } = useResponsiveSurface({
  compactSize: 'min(88%, 640px)',
  dialogMaxWidth: '560px',
  modalClass: 'know-app-sheet',
  sheetProps: { forceBottom: true },
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const loading = ref(false)
const rows = ref<KnowledgeEntry[]>([])
/** 预解析后的标签，避免模板重复 split 与表格重排闪烁 */
const rowTags = ref<Record<number, string[]>>({})
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const saving = ref(false)
const page = ref(1)
const pageSize = ref(20)
const filterExpanded = ref(false)
/** 请求序号，避免快速切换分区时旧响应覆盖新数据 */
let loadSeq = 0

const sectionMap: Record<
  string,
  { category: string; title: string; summaryLabel: string; createLabel: string }
> = {
  scripts: {
    category: 'script',
    title: '沟通话术',
    summaryLabel: '沟通话术',
    createLabel: '新建话术',
  },
  objections: {
    category: 'objection',
    title: '异议处理',
    summaryLabel: '异议处理',
    createLabel: '新建异议',
  },
  banned: {
    category: 'banned',
    title: '禁用词列表',
    summaryLabel: '禁用词',
    createLabel: '新建禁用词',
  },
}

const sectionKey = computed(() => String(route.params.section || 'scripts'))

const section = computed(() => sectionMap[sectionKey.value] || sectionMap.scripts)

const filters = reactive({
  q: '',
  status: '' as '' | 'active' | 'inactive',
})

const form = reactive({
  category: 'script',
  title: '',
  content: '',
  is_active: true,
})
const formTags = ref<string[]>([])
const tagInput = ref('')

const rules: FormRules = {
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  content: [{ required: true, message: '请填写内容', trigger: 'blur' }],
}

const statusLabels: Record<string, string> = {
  active: '启用',
  inactive: '停用',
}

/** 将后端逗号分隔的标签字符串解析为数组 */
function parseTags(raw?: string | null): string[] {
  if (!raw?.trim()) return []
  return raw
    .split(/[,，、;；\s]+/)
    .map((t) => t.trim())
    .filter(Boolean)
}

function joinTags(tags: string[]): string {
  return tags.join(',')
}

function addTag() {
  const value = tagInput.value.trim()
  if (!value) return
  const parts = parseTags(value)
  for (const part of parts) {
    if (!formTags.value.includes(part)) {
      formTags.value.push(part)
    }
  }
  tagInput.value = ''
}

function removeFormTag(tag: string) {
  formTags.value = formTags.value.filter((t) => t !== tag)
}

function buildRowTags(list: KnowledgeEntry[]) {
  const map: Record<number, string[]> = {}
  for (const row of list) {
    map[row.id] = parseTags(row.tags)
  }
  rowTags.value = map
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.q.trim()) n += 1
  if (filters.status) n += 1
  return n
})

/** 本地筛选（接口按分区拉全量） */
const filtered = computed(() => {
  const q = filters.q.trim().toLowerCase()
  return rows.value.filter((row) => {
    if (filters.status === 'active' && !row.is_active) return false
    if (filters.status === 'inactive' && row.is_active) return false
    if (!q) return true
    const tags = (rowTags.value[row.id] || []).join(' ')
    const hay = `${row.title} ${row.content} ${tags}`.toLowerCase()
    return hay.includes(q)
  })
})

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  loadMore,
} = useInfiniteScroll(filtered, {
  chunk: SCROLL_CHUNK,
  enabled: isApp,
  sentinelRef,
})

// 知识库无独立详情页，不恢复滚动；仅用 finishListEnter 回顶
const { finishListEnter, clearSnapshot } = useListScrollRestore('knowledge', {
  visibleCount,
  enabled: isApp,
  stateStorageKey: LIST_STATE_KEY,
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
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

function onPageChange() {
  saveListState()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
}

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY)
    if (!raw) return
    const s = JSON.parse(raw) as {
      section?: string
      filters?: Partial<typeof filters>
      page?: number
      pageSize?: number
    }
    // 仅恢复当前分区的筛选，避免串页
    if (s.section && s.section !== sectionKey.value) return
    if (s.filters) {
      filters.q = s.filters.q ?? ''
      filters.status = s.filters.status ?? ''
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
        section: sectionKey.value,
        filters: { ...filters },
        page: page.value,
        pageSize: pageSize.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

async function load(opts?: { resetPage?: boolean }) {
  const seq = ++loadSeq
  const category = section.value.category
  // 成长中心无独立详情，切换分区/进入一律回顶，不恢复滚动
  const snap = null
  clearSnapshot()

  loading.value = true
  // 切换分区先清空，避免旧分区标签/列宽残留再被新数据顶替造成闪烁
  rows.value = []
  rowTags.value = {}
  if (opts?.resetPage) page.value = 1
  try {
    const list = await listKnowledge(category)
    if (seq !== loadSeq) return
    buildRowTags(list)
    rows.value = list
    clampPage()
    resetInfinite()
  } finally {
    if (seq === loadSeq) loading.value = false
  }
  if (seq === loadSeq) void finishListEnter({ snap, forceTop: true })
}

function runQuery() {
  clearSnapshot()
  collapseAll()
  page.value = 1
  filterExpanded.value = false
  saveListState()
  resetInfinite()
  clampPage()
}

function resetFilters() {
  clearSnapshot()
  collapseAll()
  filters.q = ''
  filters.status = ''
  page.value = 1
  filterExpanded.value = false
  saveListState()
  resetInfinite()
}

function openCreate() {
  editingId.value = null
  form.category = section.value.category
  form.title = ''
  form.content = ''
  formTags.value = []
  tagInput.value = ''
  form.is_active = true
  dialogVisible.value = true
}

function openEdit(row: KnowledgeEntry) {
  editingId.value = row.id
  form.category = row.category
  form.title = row.title
  form.content = row.content
  formTags.value = parseTags(row.tags)
  tagInput.value = ''
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  if (tagInput.value.trim()) addTag()
  saving.value = true
  try {
    form.category = section.value.category
    const payload = { ...form, tags: joinTags(formTags.value) }
    if (editingId.value) {
      await updateKnowledge(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createKnowledge(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: KnowledgeEntry) {
  await ElMessageBox.confirm(`删除「${row.title}」？`, '确认', { type: 'warning' })
  await deleteKnowledge(row.id)
  ElMessage.success('已删除')
  await load()
}

watch(
  () => route.params.section,
  () => {
    if (!sectionMap[String(route.params.section || '')]) {
      router.replace('/knowledge/scripts')
      return
    }
    filters.q = ''
    filters.status = ''
    page.value = 1
    filterExpanded.value = false
    try {
      sessionStorage.removeItem(LIST_STATE_KEY)
    } catch {
      /* ignore */
    }
    load({ resetPage: true })
  },
)

watch(filtered, () => {
  clampPage()
})

onMounted(() => {
  restoreListState()
  load()
})
</script>

<template>
  <div class="know-page">
    <div class="page-toolbar know-toolbar" :class="{ 'is-compact': isApp }">
      <el-page-header class="is-title-only" :content="section.title" />
      <el-button
        v-if="auth.hasPermission('knowledge.write')"
        class="create-btn tb-btn tb-btn--primary"
        type="primary"
        @click="openCreate"
      >
        <el-icon><Plus /></el-icon>
        {{ section.createLabel }}
      </el-button>
    </div>

    <el-alert
      v-if="!auth.hasPermission('knowledge.write')"
      class="know-readonly-tip"
      type="info"
      :closable="false"
      title="运营可阅读成长中心内容；新建/编辑仅负责人可操作。"
    />

    <!-- PC 筛选：摘要胶囊放右上，不在标题下堆说明 -->
    <div class="know-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">{{ section.summaryLabel }}</span>
            <span class="pc-list-summary__count">
              共 <strong>{{ filtered.length }}</strong> 条
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="关键词">
            <el-input
              v-model="filters.q"
              clearable
              placeholder="标题 / 内容 / 标签"
              style="width: 200px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
              <el-option
                v-for="(label, key) in statusLabels"
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

    <CompactFilterBar class="know-m" :active-count="activeFilterCount" :total="filtered.length" :label="`条${section.title}`" @open="filterExpanded = true" />
    <MobileFilterSheet v-model="filterExpanded" :active-count="activeFilterCount" @apply="runQuery" @reset="resetFilters">
      <el-form label-position="top" @submit.prevent="runQuery">
        <el-form-item label="关键词"><el-input v-model="filters.q" clearable placeholder="标题 / 内容 / 标签" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" /></el-select></el-form-item>
      </el-form>
    </MobileFilterSheet>

    <!-- 移动卡片（互斥折叠；CSS 控制显隐） -->
    <div v-loading="loading" class="know-m know-card-list">
      <div v-if="!filtered.length && !loading" class="know-card know-card--empty">
        暂无{{ section.title }}
      </div>
      <div
        v-for="row in infiniteRows"
        :key="`${section.category}-${row.id}`"
        class="know-card"
        :class="{ 'is-expanded': isExpanded(row.id) }"
      >
        <div class="know-card__top" @click="toggleCard(row.id, $event)">
          <div class="know-card__who">
            <div class="know-card__name">{{ row.title }}</div>
          </div>
          <el-tag
            :type="row.is_active ? 'success' : 'info'"
            size="small"
            effect="plain"
            round
          >
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
          <button
            type="button"
            class="m-card-acc-toggle"
            :aria-expanded="isExpanded(row.id)"
            :aria-label="isExpanded(row.id) ? '收起条目详情' : '展开条目详情'"
            @click.stop="toggleForce(row.id)"
          >
            <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(row.id) }">
              <ArrowDown />
            </el-icon>
          </button>
        </div>

        <div v-show="isExpanded(row.id)" class="m-card-acc-body">
          <div class="know-card__body">{{ row.content }}</div>

          <div class="know-card__tags">
            <template v-if="rowTags[row.id]?.length">
              <el-tag
                v-for="tag in rowTags[row.id]"
                :key="`${row.id}-${tag}`"
                size="small"
                effect="plain"
                type="warning"
                class="tag-chip"
              >
                {{ tag }}
              </el-tag>
            </template>
            <span v-else class="tag-empty">无标签</span>
          </div>

          <div v-if="auth.hasPermission('knowledge.write')" class="know-card__actions">
            <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" plain @click="remove(row)">删除</el-button>
          </div>
        </div>
      </div>
      <div ref="sentinelRef" class="list-load-sentinel">
        <ListLoadStatus
          :has-more="hasMoreInfinite"
          :loading="loadingMore"
          :loaded="infiniteRows.length"
          :total="filtered.length"
          @more="loadMore"
          @retry="loadMore"
        />
      </div>
    </div>

    <!-- PC 表格 -->
    <div class="know-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <!--
          固定 table-layout + 固定列宽；标签列始终同一结构。
          快速切换分区时不再因 min-width 自适应导致标签列左右跳动。
        -->
        <div class="table-scroll">
          <el-table
            :data="pagedRows"
            stripe
            class="pc-know-table"
            style="width: 100%"
            table-layout="fixed"
            empty-text="暂无内容"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="title" label="标题" width="168" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-title-text">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
            <el-table-column label="标签" width="200" class-name="col-tags">
              <template #default="{ row }">
                <div class="tag-chips">
                  <template v-if="rowTags[row.id]?.length">
                    <el-tag
                      v-for="tag in rowTags[row.id]"
                      :key="`${row.id}-${tag}`"
                      size="small"
                      effect="plain"
                      type="warning"
                      class="tag-chip"
                    >
                      {{ tag }}
                    </el-tag>
                  </template>
                  <span v-else class="tag-empty">—</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88" align="center" class-name="col-status">
              <template #default="{ row }">
                <el-tag
                  :type="row.is_active ? 'success' : 'info'"
                  size="small"
                  effect="plain"
                  round
                  class="status-tag"
                >
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              v-if="auth.hasPermission('knowledge.write')"
              label="操作"
              width="120"
              align="center"
              class-name="col-actions"
            >
              <template #default="{ row }">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="remove(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
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

    <component
      :is="knowSurface"
      v-model="dialogVisible"
      v-bind="knowSurfaceProps"
      :title="editingId ? `编辑${section.title}` : section.createLabel"
      destroy-on-close
      class="know-dialog"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="简短标题" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="6" placeholder="正文内容" />
        </el-form-item>
        <el-form-item label="标签">
          <div class="tag-editor">
            <el-input
              v-model="tagInput"
              class="tag-input"
              placeholder="输入标签后点击 +"
              clearable
              @keydown.enter.prevent="addTag"
            >
              <template #append>
                <el-button class="tag-add-btn" @click="addTag" title="添加标签">+</el-button>
              </template>
            </el-input>
            <div v-if="formTags.length" class="tag-chips tag-preview">
              <el-tag
                v-for="tag in formTags"
                :key="tag"
                size="small"
                effect="plain"
                type="warning"
                closable
                @close="removeFormTag(tag)"
              >
                {{ tag }}
              </el-tag>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </template>
    </component>
  </div>
</template>

<style scoped>
.know-page {
  min-width: 0;
}

/* ≤991：只显示移动布局；≥992：只显示 PC */
.know-pc {
  display: none;
}

.know-m {
  display: block;
}

@media (min-width: 1200px) {
  .know-pc {
    display: block;
  }

  .know-m {
    display: none !important;
  }
}

.know-toolbar.is-compact {
  gap: 10px;
}

.create-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tb-btn--primary {
  height: 36px;
  border-radius: 9px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.22);
}

.know-readonly-tip {
  margin-top: 12px;
}

/* ── PC 筛选卡 ── */
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
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
}

.m-filter-hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
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

/* ── 移动卡片 ── */
.know-card-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 80px;
}

.know-card {
  padding: 14px;
  border-radius: 14px;
  border: 2px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.know-card--empty {
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  padding: 28px 14px;
  border-style: dashed;
}

.know-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

.know-card__who {
  flex: 1;
  min-width: 0;
}

.know-card__name {
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
  word-break: break-word;
}

.know-card__body {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #faf6ee;
  font-size: 13px;
  color: var(--oc-ink, #44403c);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 7.75em;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 5;
  -webkit-box-orient: vertical;
}

.know-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  min-height: 22px;
  align-items: center;
}

.know-card__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.know-card__actions .el-button {
  margin: 0;
  width: 100%;
}

/* ── PC 表格卡 ── */
.pc-table-card {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  min-height: 200px;
}

.pc-table-card :deep(.el-card__body) {
  padding: 0;
}

.table-scroll {
  width: 100%;
  overflow-x: auto;
}

.pc-know-table {
  width: 100%;
}

.pc-know-table :deep(table) {
  table-layout: fixed !important;
  width: 100% !important;
}

.pc-know-table :deep(.el-table__header th),
.pc-know-table :deep(.el-table__body td) {
  transition: none;
}

.pc-know-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee !important;
}

.pc-know-table :deep(.col-tags),
.pc-know-table :deep(.col-status),
.pc-know-table :deep(.col-actions) {
  overflow: hidden;
}

.pc-know-table :deep(.col-tags .cell) {
  overflow: hidden;
  line-height: 24px;
  height: auto;
  min-height: 32px;
  display: flex;
  align-items: center;
}

.tag-chips {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  width: 100%;
  min-height: 24px;
  max-height: 24px;
  overflow: hidden;
}

.tag-chip {
  margin: 0 !important;
  flex-shrink: 0;
  max-width: 72px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-chip :deep(.el-tag__content) {
  overflow: hidden;
  text-overflow: ellipsis;
}

.tag-empty {
  color: var(--oc-muted, #78716c);
  display: inline-block;
  font-size: 12px;
  line-height: 24px;
  flex-shrink: 0;
}

.status-tag {
  min-width: 44px;
  justify-content: center;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */

/* ── 对话框标签编辑 ── */
.tag-editor {
  width: 100%;
}

.tag-input {
  width: 100%;
}

.tag-input :deep(.el-input-group__append) {
  padding: 0;
  background: var(--oc-primary, #a16207);
  border-color: var(--oc-primary, #a16207);
  box-shadow: none;
  overflow: hidden;
}

.tag-add-btn {
  margin: 0;
  width: 42px;
  min-width: 42px;
  height: 100%;
  padding: 0 12px;
  border: none !important;
  border-radius: 0;
  background: transparent !important;
  color: #fff !important;
  font-size: 18px;
  font-weight: 600;
  line-height: 1;
}

.tag-add-btn:hover,
.tag-add-btn:focus {
  background: var(--oc-primary-hover, #86530a) !important;
  color: #fff !important;
}

.tag-preview {
  margin-top: 10px;
  max-height: none;
  flex-wrap: wrap;
}
</style>

<style>
/* teleported 下拉：避免被父级裁切 */
.know-m-select-popper {
  z-index: 5000 !important;
}
</style>
