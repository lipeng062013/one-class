<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  generatePoster,
  openPosterDownload,
  posterObjectUrl,
  type GeneratedPoster,
  type PosterMode,
} from '../../api/posters'
import { listPosterTemplates, type PosterTemplate } from '../../api/templates'
import { getIntegrationsStatus, type IntegrationsStatus } from '../../api/system'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const templates = ref<PosterTemplate[]>([])
const result = ref<GeneratedPoster | null>(null)
const previewUrl = ref('')
const integrations = ref<IntegrationsStatus | null>(null)

const form = reactive({
  template_id: undefined as number | undefined,
  mode: 'layout' as PosterMode,
  title: '壹号教室',
  subtitle: '',
  footer: '扫码预约沟通',
  prompt: '',
  material_id: undefined as number | undefined,
})

function revokePreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

async function loadTemplates() {
  const [tpls, integ] = await Promise.all([
    listPosterTemplates(),
    getIntegrationsStatus().catch(() => null),
  ])
  templates.value = tpls
  integrations.value = integ
  if (!form.template_id && templates.value.length) {
    form.template_id = templates.value.find((t) => t.is_system)?.id || templates.value[0].id
  }
  const q = route.query.material_id
  if (q) {
    const id = Number(q)
    if (!Number.isNaN(id)) form.material_id = id
  }
}

async function submit() {
  if (form.mode === 'ai_image' && !form.template_id) {
    ElMessage.warning('AI 生图在未配置或失败时会回退版式，请先选择海报模板')
    return
  }
  if (form.mode === 'ai_image' && integrations.value && !integrations.value.image.configured) {
    ElMessage.info('当前未配置图片大模型，将使用本地版式导出；配置 IMAGE_* 并重启后端后可 AI 生图')
  }
  loading.value = true
  result.value = null
  revokePreview()
  try {
    result.value = await generatePoster({
      material_id: form.material_id ?? null,
      template_id: form.template_id ?? null,
      mode: form.mode,
      title: form.title,
      payload: { subtitle: form.subtitle, footer: form.footer },
      prompt: form.prompt || null,
    })
    previewUrl.value = await posterObjectUrl(result.value.id)
    if (result.value.image_error) {
      ElMessage.warning(result.value.image_error)
    } else {
      ElMessage.success('海报已生成')
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '生成失败')
  } finally {
    loading.value = false
  }
}

async function download() {
  if (!result.value) return
  await openPosterDownload(result.value.id, `${result.value.title}-${result.value.id}.png`)
}

watch(
  () => form.mode,
  (mode) => {
    if (mode === 'ai_image' && integrations.value && !integrations.value.image.configured) {
      ElMessage.info('AI 生图需配置 IMAGE_API_BASE_URL 与 IMAGE_API_KEY')
    }
  },
)

onMounted(loadTemplates)
onUnmounted(revokePreview)
</script>

<template>
  <div>
    <el-page-header content="生成海报" @back="router.push('/posters')" />
    <el-alert
      style="margin-top: 12px"
      :type="integrations?.image.configured ? 'success' : 'info'"
      :closable="false"
      show-icon
      :title="
        integrations?.image.configured
          ? `图片 API 已配置${integrations.image.model ? '：' + integrations.image.model : ''}`
          : '图片 API 未配置：请用「版式导出」；AI 生图需配置 IMAGE_*'
      "
    />
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :md="12">
        <el-card>
          <el-form label-position="top">
            <el-form-item label="版式模板">
              <el-select v-model="form.template_id" style="width: 100%">
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
                <el-radio-button value="layout">版式导出</el-radio-button>
                <el-radio-button value="ai_image">AI 生图</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="标题">
              <el-input v-model="form.title" />
            </el-form-item>
            <el-form-item label="副标题">
              <el-input v-model="form.subtitle" />
            </el-form-item>
            <el-form-item label="页脚">
              <el-input v-model="form.footer" />
            </el-form-item>
            <el-form-item v-if="form.mode === 'ai_image'" label="AI 提示词">
              <el-input v-model="form.prompt" type="textarea" :rows="3" />
            </el-form-item>
            <el-button type="primary" :loading="loading" style="width: 100%" @click="submit">生成</el-button>
          </el-form>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>预览 / 下载</template>
          <el-empty v-if="!result" description="生成后显示预览" />
          <div v-else>
            <el-alert
              v-if="result.image_error"
              type="warning"
              :closable="false"
              show-icon
              :title="result.image_error"
              style="margin-bottom: 12px"
            />
            <p><strong>{{ result.title }}</strong>（{{ result.mode }}）</p>
            <el-image v-if="previewUrl" :src="previewUrl" fit="contain" class="preview" :preview-src-list="[previewUrl]" />
            <p class="muted">{{ result.file_path }}</p>
            <el-button type="success" @click="download">下载海报</el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.muted {
  color: #909399;
  font-size: 13px;
}

.preview {
  width: 100%;
  max-height: 420px;
  background: #f5f7fa;
  border-radius: 6px;
  margin: 8px 0;
}
</style>
