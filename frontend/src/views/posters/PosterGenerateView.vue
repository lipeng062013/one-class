<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  generatePoster,
  openPosterDownload,
  posterModeLabel,
  posterObjectUrl,
  type GeneratedPoster,
  type PosterMode,
} from '../../api/posters'
import { listPosterTemplates, type PosterTemplate } from '../../api/templates'
import { getIntegrationsStatus, type IntegrationsStatus } from '../../api/system'
import { POSTER_GENERATE_FIELDS, type TemplateParamHint } from '../../constants/templateParams'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { usePageBack } from '../../composables/usePageBack'

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/posters')
const { isApp } = useBreakpoint()
const loading = ref(false)
const templates = ref<PosterTemplate[]>([])
const result = ref<GeneratedPoster | null>(null)
const previewUrl = ref('')
const integrations = ref<IntegrationsStatus | null>(null)

const form = reactive({
  template_id: undefined as number | undefined,
  mode: 'layout' as PosterMode,
  title: '嘉壹启航',
  subtitle: '',
  footer: '扫码预约沟通',
  prompt: '',
  material_id: undefined as number | undefined,
})

const selectedTemplate = computed(() => {
  if (!form.template_id) return null
  return templates.value.find((t) => t.id === form.template_id) || null
})

const textFields = computed(() =>
  POSTER_GENERATE_FIELDS.map((p) => ({
    ...p,
    modelKey: p.key as 'title' | 'subtitle' | 'footer',
  })),
)

function fieldModel(key: 'title' | 'subtitle' | 'footer') {
  return form[key]
}

function setFieldModel(key: 'title' | 'subtitle' | 'footer', value: string) {
  form[key] = value
}

function fieldPlaceholder(p: TemplateParamHint) {
  if (p.key === 'title') return '例如：嘉壹启航'
  if (p.key === 'subtitle') return '例如：本周试听名额有限'
  return '例如：扫码预约沟通'
}

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
  const qt = route.query.template_id
  if (qt) {
    const tid = Number(qt)
    if (!Number.isNaN(tid) && templates.value.some((t) => t.id === tid)) {
      form.template_id = tid
    }
  }
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
  <div class="poster-generate">
    <div class="page-head">
      <el-page-header content="生成海报" @back="goBack" />
    </div>

    <div
      class="status-bar"
      :class="integrations?.image.configured ? 'is-ok' : 'is-info'"
    >
      <div class="status-main">
        <span class="status-dot" />
        <span v-if="integrations?.image.configured">
          图片 API 已配置
          <strong v-if="integrations.image.model">{{ integrations.image.model }}</strong>
        </span>
        <span v-else>图片 API 未配置 · 可先用「版式导出」</span>
      </div>
      <el-button
        v-if="integrations?.image.configured"
        link
        type="primary"
        class="status-link"
        @click="router.push('/ai-image')"
      >
        需要参考图改图？打开 GPT 生图
      </el-button>
      <span v-else class="status-sub">配置 IMAGE_* 后可使用 AI 生图</span>
    </div>

    <el-row
      :gutter="isApp ? 0 : 20"
      class="generate-layout"
      :class="{ 'is-stacked': isApp }"
    >
      <el-col :xs="24" :sm="24" :lg="9" :md="isApp ? 24 : 10" class="generate-form-col">
        <el-card class="form-card" shadow="never">
          <template #header>
            <div class="card-head">
              <div>
                <div class="card-title">海报配置</div>
                <div class="card-sub">选择模板与文案，右侧实时预览生成结果</div>
              </div>
            </div>
          </template>

          <el-form label-position="top" class="poster-form" @submit.prevent>
            <el-form-item>
              <template #label>
                <span class="label-row">
                  <span>版式模板</span>
                </span>
              </template>
              <el-select
                v-model="form.template_id"
                filterable
                style="width: 100%"
                placeholder="选择海报模板"
              >
                <el-option
                  v-for="t in templates"
                  :key="t.id"
                  :label="`${t.name}${t.is_system ? '（系统）' : ''}`"
                  :value="t.id"
                />
              </el-select>
              <p class="field-hint">
                来自「模板管理 · 海报模板」
                <template v-if="selectedTemplate">
                  · 当前：{{ selectedTemplate.name }}
                </template>
              </p>
            </el-form-item>

            <el-form-item label="生成模式">
              <div class="mode-grid">
                <button
                  type="button"
                  class="mode-card"
                  :class="{ active: form.mode === 'layout' }"
                  @click="form.mode = 'layout'"
                >
                  <div class="mode-name">版式导出</div>
                  <div class="mode-desc">按模板本地合成，稳定快速</div>
                </button>
                <button
                  type="button"
                  class="mode-card"
                  :class="{ active: form.mode === 'ai_image' }"
                  @click="form.mode = 'ai_image'"
                >
                  <div class="mode-name">AI 生图</div>
                  <div class="mode-desc">大模型出图，失败自动回退版式</div>
                </button>
              </div>
            </el-form-item>

            <div class="text-fields">
              <div v-for="p in textFields" :key="p.key" class="text-field">
                <div class="text-field-head">
                  <span class="text-field-label">{{ p.label }}</span>
                  <el-tooltip placement="top" effect="dark" :show-after="120" popper-class="poster-param-tip">
                    <template #content>
                      <div class="tip-body">
                        <div class="tip-title">模板字段 key</div>
                        <code class="tip-code">{{ p.key }}</code>
                        <div class="tip-desc">{{ p.source }}</div>
                      </div>
                    </template>
                    <button type="button" class="param-mark" aria-label="查看字段参数">{ }</button>
                  </el-tooltip>
                </div>
                <el-input
                  :model-value="fieldModel(p.modelKey)"
                  :placeholder="fieldPlaceholder(p)"
                  clearable
                  @update:model-value="(v: string) => setFieldModel(p.modelKey, v)"
                />
              </div>
            </div>

            <el-form-item v-if="form.mode === 'ai_image'" label="AI 提示词" class="prompt-item">
              <el-input
                v-model="form.prompt"
                type="textarea"
                :rows="3"
                placeholder="描述画面风格、构图、氛围等（仅 AI 生图模式）"
              />
              <p class="field-hint">不会写入版式 fields，只作为生图提示</p>
            </el-form-item>

            <div class="param-chips">
              <span class="param-chips-label">字段对照</span>
              <el-tooltip
                v-for="p in POSTER_GENERATE_FIELDS"
                :key="p.key"
                placement="top"
                effect="dark"
                :show-after="100"
                popper-class="poster-param-tip"
              >
                <template #content>
                  <div class="tip-body">
                    <div class="tip-title">{{ p.label }}</div>
                    <code class="tip-code">{{ p.key }}</code>
                    <div class="tip-desc">{{ p.source }}</div>
                  </div>
                </template>
                <button type="button" class="param-chip">
                  <span class="chip-key">{{ p.key }}</span>
                  <span class="chip-label">{{ p.label }}</span>
                </button>
              </el-tooltip>
            </div>

            <el-button
              type="primary"
              size="large"
              class="submit-btn"
              :loading="loading"
              @click="submit"
            >
              {{
                loading
                  ? form.mode === 'ai_image'
                    ? 'AI 生图中，可能需 1–2 分钟…'
                    : '生成中…'
                  : '生成海报'
              }}
            </el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="24" :lg="15" :md="isApp ? 24 : 14" class="generate-side-col">
        <el-card class="preview-card" shadow="never" v-loading="loading">
          <template #header>
            <div class="card-head">
              <div>
                <div class="card-title">预览 / 下载</div>
                <div class="card-sub">
                  <template v-if="result">
                    {{ result.title || '未命名' }} · {{ posterModeLabel(result.mode) }}
                  </template>
                  <template v-else>生成后在此查看海报效果</template>
                </div>
              </div>
              <el-button
                v-if="result && previewUrl"
                type="primary"
                @click="download"
              >
                下载海报
              </el-button>
            </div>
          </template>

          <div v-if="!result" class="preview-empty">
            <div class="preview-frame empty-frame">
              <div class="empty-art">
                <div class="empty-poster-mock">
                  <div class="mock-bar" />
                  <div class="mock-line short" />
                  <div class="mock-line" />
                  <div class="mock-footer" />
                </div>
              </div>
              <p class="empty-title">等待生成</p>
              <p class="empty-desc">填写左侧文案后点击「生成海报」，预览会出现在这里</p>
            </div>
          </div>

          <div v-else class="preview-body">
            <el-alert
              v-if="result.image_error"
              type="warning"
              :closable="false"
              show-icon
              :title="result.image_error"
              class="preview-alert"
            />
            <div class="preview-frame">
              <el-image
                v-if="previewUrl"
                :src="previewUrl"
                fit="contain"
                class="preview-image"
                :preview-src-list="[previewUrl]"
                preview-teleported
              />
              <div v-else class="stage-empty">预览加载失败</div>
            </div>
            <div class="preview-meta">
              <el-tag size="small" effect="plain" type="warning">
                {{ posterModeLabel(result.mode) }}
              </el-tag>
              <span v-if="result.file_path" class="meta-path" :title="result.file_path">
                {{ result.file_path }}
              </span>
            </div>
            <div class="preview-actions">
              <el-button type="primary" @click="download">下载海报</el-button>
              <el-button @click="submit" :loading="loading">重新生成</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.poster-generate {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.page-head {
  margin-bottom: 4px;
}

.status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  margin-top: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.45;
}

.status-bar.is-ok {
  background: linear-gradient(90deg, #f0fdf4, #ecfdf5);
  border: 1px solid #bbf7d0;
  color: #166534;
}

.status-bar.is-info {
  background: linear-gradient(90deg, #faf6ee, #f5f0e6);
  border: 1px solid var(--oc-border, #e8e0d0);
  color: var(--oc-ink, #44403c);
}

.status-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: currentColor;
  opacity: 0.7;
}

.status-bar.is-ok .status-dot {
  background: #22c55e;
  opacity: 1;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.2);
}

.status-main strong {
  font-weight: 600;
  margin-left: 4px;
}

.status-link {
  font-weight: 600;
}

.status-sub {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.generate-layout {
  margin-top: 16px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.generate-form-col,
.generate-side-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: 100%;
}

.generate-form-col > .form-card,
.generate-side-col > .preview-card {
  width: 100%;
  flex: 1;
}

.generate-layout.is-stacked .generate-side-col {
  margin-top: 16px;
}

@media (max-width: 991px) {
  /*
   * compact 下 gutter=0，清掉 EP 左右负 margin / col padding，
   * 避免窄屏内容与右边框间距明显大于左侧。
   */
  .poster-generate {
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    box-sizing: border-box;
  }

  .generate-layout {
    margin-left: 0 !important;
    margin-right: 0 !important;
    width: 100% !important;
  }

  .generate-layout > :deep(.el-col) {
    padding-left: 0 !important;
    padding-right: 0 !important;
    max-width: 100%;
  }

  .generate-layout .generate-side-col {
    margin-top: 16px;
  }
}

.form-card,
.preview-card {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.form-card :deep(.el-card__header),
.preview-card :deep(.el-card__header) {
  padding: 14px 18px;
  border-bottom-color: var(--oc-border, #e8e0d0);
}

.form-card :deep(.el-card__body),
.preview-card :deep(.el-card__body) {
  padding: 18px;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.01em;
}

.card-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.45;
}

.poster-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.poster-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--oc-ink, #44403c);
}

.label-row {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.mode-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  width: 100%;
}

@media (max-width: 480px) {
  .mode-grid {
    grid-template-columns: 1fr;
  }
}

.mode-card {
  text-align: left;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1.5px solid var(--oc-border, #e8e0d0);
  background: #fffdfb;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
}

.mode-card:hover {
  border-color: #dbbf94;
}

.mode-card.active {
  border-color: var(--oc-primary, #a16207);
  background: linear-gradient(180deg, #faf6ee 0%, #f2e8d6 100%);
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.12);
}

.mode-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.mode-desc {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.text-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 18px;
}

.text-field {
  padding: 12px 12px 12px;
  border-radius: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
}

.text-field-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.text-field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--oc-ink, #44403c);
}

.param-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 18px;
  padding: 0;
  border: 1px solid #e6d2b3;
  border-radius: 999px;
  background: #f2e8d6;
  color: var(--oc-primary, #a16207);
  font-size: 10px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  letter-spacing: -0.5px;
  line-height: 1;
  cursor: help;
  flex-shrink: 0;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s,
    transform 0.15s;
}

.param-mark:hover,
.param-mark:focus-visible {
  background: var(--oc-primary, #a16207);
  border-color: var(--oc-primary, #a16207);
  color: #fff;
  outline: none;
  transform: scale(1.06);
}

.prompt-item {
  margin-top: 4px;
}

.param-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f5f0e6;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.param-chips-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-muted, #78716c);
  margin-right: 2px;
}

.param-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid #e6d2b3;
  background: #fffdf8;
  cursor: help;
  transition:
    border-color 0.15s,
    background 0.15s;
}

.param-chip:hover {
  border-color: var(--oc-primary, #a16207);
  background: #f2e8d6;
}

.chip-key {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
}

.chip-label {
  font-size: 12px;
  color: var(--oc-ink, #44403c);
}

.submit-btn {
  width: 100%;
  height: 44px;
  font-weight: 600;
  letter-spacing: 0.04em;
  border-radius: 10px;
}

.preview-card {
  min-height: 100%;
}

.preview-empty,
.preview-body {
  min-height: min(62vh, 560px);
  display: flex;
  flex-direction: column;
}

.preview-body .preview-frame {
  flex: 1;
}

.preview-frame {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: min(62vh, 560px);
  padding: 20px;
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    radial-gradient(circle at 30% 20%, rgba(245, 230, 200, 0.5), transparent 55%),
    #faf6ee;
  overflow: hidden;
}

.empty-frame {
  flex-direction: column;
  gap: 10px;
  text-align: center;
}

.empty-art {
  margin-bottom: 4px;
}

.empty-poster-mock {
  width: 120px;
  height: 160px;
  margin: 0 auto;
  padding: 16px 14px;
  border-radius: 10px;
  background: linear-gradient(160deg, #176b4d 0%, #0f4d38 100%);
  box-shadow: 0 12px 28px rgba(23, 107, 77, 0.28);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mock-bar {
  height: 10px;
  width: 70%;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.9);
}

.mock-line {
  height: 6px;
  width: 88%;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.35);
}

.mock-line.short {
  width: 55%;
}

.mock-footer {
  margin-top: auto;
  height: 6px;
  width: 40%;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.55);
}

.empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.empty-desc {
  margin: 0;
  max-width: 260px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.preview-alert {
  margin-bottom: 12px;
}

.preview-image {
  width: 100%;
  max-width: 420px;
  max-height: min(58vh, 520px);
  margin: 0 auto;
  border-radius: 8px;
  box-shadow: 0 8px 28px rgba(41, 37, 36, 0.1);
}

.stage-empty {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.preview-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-top: 12px;
}

.meta-path {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.preview-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

:global(.poster-param-tip.el-popper) {
  max-width: 280px;
  padding: 10px 12px !important;
  border-radius: 8px !important;
}

:global(.poster-param-tip .tip-body) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

:global(.poster-param-tip .tip-title) {
  font-size: 11px;
  opacity: 0.75;
  letter-spacing: 0.04em;
}

:global(.poster-param-tip .tip-code) {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.14);
  color: #fde68a;
  font-size: 13px;
  font-weight: 600;
}

:global(.poster-param-tip .tip-desc) {
  font-size: 11px;
  line-height: 1.45;
  opacity: 0.8;
}
</style>
