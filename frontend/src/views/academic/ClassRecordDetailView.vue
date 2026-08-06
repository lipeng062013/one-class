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

const route = useRoute()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const { goBack } = usePageBack('/academic/class-records')
/** 点名编辑/改状态：老师默认无 academic.write */
const canRollCall = computed(() => auth.hasPermission('academic.write'))

const loading = ref(false)
const saving = ref(false)
const detail = ref<ClassRecordDetail | null>(null)
const activeTab = ref('members')
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

const statusOptions = [
  { value: 'present', label: '出勤' },
  { value: 'late', label: '迟到' },
  { value: 'leave', label: '请假' },
  { value: 'absent', label: '缺勤' },
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

function combineDateTime(date: string, time: string) {
  return date && time ? `${date}T${time}:00` : null
}

async function saveEdit() {
  if (!detail.value) return
  if (!editForm.class_date || !editForm.start_time || !editForm.end_time) {
    ElMessage.warning('请完整填写上课日期和时间')
    return
  }
  const start = combineDateTime(editForm.class_date, editForm.start_time)
  const end = combineDateTime(editForm.class_date, editForm.end_time)
  if (!start || !end || new Date(end).getTime() <= new Date(start).getTime()) {
    ElMessage.warning('下课时间须晚于上课时间')
    return
  }
  saving.value = true
  try {
    detail.value = await updateClassRecordApi(detail.value.id, {
      class_start: start,
      class_end: end,
      hours: editForm.hours,
      salary_hours: editForm.salary_hours,
      room: detail.value.schedule_id ? editForm.room : undefined,
      teacher_ids: editForm.teacher_ids,
      content: editForm.content,
    })
    editVisible.value = false
    ElMessage.success('课次信息已更新')
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
  <div v-loading="loading" class="record-detail-page oc-page-shell">
    <div class="page-toolbar">
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
          编辑
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
      <el-card class="hero-card" shadow="never">
        <div class="hero-top">
          <div class="hero-identity">
            <div class="hero-avatar" :class="{ 'is-void': detail.status === 'void' }">
              {{ nameInitial }}
            </div>
            <div class="hero-main">
              <div class="title-row">
                <h2 class="class-title">{{ title }}</h2>
                <el-tag
                  size="small"
                  effect="plain"
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

        <div class="info-panel">
          <div class="info-panel-title">课次资料</div>
          <div class="info-grid">
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
      </el-card>

      <el-card class="module-card" shadow="never">
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
          <div v-if="isCompact" class="member-cards">
            <div v-if="!activeMembers.length" class="m-card m-card-empty">暂无学员名单</div>
            <div v-for="row in activeMembers" :key="row.student_id" class="member-card">
              <div class="member-card-head">
                <div class="member-who">
                  <span class="member-avatar">{{ memberInitial(row.student_name) }}</span>
                  <strong>{{ row.student_name }}</strong>
                </div>
                <el-tag size="small" effect="plain" :type="statusTagType(row.status)">
                  {{ row.status_label }}
                </el-tag>
              </div>
              <div class="member-card-meta">
                <span><span class="k">消耗</span>课程【{{ detail.course_name || '-' }}】</span>
                <span><span class="k">扣除</span>{{ row.hours_consumed }}课时</span>
                <span><span class="k">课消</span>{{ formatMoney(row.amount) }}</span>
                <span>
                  <span class="k">补课</span>
                  {{ row.status === 'absent' || row.status === 'leave' ? '待补课' : '-' }}
                </span>
              </div>
              <div v-if="canRollCall" class="member-card-actions">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :disabled="detail.status === 'void'"
                  @click="openAttendance(row)"
                >
                  修改
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
            </div>
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
          <el-empty v-if="!logs.length && !logsLoading" description="暂无修改记录" :image-size="70" />
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
      </el-card>
    </template>

    <el-dialog
      v-model="editVisible"
      title="修改课次信息"
      :width="isCompact ? '94%' : '560px'"
      destroy-on-close
      align-center
    >
      <el-form label-position="top" class="edit-form">
        <el-form-item label="上课日期" required>
          <el-date-picker
            v-model="editForm.class_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <div class="time-row">
          <el-form-item label="上课时间" required>
            <el-time-select
              v-model="editForm.start_time"
              start="06:00"
              step="00:15"
              end="23:00"
              style="width: 100%"
            />
          </el-form-item>
          <span class="time-sep">至</span>
          <el-form-item label="下课时间" required>
            <el-time-select
              v-model="editForm.end_time"
              start="06:15"
              step="00:15"
              end="23:45"
              style="width: 100%"
            />
          </el-form-item>
        </div>
        <el-form-item label="授课课时" required>
          <el-input-number v-model="editForm.hours" :min="0.01" :step="0.25" :precision="2" />
          <span class="field-hint">学员扣课基准，修改后将同步重算学员课消</span>
        </el-form-item>
        <el-form-item label="计薪课时" required>
          <el-input-number
            v-model="editForm.salary_hours"
            :min="0.01"
            :step="0.25"
            :precision="2"
          />
          <span class="field-hint">仅用于老师薪资统计，修改不会影响学员扣课</span>
        </el-form-item>
        <el-form-item label="上课老师">
          <el-select
            v-model="editForm.teacher_ids"
            multiple
            filterable
            style="width: 100%"
            placeholder="请选择老师"
          >
            <el-option
              v-for="teacher in teachers"
              :key="teacher.id"
              :label="teacher.name"
              :value="teacher.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="上课教室">
          <el-select
            v-model="editForm.room"
            filterable
            allow-create
            clearable
            :disabled="!detail?.schedule_id"
            style="width: 100%"
            placeholder="不指定"
          >
            <el-option v-for="room in rooms" :key="room" :label="room" :value="room" />
          </el-select>
          <span v-if="!detail?.schedule_id" class="field-hint">
            未关联排课的历史记录不支持单独修改教室
          </span>
        </el-form-item>
        <el-form-item label="上课内容">
          <el-input
            v-model="editForm.content"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="请输入本次上课内容"
          />
        </el-form-item>
      </el-form>
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
    </el-dialog>

    <el-dialog
      v-model="attendanceVisible"
      title="修改到课状态"
      :width="isCompact ? '94%' : '430px'"
      destroy-on-close
      align-center
    >
      <div class="attendance-editor">
        <div class="attendance-who">
          <span class="member-avatar">{{ memberInitial(selectedAttendance?.student_name) }}</span>
          <p class="attendance-name">{{ selectedAttendance?.student_name }}</p>
        </div>
        <el-radio-group v-model="attendanceStatus" class="status-options">
          <el-radio-button
            v-for="option in statusOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </el-radio-button>
        </el-radio-group>
        <p class="field-hint">状态变化会重算课消：出勤/迟到扣课，请假/缺勤不扣。</p>
      </div>
      <template #footer>
        <el-button class="tb-btn" @click="attendanceVisible = false">取消</el-button>
        <el-button
          type="primary"
          class="tb-btn tb-btn--primary"
          :loading="attendanceSaving"
          @click="saveAttendance"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.record-detail-page {
  width: 100%;
  padding-bottom: 24px;
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
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    linear-gradient(135deg, rgba(245, 240, 230, 0.65) 0%, transparent 42%),
    var(--oc-card, #fffdf8);
  margin-bottom: 14px;
  box-shadow: 0 8px 24px rgba(41, 37, 36, 0.05);
  overflow: hidden;
}

.hero-card :deep(.el-card__body) {
  padding: 18px 20px 16px;
}

.hero-top {
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
  padding: 12px 14px 8px;
}

.info-panel-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.info-panel-title::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--oc-primary, #a16207);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
  min-width: 0;
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
  font-weight: 550;
  word-break: break-word;
}

.info-item .v.highlight {
  color: #b45309;
  font-weight: 700;
}

.module-card {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 6px 20px rgba(41, 37, 36, 0.04);
}

.module-card :deep(.el-card__body) {
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
  gap: 10px;
}

.member-card {
  padding: 12px 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 4px 12px rgba(41, 37, 36, 0.03);
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

.member-card-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 12px 0 10px;
  color: var(--oc-ink, #44403c);
  font-size: 12px;
}

.member-card-meta .k {
  color: var(--oc-muted, #78716c);
  margin-right: 4px;
}

.member-card-actions {
  justify-content: flex-end;
  border-top: 1px solid #f0e9dc;
  padding-top: 8px;
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
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
  background: linear-gradient(180deg, #fffdfb, #faf6ee);
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
  font-size: 13px;
  font-weight: 650;
}

.log-item-head small {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.log-detail {
  margin: 8px 0 0;
  font-size: 13px;
  color: #57534e;
  line-height: 1.55;
}

.edit-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.time-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
}

.time-sep {
  margin-top: 18px;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.field-hint {
  display: block;
  width: 100%;
  margin-top: 5px;
  line-height: 1.5;
}

.attendance-editor {
  text-align: center;
}

.attendance-who {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.attendance-name {
  margin: 0;
  color: var(--oc-ink, #44403c);
  font-weight: 650;
  font-size: 15px;
}

.status-options {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: 8px;
}

@media (max-width: 991px) {
  .page-toolbar {
    align-items: stretch;
  }

  .toolbar-actions {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  }

  .toolbar-actions :deep(.el-button) {
    width: 100%;
    margin: 0;
  }

  .hero-card :deep(.el-card__body) {
    padding: 14px;
  }

  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .info-grid {
    grid-template-columns: 1fr;
    gap: 4px 0;
  }
}

@media (max-width: 520px) {
  .stat-row,
  .member-card-meta,
  .time-row {
    grid-template-columns: 1fr;
  }

  .time-sep {
    display: none;
  }

  .class-title {
    font-size: 18px;
  }
}
</style>
