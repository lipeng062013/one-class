<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createKnowledge,
  deleteKnowledge,
  listKnowledge,
  updateKnowledge,
  type KnowledgeEntry,
} from '../../api/knowledge'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const loading = ref(false)
const rows = ref<KnowledgeEntry[]>([])
const category = ref('')
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const saving = ref(false)

const form = reactive({
  category: 'faq',
  title: '',
  content: '',
  tags: '',
  is_active: true,
})

const rules: FormRules = {
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
}

const categoryLabels: Record<string, string> = {
  course: '课程',
  faq: 'FAQ',
  tone: '语气',
  banned: '禁用词',
  staff: '师资',
  process: '流程',
}

async function load() {
  loading.value = true
  try {
    rows.value = await listKnowledge(category.value || undefined)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.category = 'faq'
  form.title = ''
  form.content = ''
  form.tags = ''
  form.is_active = true
  dialogVisible.value = true
}

function openEdit(row: KnowledgeEntry) {
  editingId.value = row.id
  form.category = row.category
  form.title = row.title
  form.content = row.content
  form.tags = row.tags
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    if (editingId.value) {
      await updateKnowledge(editingId.value, { ...form })
      ElMessage.success('已更新')
    } else {
      await createKnowledge({ ...form })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function remove(row: KnowledgeEntry) {
  await ElMessageBox.confirm(`删除「${row.title}」？`, '确认', { type: 'warning' })
  await deleteKnowledge(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <el-page-header content="知识库" />
      <el-space wrap>
        <el-select v-model="category" clearable placeholder="分类" style="width: 140px" @change="load">
          <el-option v-for="(label, key) in categoryLabels" :key="key" :label="label" :value="key" />
        </el-select>
        <el-button v-if="auth.isAdmin" type="primary" @click="openCreate">新建</el-button>
      </el-space>
    </div>

    <el-alert
      v-if="!auth.isAdmin"
      style="margin-top: 12px"
      type="info"
      :closable="false"
      title="运营账号为只读；修改请联系负责人。"
    />

    <el-card style="margin-top: 16px" v-loading="loading">
      <el-table :data="rows" stripe>
        <el-table-column label="分类" width="100">
          <template #default="{ row }">{{ categoryLabels[row.category] || row.category }}</template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="content" label="内容" min-width="220" show-overflow-tooltip />
        <el-table-column prop="tags" label="标签" width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="auth.isAdmin" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑条目' : '新建条目'"
      width="90%"
      style="max-width: 560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" style="width: 100%">
            <el-option v-for="(label, key) in categoryLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="form.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
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
}
</style>
