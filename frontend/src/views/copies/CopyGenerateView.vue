<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { generateCopy, type CopyMode, type GeneratedCopy } from '../../api/copies'
import { listMaterials, type Material } from '../../api/materials'
import { listCopyTemplates, type CopyTemplate } from '../../api/templates'

const router = useRouter()
const loading = ref(false)
const materials = ref<Material[]>([])
const templates = ref<CopyTemplate[]>([])
const result = ref<GeneratedCopy | null>(null)

const form = reactive({
  material_id: undefined as number | undefined,
  template_id: undefined as number | undefined,
  mode: 'template' as CopyMode,
  platform: 'xhs',
  extra_instruction: '',
})

async function loadOptions() {
  const [mats, tpls] = await Promise.all([listMaterials(), listCopyTemplates()])
  materials.value = mats
  templates.value = tpls
  if (!form.template_id && tpls.length) {
    form.template_id = tpls.find((t) => t.is_system)?.id || tpls[0].id
  }
}

async function submit() {
  loading.value = true
  result.value = null
  try {
    result.value = await generateCopy({
      material_id: form.material_id ?? null,
      template_id: form.template_id ?? null,
      mode: form.mode,
      platform: form.platform,
      extra_instruction: form.extra_instruction || null,
    })
    ElMessage.success('生成成功')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '生成失败')
  } finally {
    loading.value = false
  }
}

async function copyResult() {
  if (!result.value) return
  await navigator.clipboard.writeText(`${result.value.title}\n\n${result.value.body}`)
  ElMessage.success('已复制')
}

onMounted(loadOptions)
</script>

<template>
  <div>
    <el-page-header content="生成文案" @back="router.push('/copies')" />
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :md="10">
        <el-card>
          <el-form label-position="top">
            <el-form-item label="素材（可选）">
              <el-select v-model="form.material_id" clearable filterable style="width: 100%" placeholder="选择素材">
                <el-option v-for="m in materials" :key="m.id" :label="`#${m.id} ${m.title}`" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="模板">
              <el-select v-model="form.template_id" filterable style="width: 100%">
                <el-option
                  v-for="t in templates"
                  :key="t.id"
                  :label="`${t.name}${t.is_system ? '（系统）' : ''}`"
                  :value="t.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="模式">
              <el-radio-group v-model="form.mode">
                <el-radio-button value="template">仅模板</el-radio-button>
                <el-radio-button value="template_then_llm">模板+润色</el-radio-button>
                <el-radio-button value="llm">直接大模型</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="补充说明">
              <el-input v-model="form.extra_instruction" type="textarea" :rows="3" />
            </el-form-item>
            <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">生成</el-button>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="14">
        <el-card>
          <template #header>
            <div class="card-head">
              <span>结果</span>
              <el-button v-if="result" type="primary" link @click="copyResult">一键复制</el-button>
            </div>
          </template>
          <el-empty v-if="!result" description="生成后显示文案" />
          <div v-else>
            <el-alert
              v-if="result.banned_hits?.length"
              type="warning"
              :closable="false"
              show-icon
              :title="`命中禁用词：${result.banned_hits.join('、')}`"
              style="margin-bottom: 12px"
            />
            <el-alert
              v-if="result.llm_error"
              type="info"
              :closable="false"
              :title="`大模型提示：${result.llm_error}`"
              style="margin-bottom: 12px"
            />
            <h3 style="margin-top: 0">{{ result.title || '（无标题）' }}</h3>
            <el-input :model-value="result.body" type="textarea" :rows="14" readonly />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
