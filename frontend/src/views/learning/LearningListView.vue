<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listLearningApi, type LearningRecord } from '../../api/students'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'

type ListScope = 'mine' | 'all'

const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const router = useRouter()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const rows = ref<LearningRecord[]>([])
const q = ref('')
const page = ref(1)
const pageSize = ref(20)
/** 老师默认我的；负责人默认全部；每次进入不记忆 tab */
const listScope = ref<ListScope>(auth.isTeacher ? 'mine' : 'all')

const classLabels: Record<string, string> = {
  attended: '已上课',
  absent: '缺勤',
  late: '迟到',
  leave: '请假',
  makeup: '补课',
}

const classTagType: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
  attended: 'success',
  absent: 'danger',
  late: 'warning',
  leave: 'info',
  makeup: 'warning',
}

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const pageTitle = computed(() => (listScope.value === 'mine' ? '我的学情' : '全部学情'))

const filteredRows = computed(() => {
  const raw = q.value.trim().toLowerCase()
  if (!raw) return rows.value
  return rows.value.filter((r) => {
    const hay =
      `${r.student_name || ''} ${r.subject || ''} ${r.learning_summary || ''} ${r.teacher_name || ''}`.toLowerCase()
    return hay.includes(raw)
  })
})

const totalPages = computed(() =>
  Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value) || 1),
)

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

const listSummary = computed(() => {
  const n = filteredRows.value.length
  return listScope.value === 'mine' ? `我填写的 ${n} 条` : `共 ${n} 条`
})

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  resetVisible: resetInfinite,
} = useInfiniteScroll(filteredRows, { chunk: SCROLL_CHUNK, enabled: isCompact, sentinelRef })

function clampPage() {
  if (page.value > totalPages.value) page.value = totalPages.value
  if (page.value < 1) page.value = 1
}

function goFirstPage() {
  page.value = 1
}

function goLastPage() {
  page.value = totalPages.value
}

function onPageChange() {
  /* v-model already updated */
}

function onPageSizeChange() {
  page.value = 1
}

async function load() {
  loading.value = true
  try {
    rows.value = await listLearningApi({
      mine: listScope.value === 'mine',
    })
    page.value = 1
    resetInfinite()
  } finally {
    loading.value = false
  }
}

function onScopeChange() {
  // 不持久化 scope：仅当次会话内切换
  page.value = 1
  load()
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function goStudent(id: number) {
  void router.push(`/students/${id}`)
}

function goNew() {
  void router.push('/learning/new')
}

watch(pageSize, () => clampPage())
watch(
  () => filteredRows.value.length,
  () => clampPage(),
)
watch(q, () => {
  page.value = 1
  resetInfinite()
})

onMounted(() => {
  // 每次进入：老师默认我的，负责人默认全部
  listScope.value = auth.isTeacher ? 'mine' : 'all'
  load()
})
</script>

<template>
  <div class="learning-page">
    <div class="page-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header class="is-title-only" :content="pageTitle" />
      <div class="toolbar-right">
        <el-button class="tb-btn tb-btn--primary" type="primary" @click="goNew">
          <el-icon><EditPen /></el-icon>
          编写学情
        </el-button>
      </div>
    </div>

    <div class="scope-bar" :class="{ 'is-compact': isCompact }">
      <el-radio-group v-model="listScope" size="default" @change="onScopeChange">
        <el-radio-button value="mine">我填写的</el-radio-button>
        <el-radio-button value="all">全部学情</el-radio-button>
      </el-radio-group>
    </div>

    <el-card v-if="!isCompact" class="filters pc-filters" shadow="never">
      <div class="pc-filters-head">
        <div class="pc-filters-head-main">
          <span class="pc-filters-title">筛选</span>
        </div>
        <div class="pc-list-summary">
          <span class="pc-list-summary__label">{{ pageTitle }}</span>
          <span class="pc-list-summary__count">
            共 <strong>{{ filteredRows.length }}</strong> 条
          </span>
        </div>
      </div>
      <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent>
        <el-form-item label="搜索">
          <el-input
            v-model="q"
            clearable
            placeholder="学生 / 科目 / 摘要 / 填写人"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">刷新</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-else class="m-filter">
      <el-input
        v-model="q"
        clearable
        size="large"
        placeholder="搜学生 / 科目 / 摘要"
        class="m-search"
      />
      <div class="list-meta">{{ listSummary }}</div>
    </div>

    <!-- 紧凑：卡片 + 无限滚动 -->
    <div v-if="isCompact" v-loading="loading" class="card-list">
      <el-empty
        v-if="!filteredRows.length && !loading"
        :description="listScope === 'mine' ? '还没有提交过学情' : '暂无学情记录'"
      />
      <el-card
        v-for="r in infiniteRows"
        :key="r.id"
        class="card"
        shadow="hover"
        @click="goStudent(r.student_id)"
      >
        <div class="row1">
          <strong>{{ r.student_name || `学生#${r.student_id}` }}</strong>
          <el-tag
            size="small"
            effect="plain"
            round
            :type="classTagType[r.class_status] || 'info'"
          >
            {{ classLabels[r.class_status] || r.class_status }}
          </el-tag>
        </div>
        <div class="time">
          {{ formatTime(r.class_date) }}
          <span v-if="r.subject"> · {{ r.subject }}</span>
          <span v-if="listScope === 'all' && r.teacher_name"> · {{ r.teacher_name }}</span>
        </div>
        <p class="summary">{{ r.learning_summary }}</p>
        <el-button link type="primary" @click.stop="goStudent(r.student_id)">看学生档案</el-button>
      </el-card>
      <div v-if="filteredRows.length" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ filteredRows.length }} 条</span>
      </div>
    </div>

    <!-- PC：表格 -->
    <el-card v-else v-loading="loading" class="pc-table-card" shadow="never">
      <div class="table-scroll">
        <el-table
          :data="pagedRows"
          stripe
          style="width: 100%"
          empty-text="暂无学情"
          :header-cell-style="pcHeaderStyle"
        >
          <el-table-column label="学生" min-width="120">
            <template #default="{ row }">
              <button type="button" class="name-link" @click="goStudent(row.student_id)">
                {{ row.student_name || `#${row.student_id}` }}
              </button>
            </template>
          </el-table-column>
          <el-table-column label="上课时间" min-width="160">
            <template #default="{ row }">
              <span class="muted">{{ formatTime(row.class_date) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                round
                :type="classTagType[row.class_status] || 'info'"
              >
                {{ classLabels[row.class_status] || row.class_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="subject" label="科目" width="100" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="muted">{{ row.subject || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column
            v-if="listScope === 'all'"
            label="填写人"
            min-width="100"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span class="muted">{{ row.teacher_name || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="学习情况" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.learning_summary || '—' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right" align="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="goStudent(row.student_id)">档案</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- PC 底部分页 -->
    <div v-if="!isCompact && filteredRows.length" class="pager-bar pc-pager">
      <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZES"
        :total="filteredRows.length"
        :pager-count="5"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
      <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
    </div>
  </div>
</template>

<style scoped>
.learning-page {
  width: 100%;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.page-toolbar.is-compact {
  flex-direction: column;
  align-items: stretch;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.scope-bar {
  margin-bottom: 12px;
}

.scope-bar.is-compact :deep(.el-radio-group) {
  display: flex;
  width: 100%;
}

.scope-bar.is-compact :deep(.el-radio-button) {
  flex: 1;
}

.scope-bar.is-compact :deep(.el-radio-button__inner) {
  width: 100%;
}

.m-filter {
  margin-bottom: 10px;
}

.m-search {
  margin-bottom: 8px;
}

.list-meta {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 8px;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
}

.card {
  cursor: pointer;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.row1 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.time {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin: 4px 0;
}

.summary {
  margin: 6px 0;
  white-space: pre-wrap;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
}

.name-link {
  border: none;
  background: transparent;
  color: var(--oc-primary, #a16207);
  font-weight: 600;
  cursor: pointer;
  padding: 0;
  font-size: inherit;
}

.name-link:hover {
  text-decoration: underline;
}

.muted {
  color: var(--oc-muted, #78716c);
}

.table-scroll {
  width: 100%;
  overflow-x: auto;
}

.scroll-sentinel {
  text-align: center;
  padding: 12px 0 8px;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}
</style>
