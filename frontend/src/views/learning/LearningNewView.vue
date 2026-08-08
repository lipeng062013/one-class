<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadUserFile } from 'element-plus'
import {
  createLearningApi,
  getStudentApi,
  listStudentsApi,
  uploadLearningFileApi,
  type ClassStatus,
  type Student,
} from '../../api/students'
import { usePageBack } from '../../composables/usePageBack'
import { useBreakpoint } from '../../composables/useBreakpoint'
import MobileActionBar from '../../components/MobileActionBar.vue'
import { toBusinessDateTimeIso } from '../../utils/datetime'

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/learning')
const { isApp } = useBreakpoint()
const formRef = ref<FormInstance>()
const loading = ref(false)
const studentLoading = ref(false)
const students = ref<Student[]>([])
const fileList = ref<UploadUserFile[]>([])
const uploadField = ref<HTMLElement>()

const form = reactive({
  student_id: undefined as number | undefined,
  class_date: new Date() as Date | null,
  class_status: 'attended' as ClassStatus,
  subject: '',
  learning_summary: '',
  homework_note: '',
  notes: '',
})

const classLabels: Record<string, string> = {
  attended: '已上课',
  absent: '缺勤',
  late: '迟到',
  leave: '请假',
  makeup: '补课',
}

const rules: FormRules = {
  student_id: [{ required: true, message: '请选择学生', trigger: 'change' }],
  learning_summary: [{ required: true, message: '请填写学习情况', trigger: 'blur' }],
  class_status: [{ required: true, message: '请选择上课状态', trigger: 'change' }],
}

const prefilled = computed(() => {
  const raw = route.query.student_id
  return raw ? Number(raw) : undefined
})

const selectedStudent = computed(() =>
  students.value.find((s) => s.id === form.student_id) || null,
)

function mergeStudents(items: Student[]) {
  const map = new Map(students.value.map((s) => [s.id, s]))
  for (const s of items) map.set(s.id, s)
  // 已选学员始终保留在选项中，避免远程搜索后选中项消失
  if (form.student_id != null && !map.has(form.student_id)) {
    const kept = students.value.find((s) => s.id === form.student_id)
    if (kept) map.set(kept.id, kept)
  }
  students.value = Array.from(map.values())
}

async function searchStudents(q: string) {
  studentLoading.value = true
  try {
    const res = await listStudentsApi({
      status: 'active',
      q: q.trim() || undefined,
      page: 1,
      page_size: 30,
    }).catch(() => ({ items: [] as Student[] }))
    // 远程结果替换列表，但保留已选
    const selected = form.student_id != null
      ? students.value.find((s) => s.id === form.student_id)
      : undefined
    students.value = res.items
    if (selected && !students.value.some((s) => s.id === selected.id)) {
      students.value = [selected, ...students.value]
    }
  } finally {
    studentLoading.value = false
  }
}

async function ensurePrefilledStudent() {
  const id = prefilled.value
  if (!id || !Number.isFinite(id)) return
  form.student_id = id
  if (students.value.some((s) => s.id === id)) return
  try {
    const s = await getStudentApi(id)
    mergeStudents([s])
  } catch {
    /* ignore */
  }
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.student_id) return
  loading.value = true
  try {
    const rec = await createLearningApi({
      student_id: form.student_id,
      class_date: toBusinessDateTimeIso(form.class_date),
      class_status: form.class_status,
      subject: form.subject || null,
      learning_summary: form.learning_summary,
      homework_note: form.homework_note,
      notes: form.notes,
    })
    for (const item of fileList.value) {
      if (item.raw) await uploadLearningFileApi(rec.id, item.raw as File)
    }
    ElMessage.success('学情已提交')
    await router.replace(`/students/${form.student_id}`)
  } catch {
    /* interceptor */
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // Element Plus keeps the upload trigger's ARIA attributes on the component
  // boundary in some versions. Label the actual keyboard/click target as well.
  await nextTick()
  const trigger = uploadField.value?.querySelector<HTMLElement>('.el-upload--picture-card')
  trigger?.setAttribute('aria-label', '添加学情图片')
  trigger?.setAttribute('title', '添加学情图片')
  await searchStudents('')
  await ensurePrefilledStudent()
})
</script>

<template>
  <div class="page oc-page-shell learning-new-page">
    <div class="page-toolbar" :class="{ 'is-app': isApp }">
      <el-page-header content="编写学情" @back="goBack" />
      <el-button v-if="!isApp" plain @click="goBack()">学情列表</el-button>
    </div>

    <el-card class="form-card" shadow="never">
      <el-form
        ref="formRef"
        class="learning-form"
        :model="form"
        :rules="rules"
        label-position="top"
        :size="isApp ? 'large' : 'default'"
      >
        <section class="form-section">
          <div class="section-title">学员与课次</div>
          <el-form-item label="选择学生" prop="student_id">
            <el-select
              v-model="form.student_id"
              filterable
              remote
              reserve-keyword
              clearable
              :remote-method="searchStudents"
              :loading="studentLoading"
              placeholder="搜索姓名 / 手机号"
              style="width: 100%"
            >
              <el-option
                v-for="s in students"
                :key="s.id"
                :label="`${s.name} · ${s.grade}${s.school ? ' · ' + s.school : ''}`"
                :value="s.id"
              />
            </el-select>
            <div v-if="selectedStudent" class="student-chip">
              <span class="student-chip__av">{{ (selectedStudent.name || '?').slice(0, 1) }}</span>
              <span class="student-chip__copy">
                <strong>{{ selectedStudent.name }}</strong>
                <em>
                  {{ selectedStudent.grade || '未填年级' }}
                  <template v-if="selectedStudent.school"> · {{ selectedStudent.school }}</template>
                </em>
              </span>
            </div>
          </el-form-item>
          <el-form-item label="上课日期">
            <el-date-picker
              v-model="form.class_date"
              type="datetime"
              style="width: 100%"
              placeholder="选择上课时间"
            />
          </el-form-item>
          <el-form-item label="上课状态" prop="class_status">
            <el-radio-group v-model="form.class_status" class="status-group">
              <el-radio-button v-for="(label, key) in classLabels" :key="key" :value="key">
                {{ label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="科目">
            <el-input v-model="form.subject" placeholder="可选，如数学 / 英语" clearable />
          </el-form-item>
        </section>

        <section class="form-section">
          <div class="section-title">学习内容</div>
          <el-form-item class="field-wide" label="学习情况" prop="learning_summary">
            <el-input
              v-model="form.learning_summary"
              type="textarea"
              :rows="isApp ? 5 : 4"
              maxlength="2000"
              show-word-limit
              placeholder="今日掌握、问题、亮点…"
            />
          </el-form-item>
          <el-form-item class="field-wide" label="作业 / 下次">
            <el-input
              v-model="form.homework_note"
              type="textarea"
              :rows="isApp ? 3 : 2"
              maxlength="1000"
              show-word-limit
              placeholder="布置作业、下次课重点（可选）"
            />
          </el-form-item>
          <el-form-item class="field-wide" label="备注">
            <el-input
              v-model="form.notes"
              type="textarea"
              :rows="2"
              maxlength="500"
              show-word-limit
              placeholder="内部备注（可选）"
            />
          </el-form-item>
        </section>

        <section class="form-section">
          <div class="section-title">图片附件</div>
          <el-form-item class="field-wide" label="课堂 / 作业图片">
            <div ref="uploadField" class="upload-wrap">
              <el-upload
                v-model:file-list="fileList"
                list-type="picture-card"
                :auto-upload="false"
                accept="image/*"
                multiple
                aria-label="添加学情图片"
              >
                <el-icon><Plus /></el-icon>
                <span class="oc-visually-hidden">添加学情图片</span>
              </el-upload>
            </div>
            <p class="field-hint">可多选图片，提交时一并上传</p>
          </el-form-item>
        </section>

        <el-button
          v-if="!isApp"
          class="field-wide submit-pc"
          type="primary"
          size="large"
          :loading="loading"
          @click="submit"
        >
          提交学情
        </el-button>
      </el-form>
    </el-card>

    <MobileActionBar :visible="isApp">
      <el-button plain @click="goBack()">取消</el-button>
      <el-button type="primary" :loading="loading" @click="submit">提交学情</el-button>
    </MobileActionBar>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 24px;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.form-card {
  margin-top: 12px;
  width: 100%;
  max-width: none;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  box-sizing: border-box;
}

.form-section {
  margin-bottom: 8px;
}

.section-title {
  font-size: 15px;
  font-weight: 720;
  color: var(--oc-ink, #44403c);
  margin: 4px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-title::before {
  content: '';
  width: 4px;
  height: 14px;
  border-radius: 999px;
  background: linear-gradient(180deg, #d97706, #a16207);
  flex-shrink: 0;
}

.status-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
}

.learning-form {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0 16px;
}

.field-wide {
  grid-column: 1 / -1;
  width: 100%;
}

.student-chip {
  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  background: linear-gradient(135deg, #fffefb, #faf3e6);
}

.student-chip__av {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 750;
  color: #fffdf8;
  background: linear-gradient(145deg, #d97706, #a16207);
  flex-shrink: 0;
}

.student-chip__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.student-chip__copy strong {
  font-size: 14px;
  color: #44403c;
}

.student-chip__copy em {
  font-style: normal;
  font-size: 12px;
  color: #8a8178;
}

.field-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.submit-pc {
  margin-top: 8px;
}

@media (min-width: 768px) and (max-width: 1199px) {
  .learning-form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .form-section {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0 16px;
  }

  .section-title,
  .field-wide {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1199px) {
  .page {
    padding-bottom: 0;
  }

  .page-toolbar.is-app {
    margin-bottom: 2px;
  }

  .form-card {
    margin-top: 4px;
    border: 0;
    border-radius: 0;
    background: transparent;
  }

  .form-card :deep(.el-card__body) {
    padding: 4px 2px 12px;
  }

  .form-section {
    margin-bottom: 14px;
    padding: 14px 12px 8px;
    border-radius: 16px;
    border: 1px solid rgba(181, 145, 83, 0.22);
    background:
      linear-gradient(155deg, rgba(255, 255, 255, 0.92), transparent 48%),
      #fffdf8;
    box-shadow: 0 8px 20px rgba(88, 60, 24, 0.06);
  }

  .section-title {
    margin: 0 0 12px;
    padding-bottom: 0;
    border-bottom: 0;
    font-size: 14px;
  }

  .learning-form :deep(.el-form-item) {
    margin-bottom: 14px;
  }

  .learning-form :deep(.el-form-item__label) {
    font-weight: 650;
    color: #57534e;
    margin-bottom: 6px !important;
    line-height: 1.3;
  }

  .learning-form :deep(.el-input__wrapper),
  .learning-form :deep(.el-select__wrapper),
  .learning-form :deep(.el-textarea__inner) {
    min-height: 44px;
    border-radius: 12px;
  }

  .learning-form :deep(.el-textarea__inner) {
    min-height: 96px;
    padding: 10px 12px;
  }

  .status-group {
    width: 100%;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .status-group :deep(.el-radio-button) {
    margin: 0;
  }

  .status-group :deep(.el-radio-button__inner) {
    width: 100%;
    min-height: 40px;
    padding: 0 6px;
    border-radius: 11px !important;
    border: 1px solid rgba(181, 145, 83, 0.28) !important;
    box-shadow: none !important;
    font-weight: 650;
    background: #fffefb;
  }

  .status-group :deep(.el-radio-button:first-child .el-radio-button__inner),
  .status-group :deep(.el-radio-button:last-child .el-radio-button__inner) {
    border-radius: 11px !important;
  }

  .status-group :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
    color: #fffdf8 !important;
    background: linear-gradient(145deg, #c07a12, #a16207) !important;
    border-color: transparent !important;
  }

  .upload-wrap :deep(.el-upload--picture-card) {
    width: 88px;
    height: 88px;
    border-radius: 14px;
    border-color: rgba(181, 145, 83, 0.35);
    background: #fffefb;
  }

  .upload-wrap :deep(.el-upload-list--picture-card .el-upload-list__item) {
    width: 88px;
    height: 88px;
    border-radius: 14px;
  }
}
</style>
