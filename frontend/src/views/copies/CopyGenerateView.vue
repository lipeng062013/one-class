<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { generateCopy, type CopyMode, type GeneratedCopy } from '../../api/copies'
import {
  listMaterialsForPicker,
  materialFileObjectUrl,
  type Material,
} from '../../api/materials'
import { listCopyTemplates, type CopyTemplate } from '../../api/templates'
import { getIntegrationsStatus, type IntegrationsStatus } from '../../api/system'
import { COPY_TEMPLATE_PARAMS, copyParamPlaceholder } from '../../constants/templateParams'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { usePageBack } from '../../composables/usePageBack'
import { asyncPool } from '../../utils/asyncPool'

const route = useRoute()
const { goBack } = usePageBack('/copies')
const { isApp } = useBreakpoint()
const loading = ref(false)
const materials = ref<Material[]>([])
const templates = ref<CopyTemplate[]>([])
const result = ref<GeneratedCopy | null>(null)
const integrations = ref<IntegrationsStatus | null>(null)

const form = reactive({
  material_id: undefined as number | undefined,
  template_id: undefined as number | undefined,
  mode: 'template' as CopyMode,
  platform: 'xhs',
  extra_instruction: '',
})

const selectedMaterial = computed(() => {
  if (!form.material_id) return null
  return materials.value.find((m) => m.id === form.material_id) || null
})

const selectedTemplate = computed(() => {
  if (!form.template_id) return null
  return templates.value.find((t) => t.id === form.template_id) || null
})

const materialFieldRows = computed(() => {
  const m = selectedMaterial.value
  if (!m) return []
  return [
    { key: 'title', label: '场景标题', value: m.title || '' },
    { key: 'grade', label: '年级', value: m.grade || '' },
    { key: 'subject', label: '科目', value: m.subject || '' },
    { key: 'pain_point', label: '家长痛点', value: m.pain_point || '' },
    { key: 'teacher_action', label: '老师处理', value: m.teacher_action || '' },
    { key: 'next_step', label: '下一步行动', value: m.next_step || '' },
  ]
})

const materialParams = computed(() =>
  COPY_TEMPLATE_PARAMS.filter((x) => x.usedIn?.includes('素材')),
)

const modes: { value: CopyMode; name: string; desc: string }[] = [
  { value: 'template', name: '仅模板', desc: '本地替换变量，无需大模型' },
  { value: 'template_then_llm', name: '模板+润色', desc: '先套模板再交给大模型润色' },
  { value: 'llm', name: '直接大模型', desc: '完全由大模型生成文案' },
]

const previewUrls = ref<Record<number, string>>({})
const previewLoading = ref(false)
const activePreviewId = ref<number | null>(null)
const stageViewerVisible = ref(false)

const activePreviewUrl = computed(() => {
  if (activePreviewId.value == null) return ''
  return previewUrls.value[activePreviewId.value] || ''
})

const allPreviewUrls = computed(() => {
  const m = selectedMaterial.value
  if (!m?.files?.length) return [] as string[]
  return m.files.map((f) => previewUrls.value[f.id]).filter(Boolean) as string[]
})

const activePreviewIndex = computed(() => {
  const url = activePreviewUrl.value
  if (!url) return 0
  const idx = allPreviewUrls.value.indexOf(url)
  return idx >= 0 ? idx : 0
})

function revokePreviews() {
  Object.values(previewUrls.value).forEach((u) => URL.revokeObjectURL(u))
  previewUrls.value = {}
  activePreviewId.value = null
}

const PREVIEW_CONCURRENCY = 4

async function loadMaterialPreviews(material: Material | null) {
  revokePreviews()
  if (!material?.files?.length) return
  previewLoading.value = true
  try {
    await asyncPool(material.files, PREVIEW_CONCURRENCY, async (f) => {
      try {
        const url = await materialFileObjectUrl(f.id, { thumb: true })
        previewUrls.value[f.id] = url
        if (activePreviewId.value == null) activePreviewId.value = f.id
      } catch {
        /* skip broken */
      }
    })
  } finally {
    previewLoading.value = false
  }
}

function selectThumb(fileId: number) {
  if (!previewUrls.value[fileId]) return
  activePreviewId.value = fileId
}

function openStageLightbox() {
  if (!activePreviewUrl.value || !allPreviewUrls.value.length) return
  stageViewerVisible.value = true
}

watch(
  () => form.material_id,
  () => {
    loadMaterialPreviews(selectedMaterial.value)
  },
)

async function loadOptions() {
  const [mats, tpls, integ] = await Promise.all([
    listMaterialsForPicker(100),
    listCopyTemplates(),
    getIntegrationsStatus().catch(() => null),
  ])
  materials.value = mats
  templates.value = tpls
  integrations.value = integ
  const qt = route.query.template_id
  if (qt) {
    const tid = Number(qt)
    if (!Number.isNaN(tid) && tpls.some((t) => t.id === tid)) {
      form.template_id = tid
    }
  }
  if (!form.template_id && tpls.length) {
    form.template_id = tpls.find((t) => t.is_system)?.id || tpls[0].id
  }
  const q = route.query.material_id
  if (q && !form.material_id) {
    const id = Number(q)
    if (!Number.isNaN(id)) form.material_id = id
  }
  if (form.material_id) {
    void loadMaterialPreviews(selectedMaterial.value)
  }
}

async function submit() {
  if (
    (form.mode === 'llm' || form.mode === 'template_then_llm') &&
    integrations.value &&
    !integrations.value.llm.configured
  ) {
    ElMessage.info(
      '当前未配置大模型，将使用本地模板/草稿；配置 .env 中 LLM_* 并重启后端后可真正调用大模型',
    )
  }
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
    if (result.value.llm_error) {
      ElMessage.warning(result.value.llm_error)
    } else {
      ElMessage.success('生成成功')
    }
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
onUnmounted(revokePreviews)
</script>

<template>
  <div class="copy-generate">
    <div class="page-head">
      <el-page-header content="生成文案" @back="goBack" />
    </div>

    <div class="status-bar" :class="integrations?.llm.configured ? 'is-ok' : 'is-info'">
      <div class="status-main">
        <span class="status-dot" />
        <span v-if="integrations?.llm.configured">
          大模型已配置
          <strong>{{ integrations.llm.model }}</strong>
        </span>
        <span v-else>大模型未配置 · 可先用「仅模板」</span>
      </div>
      <span class="status-sub">
        {{
          integrations?.llm.configured
            ? '模板+润色 / 直接大模型可用'
            : '配置 LLM_* 后可启用润色与直出'
        }}
      </span>
    </div>

    <el-row
      :gutter="isApp ? 0 : 20"
      class="generate-layout"
      :class="{ 'is-stacked': isApp }"
    >
      <!-- 左侧配置 -->
      <el-col :xs="24" :sm="24" :lg="9" :md="isApp ? 24 : 10" class="generate-form-col">
        <el-card class="form-card" shadow="never">
          <template #header>
            <div class="card-head">
              <div>
                <div class="card-title">文案配置</div>
                <div class="card-sub">选择素材与模板，右侧对照素材并查看生成结果</div>
              </div>
            </div>
          </template>

          <el-form label-position="top" class="copy-form" @submit.prevent>
            <el-form-item label="素材（可选）">
              <el-select
                v-model="form.material_id"
                clearable
                filterable
                style="width: 100%"
                placeholder="选择素材以填充模板变量"
              >
                <el-option
                  v-for="m in materials"
                  :key="m.id"
                  :label="`#${m.id} ${m.title}`"
                  :value="m.id"
                />
              </el-select>
              <p class="field-hint">
                来自「素材管理」
                <template v-if="selectedMaterial">· 当前：{{ selectedMaterial.title }}</template>
              </p>
            </el-form-item>

            <el-form-item label="文案模板">
              <el-select
                v-model="form.template_id"
                filterable
                style="width: 100%"
                placeholder="选择文案模板"
              >
                <el-option
                  v-for="t in templates"
                  :key="t.id"
                  :label="`${t.name}${t.is_system ? '（系统）' : ''}`"
                  :value="t.id"
                />
              </el-select>
              <p class="field-hint">
                来自「模板管理 · 文案模板」
                <template v-if="selectedTemplate">· 当前：{{ selectedTemplate.name }}</template>
              </p>
            </el-form-item>

            <el-form-item label="生成模式">
              <div class="mode-grid">
                <button
                  v-for="m in modes"
                  :key="m.value"
                  type="button"
                  class="mode-card"
                  :class="{ active: form.mode === m.value }"
                  @click="form.mode = m.value"
                >
                  <div class="mode-name">{{ m.name }}</div>
                  <div class="mode-desc">{{ m.desc }}</div>
                </button>
              </div>
            </el-form-item>

            <el-form-item label="补充说明">
              <el-input
                v-model="form.extra_instruction"
                type="textarea"
                :rows="3"
                placeholder="给大模型的额外要求（仅润色 / 直接大模型生效）"
              />
              <p class="field-hint">本页填写，会附加到大模型提示中</p>
            </el-form-item>

            <div class="param-chips">
              <span class="param-chips-label">变量对照</span>
              <el-tooltip
                v-for="p in COPY_TEMPLATE_PARAMS"
                :key="p.key"
                placement="top"
                effect="dark"
                :show-after="100"
                popper-class="copy-param-tip"
              >
                <template #content>
                  <div class="tip-body">
                    <div class="tip-title">{{ p.label }}</div>
                    <code class="tip-code">{{ copyParamPlaceholder(p.key) }}</code>
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
              {{ loading ? '生成中…' : '生成文案' }}
            </el-button>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：素材 + 结果 -->
      <el-col :xs="24" :sm="24" :lg="15" :md="isApp ? 24 : 14" class="generate-side-col">
        <el-card class="material-card" shadow="never" v-loading="previewLoading">
          <template #header>
            <div class="card-head">
              <div>
                <div class="card-title">素材内容</div>
                <div class="card-sub">
                  <template v-if="selectedMaterial">
                    对照字段与图片 · 悬停
                    <span class="param-mark param-mark--inline">{ }</span>
                    查看模板变量
                  </template>
                  <template v-else>选择左侧素材后展示字段与预览</template>
                </div>
              </div>
              <el-tag v-if="selectedMaterial" type="success" size="small" effect="plain">
                已选中
              </el-tag>
              <el-tag v-else type="info" size="small" effect="plain">未选择</el-tag>
            </div>
          </template>

          <div v-if="!selectedMaterial" class="material-empty">
            <div class="material-empty-art">
              <div class="empty-doc">
                <div class="empty-line w60" />
                <div class="empty-line w90" />
                <div class="empty-line w75" />
                <div class="empty-line w50" />
              </div>
            </div>
            <p class="empty-title">尚未选择素材</p>
            <p class="empty-desc">
              素材可提供
              <template v-for="(p, i) in materialParams" :key="p.key">
                <code>{{ copyParamPlaceholder(p.key) }}</code
                ><template v-if="i < materialParams.length - 1">、</template>
              </template>
              等变量
            </p>
          </div>

          <div v-else class="material-split" :class="{ 'is-compact': isApp }">
            <div class="material-left">
              <div v-if="selectedMaterial.files?.length" class="thumb-row">
                <button
                  v-for="(f, idx) in selectedMaterial.files"
                  :key="f.id"
                  type="button"
                  class="thumb-btn"
                  :class="{ active: activePreviewId === f.id }"
                  :title="`图 ${idx + 1}，点击右侧预览`"
                  @click="selectThumb(f.id)"
                >
                  <img v-if="previewUrls[f.id]" :src="previewUrls[f.id]" alt="" />
                  <span v-else class="thumb-fallback">…</span>
                  <span class="thumb-index">{{ idx + 1 }}</span>
                </button>
              </div>
              <p v-else class="no-images">该素材暂无图片</p>

              <div class="material-fields">
                <div v-for="row in materialFieldRows" :key="row.key" class="material-field">
                  <div class="material-field-head">
                    <span class="material-field-label">{{ row.label }}</span>
                    <el-tooltip
                      placement="top"
                      effect="dark"
                      :show-after="120"
                      popper-class="copy-param-tip"
                    >
                      <template #content>
                        <div class="tip-body">
                          <div class="tip-title">模板变量</div>
                          <code class="tip-code">{{ copyParamPlaceholder(row.key) }}</code>
                          <div class="tip-desc">
                            在文案模板中使用此占位符，生成时替换为本字段内容
                          </div>
                        </div>
                      </template>
                      <button type="button" class="param-mark" aria-label="查看模板变量">
                        { }
                      </button>
                    </el-tooltip>
                  </div>
                  <div class="material-field-value" :class="{ empty: !row.value }">
                    {{ row.value || '未填写' }}
                  </div>
                </div>
              </div>
            </div>

            <div
              class="material-stage"
              :class="{ clickable: !!activePreviewUrl }"
              role="button"
              :tabindex="activePreviewUrl ? 0 : -1"
              @click="openStageLightbox"
              @keydown.enter.prevent="openStageLightbox"
            >
              <template v-if="activePreviewUrl">
                <img :src="activePreviewUrl" alt="素材预览" class="stage-img" />
                <div class="stage-overlay">
                  <span class="stage-overlay-text">点击查看大图</span>
                </div>
              </template>
              <div v-else class="stage-empty">
                <span v-if="selectedMaterial.files?.length">点击左侧缩略图预览</span>
                <span v-else>无图片可预览</span>
              </div>
            </div>
          </div>

          <el-image-viewer
            v-if="stageViewerVisible && allPreviewUrls.length"
            :url-list="allPreviewUrls"
            :initial-index="activePreviewIndex"
            teleported
            @close="stageViewerVisible = false"
          />
        </el-card>

        <el-card class="result-card" shadow="never" v-loading="loading">
          <template #header>
            <div class="card-head">
              <div>
                <div class="card-title">生成结果</div>
                <div class="card-sub">
                  <template v-if="result">{{ result.title || '（无标题）' }}</template>
                  <template v-else>生成后在此展示文案，可一键复制</template>
                </div>
              </div>
              <el-button v-if="result" type="primary" @click="copyResult">一键复制</el-button>
            </div>
          </template>

          <div v-if="!result" class="result-empty">
            <div class="result-empty-art">
              <div class="empty-lines">
                <div class="empty-line w40" />
                <div class="empty-line w95" />
                <div class="empty-line w88" />
                <div class="empty-line w92" />
                <div class="empty-line w70" />
              </div>
            </div>
            <p class="empty-title">等待生成</p>
            <p class="empty-desc">配置左侧选项后点击「生成文案」</p>
          </div>

          <div v-else class="result-body">
            <el-alert
              v-if="result.banned_hits?.length"
              type="warning"
              :closable="false"
              show-icon
              :title="`命中禁用词：${result.banned_hits.join('、')}`"
              class="result-alert"
            />
            <el-alert
              v-if="result.llm_error"
              type="info"
              :closable="false"
              :title="`已回退模板。大模型提示：${result.llm_error}`"
              class="result-alert"
            />
            <h3 class="result-title">{{ result.title || '（无标题）' }}</h3>
            <div class="result-text">{{ result.body }}</div>
            <div class="result-actions">
              <el-button type="primary" @click="copyResult">一键复制</el-button>
              <el-button :loading="loading" @click="submit">重新生成</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.copy-generate {
  width: 100%;
  max-width: none;
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

.status-sub {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.status-bar.is-ok .status-sub {
  color: #15803d;
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

.generate-form-col > .form-card {
  width: 100%;
}

.generate-layout.is-stacked .generate-side-col {
  margin-top: 16px;
}

@media (max-width: 991px) {
  /*
   * compact 下 gutter=0，仍清掉 EP 可能残留的左右负 margin / col padding，
   * 避免窄屏右侧比左侧多出一截。
   */
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

  .copy-generate {
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    box-sizing: border-box;
  }
}

.form-card,
.material-card,
.result-card {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.form-card :deep(.el-card__header),
.material-card :deep(.el-card__header),
.result-card :deep(.el-card__header) {
  padding: 14px 18px;
  border-bottom-color: var(--oc-border, #e8e0d0);
}

.form-card :deep(.el-card__body),
.material-card :deep(.el-card__body),
.result-card :deep(.el-card__body) {
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
}

.card-sub {
  margin-top: 4px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.45;
}

.copy-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.copy-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: var(--oc-ink, #44403c);
}

.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.mode-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  width: 100%;
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

.result-card {
  margin-top: 16px;
}

/* 素材区 */
.material-empty,
.result-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  padding: 24px 16px;
  text-align: center;
  border-radius: 12px;
  border: 1px dashed var(--oc-border, #e8e0d0);
  background:
    radial-gradient(circle at 30% 20%, rgba(245, 230, 200, 0.45), transparent 55%),
    #faf6ee;
}

.material-empty-art,
.result-empty-art {
  margin-bottom: 12px;
}

.empty-doc,
.empty-lines {
  width: 140px;
  padding: 14px;
  border-radius: 10px;
  background: #fffdf8;
  border: 1px solid var(--oc-border, #e8e0d0);
  box-shadow: 0 8px 20px rgba(41, 37, 36, 0.06);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-line {
  height: 6px;
  border-radius: 3px;
  background: #e8e0d0;
}

.empty-line.w40 {
  width: 40%;
}
.empty-line.w50 {
  width: 50%;
}
.empty-line.w60 {
  width: 60%;
}
.empty-line.w70 {
  width: 70%;
}
.empty-line.w75 {
  width: 75%;
}
.empty-line.w88 {
  width: 88%;
}
.empty-line.w90 {
  width: 90%;
}
.empty-line.w92 {
  width: 92%;
}
.empty-line.w95 {
  width: 95%;
}

.empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.empty-desc {
  margin: 6px 0 0;
  max-width: 320px;
  font-size: 12px;
  line-height: 1.55;
  color: var(--oc-muted, #78716c);
}

.empty-desc code {
  margin: 0 1px;
  padding: 0 4px;
  border-radius: 3px;
  background: rgba(161, 98, 7, 0.08);
  color: var(--oc-primary, #a16207);
  font-size: 11px;
}

.material-split {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(240px, 1.15fr);
  gap: 18px;
  align-items: stretch;
  min-height: 280px;
}

.material-split.is-compact {
  grid-template-columns: 1fr;
  min-height: 0;
}

.material-left {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.thumb-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.thumb-btn {
  position: relative;
  width: 64px;
  height: 64px;
  padding: 0;
  border: 2px solid transparent;
  border-radius: 10px;
  overflow: hidden;
  background: #f5f0e6;
  cursor: pointer;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(41, 37, 36, 0.08);
  transition:
    border-color 0.15s,
    box-shadow 0.15s,
    transform 0.15s;
}

.thumb-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-btn.active {
  border-color: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 2px rgba(161, 98, 7, 0.2);
}

.thumb-btn:hover {
  transform: translateY(-1px);
  border-color: var(--oc-primary-hover, #86530a);
}

.thumb-index {
  position: absolute;
  right: 3px;
  bottom: 3px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: rgba(41, 37, 36, 0.65);
  color: #fff;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
}

.thumb-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.no-images {
  margin: 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.material-fields {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.material-field {
  padding: 10px 12px;
  border-radius: 10px;
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
  border: 1px solid var(--oc-border, #e8e0d0);
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
}

.material-field:hover {
  border-color: #dbbf94;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.06);
}

.material-field-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.material-field-label {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  font-weight: 500;
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

.param-mark--inline {
  display: inline-flex;
  vertical-align: middle;
  margin: 0 2px;
  cursor: default;
  pointer-events: none;
  width: 18px;
  height: 14px;
  font-size: 9px;
}

.material-field-value {
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.material-field-value.empty {
  color: #a8a29e;
  font-weight: 400;
  font-style: italic;
}

.material-stage {
  position: relative;
  min-width: 0;
  min-height: 260px;
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    radial-gradient(circle at 30% 20%, rgba(245, 230, 200, 0.55), transparent 55%),
    #faf6ee;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 14px;
  overflow: hidden;
}

.material-stage.clickable {
  cursor: zoom-in;
}

.material-stage.clickable:hover {
  border-color: var(--oc-primary, #a16207);
}

.material-stage.clickable:hover .stage-overlay {
  opacity: 1;
}

.stage-img {
  width: 100%;
  flex: 1;
  min-height: 200px;
  max-height: 320px;
  object-fit: contain;
  border-radius: 8px;
  pointer-events: none;
  user-select: none;
}

.stage-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(41, 37, 36, 0.28);
  opacity: 0;
  transition: opacity 0.18s;
  pointer-events: none;
  border-radius: 12px;
}

.stage-overlay-text {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.92);
  color: var(--oc-ink, #44403c);
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.stage-empty {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  text-align: center;
  padding: 24px;
}

/* 结果 */
.result-alert {
  margin-bottom: 12px;
}

.result-title {
  margin: 0 0 12px;
  font-size: 17px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.4;
}

.result-text {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #faf6ee;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  min-height: 200px;
  max-height: 480px;
  overflow-y: auto;
}

.result-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

:global(.copy-param-tip.el-popper) {
  max-width: 280px;
  padding: 10px 12px !important;
  border-radius: 8px !important;
}

:global(.copy-param-tip .tip-body) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

:global(.copy-param-tip .tip-title) {
  font-size: 11px;
  opacity: 0.75;
  letter-spacing: 0.04em;
}

:global(.copy-param-tip .tip-code) {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.14);
  color: #fde68a;
  font-size: 13px;
  font-weight: 600;
}

:global(.copy-param-tip .tip-desc) {
  font-size: 11px;
  line-height: 1.45;
  opacity: 0.8;
}
</style>
