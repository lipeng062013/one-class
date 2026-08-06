<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/learning')
const formRef = ref<FormInstance>()
const loading = ref(false)
const studentLoading = ref(false)
const students = ref<Student[]>([])
const fileList = ref<UploadUserFile[]>([])

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
      class_date: form.class_date ? form.class_date.toISOString() : null,
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
  await searchStudents('')
  await ensurePrefilledStudent()
})
</script>

<template>
  <div class="page oc-page-shell">
    <div class="page-toolbar">
      <el-page-header content="编写学情" @back="goBack" />
      <el-button plain @click="goBack()">学情列表</el-button>
    </div>

    <el-card class="form-card" shadow="never">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
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
        </el-form-item>
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
          <el-input
            v-model="form.learning_summary"
            type="textarea"
            :rows="4"
            placeholder="今日掌握、问题、亮点…"
          />
        </el-form-item>
        <el-form-item label="作业 / 下次">
          <el-input v-model="form.homework_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="备注">
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
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          提交学情
        </el-button>
      </el-form>
    </el-card>
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

.status-group {
  display: flex;
  flex-wrap: wrap;
}
</style>
