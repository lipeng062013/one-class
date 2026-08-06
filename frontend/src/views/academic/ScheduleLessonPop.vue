<script setup lang="ts">
import { computed } from 'vue'
import type { ScheduleLesson } from '../../api/academic'

const props = defineProps<{
  lesson: ScheduleLesson
  canManage?: boolean
}>()

const emit = defineEmits<{
  roll: []
  adjust: []
  detail: []
  editTime: []
  remove: []
}>()

const dateLine = computed(() => {
  const s = new Date(props.lesson.start_at)
  const e = new Date(props.lesson.end_at)
  if (Number.isNaN(s.getTime())) return ''
  const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const pad = (n: number) => String(n).padStart(2, '0')
  const datePart = `${pad(s.getMonth() + 1)}月${pad(s.getDate())}日(${weekNames[s.getDay()]})`
  const timePart = `${pad(s.getHours())}:${pad(s.getMinutes())}-${pad(e.getHours())}:${pad(e.getMinutes())}`
  return `${datePart} ${timePart}`
})

const capPercent = computed(() => {
  const cap = props.lesson.capacity
  const n = props.lesson.member_count ?? 0
  if (cap == null || cap <= 0) return 0
  return Math.min(100, Math.round((n / cap) * 100))
})

const capText = computed(() => {
  return props.lesson.capacity_label || `${props.lesson.member_count ?? 0}/未设置`
})

const nameInitial = computed(() => (props.lesson.class_name || '?').trim().slice(0, 1))

const isDone = computed(() => props.lesson.status === 'completed')

const canRoll = computed(() => {
  const l = props.lesson
  if (l.status !== 'scheduled') return false
  if (typeof l.can_roll_call === 'boolean') return l.can_roll_call
  const start = new Date(l.start_at)
  if (Number.isNaN(start.getTime())) return false
  const lessonDay = new Date(start)
  lessonDay.setHours(0, 0, 0, 0)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return lessonDay.getTime() <= today.getTime()
})

const isFuturePending = computed(
  () => props.lesson.status === 'scheduled' && !canRoll.value,
)

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    scheduled: '待上课',
    completed: '已点名',
    cancelled: '已取消',
  }
  return map[props.lesson.status] || props.lesson.status || ''
})
</script>

<template>
  <div class="lesson-pop">
    <div class="lp-head">
      <span class="lp-avatar" :class="{ 'is-done': isDone }">{{ nameInitial }}</span>
      <div class="lp-head-main">
        <div class="lp-title-row">
          <div class="lp-title">{{ lesson.class_name || '未命名班级' }}</div>
          <el-tag
            v-if="statusLabel"
            size="small"
            effect="plain"
            :type="isDone ? 'success' : lesson.status === 'cancelled' ? 'info' : 'warning'"
          >
            {{ statusLabel }}
          </el-tag>
        </div>
        <div class="lp-datetime">{{ dateLine }}</div>
      </div>
    </div>

    <div class="lp-rows">
      <div class="lp-row">
        <el-icon class="lp-ico"><Reading /></el-icon>
        <span class="lp-label">授课课程</span>
        <span class="lp-val">{{ lesson.course_name || '—' }}</span>
      </div>
      <div class="lp-row">
        <el-icon class="lp-ico"><User /></el-icon>
        <span class="lp-label">上课老师</span>
        <span class="lp-val">{{ lesson.teachers || '待分配' }}</span>
      </div>
      <div class="lp-row">
        <el-icon class="lp-ico"><OfficeBuilding /></el-icon>
        <span class="lp-label">上课教室</span>
        <span class="lp-val">{{ lesson.room || '教室待定' }}</span>
      </div>
      <div class="lp-row lp-row--cap">
        <el-icon class="lp-ico"><DataLine /></el-icon>
        <span class="lp-label">人数/容量</span>
        <div class="lp-cap">
          <el-progress
            :percentage="capPercent"
            :stroke-width="8"
            :show-text="false"
            :color="capPercent >= 100 ? '#dc2626' : '#a16207'"
          />
          <span class="lp-cap-text">{{ capText }}</span>
        </div>
      </div>
      <div class="lp-row lp-row--top">
        <el-icon class="lp-ico"><Avatar /></el-icon>
        <span class="lp-label">上课学员</span>
        <span class="lp-val lp-students">{{ lesson.students || '暂无学员' }}</span>
      </div>
      <div v-if="lesson.remark" class="lp-row lp-row--top">
        <el-icon class="lp-ico"><Document /></el-icon>
        <span class="lp-label">上课内容</span>
        <span class="lp-val">{{ lesson.remark }}</span>
      </div>
    </div>

    <div class="lp-actions">
      <el-button
        v-if="canManage && canRoll"
        type="primary"
        size="small"
        @click="emit('roll')"
      >
        点名
      </el-button>
      <el-tag v-else-if="canManage && isFuturePending" size="small" type="info" effect="plain">
        未到时间
      </el-tag>
      <el-button v-if="canManage" type="primary" plain size="small" @click="emit('adjust')">
        调整课次
      </el-button>
      <el-button type="primary" plain size="small" @click="emit('detail')">查看详情</el-button>
      <el-button v-if="canManage" plain size="small" @click="emit('editTime')">改时间</el-button>
      <el-button v-if="canManage" plain type="danger" size="small" @click="emit('remove')">
        删除
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.lesson-pop {
  min-width: 280px;
  max-width: 360px;
  padding: 2px 0;
}

.lp-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.lp-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 800;
  flex-shrink: 0;
  color: #fff;
  background: linear-gradient(145deg, #c9a066, #a16207);
  box-shadow: 0 3px 8px rgba(161, 98, 7, 0.22);
}

.lp-avatar.is-done {
  background: linear-gradient(145deg, #86efac, #16a34a);
  box-shadow: 0 3px 8px rgba(22, 163, 74, 0.2);
}

.lp-head-main {
  min-width: 0;
  flex: 1;
}

.lp-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.lp-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
}

.lp-datetime {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.lp-rows {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: linear-gradient(180deg, #fffdfb, #faf6ee);
  border: 1px solid var(--oc-border, #e8e0d0);
}

.lp-row {
  display: grid;
  grid-template-columns: 16px 64px minmax(0, 1fr);
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--oc-ink, #44403c);
}

.lp-row--top {
  align-items: flex-start;
}

.lp-row--cap {
  align-items: center;
}

.lp-ico {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--oc-primary, #a16207);
  font-size: 14px;
}

.lp-label {
  flex-shrink: 0;
  color: var(--oc-muted, #78716c);
}

.lp-val {
  min-width: 0;
  word-break: break-word;
  font-weight: 550;
}

.lp-students {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.lp-cap {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.lp-cap :deep(.el-progress) {
  flex: 1;
  min-width: 72px;
}

.lp-cap-text {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--oc-ink, #44403c);
  white-space: nowrap;
  font-weight: 600;
}

.lp-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

/* EP 默认 .el-button + .el-button { margin-left } 会在换行后
 * 让第二行首个按钮仍带左边距，行距/对齐都错乱；统一清掉，只靠 gap */
.lp-actions :deep(.el-button),
.lp-actions :deep(.el-button + .el-button) {
  margin: 0 !important;
}
</style>
