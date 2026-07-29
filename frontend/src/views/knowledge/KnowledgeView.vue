<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const rows = ref<KnowledgeEntry[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const saving = ref(false)

const sectionMap: Record<string, { category: string; title: string; desc: string }> = {
  scripts: {
    category: 'script',
    title: '沟通话术',
    desc: '培养新人学管师：电话/面谈开场、邀约、跟进话术',
  },
  objections: {
    category: 'objection',
    title: '异议处理',
    desc: '价格、考虑、竞品等常见异议应对',
  },
  banned: {
    category: 'banned',
    title: '禁用词列表',
    desc: '对外表达合规红线，文案生成时也会参考',
  },
}

const section = computed(() => {
  const key = String(route.params.section || 'scripts')
  return sectionMap[key] || sectionMap.scripts
})

const form = reactive({
  category: 'script',
  title: '',
  content: '',
  tags: '',
  is_active: true,
})

const rules: FormRules = {
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  content: [{ required: true, message: '请填写内容', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    rows.value = await listKnowledge(section.value.category)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.category = section.value.category
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
    form.category = section.value.category
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

watch(
  () => route.params.section,
  () => {
    if (!sectionMap[String(route.params.section || '')]) {
      router.replace('/knowledge/scripts')
      return
    }
    load()
  },
)

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <el-page-header :content="`成长中心 · ${section.title}`" />
        <p class="desc">{{ section.desc }}</p>
      </div>
      <el-button v-if="auth.isAdmin" type="primary" @click="openCreate">新建</el-button>
    </div>

    <el-alert
      v-if="!auth.isAdmin"
      style="margin-top: 12px"
      type="info"
      :closable="false"
      title="运营可阅读成长中心内容；新建/编辑仅负责人可操作。"
    />

    <el-card style="margin-top: 16px" v-loading="loading">
      <el-empty v-if="!rows.length" description="暂无内容" />
      <el-table v-else :data="rows" stripe>
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="content" label="内容" min-width="260" show-overflow-tooltip />
        <el-table-column prop="tags" label="标签" width="120" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="auth.isAdmin" label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑' : '新建'"
      width="90%"
      style="max-width: 560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="6" />
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}
</style>
