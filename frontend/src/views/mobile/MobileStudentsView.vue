<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  createStudentApi,
  listManagersApi,
  listStudentsApi,
  type ManagerOption,
  type Student,
} from '../../api/students'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const rows = ref<Student[]>([])
const managers = ref<ManagerOption[]>([])
const gradeFilter = ref('')
const q = ref('')

const createVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  grade: '',
  school: '',
  phone: '',
  parent_name: '',
  academic_manager_id: undefined as number | undefined,
  notes: '',
})

const gradeOptions = [
  '一年级',
  '二年级',
  '三年级',
  '四年级',
  '五年级',
  '六年级',
  '初一',
  '初二',
  '初三',
  '高一',
  '高二',
  '高三',
  '其他',
]

const rules: FormRules = {
  name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  grade: [{ required: true, message: '请选择年级', trigger: 'change' }],
  school: [{ required: true, message: '请填写学校', trigger: 'blur' }],
  academic_manager_id: [{ required: true, message: '请选择学管师', trigger: 'change' }],
}

async function load() {
  loading.value = true
  try {
    const params: Record<string, string | number> = { status: 'active' }
    if (gradeFilter.value) params.grade = gradeFilter.value
    if (q.value.trim()) {
      // 后端支持 name/phone 分开；这里先按姓名，电话可再查
      if (/^\d+$/.test(q.value.trim())) params.phone = q.value.trim()
      else params.name = q.value.trim()
    }
    rows.value = await listStudentsApi(params)
  } finally {
    loading.value = false
  }
}

async function loadManagers() {
  managers.value = await listManagersApi(false)
  // 默认自己为学管师
  const me = managers.value.find((m) => m.id === auth.user?.id)
  if (me) form.academic_manager_id = me.id
}

function openCreate() {
  form.name = ''
  form.grade = ''
  form.school = ''
  form.phone = ''
  form.parent_name = ''
  form.notes = ''
  const me = managers.value.find((m) => m.id === auth.user?.id)
  form.academic_manager_id = me?.id
  createVisible.value = true
}

async function submitCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createStudentApi({
      name: form.name,
      grade: form.grade,
      school: form.school,
      phone: form.phone || null,
      parent_name: form.parent_name || null,
      academic_manager_id: form.academic_manager_id ?? null,
      notes: form.notes,
    })
    ElMessage.success('学生已添加')
    createVisible.value = false
    await load()
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await loadManagers()
  await load()
})
</script>

<template>
  <div class="page">
    <div class="head">
      <h2>我的学生</h2>
      <el-button type="primary" size="small" @click="openCreate">新建</el-button>
    </div>

    <el-input
      v-model="q"
      clearable
      placeholder="搜姓名或电话"
      size="large"
      class="search"
      @keyup.enter="load"
      @clear="load"
    >
      <template #append>
        <el-button @click="load">搜索</el-button>
      </template>
    </el-input>

    <div class="chips">
      <el-check-tag
        :checked="!gradeFilter"
        @change="
          () => {
            gradeFilter = ''
            load()
          }
        "
      >
        全部年级
      </el-check-tag>
      <el-check-tag
        v-for="g in gradeOptions.slice(0, 9)"
        :key="g"
        :checked="gradeFilter === g"
        @change="
          (v: boolean) => {
            gradeFilter = v ? g : ''
            load()
          }
        "
      >
        {{ g }}
      </el-check-tag>
    </div>

    <div v-loading="loading" class="list">
      <el-empty v-if="!rows.length" description="暂无学生，点右上角新建" />
      <el-card
        v-for="s in rows"
        :key="s.id"
        class="card"
        shadow="hover"
        @click="router.push(`/m/students/${s.id}`)"
      >
        <div class="row1">
          <strong>{{ s.name }}</strong>
          <el-tag size="small" type="info">{{ s.grade }}</el-tag>
        </div>
        <div class="row2">{{ s.school || '未填学校' }}</div>
        <div class="row2">
          {{ s.phone || '无电话' }}
          <span v-if="s.academic_manager_name"> · 学管 {{ s.academic_manager_name }}</span>
        </div>
      </el-card>
    </div>

    <el-dialog v-model="createVisible" title="新建学生" width="92%" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-select v-model="form.grade" style="width: 100%" filterable allow-create>
            <el-option v-for="g in gradeOptions" :key="g" :label="g" :value="g" />
          </el-select>
        </el-form-item>
        <el-form-item label="学校" prop="school">
          <el-input v-model="form.school" />
        </el-form-item>
        <el-form-item label="学管师（班主任）" prop="academic_manager_id">
          <el-select v-model="form.academic_manager_id" style="width: 100%">
            <el-option
              v-for="m in managers"
              :key="m.id"
              :label="m.display_name"
              :value="m.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="家长称呼">
          <el-input v-model="form.parent_name" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 72px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

h2 {
  margin: 0;
  font-size: 1.15rem;
}

.search {
  margin-bottom: 10px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
}

.card {
  cursor: pointer;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.row1 {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.row2 {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-top: 2px;
}
</style>
