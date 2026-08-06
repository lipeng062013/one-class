<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listLearningApi, type LearningRecord } from '../../api/students'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useServerPagedList } from '../../composables/useServerPagedList'

type ListScope = 'mine' | 'all'

const router = useRouter()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()
const q = ref('')
/** 老师默认我的；负责人默认全部 */
const listScope = ref<ListScope>(auth.isTeacher ? 'mine' : 'all')

const {
  page,
  pageSize,
  total,
  rows,
  loading,
  loadingMore,
  hasMore: hasMoreInfinite,
  sentinelRef,
  load,
  resetAndLoad,
  onPageChange,
  onPageSizeChange,
  setupScrollObserver,
} = useServerPagedList<LearningRecord>({
  isCompact,
  getId: (r) => r.id,
  fetchPage: (p, size) =>
    listLearningApi({
      mine: listScope.value === 'mine',
      q: q.value.trim() || undefined,
      page: p,
      page_size: size,
    }),
})

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

const listSummary = computed(() => {
  const n = total.value
  return listScope.value === 'mine' ? `我填写的 ${n} 条` : `共 ${n} 条`
})

function runQuery() {
  collapseAll()
  void resetAndLoad()
}

function onScopeChange() {
  collapseAll()
  void resetAndLoad()
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

let searchTimer: ReturnType<typeof setTimeout> | null = null
watch(q, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    collapseAll()
    void resetAndLoad()
  }, 300)
})

onMounted(async () => {
  listScope.value = auth.isTeacher ? 'mine' : 'all'
  await load({ reset: true })
  await nextTick()
  if (sentinelRef.value) setupScrollObserver()
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
            共 <strong>{{ total }}</strong> 条
          </span>
        </div>
      </div>
      <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
        <el-form-item label="搜索">
          <el-input
            v-model="q"
            clearable
            placeholder="学生 / 科目 / 摘要 / 填写人"
            style="width: 260px"
            @keyup.enter="runQuery"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="runQuery">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-else class="compact-search">
      <el-input
        v-model="q"
        clearable
        placeholder="搜索学生 / 科目 / 摘要"
        @keyup.enter="runQuery"
      />
      <p class="list-summary compact">{{ listSummary }}</p>
    </div>

    <!-- wap/pad 卡片 + 服务端上拉 -->
    <div v-if="isCompact" v-loading="loading" class="card-list">
      <div
        v-for="row in rows"
        :key="row.id"
        class="learn-card"
        :class="{ 'is-expanded': isExpanded(row.id) }"
        @click="toggleCard(row.id)"
      >
        <div class="learn-card__main">
          <div class="learn-card__title">{{ row.student_name || '学员' }}</div>
          <el-tag size="small" effect="plain" round :type="classTagType[row.class_status] || 'info'">
            {{ classLabels[row.class_status] || row.class_status }}
          </el-tag>
        </div>
        <div class="learn-card__meta">
          {{ row.subject || '—' }} · {{ formatTime(row.class_date) }}
        </div>
        <div v-if="isExpanded(row.id)" class="learn-card__body" @click.stop>
          <p>{{ row.learning_summary }}</p>
          <div class="learn-card__ops">
            <el-button size="small" type="primary" plain @click="goStudent(row.student_id)">
              学员档案
            </el-button>
          </div>
        </div>
        <button type="button" class="learn-card__more" @click.stop="toggleForce(row.id)">
          {{ isExpanded(row.id) ? '收起' : '展开' }}
        </button>
      </div>
      <div v-if="!total && !loading" class="empty-hint">暂无学情</div>
      <div v-if="total" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="loadingMore" class="scroll-hint">加载中…</span>
        <span v-else-if="hasMoreInfinite" class="scroll-hint">上拉加载更多</span>
        <span v-else class="scroll-hint">已加载 {{ rows.length }} / {{ total }} 条</span>
      </div>
    </div>

    <template v-else>
      <el-card class="pc-table-card" shadow="never" v-loading="loading">
        <el-table :data="rows" row-key="id" stripe border :header-cell-style="pcHeaderStyle">
          <el-table-column label="学员" min-width="120">
            <template #default="{ row }">
              <el-button link type="primary" @click="goStudent(row.student_id)">
                {{ row.student_name || '—' }}
              </el-button>
            </template>
          </el-table-column>
          <el-table-column prop="subject" label="科目" width="100" />
          <el-table-column label="上课状态" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" effect="plain" round :type="classTagType[row.class_status] || 'info'">
                {{ classLabels[row.class_status] || row.class_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="learning_summary" label="学习情况" min-width="200" show-overflow-tooltip />
          <el-table-column prop="teacher_name" label="填写人" width="110" />
          <el-table-column label="上课时间" width="170">
            <template #default="{ row }">{{ formatTime(row.class_date) }}</template>
          </el-table-column>
        </el-table>
        <div v-if="!total && !loading" class="pc-table-empty">暂无学情，可点「编写学情」</div>
      </el-card>

      <PcPagerBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        @change="onPageChange"
        @size-change="onPageSizeChange"
      />
    </template>
  </div>
</template>

<style scoped>
.learning-page {
  width: 100%;
}

.scope-bar {
  margin: 8px 0 12px;
}

.compact-search {
  margin-bottom: 12px;
}

.list-summary.compact {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.learn-card {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--oc-card, #fffdf8);
}

.learn-card__main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.learn-card__title {
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.learn-card__meta {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.learn-card__body {
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--oc-ink, #44403c);
}

.learn-card__ops {
  margin-top: 10px;
}

.learn-card__more {
  margin-top: 8px;
  border: none;
  background: none;
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  padding: 0;
  cursor: pointer;
}

.empty-hint,
.pc-table-empty {
  padding: 24px;
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.scroll-sentinel {
  padding: 16px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */
</style>
