<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  downloadGrowthReportApi,
  getStudentApi,
  learningFileObjectUrl,
  listLearningApi,
  type LearningRecord,
  type Student,
} from '../../api/students'
import { asyncPool } from '../../utils/asyncPool'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const student = ref<Student | null>(null)
const records = ref<LearningRecord[]>([])
const imageUrls = ref<Record<number, string>>({})

const studentId = computed(() => Number(route.params.id))

const classLabels: Record<string, string> = {
  attended: '已上课',
  absent: '缺勤',
  late: '迟到',
  leave: '请假',
  makeup: '补课',
}

const classTagType: Record<string, 'success' | 'danger' | 'warning' | 'info' | 'primary'> = {
  attended: 'success',
  absent: 'danger',
  late: 'warning',
  leave: 'info',
  makeup: 'primary',
}

function recordPreviewList(rec: LearningRecord): string[] {
  return (rec.files || []).map((f) => imageUrls.value[f.id]).filter(Boolean) as string[]
}

function recordPreviewIndex(rec: LearningRecord, fileId: number): number {
  const list = recordPreviewList(rec)
  const url = imageUrls.value[fileId]
  if (!url) return 0
  const idx = list.indexOf(url)
  return idx >= 0 ? idx : 0
}

const IMAGE_CONCURRENCY = 4

async function loadImages(list: LearningRecord[]) {
  for (const url of Object.values(imageUrls.value)) URL.revokeObjectURL(url)
  imageUrls.value = {}
  const files = list.flatMap((rec) => rec.files || [])
  await asyncPool(files, IMAGE_CONCURRENCY, async (f) => {
    try {
      imageUrls.value[f.id] = await learningFileObjectUrl(f.id, { thumb: true })
    } catch {
      /* ignore */
    }
  })
}

async function load() {
  loading.value = true
  try {
    student.value = await getStudentApi(studentId.value)
    records.value = await listLearningApi({ student_id: studentId.value })
  } finally {
    loading.value = false
  }
  void loadImages(records.value)
}

function formatTime(v?: string | null) {
  if (!v) return ''
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

const reportLoading = ref(false)
const reportVisible = ref(false)
const reportMode = ref<'all' | 'range' | 'records'>('all')
const reportRange = ref<[string, string] | null>(null)
const reportRecordIds = ref<number[]>([])

function writeLearning() {
  router.push({ path: '/m/learning/new', query: { student_id: String(studentId.value) } })
}

function openReportDialog() {
  reportMode.value = 'all'
  reportRange.value = null
  reportRecordIds.value = []
  reportVisible.value = true
}

function toDateParam(v: string | Date | null | undefined): string | undefined {
  if (v == null || v === '') return undefined
  if (typeof v === 'string') {
    const m = v.match(/^(\d{4}-\d{2}-\d{2})/)
    return m ? m[1] : undefined
  }
  if (v instanceof Date && !Number.isNaN(v.getTime())) {
    const y = v.getFullYear()
    const mo = String(v.getMonth() + 1).padStart(2, '0')
    const day = String(v.getDate()).padStart(2, '0')
    return `${y}-${mo}-${day}`
  }
  return undefined
}

function recordOptionLabel(r: LearningRecord): string {
  const when = r.class_date ? new Date(r.class_date).toLocaleString() : `#${r.id}`
  const st = classLabels[r.class_status] || r.class_status || ''
  const sub = r.subject ? ` · ${r.subject}` : ''
  const summary = (r.learning_summary || '').replace(/\s+/g, ' ').slice(0, 20)
  const tail = summary ? ` · ${summary}${summary.length >= 20 ? '…' : ''}` : ''
  return `${when} ${st}${sub}${tail}`
}

async function submitReport() {
  if (!student.value) return
  if (reportMode.value === 'records' && !reportRecordIds.value.length) {
    ElMessage.warning('请至少勾选一条学情记录')
    return
  }
  if (reportMode.value === 'range' && !reportRange.value?.[0] && !reportRange.value?.[1]) {
    ElMessage.warning('请选择学情时间区间，或改选「全部学情」')
    return
  }
  reportLoading.value = true
  try {
    if (reportMode.value === 'records') {
      await downloadGrowthReportApi(student.value.id, student.value.name, {
        record_ids: [...reportRecordIds.value],
      })
      ElMessage.success(
        reportRecordIds.value.length === 1
          ? '成长档案已开始下载（指定 1 条学情）'
          : `成长档案已开始下载（指定 ${reportRecordIds.value.length} 条学情）`,
      )
    } else if (reportMode.value === 'range') {
      await downloadGrowthReportApi(student.value.id, student.value.name, {
        date_from: toDateParam(reportRange.value?.[0]),
        date_to: toDateParam(reportRange.value?.[1]),
      })
      ElMessage.success('成长档案已开始下载（按时间区间）')
    } else {
      await downloadGrowthReportApi(student.value.id, student.value.name)
      ElMessage.success('成长档案已开始下载（全部学情）')
    }
    reportVisible.value = false
  } catch {
    /* interceptor */
  } finally {
    reportLoading.value = false
  }
}

watch(studentId, load)
onMounted(load)
onUnmounted(() => {
  for (const url of Object.values(imageUrls.value)) URL.revokeObjectURL(url)
})
</script>

<template>
  <div v-loading="loading" class="page">
    <el-page-header @back="router.push('/m/students')">
      <template #content>
        <span>{{ student?.name || '学生详情' }}</span>
      </template>
    </el-page-header>

    <el-card v-if="student" class="profile" shadow="never">
      <p><b>年级</b> {{ student.grade }}</p>
      <p><b>学校</b> {{ student.school || '—' }}</p>
      <p><b>学管师</b> {{ student.academic_manager_name || '—' }}</p>
      <p><b>电话</b> {{ student.phone || '—' }}</p>
      <p v-if="student.parent_name"><b>家长</b> {{ student.parent_name }}</p>
      <p v-if="student.notes"><b>备注</b> {{ student.notes }}</p>
    </el-card>

    <el-button type="primary" plain size="large" class="write-btn" @click="openReportDialog">
      生成学情报告
    </el-button>

    <div class="section-row">
      <h3 class="section-title">学情记录</h3>
      <el-button type="primary" size="small" class="report-btn" @click="writeLearning">
        编写学情
      </el-button>
    </div>
    <el-empty v-if="!records.length" description="暂无学情，点击「编写学情」开始记录" />
    <el-card v-for="r in records" :key="r.id" class="rec" shadow="hover">
      <div class="rec-head">
        <div class="rec-tags">
          <el-tag
            size="small"
            effect="dark"
            :type="classTagType[r.class_status] || 'info'"
            class="tag-status"
          >
            {{ classLabels[r.class_status] || r.class_status }}
          </el-tag>
          <el-tag v-if="r.subject" size="small" effect="plain" type="warning" class="tag-subject">
            {{ r.subject }}
          </el-tag>
          <el-tag v-if="r.teacher_name" size="small" effect="plain" type="info" class="tag-author">
            填写人 · {{ r.teacher_name }}
          </el-tag>
        </div>
        <span class="time">{{ formatTime(r.class_date) }}</span>
      </div>

      <div class="rec-fields">
        <div class="rec-field">
          <div class="rec-field-title">学习情况</div>
          <div class="rec-field-content">{{ r.learning_summary || '—' }}</div>
        </div>

        <div v-if="r.homework_note" class="rec-field">
          <div class="rec-field-title">作业 / 下次</div>
          <div class="rec-field-content">{{ r.homework_note }}</div>
        </div>

        <div v-if="r.notes" class="rec-field">
          <div class="rec-field-title">内部备注</div>
          <div class="rec-field-content">{{ r.notes }}</div>
        </div>

        <div v-if="r.files?.length" class="rec-field">
          <div class="rec-field-title">
            附件图片
            <span class="rec-field-count">{{ r.files.length }}</span>
          </div>
          <div class="imgs">
            <el-image
              v-for="f in r.files"
              :key="f.id"
              :src="imageUrls[f.id]"
              fit="cover"
              class="thumb"
              lazy
              :preview-src-list="recordPreviewList(r)"
              :initial-index="recordPreviewIndex(r, f.id)"
              preview-teleported
            />
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="reportVisible"
      title="生成学情报告"
      width="92%"
      style="max-width: 420px"
      destroy-on-close
    >
      <p class="report-hint">全部 / 时间区间 / 指定某次学情。PDF 不展示筛选条件。</p>
      <el-radio-group v-model="reportMode" size="small" class="report-mode">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="range">区间</el-radio-button>
        <el-radio-button value="records">指定</el-radio-button>
      </el-radio-group>
      <el-date-picker
        v-if="reportMode === 'range'"
        v-model="reportRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始"
        end-placeholder="结束"
        value-format="YYYY-MM-DD"
        format="YYYY-MM-DD"
        style="width: 100%; margin-top: 12px"
        clearable
      />
      <el-checkbox-group
        v-if="reportMode === 'records'"
        v-model="reportRecordIds"
        class="report-record-list"
      >
        <el-checkbox
          v-for="r in records"
          :key="r.id"
          :value="r.id"
          :label="r.id"
          class="report-record-item"
        >
          {{ recordOptionLabel(r) }}
        </el-checkbox>
      </el-checkbox-group>
      <el-empty
        v-if="reportMode === 'records' && !records.length"
        description="暂无学情"
        :image-size="48"
      />
      <template #footer>
        <el-button @click="reportVisible = false">取消</el-button>
        <el-button type="primary" :loading="reportLoading" @click="submitReport">生成 PDF</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 80px;
}

.profile {
  margin: 12px 0;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.profile p {
  margin: 4px 0;
  font-size: 14px;
}

.write-btn {
  display: block;
  width: 100%;
  margin: 0 0 14px !important; /* 覆盖 .el-button + .el-button 的 margin-left */
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 0 0 10px;
}

.section-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  min-width: 0;
}

.report-btn {
  flex-shrink: 0;
  margin: 0 !important;
}

.rec {
  margin-bottom: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.rec :deep(.el-card__body) {
  padding: 12px 14px 14px;
}

.rec-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--oc-border, #f0e9dc);
}

.rec-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.tag-status {
  font-weight: 650;
}

.tag-subject {
  --el-tag-border-color: #e8c98a;
  --el-tag-text-color: #92400e;
  --el-tag-bg-color: #fff7ed;
  font-weight: 600;
}

.tag-author {
  --el-tag-border-color: #c4b5a0;
  --el-tag-text-color: #57534e;
  --el-tag-bg-color: #f5f0e6;
}

.time {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  flex-shrink: 0;
  padding-top: 2px;
}

.rec-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rec-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rec-field-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  border-left: 3px solid var(--oc-primary, #a16207);
  padding-left: 8px;
  line-height: 1.4;
  display: flex;
  align-items: center;
  gap: 6px;
}

.rec-field-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  background: #f5e6c8;
  color: var(--oc-primary, #a16207);
}

.rec-field-content {
  margin: 0;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.55;
  color: #57534e;
  white-space: pre-wrap;
  word-break: break-word;
  padding-left: 11px;
}

.imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-left: 11px;
}

.thumb {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.report-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  line-height: 1.5;
}

.report-mode {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}

.report-record-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 240px;
  overflow-y: auto;
  width: 100%;
  margin-top: 12px;
}

.report-record-item {
  margin: 0 !important;
  height: auto;
  align-items: flex-start;
  white-space: normal;
  line-height: 1.4;
  padding: 8px 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
}

.report-record-item :deep(.el-checkbox__label) {
  white-space: normal;
  font-size: 12px;
}
</style>
