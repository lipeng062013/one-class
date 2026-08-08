<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  addClassStudentsApi,
  getScheduleApi,
  listCourseEligibleStudentsApi,
  type CourseEligibleStudent,
  type ScheduleLessonDetail,
  type ScheduleLessonMember,
} from '../../api/academic'
import AppSheet from '../../components/AppSheet.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'

const props = defineProps<{
  modelValue: boolean
  lessonId: number | null
  canManage?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  edit: [ScheduleLessonDetail]
  remove: [ScheduleLessonDetail]
  roll: [ScheduleLessonDetail]
  refreshed: []
}>()

const { isApp } = useBreakpoint()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const loading = ref(false)
const detail = ref<ScheduleLessonDetail | null>(null)

const addVisible = ref(false)
const addSaving = ref(false)
const studentOptions = ref<CourseEligibleStudent[]>([])
const pickStudentIds = ref<number[]>([])

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const nameInitial = computed(() => (detail.value?.class_name || '?').trim().slice(0, 1))
const isDone = computed(() => detail.value?.status === 'completed')
const memberCount = computed(
  () => detail.value?.members?.length ?? detail.value?.member_count ?? 0,
)

const isRollable = computed(() => {
  if (!detail.value || !props.canManage) return false
  if (detail.value.status !== 'scheduled') return false
  return canRollCall(detail.value)
})

function formatTimeRange(d: ScheduleLessonDetail | null) {
  if (!d?.start_at) return '—'
  const s = new Date(d.start_at)
  const e = new Date(d.end_at)
  if (Number.isNaN(s.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const datePart = `${s.getFullYear()}-${pad(s.getMonth() + 1)}-${pad(s.getDate())}（${weekNames[s.getDay()]}）`
  const timePart = `${pad(s.getHours())}:${pad(s.getMinutes())}-${pad(e.getHours())}:${pad(e.getMinutes())}`
  return `${datePart} ${timePart}`
}

function hoursLabel(n?: number | null) {
  const v = Number(n ?? 0)
  if (!v) return '—'
  return v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function remainLabel(n?: number | null) {
  const v = Number(n ?? 0)
  const t = v.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  return `${t}课时`
}

function deductedLabel(n?: number | null) {
  if (n === null || n === undefined) return '—'
  const value = Number(n)
  const text = value.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  return `${text}课时`
}

function memberInitial(name?: string | null) {
  return (name || '?').trim().slice(0, 1)
}

async function loadDetail() {
  if (!props.lessonId) {
    detail.value = null
    return
  }
  loading.value = true
  try {
    detail.value = await getScheduleApi(props.lessonId)
  } catch {
    detail.value = null
    ElMessage.error('加载课次详情失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.modelValue, props.lessonId] as const,
  ([open, id]) => {
    if (open && id) void loadDetail()
    if (!open) {
      addVisible.value = false
      pickStudentIds.value = []
    }
  },
)

function onEdit() {
  if (!detail.value) return
  emit('edit', detail.value)
}

function onRemove() {
  if (!detail.value) return
  emit('remove', detail.value)
}

function canRollCall(lesson: ScheduleLessonDetail) {
  if (lesson.status !== 'scheduled') return false
  if (typeof lesson.can_roll_call === 'boolean') return lesson.can_roll_call
  const start = new Date(lesson.start_at)
  if (Number.isNaN(start.getTime())) return false
  const lessonDay = new Date(start)
  lessonDay.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return lessonDay.getTime() <= today.getTime()
}

function onRoll() {
  if (!detail.value) return
  if (!canRollCall(detail.value)) {
    ElMessage.warning('不能对未来课程点名，仅可点当天及过去的课次')
    return
  }
  emit('roll', detail.value)
}

function onLeave(row: ScheduleLessonMember) {
  ElMessage.info(`请在点名时将「${row.name}」标记为请假`)
}

function onTransfer(row: ScheduleLessonMember) {
  ElMessage.info(`「${row.name}」调课：请使用「编辑课次」调整本节约课时间，或在班级中调整学员`)
}

async function searchStudents(q: string) {
  if (!q.trim()) {
    studentOptions.value = []
    return
  }
  if (!detail.value?.course_id) return
  const res = await listCourseEligibleStudentsApi(detail.value.course_id, {
    q: q.trim(),
    page: 1,
    page_size: 20,
  }).catch(() => ({ items: [] as CourseEligibleStudent[] }))
  const exist = new Set((detail.value?.members || []).map((m) => m.id))
  studentOptions.value = res.items.filter((s) => !exist.has(s.id))
}

function openAddStudent() {
  pickStudentIds.value = []
  studentOptions.value = []
  addVisible.value = true
}

async function submitAddStudent() {
  if (!detail.value?.class_id) return
  if (!pickStudentIds.value.length) {
    ElMessage.warning('请选择学员')
    return
  }
  addSaving.value = true
  try {
    await addClassStudentsApi(detail.value.class_id, pickStudentIds.value)
    ElMessage.success('已添加学员到班级')
    addVisible.value = false
    await loadDetail()
    emit('refreshed')
  } catch {
    /* interceptor */
  } finally {
    addSaving.value = false
  }
}
</script>

<template>
  <AppSheet
    v-model="visible"
    title="课次详情"
    size="680px"
    modal-class="lesson-detail-drawer"
  >
    <div v-loading="loading" class="ld-body">
      <template v-if="detail">
        <div class="ld-hero">
          <div class="ld-hero-top">
            <div class="ld-identity">
              <div class="ld-avatar" :class="{ 'is-done': isDone }">{{ nameInitial }}</div>
              <div class="ld-hero-main">
                <div class="ld-title-wrap">
                  <div class="ld-title">{{ detail.class_name || '未命名班级' }}</div>
                  <el-tag
                    size="small"
                    effect="plain"
                    :type="isDone ? 'success' : 'warning'"
                  >
                    {{ detail.status_label || detail.status }}
                  </el-tag>
                </div>
                <div class="ld-hero-meta">
                  <span v-if="detail.course_name" class="meta-item">
                    <el-icon><Reading /></el-icon>
                    {{ detail.course_name }}
                  </span>
                  <span class="meta-item">
                    <el-icon><User /></el-icon>
                    {{ detail.teachers || '待分配老师' }}
                  </span>
                  <span class="meta-item">
                    <el-icon><Clock /></el-icon>
                    {{ formatTimeRange(detail) }}
                  </span>
                </div>
              </div>
            </div>
            <div v-if="canManage" class="ld-head-actions">
              <el-button type="primary" class="tb-btn tb-btn--primary" size="small" @click="onEdit">
                编辑课次
              </el-button>
              <el-button class="tb-btn" plain size="small" type="danger" @click="onRemove">
                删除课次
              </el-button>
            </div>
          </div>

          <div class="ld-stat-row">
            <div class="ld-stat tone-gold">
              <div class="ld-stat-label">授课课时</div>
              <div class="ld-stat-value">
                {{ hoursLabel(detail.hours_per_session ?? detail.hours) }}
              </div>
            </div>
            <div class="ld-stat tone-amber">
              <div class="ld-stat-label">上课教室</div>
              <div class="ld-stat-value sm">{{ detail.room || '待定' }}</div>
            </div>
            <div class="ld-stat tone-green">
              <div class="ld-stat-label">人数/容量</div>
              <div class="ld-stat-value sm">{{ detail.capacity_label || '—' }}</div>
            </div>
            <div class="ld-stat tone-stone">
              <div class="ld-stat-label">学员</div>
              <div class="ld-stat-value">{{ memberCount }}</div>
            </div>
          </div>
        </div>

        <section class="ld-section">
          <h4 class="ld-sec-title">课次信息</h4>
          <div class="ld-grid">
            <div class="ld-item">
              <span class="ld-k">上课时间</span>
              <span class="ld-v">{{ formatTimeRange(detail) }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">授课课程</span>
              <span class="ld-v">{{ detail.course_name || '—' }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">上课老师</span>
              <span class="ld-v">{{ detail.teachers || '待分配' }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">授课课时</span>
              <span class="ld-v">{{ hoursLabel(detail.hours_per_session ?? detail.hours) }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">上课教室</span>
              <span class="ld-v">{{ detail.room || '教室待定' }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">上课内容</span>
              <span class="ld-v">{{ detail.remark || '—' }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">班级容量</span>
              <span class="ld-v">{{ detail.capacity_text || '未设置' }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">开课人数</span>
              <span class="ld-v">{{ detail.open_count_label || '未设置' }}</span>
            </div>
            <div class="ld-item">
              <span class="ld-k">人数/容量</span>
              <span class="ld-v">{{ detail.capacity_label || '—' }}</span>
            </div>
          </div>
        </section>

        <section class="ld-section">
          <div class="ld-sec-row">
            <h4 class="ld-sec-title">
              上课学员
              <span class="ld-count">共 {{ memberCount }} 名</span>
            </h4>
            <div class="ld-sec-actions">
              <el-tag
                v-if="canManage && detail.status === 'scheduled' && !isRollable && !isApp"
                size="small"
                type="info"
                effect="plain"
              >
                未到时间不可点名
              </el-tag>
              <el-button
                v-if="canManage"
                type="primary"
                plain
                size="small"
                @click="openAddStudent"
              >
                添加临时学员
              </el-button>
            </div>
          </div>

          <div v-if="isApp" class="ld-member-list">
            <article v-for="row in detail.members || []" :key="row.id" class="ld-member-card">
              <header class="ld-member-head">
                <span class="ld-member-avatar">{{ memberInitial(row.name) }}</span>
                <span class="ld-member-main">
                  <strong>{{ row.name }}</strong>
                  <small>{{ row.phone || '未填写手机号' }}</small>
                </span>
              </header>
              <div class="ld-member-chips">
                <span class="ld-chip">{{ row.consume_label || '未关联消耗方式' }}</span>
                <span class="ld-chip tone-deduct">扣除 {{ deductedLabel(row.deducted_hours) }}</span>
                <span class="ld-chip tone-remain">剩余 {{ remainLabel(row.remain_hours) }}</span>
              </div>
              <footer v-if="canManage" class="ld-member-actions">
                <el-button size="small" plain type="primary" @click="onTransfer(row)">调课</el-button>
                <el-button size="small" plain type="warning" @click="onLeave(row)">请假</el-button>
              </footer>
            </article>
            <div v-if="!detail.members?.length" class="ld-member-empty">
              <span class="ld-empty-ico" aria-hidden="true">👥</span>
              <strong>暂无学员</strong>
              <em>可添加临时学员到本班级</em>
            </div>
          </div>

          <div v-else class="ld-table-wrap">
            <el-table
              :data="detail.members || []"
              border
              stripe
              size="small"
              empty-text="暂无学员"
              class="ld-table"
              :header-cell-style="pcHeaderStyle"
            >
              <el-table-column prop="name" label="学员姓名" min-width="120" show-overflow-tooltip>
                <template #default="{ row }">
                  <div class="ld-name-cell">
                    <span class="ld-member-avatar">{{ memberInitial(row.name) }}</span>
                    <span class="ld-name">{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column prop="phone" label="手机号" width="118">
                <template #default="{ row }">
                  <span class="ld-mono">{{ row.phone || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column
                prop="consume_label"
                label="消耗方式"
                min-width="120"
                show-overflow-tooltip
              />
              <el-table-column label="扣除额度" width="100" align="center">
                <template #default="{ row }">
                  <span class="hours-pill">{{ deductedLabel(row.deducted_hours) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="剩余额" width="88" align="center">
                <template #default="{ row }">
                  <span class="remain-num">{{ remainLabel(row.remain_hours) }}</span>
                </template>
              </el-table-column>
              <el-table-column v-if="canManage" label="操作" width="120" fixed="right" align="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="onTransfer(row)">调课</el-button>
                  <el-button link type="warning" size="small" @click="onLeave(row)">请假</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </section>
      </template>
      <el-empty v-else-if="!loading" description="课次不存在或已删除" />
    </div>

    <template v-if="isRollable || (isApp && canManage && detail)" #footer>
      <el-button
        v-if="canManage && isApp"
        class="tb-btn"
        plain
        @click="openAddStudent"
      >
        添加学员
      </el-button>
      <el-button
        v-if="isRollable"
        type="primary"
        class="tb-btn tb-btn--primary ld-roll-primary"
        @click="onRoll"
      >
        去点名
      </el-button>
      <el-button
        v-else-if="isApp && canManage && detail?.status === 'scheduled'"
        disabled
        class="tb-btn"
      >
        未到时间不可点名
      </el-button>
    </template>
  </AppSheet>

  <AppSheet
    v-model="addVisible"
    title="添加临时学员"
    size="420px"
    compact-size="min(78%, 560px)"
    modal-class="lesson-add-student-sheet"
  >
    <p class="add-hint">学员将加入本课次关联班级，之后排课/点名均可看到。</p>
    <el-select
      v-model="pickStudentIds"
      multiple
      filterable
      remote
      :remote-method="searchStudents"
      placeholder="搜索姓名/手机号"
      style="width: 100%"
    >
      <el-option
        v-for="s in studentOptions"
        :key="s.id"
        :label="`${s.name}${s.phone ? ' · ' + s.phone : ''}`"
        :value="s.id"
      />
    </el-select>
    <template #footer>
      <el-button class="tb-btn" @click="addVisible = false">取消</el-button>
      <el-button
        type="primary"
        class="tb-btn tb-btn--primary"
        :loading="addSaving"
        @click="submitAddStudent"
      >
        添加
      </el-button>
    </template>
  </AppSheet>
</template>

<style scoped>
.ld-body {
  min-height: 200px;
  padding-bottom: 24px;
}

.ld-hero {
  margin-bottom: 18px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    linear-gradient(135deg, rgba(245, 240, 230, 0.7) 0%, transparent 45%),
    var(--oc-card, #fffdf8);
  box-shadow: 0 6px 16px rgba(41, 37, 36, 0.04);
}

.ld-hero-top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.ld-identity {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.ld-avatar {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
  background: linear-gradient(145deg, #c9a066, #a16207);
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.22);
}

.ld-avatar.is-done {
  background: linear-gradient(145deg, #86efac, #16a34a);
  box-shadow: 0 6px 14px rgba(22, 163, 74, 0.2);
}

.ld-hero-main {
  min-width: 0;
  flex: 1;
}

.ld-title-wrap {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.ld-title {
  font-size: 17px;
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
}

.ld-hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin-top: 8px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.meta-item .el-icon {
  color: var(--oc-primary, #a16207);
}

.ld-head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex-shrink: 0;
}

.ld-stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.ld-stat {
  border-radius: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  padding: 10px 12px;
  min-height: 64px;
}

.ld-stat.tone-gold {
  background: linear-gradient(160deg, #fffdf8, #faf3e6);
  border-color: #e6d2b3;
}

.ld-stat.tone-amber {
  background: linear-gradient(160deg, #fffbeb, #fef3c7);
  border-color: #fde68a;
}

.ld-stat.tone-green {
  background: linear-gradient(160deg, #f0fdf4, #dcfce7);
  border-color: #bbf7d0;
}

.ld-stat.tone-stone {
  background: linear-gradient(160deg, #fafaf9, #f5f5f4);
  border-color: #e7e5e4;
}

.ld-stat-label {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 4px;
}

.ld-stat-value {
  font-size: 18px;
  font-weight: 750;
  color: var(--oc-primary, #a16207);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  word-break: break-word;
}

.ld-stat-value.sm {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.tone-green .ld-stat-value {
  color: #15803d;
}

.ld-section {
  margin-bottom: 20px;
}

.ld-sec-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  display: flex;
  align-items: center;
  gap: 8px;
}

.ld-sec-title::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--oc-primary, #a16207);
}

.ld-count {
  margin-left: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
  background: rgba(161, 98, 7, 0.1);
  padding: 1px 8px;
  border-radius: 999px;
}

.ld-sec-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.ld-sec-row .ld-sec-title {
  margin: 0;
}

.ld-sec-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.ld-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
  padding: 12px 14px;
  border-radius: 12px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
  border: 1px solid var(--oc-border, #e8e0d0);
}

.ld-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ld-k {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.ld-v {
  font-size: 13px;
  color: var(--oc-ink, #44403c);
  font-weight: 550;
  word-break: break-word;
  line-height: 1.45;
}

.ld-table-wrap {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.ld-member-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.ld-member-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
}

.ld-member-head {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ld-member-main {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
}

.ld-member-main strong,
.ld-member-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ld-member-main strong {
  color: var(--oc-ink, #44403c);
  font-size: 14px;
}

.ld-member-main small {
  color: var(--oc-muted, #78716c);
  font-size: 11px;
}

.ld-member-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.ld-chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 24px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  color: #57534e;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(181, 145, 83, 0.22);
  line-height: 1.3;
  word-break: break-word;
}

.ld-chip.tone-deduct {
  color: #9a3412;
  background: #fff7ed;
  border-color: #fed7aa;
}

.ld-chip.tone-remain {
  color: #15803d;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.ld-member-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
}

.ld-member-actions .el-button {
  flex: 1;
  margin: 0;
}

.ld-member-empty {
  grid-column: 1 / -1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 28px 12px;
  color: var(--oc-muted, #78716c);
  text-align: center;
  border-radius: 14px;
  border: 1px dashed var(--oc-border, #e8e0d0);
  background: rgba(255, 253, 248, 0.7);
}

.ld-empty-ico {
  font-size: 24px;
  line-height: 1;
}

.ld-member-empty strong {
  color: #44403c;
  font-size: 14px;
  font-weight: 700;
}

.ld-member-empty em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
}

.ld-table {
  width: 100%;
  --el-table-border-color: #f0e9dc;
}

.ld-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.ld-member-avatar {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
}

.ld-name {
  font-weight: 600;
  color: var(--oc-primary, #a16207);
}

.ld-mono {
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  color: var(--oc-muted, #78716c);
}

.hours-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
}

.remain-num {
  color: #16a34a;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.add-hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.5;
}

.ld-roll-primary {
  flex: 1.4 1 auto;
  min-width: 120px;
}

@media (max-width: 640px) {
  .ld-member-list {
    grid-template-columns: 1fr;
  }

  .ld-stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ld-grid {
    grid-template-columns: 1fr;
  }

  .ld-hero-top {
    flex-direction: column;
  }

  .ld-head-actions {
    width: 100%;
  }

  .ld-head-actions .el-button {
    flex: 1;
  }
}

@media (max-width: 520px) {
  .ld-stat-row {
    grid-template-columns: 1fr;
  }
}
</style>
