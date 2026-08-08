<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listLearningApi, type LearningRecord } from '../../api/students'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useServerPagedList } from '../../composables/useServerPagedList'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'

type ListScope = 'mine' | 'all'

const router = useRouter()
const auth = useAuthStore()
const { isApp } = useBreakpoint()
const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()
const q = ref('')
const filterVisible = ref(false)
const activeFilterCount = computed(() => Number(Boolean(q.value.trim())))
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
  loadMore,
  resetAndLoad,
  onPageChange,
  onPageSizeChange,
  setupScrollObserver,
} = useServerPagedList<LearningRecord>({
  isCompact: isApp,
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

const chipTone: Record<string, string> = {
  attended: 'is-ok',
  absent: 'is-danger',
  late: 'is-warn',
  leave: '',
  makeup: 'is-warn',
}

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const pageTitle = computed(() => (listScope.value === 'mine' ? '我的学情' : '全部学情'))

function nameInitial(name?: string | null) {
  return (name || '?').trim().slice(0, 1) || '?'
}

function summaryPreview(text?: string | null) {
  const t = (text || '').trim()
  if (!t) return '暂无学习情况摘要'
  return t.length > 72 ? `${t.slice(0, 72)}…` : t
}

function runQuery() {
  collapseAll()
  void resetAndLoad()
}

function resetFilters() {
  q.value = ''
  runQuery()
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

function formatDateShort(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleDateString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      weekday: 'short',
    })
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
    <div v-if="!isApp" class="page-toolbar">
      <el-page-header class="is-title-only" :content="pageTitle" />
      <div class="toolbar-right">
        <el-button class="tb-btn tb-btn--primary" type="primary" @click="goNew">
          <el-icon><EditPen /></el-icon>
          编写学情
        </el-button>
      </div>
    </div>

    <button v-else type="button" class="oc-app-cta learning-cta" @click="goNew">
      <span class="oc-app-cta__ico" aria-hidden="true">
        <el-icon><EditPen /></el-icon>
      </span>
      <span class="oc-app-cta__copy">
        <strong>编写学情</strong>
        <em>记录今日掌握、问题与作业</em>
      </span>
      <span class="oc-app-cta__go">
        去填写
        <el-icon><ArrowRight /></el-icon>
      </span>
    </button>

    <div class="scope-bar" :class="{ 'is-compact': isApp }">
      <el-radio-group
        v-model="listScope"
        class="scope-tabs"
        :class="{ 'oc-segment-like': isApp }"
        size="default"
        @change="onScopeChange"
      >
        <el-radio-button value="mine">我填写的</el-radio-button>
        <el-radio-button value="all">全部学情</el-radio-button>
      </el-radio-group>
    </div>

    <el-card v-if="!isApp" class="filters pc-filters" shadow="never">
      <div class="pc-filters-head">
        <div class="pc-filters-head-main">
          <span class="pc-filters-title">筛选</span>
        </div>
        <div class="pc-list-summary">
          <span class="pc-list-summary__label">{{ pageTitle }}</span>
          <span class="pc-list-summary__count">共 <strong>{{ total }}</strong> 条</span>
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

    <CompactFilterBar
      v-else
      :active-count="activeFilterCount"
      :total="total"
      label="条学情"
      @open="filterVisible = true"
    />
    <MobileFilterSheet
      v-model="filterVisible"
      :active-count="activeFilterCount"
      @apply="runQuery"
      @reset="resetFilters"
    >
      <el-form label-position="top" @submit.prevent="runQuery">
        <el-form-item label="搜索">
          <el-input v-model="q" clearable placeholder="学生 / 科目 / 摘要 / 填写人" />
        </el-form-item>
      </el-form>
    </MobileFilterSheet>

    <!-- wap/pad 卡片 + 服务端上拉 -->
    <div v-if="isApp" v-loading="loading" class="m-card-list learn-m-list">
      <div v-if="!total && !loading" class="oc-app-empty">
        <span class="learn-empty-ico" aria-hidden="true">📝</span>
        <strong>暂无学情</strong>
        <em>点击上方「编写学情」记录学员课堂表现</em>
        <el-button type="primary" class="learn-empty-cta" @click="goNew">编写学情</el-button>
      </div>

      <article
        v-for="row in rows"
        :key="row.id"
        class="m-card learn-m-card"
        :class="{ 'is-expanded': isExpanded(row.id) }"
        @click="toggleCard(row.id)"
      >
        <div class="m-card-head">
          <div class="learn-m-who">
            <span class="name-avatar">{{ nameInitial(row.student_name) }}</span>
            <div class="learn-m-text">
              <div class="m-card-title">
                {{ row.student_name || '学员' }}
                <el-tag
                  size="small"
                  effect="plain"
                  round
                  :type="classTagType[row.class_status] || 'info'"
                >
                  {{ classLabels[row.class_status] || row.class_status }}
                </el-tag>
              </div>
              <div class="learn-m-sub">{{ summaryPreview(row.learning_summary) }}</div>
            </div>
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

        <div class="oc-meta-chips learn-m-chips">
          <span v-if="row.subject" class="oc-meta-chip">
            <el-icon><Reading /></el-icon>
            {{ row.subject }}
          </span>
          <span class="oc-meta-chip" :class="chipTone[row.class_status]">
            <el-icon><Clock /></el-icon>
            {{ formatDateShort(row.class_date) }}
          </span>
          <span v-if="row.teacher_name" class="oc-meta-chip">
            <el-icon><User /></el-icon>
            {{ row.teacher_name }}
          </span>
        </div>

        <div v-if="isExpanded(row.id)" class="m-card-acc-body" @click.stop>
          <p class="learn-m-summary">{{ row.learning_summary || '—' }}</p>
          <p v-if="row.homework_note" class="learn-m-homework">
            <span class="k">作业</span>{{ row.homework_note }}
          </p>
          <p v-if="row.notes" class="learn-m-notes">
            <span class="k">备注</span>{{ row.notes }}
          </p>
          <div class="learn-m-foot">上课 {{ formatTime(row.class_date) }}</div>
          <div class="m-card-actions">
            <el-button size="small" type="primary" plain @click="goStudent(row.student_id)">
              学员档案
            </el-button>
          </div>
        </div>
      </article>

      <div ref="sentinelRef" class="list-load-sentinel">
        <ListLoadStatus
          :has-more="hasMoreInfinite"
          :loading="loadingMore"
          :loaded="rows.length"
          :total="total"
          @more="loadMore"
          @retry="loadMore"
        />
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

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.learning-cta {
  margin-bottom: 12px;
}

.scope-bar {
  margin: 8px 0 12px;
}

.scope-bar.is-compact {
  margin: 0 0 10px;
}

.card-list,
.learn-m-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.learn-m-who {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.learn-m-text {
  min-width: 0;
  flex: 1;
}

.learn-m-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.learn-m-chips {
  margin-top: 10px;
}

.learn-m-summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--oc-ink, #44403c);
  white-space: pre-wrap;
}

.learn-m-homework,
.learn-m-notes {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--oc-muted, #78716c);
}

.learn-m-homework .k,
.learn-m-notes .k {
  display: inline-block;
  margin-right: 6px;
  font-weight: 650;
  color: #a16207;
}

.learn-m-foot {
  margin-top: 10px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.learn-empty-ico {
  font-size: 28px;
  line-height: 1;
}

.learn-empty-cta {
  margin-top: 8px;
  min-height: 40px;
  border-radius: 12px;
  font-weight: 650;
}

.pc-table-empty {
  padding: 24px;
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

@media (max-width: 1199px) {
  .learning-page {
    padding-bottom: 8px;
  }

  .scope-tabs.oc-segment-like {
    display: flex;
    width: 100%;
    padding: 4px;
    border-radius: 14px;
    border: 1px solid rgba(181, 145, 83, 0.2);
    background: #f3ebe0;
  }

  .scope-tabs.oc-segment-like :deep(.el-radio-button) {
    flex: 1;
  }

  .scope-tabs.oc-segment-like :deep(.el-radio-button__inner) {
    width: 100%;
    border: 0 !important;
    border-radius: 11px !important;
    box-shadow: none !important;
    background: transparent;
    color: #78716c;
    font-weight: 650;
    min-height: 40px;
    padding: 0 10px;
  }

  .scope-tabs.oc-segment-like :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
    color: #fffdf8 !important;
    background: linear-gradient(145deg, #c07a12, #a16207) !important;
    box-shadow: 0 4px 12px rgba(161, 98, 7, 0.25) !important;
  }

  .learn-m-list {
    gap: 12px;
  }

  .learn-m-card {
    padding: 14px 14px 12px 16px;
    border-radius: 18px !important;
    border: 1px solid rgba(181, 145, 83, 0.3) !important;
    background:
      linear-gradient(155deg, rgba(255, 255, 255, 0.92), transparent 46%),
      #fffdf8 !important;
    box-shadow:
      0 12px 28px rgba(88, 60, 24, 0.09),
      0 2px 0 rgba(255, 255, 255, 0.9) inset !important;
  }

  .learn-m-card .m-card-title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-size: 15px;
    font-weight: 720;
  }

  .learn-m-card .m-card-actions {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed rgba(181, 145, 83, 0.22);
  }

  .learn-m-card .m-card-actions .el-button {
    min-height: 36px;
    border-radius: 10px;
    font-weight: 650;
  }

  .name-avatar {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 15px;
    font-weight: 750;
    color: #fffdf8;
    background: linear-gradient(145deg, #d97706, #a16207);
    box-shadow: 0 4px 10px rgba(161, 98, 7, 0.22);
  }
}
</style>
