<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getClassRecordApi,
  listAcademicTeachersApi,
  listClassRecordLogsApi,
  listRoomsApi,
  removeClassAttendanceApi,
  updateClassAttendanceApi,
  updateClassRecordApi,
  voidClassRecordApi,
  type ClassAttendanceDetail,
  type ClassRecordDetail,
  type ClassRecordOperationLog,
  type TeacherManage,
} from '../../api/academic'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { usePageBack } from '../../composables/usePageBack'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import MobileActionBar from '../../components/MobileActionBar.vue'

const route = useRoute()
const auth = useAuthStore()
const { isApp } = useBreakpoint()
const { goBack } = usePageBack('/academic/class-records')
const { surface: editSurface, surfaceProps: editSurfaceProps } = useResponsiveSurface({
  compactSize: 'min(78%, 560px)',
  dialogMaxWidth: '460px',
  modalClass: 'record-detail-sheet',
  sheetProps: { forceBottom: true },
})
const { surface: attendanceSurface, surfaceProps: attendanceSurfaceProps } = useResponsiveSurface({
  compactSize: 'min(78%, 560px)',
  dialogMaxWidth: '460px',
  modalClass: 'record-detail-sheet',
  sheetProps: { forceBottom: true },
})
/** 点名编辑/改状态：老师默认无 academic.write */
const canRollCall = computed(() => auth.hasPermission('academic.write'))

const loading = ref(false)
const saving = ref(false)
const detail = ref<ClassRecordDetail | null>(null)
const activeTab = ref('members')
/** 课次资料默认折叠，减少首屏高度 */
const infoPanelExpanded = ref(false)
const logs = ref<ClassRecordOperationLog[]>([])
const logsLoading = ref(false)
const teachers = ref<TeacherManage[]>([])
const rooms = ref<string[]>([])

const editVisible = ref(false)
const editForm = reactive({
  class_date: '',
  start_time: '',
  end_time: '',
  hours: 1,
  salary_hours: 1,
  room: '',
  teacher_ids: [] as number[],
  content: '',
})

const attendanceVisible = ref(false)
const attendanceSaving = ref(false)
const selectedAttendance = ref<ClassAttendanceDetail | null>(null)
const attendanceStatus = ref('present')

const recordId = computed(() => Number(route.params.id))
const title = computed(() => detail.value?.class_name || '点名详情')
const activeMembers = computed(() => detail.value?.attendances ?? [])
const nameInitial = computed(() => (title.value || '?').trim().slice(0, 1))

const presentCount = computed(
  () => activeMembers.value.filter((m) => m.status === 'present' || m.status === 'late').length,
)
const absentCount = computed(
  () => activeMembers.value.filter((m) => m.status === 'absent' || m.status === 'leave').length,
)
const consumeTotal = computed(() =>
  activeMembers.value.reduce((sum, m) => sum + Number(m.amount || 0), 0),
)

/** 折叠态一行摘要（完整资料收进展开区） */
const infoPanelSummary = computed(() => {
  const d = detail.value
  if (!d) return '点名、教室、内容等'
  const parts: string[] = []
  if (d.course_name) parts.push(d.course_name)
  if (d.creator_name) parts.push(d.creator_name)
  if (d.room) parts.push(d.room)
  if (absentCount.value > 0) parts.push(`缺勤${absentCount.value}`)
  return parts.length ? parts.join(' · ') : '点名、教室、内容等'
})

const statusOptions = [
  { value: 'present', label: '出勤', hint: '正常到课 · 扣课时', tone: 'ok' },
  { value: 'late', label: '迟到', hint: '迟到到课 · 扣课时', tone: 'warn' },
  { value: 'leave', label: '请假', hint: '已请假 · 不扣课', tone: 'mute' },
  { value: 'absent', label: '缺勤', hint: '未到课 · 不扣课', tone: 'danger' },
]

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function pad(value: number) {
  return String(value).padStart(2, '0')
}

function splitDateTime(value?: string | null) {
  if (!value) return { date: '', time: '' }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    const [rawDate = '', rawTime = ''] = value.split('T')
    return { date: rawDate, time: rawTime.slice(0, 5) }
  }
  return {
    date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    time: `${pad(date.getHours())}:${pad(date.getMinutes())}`,
  }
}

function formatDateTime(value?: string | null) {
  if (!value) return '-'
  const { date, time } = splitDateTime(value)
  return [date, time].filter(Boolean).join(' ')
}

function formatTimeRange(start?: string | null, end?: string | null) {
  if (!start && !end) return '-'
  const startParts = splitDateTime(start)
  const endParts = splitDateTime(end)
  if (startParts.date && startParts.date === endParts.date) {
    return `${startParts.date} ${startParts.time || '-'} ~ ${endParts.time || '-'}`
  }
  return `${formatDateTime(start)} ~ ${formatDateTime(end)}`
}

function formatMoney(value?: number | null) {
  return `¥${Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function statusTagType(status: string) {
  if (status === 'absent') return 'danger'
  if (status === 'leave' || status === 'late') return 'warning'
  return 'success'
}

function memberInitial(name?: string | null) {
  return (name || '?').trim().slice(0, 1)
}

async function load() {
  if (!Number.isFinite(recordId.value) || recordId.value <= 0) {
    detail.value = null
    return
  }
  loading.value = true
  try {
    detail.value = await getClassRecordApi(recordId.value)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function loadMeta() {
  const [teacherResult, roomResult] = await Promise.all([
    listAcademicTeachersApi({ page_size: 100 }).catch(() => ({ items: [] as TeacherManage[] })),
    listRoomsApi().catch(() => []),
  ])
  teachers.value = teacherResult.items
  rooms.value = roomResult.map((item) => item.name).filter(Boolean)
}

async function loadLogs() {
  if (!recordId.value) return
  logsLoading.value = true
  try {
    logs.value = await listClassRecordLogsApi(recordId.value)
  } catch {
    logs.value = []
  } finally {
    logsLoading.value = false
  }
}

function openEdit() {
  if (!detail.value) return
  if (!canRollCall.value) {
    ElMessage.warning('当前账号无点名权限')
    return
  }
  const start = splitDateTime(detail.value.class_start)
  const end = splitDateTime(detail.value.class_end)
  editForm.class_date = start.date || end.date
  editForm.start_time = start.time
  editForm.end_time = end.time
  editForm.hours = detail.value.hours || 1
  editForm.salary_hours = detail.value.salary_hours || detail.value.hours || 1
  editForm.room = detail.value.room || ''
  editForm.teacher_ids = [...(detail.value.teacher_ids || [])]
  editForm.content = detail.value.content || ''
  editVisible.value = true
}

/** 已点名课次：仅允许改计薪课时（不影响学员扣课） */
function bumpSalaryHours(delta: number) {
  const step = 0.25
  const next = Math.round((Number(editForm.salary_hours || 0) + delta * step) * 100) / 100
  editForm.salary_hours = Math.max(0.01, next)
}

async function saveEdit() {
  if (!detail.value) return
  const salary = Number(editForm.salary_hours)
  if (!Number.isFinite(salary) || salary <= 0) {
    ElMessage.warning('计薪课时须大于 0')
    return
  }
  saving.value = true
  try {
    // 点名完成后仅允许调整计薪课时，其它字段只读展示
    detail.value = await updateClassRecordApi(detail.value.id, {
      salary_hours: salary,
    })
    editVisible.value = false
    ElMessage.success('计薪课时已更新')
    await loadLogs()
  } finally {
    saving.value = false
  }
}

async function onVoid() {
  if (!detail.value || detail.value.status === 'void') return
  try {
    await ElMessageBox.confirm(
      '确定撤销这条点名记录？关联课消将作废，已扣课时会退回学员课包。',
      '撤销点名记录',
      { type: 'warning', confirmButtonText: '确认撤销', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  await voidClassRecordApi(detail.value.id)
  ElMessage.success('点名记录已撤销，课时已回滚')
  await Promise.all([load(), loadLogs()])
}

function openAttendance(row: ClassAttendanceDetail) {
  selectedAttendance.value = row
  attendanceStatus.value = row.status
  attendanceVisible.value = true
}

async function saveAttendance() {
  if (!detail.value || !selectedAttendance.value) return
  attendanceSaving.value = true
  try {
    detail.value = await updateClassAttendanceApi(
      detail.value.id,
      selectedAttendance.value.student_id,
      attendanceStatus.value,
    )
    attendanceVisible.value = false
    ElMessage.success('到课状态已更新，课消已同步重算')
    await loadLogs()
  } finally {
    attendanceSaving.value = false
  }
}

async function removeAttendance(row: ClassAttendanceDetail) {
  if (!detail.value) return
  try {
    await ElMessageBox.confirm(
      `确定将“${row.student_name}”移出本次点名名单？该学员本次课消会同步回滚。`,
      '移出学员',
      { type: 'warning', confirmButtonText: '确认移出', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  detail.value = await removeClassAttendanceApi(detail.value.id, row.student_id)
  ElMessage.success('学员已移出，课消已同步更新')
  await loadLogs()
}

watch(recordId, () => {
  infoPanelExpanded.value = false
  void load()
})

watch(activeTab, (value) => {
  if (value === 'logs') void loadLogs()
})

onMounted(() => {
  void Promise.all([load(), loadMeta(), loadLogs()])
})
</script>

<template>
  <div v-loading="loading" class="record-detail-page oc-page-shell" :class="{ 'is-app': isApp }">
    <div v-if="!isApp" class="page-toolbar">
      <el-page-header content="点名详情" @back="goBack" />
      <div v-if="detail" class="toolbar-actions">
        <el-button
          v-if="canRollCall"
          type="primary"
          class="tb-btn tb-btn--primary"
          :disabled="detail.status === 'void'"
          @click="openEdit"
        >
          <el-icon><Edit /></el-icon>
          调整计薪
        </el-button>
        <el-button
          v-if="auth.isAdmin"
          class="tb-btn"
          plain
          type="danger"
          :disabled="detail.status === 'void'"
          @click="onVoid"
        >
          撤销点名
        </el-button>
      </div>
    </div>

    <el-empty v-if="!loading && !detail" description="上课记录不存在或已删除" />

    <template v-else-if="detail">
      <div v-if="detail.status === 'void'" class="void-banner" role="status">
        <strong>本条点名已撤销</strong>
        <span>关联课消已作废，已扣课时已回滚至学员课包</span>
      </div>

      <section class="hero-card" :class="{ 'is-void': detail.status === 'void' }">
        <div class="hero-ornament" aria-hidden="true" />
        <div class="hero-top">
          <div class="hero-identity">
            <div class="hero-avatar" :class="{ 'is-void': detail.status === 'void' }">
              {{ nameInitial }}
            </div>
            <div class="hero-main">
              <div class="hero-kicker">点名详情 · #{{ detail.id }}</div>
              <div class="title-row">
                <h2 class="class-title">{{ title }}</h2>
                <el-tag
                  size="small"
                  effect="plain"
                  round
                  :type="detail.status === 'void' ? 'info' : 'success'"
                >
                  {{ detail.status_label }}
                </el-tag>
              </div>
              <div class="hero-meta">
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
                  {{ formatTimeRange(detail.class_start, detail.class_end) }}
                </span>
                <span v-if="detail.room" class="meta-item">
                  <el-icon><OfficeBuilding /></el-icon>
                  {{ detail.room }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="stat-row">
          <div class="stat-card tone-gold">
            <div class="stat-label">授课课时</div>
            <div class="stat-value">
              {{ detail.hours }}
              <span class="stat-unit">课时</span>
            </div>
          </div>
          <div class="stat-card tone-amber">
            <div class="stat-label">计薪课时</div>
            <div class="stat-value">
              {{ detail.salary_hours }}
              <span class="stat-unit">课时</span>
            </div>
          </div>
          <div class="stat-card tone-green">
            <div class="stat-label">实到 / 名单</div>
            <div class="stat-value">
              {{ presentCount }}
              <span class="stat-unit">/ {{ activeMembers.length }}</span>
            </div>
          </div>
          <div class="stat-card tone-stone">
            <div class="stat-label">课消金额</div>
            <div class="stat-value money">{{ formatMoney(detail.amount ?? consumeTotal) }}</div>
          </div>
        </div>

        <!-- 完整课次资料：默认折叠，展开后显示全部字段 -->
        <div class="info-panel" :class="{ 'is-open': infoPanelExpanded }">
          <button
            type="button"
            class="info-panel-toggle"
            :aria-expanded="infoPanelExpanded"
            @click="infoPanelExpanded = !infoPanelExpanded"
          >
            <span class="info-panel-title">
              课次资料
              <em v-if="!infoPanelExpanded" class="info-panel-preview">{{ infoPanelSummary }}</em>
            </span>
            <span class="info-panel-chevron" :class="{ 'is-open': infoPanelExpanded }" aria-hidden="true">
              ▾
            </span>
          </button>
          <div v-show="infoPanelExpanded" class="info-grid">
            <div class="info-item">
              <span class="k">授课课程</span>
              <span class="v">{{ detail.course_name || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="k">点名老师</span>
              <span class="v">{{ detail.creator_name || detail.teachers || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="k">点名时间</span>
              <span class="v">{{ formatDateTime(detail.roll_at) }}</span>
            </div>
            <div class="info-item">
              <span class="k">上课老师</span>
              <span class="v">{{ detail.teachers || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="k">上课教室</span>
              <span class="v">{{ detail.room || '不指定' }}</span>
            </div>
            <div class="info-item">
              <span class="k">实到人数</span>
              <span class="v">{{ detail.attendance }}</span>
            </div>
            <div class="info-item">
              <span class="k">缺勤/请假</span>
              <span class="v" :class="{ highlight: absentCount > 0 }">{{ absentCount }} 人</span>
            </div>
            <div class="info-item info-item--wide">
              <span class="k">上课内容</span>
              <span class="v">{{ detail.content || '—' }}</span>
            </div>
          </div>
        </div>
      </section>

      <section class="module-card detail-module">
        <el-tabs v-model="activeTab" class="detail-tabs">
          <el-tab-pane name="members">
            <template #label>
              <span class="tab-label">
                <el-icon><UserFilled /></el-icon>
                学员名单
                <em v-if="activeMembers.length">{{ activeMembers.length }}</em>
              </span>
            </template>
          </el-tab-pane>
          <el-tab-pane name="logs">
            <template #label>
              <span class="tab-label">
                <el-icon><Document /></el-icon>
                修改记录
                <em v-if="logs.length">{{ logs.length }}</em>
              </span>
            </template>
          </el-tab-pane>
        </el-tabs>

        <div v-if="activeTab === 'members'">
          <div v-if="isApp" class="member-cards">
            <div v-if="!activeMembers.length" class="member-empty">
              <strong>暂无学员名单</strong>
              <em>本课次没有可展示的到课记录</em>
            </div>
            <article
              v-for="row in activeMembers"
              :key="row.student_id"
              class="member-card"
              :class="{
                'is-absent': row.status === 'absent' || row.status === 'leave',
                'is-late': row.status === 'late',
              }"
            >
              <div class="member-card-head">
                <div class="member-who">
                  <span class="member-avatar">{{ memberInitial(row.student_name) }}</span>
                  <div class="member-who-text">
                    <strong>{{ row.student_name }}</strong>
                    <small v-if="row.status === 'absent' || row.status === 'leave'">待补课</small>
                  </div>
                </div>
                <el-tag size="small" effect="plain" round :type="statusTagType(row.status)">
                  {{ row.status_label }}
                </el-tag>
              </div>
              <div class="member-card-meta">
                <span class="mm-chip">扣除 {{ row.hours_consumed }} 课时</span>
                <span class="mm-chip tone-gold">课消 {{ formatMoney(row.amount) }}</span>
                <span class="mm-chip">课程【{{ detail.course_name || '-' }}】</span>
              </div>
              <div v-if="canRollCall" class="member-card-actions">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :disabled="detail.status === 'void'"
                  @click="openAttendance(row)"
                >
                  修改状态
                </el-button>
                <el-button
                  size="small"
                  plain
                  type="danger"
                  :disabled="detail.status === 'void'"
                  @click="removeAttendance(row)"
                >
                  移出
                </el-button>
              </div>
            </article>
          </div>

          <div v-else class="table-wrap">
            <el-table
              :data="activeMembers"
              row-key="student_id"
              stripe
              border
              class="detail-table"
              :header-cell-style="pcHeaderStyle"
              empty-text="暂无学员名单"
            >
              <el-table-column label="姓名" min-width="160">
                <template #default="{ row }">
                  <div class="student-cell">
                    <span class="member-avatar sm">{{ memberInitial(row.student_name) }}</span>
                    <strong>{{ row.student_name }}</strong>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="消耗方式" min-width="200">
                <template #default>
                  <span class="cell-muted">课程【{{ detail.course_name || '-' }}】</span>
                </template>
              </el-table-column>
              <el-table-column label="到课状态" width="110" align="center">
                <template #default="{ row }">
                  <el-tag size="small" effect="plain" :type="statusTagType(row.status)">
                    {{ row.status_label }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="补课状态" width="110" align="center">
                <template #default="{ row }">
                  <el-tag
                    v-if="row.status === 'absent' || row.status === 'leave'"
                    size="small"
                    effect="plain"
                    type="danger"
                  >
                    待补课
                  </el-tag>
                  <span v-else class="cell-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column label="扣除额度" width="110" align="center">
                <template #default="{ row }">
                  <span class="hours-pill">{{ row.hours_consumed }}课时</span>
                </template>
              </el-table-column>
              <el-table-column label="课消金额" width="120" align="right">
                <template #default="{ row }">
                  <span class="pc-mono">{{ formatMoney(row.amount) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="备注" min-width="100">
                <template #default>
                  <span class="cell-muted">-</span>
                </template>
              </el-table-column>
              <el-table-column v-if="canRollCall" label="操作" width="130" fixed="right" align="right">
                <template #default="{ row }">
                  <div class="pc-ops">
                    <el-button
                      link
                      type="primary"
                      :disabled="detail.status === 'void'"
                      @click="openAttendance(row)"
                    >
                      修改
                    </el-button>
                    <span class="op-sep" />
                    <el-button
                      link
                      type="danger"
                      :disabled="detail.status === 'void'"
                      @click="removeAttendance(row)"
                    >
                      移出
                    </el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>

        <div v-else v-loading="logsLoading" class="logs-panel">
          <div v-if="!logs.length && !logsLoading" class="member-empty">
            <strong>暂无修改记录</strong>
            <em>编辑课次或调整到课状态后，会在这里留下痕迹</em>
          </div>
          <el-timeline v-else class="log-timeline">
            <el-timeline-item
              v-for="log in logs"
              :key="log.id"
              :timestamp="formatDateTime(log.created_at)"
              placement="top"
              color="#a16207"
            >
              <div class="log-item">
                <div class="log-item-head">
                  <strong>{{ log.action_label }}</strong>
                  <small>操作人：{{ log.operator_name || '-' }}</small>
                </div>
                <p class="log-detail">{{ log.detail }}</p>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </section>

      <MobileActionBar
        :visible="
          isApp &&
          Boolean(detail) &&
          detail?.status !== 'void' &&
          (canRollCall || auth.isAdmin)
        "
      >
        <el-button
          v-if="auth.isAdmin"
          class="mab-danger"
          plain
          type="danger"
          @click="onVoid"
        >
          撤销
        </el-button>
        <el-button
          v-if="canRollCall"
          type="primary"
          @click="openEdit"
        >
          调整计薪
        </el-button>
      </MobileActionBar>
    </template>

    <!-- 已点名课次：仅允许修改计薪课时，其余只读摘要 -->
    <component
      :is="editSurface"
      v-model="editVisible"
      v-bind="editSurfaceProps"
      title="调整计薪课时"
      :class="isApp ? undefined : 'record-edit-dialog'"
      destroy-on-close
    >
      <div class="edit-form salary-only-form">
        <p class="edit-lock-tip">
          本课次已点名完成，上课时间、授课课时、老师与内容不可再改；仅可调整
          <b>计薪课时</b>（不影响学员扣课）。
        </p>

        <div class="readonly-summary">
          <div class="rs-row">
            <span class="k">上课时间</span>
            <span class="v">
              {{ editForm.class_date }}
              {{ editForm.start_time || '--:--' }}–{{ editForm.end_time || '--:--' }}
            </span>
          </div>
          <div class="rs-row">
            <span class="k">授课课时</span>
            <span class="v">{{ editForm.hours }} 课时（固定）</span>
          </div>
          <div v-if="detail?.teachers" class="rs-row">
            <span class="k">上课老师</span>
            <span class="v">{{ detail.teachers }}</span>
          </div>
          <div v-if="detail?.room" class="rs-row">
            <span class="k">教室</span>
            <span class="v">{{ detail.room }}</span>
          </div>
          <div v-if="editForm.content" class="rs-row is-block">
            <span class="k">内容</span>
            <span class="v">{{ editForm.content }}</span>
          </div>
        </div>

        <div class="form-section salary-section">
          <div class="form-section-title">计薪课时</div>
          <div class="oc-stepper" aria-label="计薪课时">
            <button
              type="button"
              class="oc-stepper-btn"
              aria-label="减少"
              :disabled="Number(editForm.salary_hours) <= 0.01"
              @click="bumpSalaryHours(-1)"
            >
              −
            </button>
            <div class="oc-stepper-value">
              <input
                v-model.number="editForm.salary_hours"
                class="oc-stepper-input"
                type="number"
                min="0.01"
                step="0.25"
                inputmode="decimal"
              />
              <span class="oc-stepper-unit">课时</span>
            </div>
            <button
              type="button"
              class="oc-stepper-btn"
              aria-label="增加"
              @click="bumpSalaryHours(1)"
            >
              +
            </button>
          </div>
          <p class="field-hint center">每次 ±0.25；仅用于老师薪资统计</p>
        </div>
      </div>
      <template #footer>
        <el-button class="tb-btn" @click="editVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="tb-btn tb-btn--primary"
          :loading="saving"
          @click="saveEdit"
        >
          保存
        </el-button>
      </template>
    </component>

    <!-- 修改到课状态 -->
    <component
      :is="attendanceSurface"
      v-model="attendanceVisible"
      v-bind="attendanceSurfaceProps"
      title="修改到课状态"
      :class="isApp ? undefined : 'record-edit-dialog'"
      destroy-on-close
    >
      <div class="attendance-editor">
        <div class="attendance-who">
          <span class="member-avatar lg">{{ memberInitial(selectedAttendance?.student_name) }}</span>
          <div class="attendance-who-text">
            <p class="attendance-name">{{ selectedAttendance?.student_name }}</p>
            <p class="attendance-sub">选择状态后将同步重算课消</p>
          </div>
        </div>
        <div class="status-grid" role="radiogroup" aria-label="到课状态">
          <button
            v-for="option in statusOptions"
            :key="option.value"
            type="button"
            class="status-card"
            :class="[`tone-${option.tone}`, { 'is-active': attendanceStatus === option.value }]"
            role="radio"
            :aria-checked="attendanceStatus === option.value"
            @click="attendanceStatus = option.value"
          >
            <strong>{{ option.label }}</strong>
            <em>{{ option.hint }}</em>
          </button>
        </div>
        <p class="attend-rule">
          <span class="sec-dot" />
          出勤 / 迟到扣课；请假 / 缺勤不扣课时
        </p>
      </div>
      <template #footer>
        <el-button class="tb-btn" @click="attendanceVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="tb-btn tb-btn--primary"
          :loading="attendanceSaving"
          @click="saveAttendance"
        >
          确认修改
        </el-button>
      </template>
    </component>
  </div>
</template>

<style scoped>
.record-detail-page {
  width: 100%;
  padding-bottom: 24px;
}

.void-banner {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #e7e5e4;
  background: linear-gradient(135deg, #fafaf9, #f5f5f4);
  color: #57534e;
}

.void-banner strong {
  font-size: 14px;
  font-weight: 750;
  color: #44403c;
}

.void-banner span {
  font-size: 12px;
  line-height: 1.45;
  color: #78716c;
}

.record-detail-page :deep(.el-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 32px);
  margin: auto !important;
}

.record-detail-page :deep(.el-dialog__body) {
  min-height: 0;
  overflow-y: auto;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-card {
  position: relative;
  border-radius: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    linear-gradient(135deg, rgba(245, 240, 230, 0.7) 0%, transparent 42%),
    var(--oc-card, #fffdf8);
  margin-bottom: 14px;
  padding: 18px 20px 16px;
  box-shadow: 0 8px 24px rgba(41, 37, 36, 0.05);
  overflow: hidden;
}

.hero-card.is-void {
  background:
    linear-gradient(135deg, rgba(245, 245, 244, 0.9) 0%, transparent 42%),
    #fafaf9;
  border-color: #e7e5e4;
}

.hero-ornament {
  position: absolute;
  top: -40px;
  right: -30px;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(201, 160, 102, 0.18), transparent 68%);
  pointer-events: none;
}

.hero-top {
  position: relative;
  margin-bottom: 16px;
}

.hero-identity {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.hero-avatar {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 800;
  color: #fff;
  flex-shrink: 0;
  background: linear-gradient(145deg, #c9a066, #a16207);
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.22);
}

.hero-avatar.is-void {
  background: linear-gradient(145deg, #a8a29e, #57534e);
  box-shadow: 0 6px 14px rgba(87, 83, 78, 0.18);
}

.hero-main {
  min-width: 0;
  flex: 1;
}

.hero-kicker {
  margin-bottom: 4px;
  font-size: 12px;
  font-weight: 650;
  color: #a16207;
  letter-spacing: 0.02em;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.class-title {
  margin: 0;
  font-size: 20px;
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.01em;
  line-height: 1.3;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.meta-item .el-icon {
  color: var(--oc-primary, #a16207);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.stat-card {
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fff;
  padding: 12px 14px;
  min-height: 72px;
}

.stat-card.tone-gold {
  background: linear-gradient(160deg, #fffdf8, #faf3e6);
  border-color: #e6d2b3;
}

.stat-card.tone-amber {
  background: linear-gradient(160deg, #fffbeb, #fef3c7);
  border-color: #fde68a;
}

.stat-card.tone-green {
  background: linear-gradient(160deg, #f0fdf4, #dcfce7);
  border-color: #bbf7d0;
}

.stat-card.tone-stone {
  background: linear-gradient(160deg, #fafaf9, #f5f5f4);
  border-color: #e7e5e4;
}

.stat-label {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 22px;
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-value.money {
  font-size: 18px;
  color: var(--oc-primary, #a16207);
}

.tone-gold .stat-value {
  color: var(--oc-primary, #a16207);
}

.tone-green .stat-value {
  color: #15803d;
}

.tone-amber .stat-value {
  color: #b45309;
}

.stat-unit {
  font-size: 12px;
  font-weight: 600;
  margin-left: 2px;
  color: var(--oc-muted, #78716c);
}

.info-panel {
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #f0e9dc;
  padding: 2px 6px 2px 12px;
  overflow: hidden;
}

.info-panel.is-open {
  padding-bottom: 10px;
}

.info-panel-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-height: 42px;
  padding: 6px 4px 6px 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
  color: inherit;
  -webkit-tap-highlight-color: transparent;
}

.info-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.info-panel-title::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--oc-primary, #a16207);
  flex-shrink: 0;
}

.info-panel-preview {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-style: normal;
  font-size: 12px;
  font-weight: 500;
  color: #a8a29e;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-panel-chevron {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #a16207;
  font-size: 12px;
  line-height: 1;
  background: rgba(161, 98, 7, 0.08);
  transition: transform 0.18s ease;
}

.info-panel-chevron.is-open {
  transform: rotate(180deg);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(181, 145, 83, 0.14);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 253, 248, 0.88);
  border: 1px solid rgba(181, 145, 83, 0.12);
}

.info-item--wide {
  grid-column: 1 / -1;
}

.info-item .k {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.info-item .v {
  font-size: 13px;
  color: var(--oc-ink, #44403c);
  font-weight: 600;
  word-break: break-word;
  line-height: 1.4;
}

.info-item .v.highlight {
  color: #b45309;
  font-weight: 700;
}

.module-card,
.detail-module {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 6px 20px rgba(41, 37, 36, 0.04);
  padding: 8px 16px 16px;
}

.detail-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.detail-tabs :deep(.el-tabs__item) {
  height: 42px;
  line-height: 42px;
  font-size: 14px;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.detail-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--oc-primary, #a16207);
  height: 3px;
  border-radius: 2px;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tab-label em {
  font-style: normal;
  font-size: 11px;
  font-weight: 700;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(161, 98, 7, 0.1);
  color: var(--oc-primary, #a16207);
}

.table-wrap {
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.detail-table {
  width: 100%;
  font-size: 13px;
  --el-table-border-color: #f0e9dc;
}

.detail-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #fbf7f0 !important;
}

.student-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.student-cell strong,
.member-card strong {
  display: block;
  color: var(--oc-ink, #44403c);
  font-weight: 650;
  font-size: 13px;
}

.student-cell small,
.member-card small,
.field-hint {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.member-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.18);
}

.member-avatar.sm {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 12px;
}

.cell-muted {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.pc-mono {
  font-variant-numeric: tabular-nums;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
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

.pc-ops {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}

.op-sep {
  width: 1px;
  height: 12px;
  background: #e8e0d0;
  margin: 0 2px;
}

.member-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.member-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 36px 16px;
  border-radius: 16px;
  border: 1px dashed rgba(181, 145, 83, 0.28);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
  text-align: center;
}

.member-empty strong {
  font-size: 14px;
  color: #44403c;
}

.member-empty em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
}

.member-card {
  padding: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 16px;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.9), transparent 48%),
    var(--oc-card, #fffdf8);
  box-shadow: 0 6px 16px rgba(41, 37, 36, 0.04);
}

.member-card.is-absent {
  border-color: rgba(220, 38, 38, 0.22);
  background:
    linear-gradient(155deg, rgba(254, 242, 242, 0.9), transparent 48%),
    #fffdf8;
}

.member-card.is-late {
  border-color: rgba(217, 119, 6, 0.28);
  background:
    linear-gradient(155deg, rgba(255, 251, 235, 0.95), transparent 48%),
    #fffdf8;
}

.member-card-head,
.member-card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.member-who {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.member-who-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.member-who-text small {
  color: #b45309;
  font-size: 11px;
  font-weight: 650;
}

.member-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 12px 0 10px;
}

.mm-chip {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: #57534e;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(181, 145, 83, 0.2);
}

.mm-chip.tone-gold {
  color: #a16207;
  background: #fff7ed;
  border-color: #fed7aa;
}

.member-card-actions {
  justify-content: stretch;
  border-top: 1px solid #f0e9dc;
  padding-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.member-card-actions .el-button {
  width: 100%;
  margin: 0;
  min-height: 40px;
  border-radius: 12px;
  font-weight: 680;
}

.member-avatar.lg {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  font-size: 20px;
}

.logs-panel {
  min-height: 120px;
  padding: 4px 0 8px;
}

.log-timeline {
  max-width: 860px;
  padding: 8px 8px 0;
}

.log-item {
  padding: 12px 14px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  border-radius: 14px;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.9), transparent 50%),
    linear-gradient(180deg, #fffdfb, #faf6ee);
  box-shadow: 0 4px 12px rgba(88, 60, 24, 0.04);
}

.log-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.log-item-head strong {
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  font-weight: 720;
}

.log-item-head small {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(181, 145, 83, 0.2);
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  font-weight: 600;
}

.log-detail {
  margin: 10px 0 0;
  font-size: 13px;
  color: #57534e;
  line-height: 1.55;
}

.edit-form {
  display: grid;
  gap: 12px;
}

.edit-lock-tip {
  margin: 0;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(180, 83, 9, 0.22);
  background: linear-gradient(180deg, #fffbeb, #fef3c7);
  font-size: 12px;
  line-height: 1.55;
  color: #92400e;
}

.edit-lock-tip b {
  font-weight: 750;
  color: #b45309;
}

.readonly-summary {
  padding: 4px 2px;
  display: grid;
  gap: 0;
}

.rs-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-height: 34px;
  padding: 8px 4px;
  border-bottom: 1px dashed rgba(181, 145, 83, 0.16);
}

.rs-row:last-child {
  border-bottom: 0;
}

.rs-row.is-block {
  flex-direction: column;
  align-items: stretch;
  gap: 4px;
}

.rs-row .k {
  flex-shrink: 0;
  width: 64px;
  font-size: 12px;
  font-weight: 650;
  color: #8a8178;
}

.rs-row .v {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: #44403c;
  word-break: break-word;
  line-height: 1.4;
}

.form-section {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(181, 145, 83, 0.18);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
}

.form-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 13px;
  font-weight: 720;
  color: #44403c;
}

.form-section-title::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--oc-primary, #a16207);
}

.salary-section {
  text-align: center;
}

/* 美化课时步进器（替代 Element 默认丑控件） */
.oc-stepper {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 48px;
  align-items: center;
  gap: 10px;
  max-width: 320px;
  margin: 0 auto;
}

.oc-stepper-btn {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  border: 1px solid rgba(161, 98, 7, 0.28);
  background: linear-gradient(145deg, #fffefb, #f5e6c8);
  color: #a16207;
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(88, 60, 24, 0.06);
  transition: transform 0.12s ease, background 0.15s ease, opacity 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}

.oc-stepper-btn:hover:not(:disabled) {
  background: linear-gradient(145deg, #fff7e8, #eddbb8);
}

.oc-stepper-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.oc-stepper-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.oc-stepper-value {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid rgba(161, 98, 7, 0.28);
  background: #fff;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.oc-stepper-input {
  width: 100%;
  border: 0;
  outline: none;
  background: transparent;
  text-align: center;
  font-size: 22px;
  font-weight: 780;
  font-variant-numeric: tabular-nums;
  color: #a16207;
  line-height: 1.2;
  /* 隐藏 number 原生箭头 */
  appearance: textfield;
  -moz-appearance: textfield;
}

.oc-stepper-input::-webkit-outer-spin-button,
.oc-stepper-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.oc-stepper-unit {
  position: absolute;
  right: 12px;
  font-size: 12px;
  font-weight: 650;
  color: #a8a29e;
  pointer-events: none;
}

.field-hint {
  display: block;
  width: 100%;
  margin-top: 10px;
  line-height: 1.5;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.field-hint.center {
  text-align: center;
}

.attendance-editor {
  display: grid;
  gap: 14px;
}

.attendance-who {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.9), transparent 50%),
    linear-gradient(180deg, #fffefb, #faf3e6);
}

.attendance-who-text {
  min-width: 0;
  flex: 1;
}

.attendance-name {
  margin: 0;
  color: var(--oc-ink, #44403c);
  font-weight: 750;
  font-size: 17px;
  line-height: 1.3;
}

.attendance-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: #8a8178;
  line-height: 1.4;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.status-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-height: 72px;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background: #fffdf8;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
  color: inherit;
}

.status-card strong {
  font-size: 15px;
  font-weight: 750;
  color: #44403c;
}

.status-card em {
  font-style: normal;
  font-size: 11px;
  line-height: 1.35;
  color: #8a8178;
}

.status-card.tone-ok.is-active,
.status-card.tone-ok:hover {
  border-color: rgba(22, 163, 74, 0.45);
  background: linear-gradient(160deg, #f0fdf4, #dcfce7);
  box-shadow: 0 4px 12px rgba(22, 163, 74, 0.12);
}

.status-card.tone-ok.is-active strong {
  color: #15803d;
}

.status-card.tone-warn.is-active,
.status-card.tone-warn:hover {
  border-color: rgba(217, 119, 6, 0.45);
  background: linear-gradient(160deg, #fffbeb, #fef3c7);
  box-shadow: 0 4px 12px rgba(217, 119, 6, 0.12);
}

.status-card.tone-warn.is-active strong {
  color: #b45309;
}

.status-card.tone-mute.is-active,
.status-card.tone-mute:hover {
  border-color: rgba(120, 113, 108, 0.35);
  background: linear-gradient(160deg, #fafaf9, #f5f5f4);
}

.status-card.tone-mute.is-active strong {
  color: #57534e;
}

.status-card.tone-danger.is-active,
.status-card.tone-danger:hover {
  border-color: rgba(220, 38, 38, 0.4);
  background: linear-gradient(160deg, #fef2f2, #fee2e2);
  box-shadow: 0 4px 12px rgba(220, 38, 38, 0.1);
}

.status-card.tone-danger.is-active strong {
  color: #b91c1c;
}

.status-card.is-active {
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.12);
}

.attend-rule {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(250, 246, 238, 0.9);
  border: 1px dashed rgba(181, 145, 83, 0.28);
  font-size: 12px;
  color: #78716c;
  line-height: 1.45;
}

.sec-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 3px rgba(161, 98, 7, 0.15);
  flex-shrink: 0;
}

@media (max-width: 1199px) {
  .record-detail-page.is-app {
    display: grid;
    gap: 12px;
    padding-bottom: 8px;
  }

  .hero-card {
    margin: 0;
    padding: 16px 14px 14px;
    border-radius: 18px;
    border-color: rgba(181, 145, 83, 0.3);
    background:
      linear-gradient(145deg, rgba(255, 255, 255, 0.92), transparent 42%),
      linear-gradient(180deg, #fffefb, #faf3e6);
    box-shadow:
      0 12px 28px rgba(88, 60, 24, 0.08),
      0 1px 0 rgba(255, 255, 255, 0.9) inset;
  }

  .hero-avatar {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    font-size: 18px;
  }

  .class-title {
    font-size: 18px;
  }

  .hero-meta {
    gap: 6px;
  }

  .meta-item {
    min-height: 26px;
    padding: 2px 10px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.8);
    border: 1px solid rgba(181, 145, 83, 0.18);
    font-size: 12px;
  }

  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 12px;
  }

  .stat-card {
    min-height: 68px;
    padding: 12px;
    border-radius: 14px;
  }

  .stat-value {
    font-size: 20px;
  }

  .stat-value.money {
    font-size: 16px;
  }

  .info-panel {
    border-radius: 14px;
    background: rgba(255, 253, 248, 0.88);
    border-color: rgba(181, 145, 83, 0.18);
  }

  .info-grid {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .info-item--wide {
    grid-column: 1 / -1;
  }

  .detail-module {
    margin: 0;
    padding: 10px 0 4px;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .detail-tabs {
    margin: 0 0 12px;
    padding: 4px;
    border-radius: 14px;
    border: 1px solid rgba(181, 145, 83, 0.2);
    background: #f3ebe0;
  }

  .detail-tabs :deep(.el-tabs__header) {
    margin: 0;
  }

  .detail-tabs :deep(.el-tabs__nav-wrap::after),
  .detail-tabs :deep(.el-tabs__active-bar) {
    display: none;
  }

  .detail-tabs :deep(.el-tabs__nav) {
    width: 100%;
    display: flex;
  }

  .detail-tabs :deep(.el-tabs__item) {
    flex: 1;
    height: 40px;
    line-height: 40px;
    padding: 0 10px !important;
    border-radius: 11px;
    justify-content: center;
    color: #78716c;
    font-weight: 650;
  }

  .detail-tabs :deep(.el-tabs__item.is-active) {
    color: #fffdf8 !important;
    background: linear-gradient(145deg, #c07a12, #a16207);
    box-shadow: 0 4px 12px rgba(161, 98, 7, 0.25);
  }

  .detail-tabs :deep(.tab-label) {
    justify-content: center;
  }

  .detail-tabs :deep(.el-tabs__item.is-active .tab-label em) {
    background: rgba(255, 253, 248, 0.22);
    color: #fffdf8;
  }

  .log-item {
    border-radius: 14px;
    border-color: rgba(181, 145, 83, 0.22);
    box-shadow: 0 4px 12px rgba(88, 60, 24, 0.04);
  }

  .log-timeline {
    max-width: none;
    padding: 4px 2px 0;
  }

  .void-banner {
    margin: 0 0 4px;
    border-radius: 16px;
  }

  .form-section {
    padding: 14px 12px;
  }

  .oc-stepper {
    max-width: none;
    gap: 8px;
  }

  .oc-stepper-btn {
    width: 46px;
    height: 46px;
  }

  .status-grid {
    gap: 8px;
  }

  .status-card {
    min-height: 68px;
    padding: 12px;
  }

  .mab-danger {
    flex: 0.72 1 0 !important;
  }
}
</style>

<!-- AppSheet 挂 body，需非 scoped -->
<style>
.el-drawer.oc-app-sheet.record-detail-sheet .el-drawer__header {
  margin-bottom: 4px !important;
  padding: 16px 16px 8px !important;
}

.el-drawer.oc-app-sheet.record-detail-sheet .el-drawer__title {
  font-weight: 750 !important;
  color: #44403c !important;
}

.el-drawer.oc-app-sheet.record-detail-sheet .el-drawer__body {
  padding: 8px 14px 8px !important;
  background:
    linear-gradient(180deg, rgba(250, 246, 238, 0.55), transparent 48px),
    #fffdf8;
}

.el-drawer.oc-app-sheet.record-detail-sheet .el-drawer__footer {
  display: flex !important;
  gap: 10px !important;
  padding: 10px 14px calc(12px + env(safe-area-inset-bottom, 0px)) !important;
  border-top: 1px solid rgba(181, 145, 83, 0.18) !important;
  background: linear-gradient(180deg, #fffefb, #faf3e6) !important;
}

.el-drawer.oc-app-sheet.record-detail-sheet .el-drawer__footer .el-button {
  min-height: 46px !important;
  border-radius: 13px !important;
  font-weight: 720 !important;
  margin: 0 !important;
  flex: 1;
}

.el-drawer.oc-app-sheet.record-detail-sheet .el-drawer__footer .el-button--primary {
  flex: 1.35;
  background: linear-gradient(145deg, #c07a12, #a16207) !important;
  border-color: transparent !important;
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.24);
}

.el-dialog.record-edit-dialog {
  border-radius: 16px !important;
  overflow: hidden;
  border: 1px solid rgba(181, 145, 83, 0.22);
}

.el-dialog.record-edit-dialog .el-dialog__header {
  padding: 16px 20px 10px;
  border-bottom: 1px solid rgba(181, 145, 83, 0.14);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
}

.el-dialog.record-edit-dialog .el-dialog__title {
  font-weight: 750;
  color: #44403c;
}

.el-dialog.record-edit-dialog .el-dialog__body {
  padding: 16px 20px 8px;
  background: #fffdf8;
}

.el-dialog.record-edit-dialog .el-dialog__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(181, 145, 83, 0.14);
  background: linear-gradient(180deg, #fffefb, #faf3e6);
}
</style>
