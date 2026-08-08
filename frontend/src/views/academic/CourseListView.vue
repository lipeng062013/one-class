<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteCourseApi,
  listCoursesApi,
  updateCourseApi,
  type Course,
} from '../../api/academic'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useServerPagedList } from '../../composables/useServerPagedList'

const router = useRouter()
const auth = useAuthStore()
const { isApp } = useBreakpoint()
const keyword = ref('')
const typeGroup = reactive({ multi: false, one: false })
const statusGroup = reactive({ on: false, off: false })
const selectedIds = ref<number[]>([])
const filterVisible = ref(false)

const canAdmin = computed(() => auth.hasPermission('academic.courses_admin'))

const activeFilterCount = computed(
  () =>
    Number(Boolean(keyword.value.trim())) +
    Number(typeGroup.multi || typeGroup.one) +
    Number(statusGroup.on || statusGroup.off),
)

const {
  page,
  pageSize,
  total,
  rows,
  loading,
  loadingMore,
  hasMore,
  load,
  loadMore,
  resetAndLoad,
  onPageChange,
  onPageSizeChange,
} = useServerPagedList<Course>({
  isCompact: isApp,
  getId: (r) => r.id,
  fetchPage: async (p, size) => {
    let course_type: string | undefined
    if (typeGroup.multi && !typeGroup.one) course_type = 'group'
    if (typeGroup.one && !typeGroup.multi) course_type = 'one_to_one'
    let enabled: boolean | undefined
    if (statusGroup.on && !statusGroup.off) enabled = true
    if (statusGroup.off && !statusGroup.on) enabled = false
    return listCoursesApi({
      q: keyword.value.trim() || undefined,
      course_type,
      enabled,
      page: p,
      page_size: size,
    })
  },
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function nameInitial(name?: string | null) {
  return (name || '?').trim().slice(0, 1)
}

function onSelectionChange(sel: Course[]) {
  selectedIds.value = sel.map((r) => r.id)
}

function goCreate() {
  void router.push('/academic/courses/new')
}

function goEdit(row: Course) {
  void router.push(`/academic/courses/${row.id}/edit`)
}

async function onToggle(row: Course, val: boolean) {
  try {
    const updated = await updateCourseApi(row.id, { enabled: val })
    row.enabled = updated.enabled
    ElMessage.success(val ? '已启用' : '已停用')
  } catch {
    /* interceptor */
  }
}

async function onDelete(row: Course) {
  try {
    await ElMessageBox.confirm(`确定删除课程「${row.name}」？`, '删除确认', { type: 'warning' })
    await deleteCourseApi(row.id)
    ElMessage.success('已删除')
    await resetAndLoad()
  } catch {
    /* cancel or error */
  }
}

function runQuery() {
  selectedIds.value = []
  void resetAndLoad()
}

function resetFilters() {
  keyword.value = ''
  typeGroup.multi = false
  typeGroup.one = false
  statusGroup.on = false
  statusGroup.off = false
  runQuery()
}

watch(isApp, () => {
  selectedIds.value = []
})

onMounted(() => {
  void load({ reset: true })
})
</script>

<template>
  <div class="course-list-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="课程管理" />
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <div v-if="!isApp" class="filter-row">
        <el-input
          v-model="keyword"
          clearable
          placeholder="请输入课程名称"
          class="filter-search"
          @keyup.enter="runQuery"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <div class="check-group">
          <span class="check-label">课程类型：</span>
          <el-checkbox v-model="typeGroup.multi">一对多</el-checkbox>
          <el-checkbox v-model="typeGroup.one">一对一</el-checkbox>
        </div>
        <div class="check-group">
          <span class="check-label">课程状态：</span>
          <el-checkbox v-model="statusGroup.on">启用</el-checkbox>
          <el-checkbox v-model="statusGroup.off">停用</el-checkbox>
        </div>
        <el-button type="primary" @click="runQuery">查询</el-button>
      </div>

      <div v-if="!isApp" class="action-row">
        <el-button
          v-if="canAdmin"
          type="primary"
          class="tb-btn tb-btn--primary"
          @click="goCreate"
        >
          <el-icon><Plus /></el-icon>
          新建课程
        </el-button>
      </div>

      <CompactFilterBar
        v-if="isApp"
        :active-count="activeFilterCount"
        :total="total"
        label="门课程"
        @open="filterVisible = true"
      />

      <div v-if="isApp && canAdmin" class="app-cta-row">
        <el-button type="primary" class="tb-btn tb-btn--primary app-cta-btn" @click="goCreate">
          <el-icon><Plus /></el-icon>
          新建课程
        </el-button>
      </div>

      <div v-if="isApp" class="m-card-list course-m-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty course-empty">
          <span class="course-empty-ico" aria-hidden="true">📚</span>
          <strong>暂无课程</strong>
          <em>创建课程后可用于开班、排课与报名</em>
          <el-button
            v-if="canAdmin"
            type="primary"
            class="tb-btn tb-btn--primary"
            size="small"
            @click="goCreate"
          >
            新建课程
          </el-button>
        </div>

        <article v-for="row in rows" :key="row.id" class="m-card course-m-card">
          <div class="m-card-head">
            <div class="course-m-who">
              <span class="course-avatar" :style="{ background: row.color || undefined }">
                {{ nameInitial(row.name) }}
              </span>
              <div class="course-m-text">
                <div class="m-card-title">
                  {{ row.name }}
                  <el-tag
                    size="small"
                    effect="plain"
                    round
                    :type="row.enabled ? 'success' : 'info'"
                  >
                    {{ row.enabled ? '启用' : '停用' }}
                  </el-tag>
                </div>
                <div class="course-m-sub">{{ row.type_label || '未设类型' }}</div>
              </div>
            </div>
            <el-switch
              :model-value="row.enabled"
              :disabled="!canAdmin"
              size="small"
              @change="(v: string | number | boolean) => onToggle(row, !!v)"
            />
          </div>

          <div class="course-m-chips">
            <span class="cm-chip">{{ row.type_label || '类型 —' }}</span>
            <span class="cm-chip">{{ row.billing_label || '收费 —' }}</span>
            <span class="cm-chip tone-gold">{{ row.price_label || '定价 —' }}</span>
            <span class="cm-chip">在读 {{ row.student_count }} 人</span>
          </div>

          <div v-if="canAdmin" class="m-card-actions">
            <el-button size="small" type="primary" plain @click="goEdit(row)">编辑</el-button>
            <el-button size="small" plain type="danger" @click="onDelete(row)">删除</el-button>
          </div>
        </article>

        <div ref="sentinelRef" class="list-load-sentinel">
          <ListLoadStatus
            :has-more="hasMore"
            :loading="loadingMore"
            :loaded="rows.length"
            :total="total"
            @more="loadMore"
            @retry="loadMore"
          />
        </div>
      </div>

      <div v-else class="oc-compact-table-wrap">
        <el-table
          :data="rows"
          row-key="id"
          stripe
          border
          class="data-table"
          :header-cell-style="pcHeaderStyle"
          @selection-change="onSelectionChange"
        >
          <el-table-column type="selection" width="44" />
          <el-table-column prop="name" label="课程名称" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="pc-title-text">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="type_label" label="类型" width="100" align="center" />
          <el-table-column prop="billing_label" label="收费方式" width="100" align="center" />
          <el-table-column prop="price_label" label="定价标准" min-width="160" />
          <el-table-column prop="student_count" label="在读学员数" width="110" align="center" />
          <el-table-column label="启用状态" width="100" align="center">
            <template #default="{ row }">
              <el-switch
                :model-value="row.enabled"
                :disabled="!canAdmin"
                @change="(v: string | number | boolean) => onToggle(row, !!v)"
              />
            </template>
          </el-table-column>
          <el-table-column v-if="canAdmin" label="操作" width="140" fixed="right" align="right">
            <template #default="{ row }">
              <div class="pc-ops">
                <el-button link type="primary" @click="goEdit(row)">编辑</el-button>
                <el-button link type="primary" @click="onDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <MobileFilterSheet
      v-model="filterVisible"
      :active-count="activeFilterCount"
      @apply="runQuery"
      @reset="resetFilters"
    >
      <el-form label-position="top" @submit.prevent="runQuery">
        <el-form-item label="课程名称">
          <el-input v-model="keyword" clearable placeholder="请输入课程名称" @keyup.enter="runQuery" />
        </el-form-item>
        <el-form-item label="课程类型">
          <el-checkbox v-model="typeGroup.multi">一对多</el-checkbox>
          <el-checkbox v-model="typeGroup.one">一对一</el-checkbox>
        </el-form-item>
        <el-form-item label="课程状态">
          <el-checkbox v-model="statusGroup.on">启用</el-checkbox>
          <el-checkbox v-model="statusGroup.off">停用</el-checkbox>
        </el-form-item>
      </el-form>
    </MobileFilterSheet>

    <PcPagerBar
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="onPageChange"
      @size-change="onPageSizeChange"
    />
  </div>
</template>

<style scoped>
.course-list-page {
  width: 100%;
}

.module-card {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.module-card :deep(.el-card__body) {
  padding: 12px 16px 8px;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-bottom: 12px;
}

.filter-search {
  width: min(280px, 100%);
}

.check-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  flex-wrap: wrap;
}

.check-label {
  color: var(--oc-muted, #78716c);
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.app-cta-row {
  margin: 0 0 12px;
}

.app-cta-btn {
  width: 100%;
  min-height: 46px;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 720;
}

.pc-title-text {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.pc-ops {
  display: inline-flex;
  gap: 4px;
}

.course-m-list {
  margin-top: 2px;
}

.course-m-card {
  -webkit-tap-highlight-color: transparent;
}

.course-m-who {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.course-m-text {
  min-width: 0;
}

.course-m-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.course-m-card .m-card-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.course-m-card .m-card-head {
  margin-bottom: 0;
  align-items: flex-start;
}

.course-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 15px;
  font-weight: 750;
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.18);
}

.course-m-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.cm-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 26px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #57534e;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(181, 145, 83, 0.2);
  line-height: 1.3;
  word-break: break-word;
}

.cm-chip.tone-gold {
  color: #a16207;
  background: #fff7ed;
  border-color: #fed7aa;
}

.course-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 36px 20px !important;
  text-align: center;
}

.course-empty-ico {
  font-size: 28px;
  line-height: 1;
  filter: grayscale(0.15);
}

.course-empty strong {
  font-size: 15px;
  font-weight: 700;
  color: #44403c;
}

.course-empty em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
  line-height: 1.4;
  max-width: 240px;
}

.course-empty .el-button {
  margin-top: 6px;
  min-height: 40px;
  min-width: 120px;
  border-radius: 12px;
}

@media (max-width: 1199px) {
  .module-card {
    margin-top: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .module-card :deep(.el-card__body) {
    padding: 0;
  }

  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-search {
    width: 100%;
  }

  .action-row .el-button {
    width: 100%;
  }

  .app-cta-btn {
    min-height: 48px;
  }
}
</style>
