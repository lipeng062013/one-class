<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import { listAcademicTeachersApi, type TeacherManage } from '../../api/academic'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'

const keyword = ref('')
const loading = ref(false)
const rows = ref<TeacherManage[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const collapsedGroups = ref<TeacherGroupKey[]>([])
const { isCompact } = useBreakpoint()

type TeacherGroupKey = 'owner' | 'manager' | 'teacher' | 'other'

interface TeacherGroup {
  key: TeacherGroupKey
  label: string
  description: string
  rows: TeacherManage[]
}

const groupMeta: Record<TeacherGroupKey, Pick<TeacherGroup, 'label' | 'description'>> = {
  owner: { label: '负责人', description: '机构负责人' },
  manager: { label: '学管师', description: '班主任与学员管理' },
  teacher: { label: '授课老师', description: '日常授课' },
  other: { label: '其他', description: '其他教学人员' },
}

function teacherGroupKey(row: TeacherManage): TeacherGroupKey {
  if (row.role_code === 'admin' || row.role === '负责人') return 'owner'
  if (
    row.role_code === 'cr' ||
    row.role_code === 'academic_manager' ||
    row.role.includes('学管师') ||
    row.role.startsWith('CR')
  ) {
    return 'manager'
  }
  if (row.role_code === 'teacher' || row.role === '老师') return 'teacher'
  return 'other'
}

const groupedRows = computed<TeacherGroup[]>(() => {
  const order: TeacherGroupKey[] = ['owner', 'manager', 'teacher', 'other']
  return order
    .map((key) => ({
      key,
      ...groupMeta[key],
      rows: rows.value.filter((row) => teacherGroupKey(row) === key),
    }))
    .filter((group) => group.rows.length > 0)
})

const isPaginated = computed(() => total.value > pageSize.value)

function isGroupCollapsed(key: TeacherGroupKey) {
  return collapsedGroups.value.includes(key)
}

function toggleGroup(key: TeacherGroupKey) {
  collapsedGroups.value = isGroupCollapsed(key)
    ? collapsedGroups.value.filter((item) => item !== key)
    : [...collapsedGroups.value, key]
}

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

async function load() {
  loading.value = true
  try {
    const res = await listAcademicTeachersApi({
      q: keyword.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function runQuery() {
  page.value = 1
  void load()
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="teacher-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="老师管理" />
    </div>

    <el-card class="pc-filters" shadow="never">
      <el-form :inline="true" class="pc-filter-form" @submit.prevent="runQuery">
        <el-form-item label="姓名">
          <el-input
            v-model="keyword"
            clearable
            placeholder="搜索老师"
            :style="isCompact ? 'width: 100%' : 'width: 180px'"
            @keyup.enter="runQuery"
          />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="runQuery">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- wap/pad 卡片 -->
    <div v-if="isCompact" v-loading="loading" class="teacher-m">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无老师</div>
      <section
        v-for="group in groupedRows"
        :key="group.key"
        class="teacher-group"
        :class="`is-${group.key}`"
      >
        <button
          type="button"
          class="group-heading"
          :class="`is-${group.key}`"
          :aria-expanded="!isGroupCollapsed(group.key)"
          @click="toggleGroup(group.key)"
        >
          <span class="group-mark" aria-hidden="true"></span>
          <div class="group-title-wrap">
            <h2>{{ group.label }}</h2>
            <span>{{ group.description }}</span>
          </div>
          <span class="group-count">{{ group.rows.length }} 人</span>
          <el-icon
            class="group-chevron"
            :class="{ 'is-collapsed': isGroupCollapsed(group.key) }"
            aria-hidden="true"
          >
            <ArrowDown />
          </el-icon>
        </button>
        <div v-show="!isGroupCollapsed(group.key)" class="m-card-list">
          <div v-for="row in group.rows" :key="row.id" class="m-card">
            <div class="m-card-head">
              <div class="pc-name-cell">
                <span class="pc-avatar">{{ (row.name || '?').slice(0, 1) }}</span>
                <div>
                  <div class="m-card-title">{{ row.name }}</div>
                  <div class="pc-muted">{{ row.username }}</div>
                </div>
              </div>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
                {{ row.status }}
              </el-tag>
            </div>
            <div class="m-card-meta">
              <span><span class="k">角色</span>{{ row.role || '—' }}</span>
              <span><span class="k">带班</span>{{ row.class_count }} 个</span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-else v-loading="loading" class="pc-group-list">
      <el-empty v-if="!rows.length && !loading" description="暂无老师" :image-size="80" />
      <section
        v-for="group in groupedRows"
        :key="group.key"
        class="teacher-group pc-teacher-group"
        :class="`is-${group.key}`"
      >
        <button
          type="button"
          class="group-heading"
          :class="`is-${group.key}`"
          :aria-expanded="!isGroupCollapsed(group.key)"
          @click="toggleGroup(group.key)"
        >
          <span class="group-mark" aria-hidden="true"></span>
          <div class="group-title-wrap">
            <h2>{{ group.label }}</h2>
            <span>{{ group.description }}</span>
          </div>
          <span class="group-count">
            {{ isPaginated ? `本页 ${group.rows.length} 人` : `${group.rows.length} 人` }}
          </span>
          <el-icon
            class="group-chevron"
            :class="{ 'is-collapsed': isGroupCollapsed(group.key) }"
            aria-hidden="true"
          >
            <ArrowDown />
          </el-icon>
        </button>
        <el-card
          v-show="!isGroupCollapsed(group.key)"
          class="pc-table-card group-table-card"
          shadow="never"
        >
          <div class="oc-compact-table-wrap">
            <el-table :data="group.rows" row-key="id" stripe border :header-cell-style="pcHeaderStyle">
              <el-table-column label="老师" min-width="160">
                <template #default="{ row }">
                  <div class="pc-name-cell">
                    <span class="pc-avatar">{{ (row.name || '?').slice(0, 1) }}</span>
                    <div>
                      <div class="pc-name-text">{{ row.name }}</div>
                      <div class="pc-muted">{{ row.username }}</div>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="role" label="角色" width="180" align="center" />
              <el-table-column prop="class_count" label="带班数" width="100" align="center" />
              <el-table-column prop="status" label="状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-card>
      </section>
      <p v-if="total" class="table-hint">共 {{ total }} 人（来自系统账号 · 教学人员）</p>
    </div>

    <PcPagerBar
      v-if="isPaginated"
      class="teacher-pager"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="load"
    />
  </div>
</template>

<style scoped>
.teacher-page {
  width: 100%;
  --teacher-surface: #fffdf8;
  --teacher-surface-muted: #f7f2e9;
}

.table-hint {
  margin: 10px 4px 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.teacher-m {
  margin-top: 12px;
}

.pc-group-list {
  min-height: 180px;
}

.teacher-group + .teacher-group {
  margin-top: 18px;
}

.group-heading {
  width: 100%;
  display: flex;
  align-items: center;
  min-height: 50px;
  padding: 0 16px;
  border: 1px solid var(--group-border);
  border-radius: 6px 6px 0 0;
  background: var(--group-bg);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(68, 64, 60, 0.035);
  transition: filter 0.18s ease, box-shadow 0.18s ease;
}

.group-heading:hover {
  filter: brightness(0.985);
  box-shadow: 0 4px 12px rgba(68, 64, 60, 0.07);
}

.group-heading:focus-visible {
  outline: 2px solid var(--group-accent);
  outline-offset: 2px;
}

.group-heading[aria-expanded='false'] {
  border-radius: 6px;
}

.group-heading.is-owner {
  --group-accent: #a96c12;
  --group-bg: #fbf3e3;
  --group-border: #ead8b6;
}

.group-heading.is-manager {
  --group-accent: #28756a;
  --group-bg: #edf7f4;
  --group-border: #cae5df;
}

.group-heading.is-teacher {
  --group-accent: #476f9c;
  --group-bg: #eff5fa;
  --group-border: #d2dfeb;
}

.group-heading.is-other {
  --group-accent: #6b7280;
  --group-bg: #f4f4f5;
  --group-border: #dedee1;
}

.group-mark {
  width: 4px;
  height: 26px;
  margin-right: 10px;
  border-radius: 2px;
  background: var(--group-accent);
}

.group-title-wrap {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.group-title-wrap h2 {
  margin: 0;
  color: var(--oc-ink, #44403c);
  font-size: 15px;
  font-weight: 700;
}

.group-title-wrap span {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.group-count {
  flex-shrink: 0;
  margin-left: auto;
  color: var(--group-accent);
  font-size: 12px;
  font-weight: 600;
}

.group-chevron {
  flex-shrink: 0;
  margin-left: 12px;
  color: var(--group-accent);
  font-size: 20px;
  line-height: 1;
  transform: rotate(0deg);
  transition: transform 0.18s ease;
}

.group-chevron.is-collapsed {
  transform: rotate(-90deg);
}

.group-table-card {
  border-top: 0;
  border-radius: 0 0 6px 6px;
  background: var(--teacher-surface);
  box-shadow: 0 4px 14px rgba(68, 64, 60, 0.045);
}

.group-table-card :deep(.el-card__body) {
  padding: 0;
}

.group-table-card :deep(.el-table) {
  --el-table-border-color: #ede6da;
  --el-table-header-bg-color: var(--teacher-surface-muted);
  --el-table-row-hover-bg-color: #fffaf0;
  background: var(--teacher-surface);
}

.group-table-card :deep(.el-table th.el-table__cell) {
  height: 42px;
  color: #6b6257;
  font-size: 12px;
  letter-spacing: 0;
}

.group-table-card :deep(.el-table td.el-table__cell) {
  height: 58px;
  color: #57504a;
}

.pc-teacher-group.is-owner .pc-avatar {
  background: linear-gradient(145deg, #e7c98e, #b9852b);
}

.pc-teacher-group.is-manager .pc-avatar,
.teacher-m .is-manager .pc-avatar {
  background: linear-gradient(145deg, #9ccfc3, #398c7d);
}

.pc-teacher-group.is-teacher .pc-avatar,
.teacher-m .is-teacher .pc-avatar {
  background: linear-gradient(145deg, #a9c5df, #527da7);
}

.teacher-page :deep(.teacher-pager.pager-bar.pc-pager) {
  position: static;
  flex: 0 0 auto;
  margin-top: 18px;
  box-shadow: none;
}

.pc-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.pc-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.pc-muted {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.pc-name-text {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.m-card-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

@media (max-width: 767px) {
  .teacher-group + .teacher-group {
    margin-top: 16px;
  }

  .group-heading {
    min-height: 42px;
    padding: 0 12px;
    border-radius: 6px;
  }

  .teacher-page :deep(.teacher-pager.pager-bar.pc-pager) {
    margin-top: 16px;
    padding: 8px;
  }

  .group-title-wrap span {
    display: none;
  }

  .teacher-group .m-card-list {
    margin-top: 8px;
  }
}
</style>
