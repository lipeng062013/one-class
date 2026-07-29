<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  createCopyTemplate,
  createPosterTemplate,
  listCopyTemplates,
  listPosterTemplates,
  type CopyTemplate,
  type PosterTemplate,
} from '../../api/templates'

const tab = ref('copies')
const loading = ref(false)
const copies = ref<CopyTemplate[]>([])
const posters = ref<PosterTemplate[]>([])
const copyDialog = ref(false)
const posterDialog = ref(false)
const copyFormRef = ref<FormInstance>()
const posterFormRef = ref<FormInstance>()
const saving = ref(false)

const copyForm = reactive({
  name: '',
  scene: 'xhs_script',
  body: '痛点：{{pain_point}}\n处理：{{teacher_action}}\n下一步：{{next_step}}',
})
const posterForm = reactive({
  name: '',
  scene: 'xhs_poster',
  layout_json: JSON.stringify(
    {
      width: 750,
      height: 1000,
      background: '#176b4d',
      fields: [
        { key: 'title', x: 40, y: 80, font_size: 48, fill: '#ffffff' },
        { key: 'subtitle', x: 40, y: 180, font_size: 28, fill: '#e8f2ed' },
        { key: 'footer', x: 40, y: 900, font_size: 24, fill: '#ffffff' },
      ],
    },
    null,
    2,
  ),
})

const copyRules: FormRules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  scene: [{ required: true, message: '请填写场景', trigger: 'blur' }],
  body: [{ required: true, message: '请填写正文模板', trigger: 'blur' }],
}
const posterRules: FormRules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  scene: [{ required: true, message: '请填写场景', trigger: 'blur' }],
  layout_json: [{ required: true, message: '请填写 layout_json', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    ;[copies.value, posters.value] = await Promise.all([listCopyTemplates(), listPosterTemplates()])
  } finally {
    loading.value = false
  }
}

async function submitCopy() {
  const ok = await copyFormRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createCopyTemplate({ ...copyForm })
    ElMessage.success('文案模板已创建')
    copyDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}

async function submitPoster() {
  const ok = await posterFormRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    JSON.parse(posterForm.layout_json)
    await createPosterTemplate({ ...posterForm })
    ElMessage.success('海报模板已创建')
    posterDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败（检查 JSON）')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <el-page-header content="模板管理" />
      <el-space>
        <el-button v-if="tab === 'copies'" type="primary" @click="copyDialog = true">新建文案模板</el-button>
        <el-button v-else type="primary" @click="posterDialog = true">新建海报模板</el-button>
      </el-space>
    </div>

    <el-card style="margin-top: 16px" v-loading="loading">
      <el-tabs v-model="tab">
        <el-tab-pane label="文案模板" name="copies">
          <el-table :data="copies" stripe>
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="scene" label="场景" width="120" />
            <el-table-column label="系统" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_system ? 'warning' : 'info'" size="small">
                  {{ row.is_system ? '系统' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="body" label="正文" min-width="220" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="海报模板" name="posters">
          <el-table :data="posters" stripe>
            <el-table-column prop="name" label="名称" min-width="140" />
            <el-table-column prop="scene" label="场景" width="120" />
            <el-table-column label="系统" width="90">
              <template #default="{ row }">
                <el-tag :type="row.is_system ? 'warning' : 'info'" size="small">
                  {{ row.is_system ? '系统' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="layout_json" label="版式 JSON" min-width="220" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="copyDialog" title="新建文案模板" width="90%" style="max-width: 560px" destroy-on-close>
      <el-form ref="copyFormRef" :model="copyForm" :rules="copyRules" label-position="top">
        <el-form-item label="名称" prop="name"><el-input v-model="copyForm.name" /></el-form-item>
        <el-form-item label="场景" prop="scene"><el-input v-model="copyForm.scene" /></el-form-item>
        <el-form-item label="正文（支持双花括号变量）" prop="body">
          <el-input v-model="copyForm.body" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="copyDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCopy">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="posterDialog" title="新建海报模板" width="90%" style="max-width: 560px" destroy-on-close>
      <el-form ref="posterFormRef" :model="posterForm" :rules="posterRules" label-position="top">
        <el-form-item label="名称" prop="name"><el-input v-model="posterForm.name" /></el-form-item>
        <el-form-item label="场景" prop="scene"><el-input v-model="posterForm.scene" /></el-form-item>
        <el-form-item label="layout_json" prop="layout_json">
          <el-input v-model="posterForm.layout_json" type="textarea" :rows="10" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="posterDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPoster">保存</el-button>
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
