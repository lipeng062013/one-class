<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteCourseApi,
  listCoursesApi,
  updateCourseApi,
  type Course,
} from '../../api/academic'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'

const router = useRouter()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const keyword = ref('')
const typeGroup = reactive({ multi: false, one: false })
const statusGroup = reactive({ on: false, off: false })
const selectedIds = ref<number[]>([])
const rows = ref<Course[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

async function load() {
  loading.value = true
  try {
    let course_type: string | undefined
    if (typeGroup.multi && !typeGroup.one) course_type = 'group'
    if (typeGroup.one && !typeGroup.multi) course_type = 'one_to_one'
    let enabled: boolean | undefined
    if (statusGroup.on && !statusGroup.off) enabled = true
    if (statusGroup.off && !statusGroup.on) enabled = false
    const res = await listCoursesApi({
      q: keyword.value.trim() || undefined,
      course_type,
      enabled,
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

function onSelectionChange(sel: Course[]) {
  selectedIds.value = sel.map((r) => r.id)
}

function goCreate() {
  void router.push('/academic/courses/new')
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
    await load()
  } catch {
    /* cancel or error */
  }
}

function runQuery() {
  page.value = 1
  void load()
}

watch([() => typeGroup.multi, () => typeGroup.one, () => statusGroup.on, () => statusGroup.off], () => {
  page.value = 1
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="course-list-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="课程管理" />
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <div class="filter-row">
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

      <div class="action-row">
        <el-button
          v-if="auth.hasPermission('academic.courses_admin')"
          type="primary"
          class="tb-btn tb-btn--primary"
          @click="goCreate"
        >
          新建课程
        </el-button>
      </div>

      <div v-if="isCompact" class="m-card-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无课程</div>
        <div v-for="row in rows" :key="row.id" class="m-card">
          <div class="m-card-head">
            <div class="m-card-title">{{ row.name }}</div>
            <el-switch
              :model-value="row.enabled"
              :disabled="!auth.hasPermission('academic.courses_admin')"
              size="small"
              @change="(v: string | number | boolean) => onToggle(row, !!v)"
            />
          </div>
          <div class="m-card-meta">
            <span><span class="k">类型</span>{{ row.type_label }}</span>
            <span><span class="k">收费</span>{{ row.billing_label }}</span>
            <span><span class="k">定价</span>{{ row.price_label }}</span>
            <span><span class="k">在读</span>{{ row.student_count }}人</span>
          </div>
          <div v-if="auth.hasPermission('academic.courses_admin')" class="m-card-actions">
            <el-button size="small" type="primary" plain @click="router.push(`/academic/courses/${row.id}/edit`)">
              编辑
            </el-button>
            <el-button size="small" @click="onDelete(row)">删除</el-button>
          </div>
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
                :disabled="!auth.hasPermission('academic.courses_admin')"
                @change="(v: string | number | boolean) => onToggle(row, !!v)"
              />
            </template>
          </el-table-column>
          <el-table-column v-if="auth.hasPermission('academic.courses_admin')" label="操作" width="140" fixed="right" align="right">
            <template #default="{ row }">
              <div class="pc-ops">
                <el-button link type="primary" @click="router.push(`/academic/courses/${row.id}/edit`)">
                  编辑
                </el-button>
                <el-button link type="primary" @click="onDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <PcPagerBar
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="load"
    />
  </div>
</template>

<style scoped>
.course-list-page {
  width: 100%;
}

.page-toolbar :deep(.el-page-header__left .el-page-header__back),
.page-toolbar :deep(.el-page-header__left > .el-divider) {
  /* 标题保留，仅藏返回 */
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

.pc-title-text {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.pc-ops {
  display: inline-flex;
  gap: 4px;
}

@media (max-width: 991px) {
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
}
</style>
