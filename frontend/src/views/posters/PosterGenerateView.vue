<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { generatePoster, openPosterDownload, type GeneratedPoster, type PosterMode } from '../../api/posters'
import { listPosterTemplates, type PosterTemplate } from '../../api/templates'

const router = useRouter()
const loading = ref(false)
const templates = ref<PosterTemplate[]>([])
const result = ref<GeneratedPoster | null>(null)

const form = reactive({
  template_id: undefined as number | undefined,
  mode: 'layout' as PosterMode,
  title: '壹号教室',
  subtitle: '',
  footer: '扫码预约沟通',
  prompt: '',
})

async function loadTemplates() {
  templates.value = await listPosterTemplates()
  if (!form.template_id && templates.value.length) {
    form.template_id = templates.value.find((t) => t.is_system)?.id || templates.value[0].id
  }
}

async function submit() {
  loading.value = true
  result.value = null
  try {
    result.value = await generatePoster({
      template_id: form.template_id ?? null,
      mode: form.mode,
      title: form.title,
      payload: { subtitle: form.subtitle, footer: form.footer },
      prompt: form.prompt || null,
    })
    ElMessage.success('海报已生成')
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

onMounted(loadTemplates)
</script>

<template>
  <div>
    <el-page-header content="生成海报" @back="router.push('/posters')" />
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
          <template #header>结果</template>
          <el-empty v-if="!result" description="生成后可下载 PNG" />
          <div v-else>
            <p><strong>{{ result.title }}</strong>（{{ result.mode }}）</p>
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
</style>
