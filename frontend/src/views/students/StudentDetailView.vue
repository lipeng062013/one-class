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

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

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

async function downloadReport() {
  if (!student.value) return
  reportLoading.value = true
  try {
    await downloadGrowthReportApi(student.value.id, student.value.name)
    ElMessage.success('成长档案已开始下载')
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

const rules: FormRules = {
  learning_summary: [{ required: true, message: '请填写学习情况', trigger: 'blur' }],
  class_status: [{ required: true, message: '请选择上课状态', trigger: 'change' }],
}

const studentId = computed(() => Number(route.params.id))

async function loadImages(list: LearningRecord[]) {
  for (const key of Object.keys(imageUrls.value)) {
    URL.revokeObjectURL(imageUrls.value[Number(key)])
  }
  imageUrls.value = {}
  for (const rec of list) {
    for (const f of rec.files || []) {
      try {
        imageUrls.value[f.id] = await learningFileObjectUrl(f.id)
      } catch {
        /* ignore */
      }
    }
  }
}

async function load() {
  loading.value = true
  try {
    student.value = await getStudentApi(studentId.value)
    records.value = await listLearningApi({ student_id: studentId.value })
    await loadImages(records.value)
  } finally {
    loading.value = false
  }
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
  <div v-loading="loading">
    <div class="toolbar">
      <el-page-header @back="router.push('/students')">
        <template #content>
          <span>学生详情{{ student ? ` · ${student.name}` : '' }}</span>
        </template>
      </el-page-header>
      <el-button v-if="canWrite" type="primary" @click="openWrite">写学情</el-button>
    </div>

    <el-card v-if="student" class="profile" shadow="never">
      <el-descriptions :column="2" border>
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
      <el-button type="primary" plain :loading="reportLoading" @click="downloadReport">
        生成学情报告
      </el-button>
    </div>
    <el-empty v-if="!records.length" description="暂无学情，点击右上角「写学情」开始记录" />
    <el-timeline v-else>
      <el-timeline-item
        v-for="r in records"
        :key="r.id"
        :timestamp="formatTime(r.class_date)"
        placement="top"
      >
        <el-card shadow="hover" class="rec-card">
          <div class="rec-head">
            <el-tag size="small">{{ classLabels[r.class_status] || r.class_status }}</el-tag>
            <span v-if="r.subject" class="meta">{{ r.subject }}</span>
            <span class="meta">{{ r.teacher_name }}</span>
          </div>
          <p class="summary">{{ r.learning_summary }}</p>
          <p v-if="r.homework_note" class="sub">作业/下次：{{ r.homework_note }}</p>
          <p v-if="r.notes" class="sub">备注：{{ r.notes }}</p>
          <div v-if="r.files?.length" class="imgs">
            <el-image
              v-for="f in r.files"
              :key="f.id"
              :src="imageUrls[f.id]"
              :preview-src-list="r.files.map((x) => imageUrls[x.id]).filter(Boolean)"
              fit="cover"
              class="thumb"
            />
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>

    <el-dialog v-model="writeVisible" title="写学情" width="90%" style="max-width: 560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="上课日期">
          <el-date-picker v-model="form.class_date" type="datetime" style="width: 100%" />
        </el-form-item>
        <el-form-item label="上课状态" prop="class_status">
          <el-radio-group v-model="form.class_status">
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
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

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

.rec-card {
  background: var(--oc-card, #fffdf8);
}

.rec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.meta {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.summary {
  margin: 0 0 6px;
  white-space: pre-wrap;
}

.sub {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.thumb {
  width: 72px;
  height: 72px;
  border-radius: 8px;
}
</style>
