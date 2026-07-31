<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadUserFile } from 'element-plus'
import {
  createLearningApi,
  downloadGrowthReportApi,
  getStudentApi,
  learningFileObjectUrl,
  listLearningApi,
  uploadLearningFileApi,
  type ClassStatus,
  type LearningRecord,
  type Student,
} from '../../api/students'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { asyncPool } from '../../utils/asyncPool'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isMobile } = useBreakpoint()
const descCols = computed(() => (isMobile.value ? 1 : 2))

const loading = ref(false)
const student = ref<Student | null>(null)
const records = ref<LearningRecord[]>([])
const imageUrls = ref<Record<number, string>>({})

const writeVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const fileList = ref<UploadUserFile[]>([])
const form = reactive({
  class_date: new Date() as Date | null,
  class_status: 'attended' as ClassStatus,
  subject: '',
  learning_summary: '',
  homework_note: '',
  notes: '',
})

const canWrite = computed(() => auth.user?.role === 'admin' || auth.user?.role === 'teacher')
const reportLoading = ref(false)
const reportVisible = ref(false)
/** all | range | records */
const reportMode = ref<'all' | 'range' | 'records'>('all')
/** 学情报告区间 YYYY-MM-DD */
const reportRange = ref<[string, string] | null>(null)
/** 指定学情记录 id */
const reportRecordIds = ref<number[]>([])

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
  const summary = (r.learning_summary || '').replace(/\s+/g, ' ').slice(0, 24)
  const tail = summary ? ` · ${summary}${summary.length >= 24 ? '…' : ''}` : ''
  return `${when}  ${st}${sub}${tail}`
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
      const from = toDateParam(reportRange.value?.[0])
      const to = toDateParam(reportRange.value?.[1])
      await downloadGrowthReportApi(student.value.id, student.value.name, {
        date_from: from,
        date_to: to,
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

const statusLabels: Record<string, string> = {
  active: '在读',
  paused: '暂停',
  graduated: '结业',
  quit: '退学',
}
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

const rules: FormRules = {
  learning_summary: [{ required: true, message: '请填写学习情况', trigger: 'blur' }],
  class_status: [{ required: true, message: '请选择上课状态', trigger: 'change' }],
}

const studentId = computed(() => Number(route.params.id))

/** 学情附件预览列表（仅已加载成功的 URL，保持与文件顺序一致） */
function recordPreviewList(rec: LearningRecord): string[] {
  return (rec.files || []).map((f) => imageUrls.value[f.id]).filter(Boolean) as string[]
}

/** 点击某张缩略图时，大图从该张开始（而不是总从第一张） */
function recordPreviewIndex(rec: LearningRecord, fileId: number): number {
  const list = recordPreviewList(rec)
  const url = imageUrls.value[fileId]
  if (!url) return 0
  const idx = list.indexOf(url)
  return idx >= 0 ? idx : 0
}

const IMAGE_CONCURRENCY = 4

async function loadImages(list: LearningRecord[]) {
  for (const key of Object.keys(imageUrls.value)) {
    URL.revokeObjectURL(imageUrls.value[Number(key)])
  }
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
  // 正文先出来，缩略图后台并发加载
  void loadImages(records.value)
}

function openWrite() {
  form.class_date = new Date()
  form.class_status = 'attended'
  form.subject = ''
  form.learning_summary = ''
  form.homework_note = ''
  form.notes = ''
  fileList.value = []
  writeVisible.value = true
}

async function submitLearning() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const rec = await createLearningApi({
      student_id: studentId.value,
      class_date: form.class_date ? form.class_date.toISOString() : null,
      class_status: form.class_status,
      subject: form.subject || null,
      learning_summary: form.learning_summary,
      homework_note: form.homework_note,
      notes: form.notes,
    })
    for (const item of fileList.value) {
      if (item.raw) {
        await uploadLearningFileApi(rec.id, item.raw as File)
      }
    }
    ElMessage.success('学情已提交')
    writeVisible.value = false
    await load()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

watch(studentId, load)
onMounted(load)
onUnmounted(() => {
  for (const url of Object.values(imageUrls.value)) {
    URL.revokeObjectURL(url)
  }
})
</script>

<template>
  <div v-loading="loading" class="student-detail-page oc-page-shell">
    <div class="page-toolbar">
      <el-page-header @back="router.push('/students')">
        <template #content>
          <span>学生详情{{ student ? ` · ${student.name}` : '' }}</span>
        </template>
      </el-page-header>
      <el-button type="primary" plain @click="openReportDialog">生成学情报告</el-button>
    </div>

    <el-card v-if="student" class="profile" shadow="never">
      <el-descriptions :column="descCols" border>
        <el-descriptions-item label="姓名">{{ student.name }}</el-descriptions-item>
        <el-descriptions-item label="年级">{{ student.grade }}</el-descriptions-item>
        <el-descriptions-item label="学校">{{ student.school || '—' }}</el-descriptions-item>
        <el-descriptions-item label="学管师">
          {{ student.academic_manager_name || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="电话">{{ student.phone || '—' }}</el-descriptions-item>
        <el-descriptions-item label="家长">{{ student.parent_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          {{ statusLabels[student.status] || student.status }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ student.notes || '—' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <div class="section-row">
      <h3 class="section-title">学情时间线</h3>
      <el-button v-if="canWrite" type="primary" @click="openWrite">编写学情</el-button>
    </div>
    <el-empty v-if="!records.length" description="暂无学情，点击「编写学情」开始记录" />
    <el-timeline v-else class="learning-timeline">
      <el-timeline-item
        v-for="r in records"
        :key="r.id"
        :timestamp="formatTime(r.class_date)"
        placement="top"
      >
        <el-card shadow="hover" class="rec-card">
          <div class="rec-head">
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

            <div v-if="r.files?.length" class="rec-field rec-field-imgs">
              <div class="rec-field-title">
                附件图片
                <span class="rec-field-count">{{ r.files.length }}</span>
              </div>
              <div class="imgs">
                <el-image
                  v-for="f in r.files"
                  :key="f.id"
                  :src="imageUrls[f.id]"
                  :preview-src-list="recordPreviewList(r)"
                  :initial-index="recordPreviewIndex(r, f.id)"
                  preview-teleported
                  lazy
                  fit="cover"
                  class="thumb"
                />
              </div>
            </div>
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>

    <el-dialog
      v-model="reportVisible"
      title="生成学情报告"
      width="90%"
      style="max-width: 520px"
      destroy-on-close
    >
      <p class="report-hint">
        可导出全部学情、按上课日期区间，或勾选指定的某一次/几次学情。PDF 正文不展示筛选条件。
      </p>
      <el-form label-position="top">
        <el-form-item label="导出范围">
          <el-radio-group v-model="reportMode" class="report-mode">
            <el-radio-button value="all">全部学情</el-radio-button>
            <el-radio-button value="range">时间区间</el-radio-button>
            <el-radio-button value="records">指定学情</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="reportMode === 'range'" label="学情上课日期">
          <el-date-picker
            v-model="reportRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            style="width: 100%"
            clearable
          />
        </el-form-item>

        <el-form-item v-if="reportMode === 'records'" label="选择学情记录">
          <el-empty v-if="!records.length" description="暂无学情可选" :image-size="64" />
          <el-checkbox-group v-else v-model="reportRecordIds" class="report-record-list">
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
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportVisible = false">取消</el-button>
        <el-button type="primary" :loading="reportLoading" @click="submitReport">
          生成 PDF
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="writeVisible" title="编写学情" width="90%" style="max-width: 560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="上课日期">
          <el-date-picker v-model="form.class_date" type="datetime" style="width: 100%" />
        </el-form-item>
        <el-form-item label="上课状态" prop="class_status">
          <el-radio-group v-model="form.class_status" class="status-group">
            <el-radio-button v-for="(label, key) in classLabels" :key="key" :value="key">
              {{ label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="科目">
          <el-input v-model="form.subject" placeholder="可选" />
        </el-form-item>
        <el-form-item label="学习情况" prop="learning_summary">
          <el-input v-model="form.learning_summary" type="textarea" :rows="4" placeholder="今日掌握点、问题、亮点…" />
        </el-form-item>
        <el-form-item label="作业 / 下次建议">
          <el-input v-model="form.homework_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内部备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="图片">
          <el-upload
            v-model:file-list="fileList"
            list-type="picture-card"
            :auto-upload="false"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="writeVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitLearning">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.profile {
  margin-bottom: 20px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 0 12px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0;
  font-size: 1.05rem;
  color: var(--oc-ink, #44403c);
}

.status-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.status-group :deep(.el-radio-button) {
  margin: 0;
}

@media (max-width: 767px) {
  .section-row .el-button {
    width: 100%;
  }

  .thumb {
    width: 96px;
    height: 96px;
  }
}

.rec-card {
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
}

.rec-card :deep(.el-card__body) {
  padding: 14px 16px 16px;
}

/* 顶部：上课状态 / 科目 / 填写人 — 不同色标签 */
.rec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--oc-border, #f0e9dc);
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

/* 字段区：左标题右内容，一眼区分 */
.rec-fields {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.rec-field {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 10px 14px;
  padding: 12px 0;
  border-bottom: 1px dashed #efe8db;
  align-items: start;
}

.rec-field:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.rec-field:first-child {
  padding-top: 0;
}

.rec-field-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  line-height: 1.5;
  padding-top: 1px;
  display: flex;
  align-items: center;
  gap: 6px;
  /* 左侧色条强调「这是标题」 */
  border-left: 3px solid var(--oc-primary, #a16207);
  padding-left: 8px;
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
  line-height: 1.6;
  color: #57534e;
  white-space: pre-wrap;
  word-break: break-word;
  min-width: 0;
}

.rec-field-imgs .rec-field-content,
.rec-field-imgs .imgs {
  grid-column: 2;
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
}

.report-record-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 280px;
  overflow-y: auto;
  width: 100%;
  padding: 4px 0;
}

.report-record-item {
  margin: 0 !important;
  height: auto;
  align-items: flex-start;
  white-space: normal;
  line-height: 1.45;
  padding: 8px 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fffdf8;
}

.report-record-item :deep(.el-checkbox__label) {
  white-space: normal;
  font-size: 13px;
  color: var(--oc-ink, #44403c);
}

.imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.thumb {
  width: 72px;
  height: 72px;
  border-radius: 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

/* 窄屏：标题在上、内容在下，仍保持标题加粗 + 色条 */
@media (max-width: 767px) {
  .rec-field {
    grid-template-columns: 1fr;
    gap: 6px;
  }

  .rec-field-imgs .imgs {
    grid-column: 1;
  }

  .thumb {
    width: 88px;
    height: 88px;
  }
}

/*
 * EP 默认 is-start 左内边距 40px + wrapper 28px，PC 也偏宽。
 * 统一收紧：节点/竖线左移，内容区更贴左。
 */
.learning-timeline {
  padding-left: 12px !important;
  padding-right: 0 !important;
}

.learning-timeline :deep(.el-timeline-item__wrapper) {
  padding-left: 16px !important;
}

.learning-timeline :deep(.el-timeline-item__tail) {
  left: 2px;
}

.learning-timeline :deep(.el-timeline-item__node) {
  left: 0;
}

.learning-timeline :deep(.el-timeline-item__timestamp) {
  font-size: 12px;
}

.learning-timeline :deep(.el-timeline-item__timestamp.is-top) {
  margin-bottom: 6px;
}

@media (max-width: 991px) {
  .learning-timeline {
    padding-left: 10px !important;
  }

  .learning-timeline :deep(.el-timeline-item__wrapper) {
    padding-left: 14px !important;
  }

  .rec-card :deep(.el-card__body) {
    padding: 12px;
  }
}

@media (max-width: 767px) {
  .learning-timeline {
    padding-left: 8px !important;
  }

  .learning-timeline :deep(.el-timeline-item__wrapper) {
    padding-left: 12px !important;
  }

  .learning-timeline :deep(.el-timeline-item) {
    padding-bottom: 14px;
  }
}
</style>
