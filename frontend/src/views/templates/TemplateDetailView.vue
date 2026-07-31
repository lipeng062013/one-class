<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteCopyTemplate,
  deletePosterTemplate,
  getCopyTemplate,
  getPosterTemplate,
  updateCopyTemplate,
  updatePosterTemplate,
  type CopyTemplate,
  type PosterTemplate,
} from '../../api/templates'
import {
  COPY_TEMPLATE_PARAMS,
  POSTER_FIELD_META,
  POSTER_LAYOUT_META,
  copyParamPlaceholder,
} from '../../constants/templateParams'
import { usePageBack } from '../../composables/usePageBack'

const SCENE_LABELS: Record<string, string> = {
  xhs_script: '小红书话术',
  xhs_poster: '小红书海报',
  douyin_script: '抖音话术',
  douyin_poster: '抖音海报',
  wechat_script: '微信话术',
  general: '通用',
}

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/templates')

const loading = ref(false)
const saving = ref(false)
const editing = ref(false)

const kind = computed<'copies' | 'posters'>(() => {
  const meta = route.meta.templateKind
  if (meta === 'posters' || meta === 'copies') return meta
  return route.path.includes('/posters/') ? 'posters' : 'copies'
})

const isCopy = computed(() => kind.value === 'copies')
const templateId = computed(() => Number(route.params.id))

const copyItem = ref<CopyTemplate | null>(null)
const posterItem = ref<PosterTemplate | null>(null)

const item = computed(() => (isCopy.value ? copyItem.value : posterItem.value))

const editForm = reactive({
  name: '',
  scene: '',
  body: '',
  layout_json: '',
  is_active: true,
})

const kindLabel = computed(() => (isCopy.value ? '文案模板' : '海报模板'))

const sceneText = computed(() => {
  const s = item.value?.scene
  if (!s) return '—'
  return SCENE_LABELS[s] || s
})

const createdAtText = computed(() => formatTime(item.value?.created_at))

const prettyLayout = computed(() => {
  const raw = editing.value ? editForm.layout_json : posterItem.value?.layout_json || ''
  try {
    return JSON.stringify(JSON.parse(raw || '{}'), null, 2)
  } catch {
    return raw || ''
  }
})

const usedCopyParams = computed(() => {
  const body = editing.value ? editForm.body : copyItem.value?.body || ''
  return COPY_TEMPLATE_PARAMS.filter((p) => body.includes(`{{${p.key}}}`) || body.includes(`{{ ${p.key} }}`))
})

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function sceneLabel(scene?: string | null) {
  if (!scene) return '—'
  return SCENE_LABELS[scene] || scene
}

async function load() {
  if (!templateId.value || Number.isNaN(templateId.value)) {
    ElMessage.error('无效的模板 ID')
    goBack()
    return
  }
  loading.value = true
  editing.value = false
  copyItem.value = null
  posterItem.value = null
  try {
    if (isCopy.value) {
      copyItem.value = await getCopyTemplate(templateId.value)
      editForm.name = copyItem.value.name
      editForm.scene = copyItem.value.scene
      editForm.body = copyItem.value.body || ''
      editForm.is_active = copyItem.value.is_active
      editForm.layout_json = ''
    } else {
      posterItem.value = await getPosterTemplate(templateId.value)
      editForm.name = posterItem.value.name
      editForm.scene = posterItem.value.scene
      editForm.is_active = posterItem.value.is_active
      try {
        editForm.layout_json = JSON.stringify(
          JSON.parse(posterItem.value.layout_json || '{}'),
          null,
          2,
        )
      } catch {
        editForm.layout_json = posterItem.value.layout_json || '{}'
      }
      editForm.body = ''
    }
  } catch {
    ElMessage.error('加载失败')
    goBack()
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!item.value) return
  if (isCopy.value && copyItem.value) {
    editForm.name = copyItem.value.name
    editForm.scene = copyItem.value.scene
    editForm.body = copyItem.value.body || ''
    editForm.is_active = copyItem.value.is_active
  } else if (posterItem.value) {
    editForm.name = posterItem.value.name
    editForm.scene = posterItem.value.scene
    editForm.is_active = posterItem.value.is_active
    try {
      editForm.layout_json = JSON.stringify(
        JSON.parse(posterItem.value.layout_json || '{}'),
        null,
        2,
      )
    } catch {
      editForm.layout_json = posterItem.value.layout_json || '{}'
    }
  }
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (isCopy.value && copyItem.value) {
    editForm.name = copyItem.value.name
    editForm.scene = copyItem.value.scene
    editForm.body = copyItem.value.body || ''
    editForm.is_active = copyItem.value.is_active
  } else if (posterItem.value) {
    editForm.name = posterItem.value.name
    editForm.scene = posterItem.value.scene
    editForm.is_active = posterItem.value.is_active
    try {
      editForm.layout_json = JSON.stringify(
        JSON.parse(posterItem.value.layout_json || '{}'),
        null,
        2,
      )
    } catch {
      editForm.layout_json = posterItem.value.layout_json || '{}'
    }
  }
}

async function saveEdit() {
  if (!item.value) return
  const name = editForm.name.trim()
  const scene = editForm.scene.trim()
  if (!name) {
    ElMessage.warning('请填写名称')
    return
  }
  if (!scene) {
    ElMessage.warning('请填写场景')
    return
  }

  saving.value = true
  try {
    if (isCopy.value) {
      if (!editForm.body.trim()) {
        ElMessage.warning('正文不能为空')
        return
      }
      copyItem.value = await updateCopyTemplate(item.value.id, {
        name,
        scene,
        body: editForm.body,
        is_active: editForm.is_active,
      })
      editForm.body = copyItem.value.body || ''
      ElMessage.success('文案模板已保存')
    } else {
      let layoutStr = editForm.layout_json
      try {
        layoutStr = JSON.stringify(JSON.parse(editForm.layout_json))
      } catch {
        ElMessage.error('layout_json 不是合法 JSON')
        return
      }
      posterItem.value = await updatePosterTemplate(item.value.id, {
        name,
        scene,
        layout_json: layoutStr,
        is_active: editForm.is_active,
      })
      try {
        editForm.layout_json = JSON.stringify(
          JSON.parse(posterItem.value.layout_json || '{}'),
          null,
          2,
        )
      } catch {
        editForm.layout_json = posterItem.value.layout_json || '{}'
      }
      ElMessage.success('海报模板已保存')
    }
    editing.value = false
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function copyContent() {
  if (!item.value) return
  const text = isCopy.value
    ? copyItem.value?.body || ''
    : prettyLayout.value
  if (!text) {
    ElMessage.warning('暂无内容可复制')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(isCopy.value ? '已复制正文模板' : '已复制 layout JSON')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function onDelete() {
  if (!item.value) return
  if (item.value.is_system) {
    ElMessage.warning('系统模板不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`删除${kindLabel.value}「${item.value.name}」？`, '确认', {
      type: 'warning',
    })
    if (isCopy.value) await deleteCopyTemplate(item.value.id)
    else await deletePosterTemplate(item.value.id)
    ElMessage.success('已删除')
    router.push('/templates')
  } catch {
    /* cancel */
  }
}

function goGenerate() {
  if (!item.value) return
  if (isCopy.value) {
    router.push({ path: '/copies/generate', query: { template_id: String(item.value.id) } })
  } else {
    router.push({ path: '/posters/generate', query: { template_id: String(item.value.id) } })
  }
}

function insertCopyParam(key: string) {
  if (!editing.value) return
  const token = copyParamPlaceholder(key)
  editForm.body = `${editForm.body || ''}${token}`
}

watch([templateId, kind], () => load())
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="tpl-detail oc-page-shell">
    <div class="page-toolbar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">{{ kindLabel }}详情</span>
        </template>
      </el-page-header>
      <div v-if="item" class="toolbar-actions">
        <el-button type="primary" plain @click="goGenerate">
          <el-icon class="btn-ico"><MagicStick /></el-icon>
          {{ isCopy ? '用此模板生成文案' : '用此模板生成海报' }}
        </el-button>
        <el-button @click="copyContent">
          <el-icon class="btn-ico"><DocumentCopy /></el-icon>
          复制内容
        </el-button>
        <el-button v-if="!editing" @click="startEdit">
          <el-icon class="btn-ico"><EditPen /></el-icon>
          编辑
        </el-button>
        <template v-else>
          <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
          <el-button :disabled="saving" @click="cancelEdit">取消</el-button>
        </template>
      </div>
    </div>

    <template v-if="item">
      <section class="hero">
        <div class="hero-ornament" aria-hidden="true" />
        <div class="hero-body">
          <div class="hero-main">
            <div class="hero-kicker">
              <el-icon><Files /></el-icon>
              <span>{{ kindLabel }} #{{ item.id }}</span>
            </div>
            <h1 class="hero-title">{{ item.name }}</h1>
            <div class="hero-tags">
              <el-tag size="small" effect="plain" round type="info">{{ sceneText }}</el-tag>
              <el-tag
                size="small"
                effect="plain"
                round
                :type="item.is_system ? 'warning' : 'info'"
              >
                {{ item.is_system ? '系统' : '自定义' }}
              </el-tag>
              <el-tag
                size="small"
                effect="plain"
                round
                :type="item.is_active ? 'success' : 'info'"
              >
                {{ item.is_active ? '启用' : '停用' }}
              </el-tag>
              <span class="meta-chip muted">
                <el-icon><Clock /></el-icon>
                {{ createdAtText }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <div class="detail-grid">
        <section class="panel content-panel">
          <div class="panel-head">
            <h2 class="panel-title">{{ editing ? '编辑模板' : '模板内容' }}</h2>
          </div>

          <template v-if="editing">
            <div class="edit-field">
              <label class="edit-label">名称</label>
              <el-input v-model="editForm.name" maxlength="120" show-word-limit />
            </div>
            <div class="edit-field">
              <label class="edit-label">场景</label>
              <el-input v-model="editForm.scene" placeholder="例如 xhs_script" />
            </div>
            <div class="edit-field">
              <label class="edit-label">状态</label>
              <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
            </div>

            <template v-if="isCopy">
              <div class="edit-field">
                <label class="edit-label">正文模板</label>
                <div class="param-row">
                  <button
                    v-for="p in COPY_TEMPLATE_PARAMS"
                    :key="p.key"
                    type="button"
                    class="param-chip"
                    @click="insertCopyParam(p.key)"
                  >
                    {{ p.label }}
                  </button>
                </div>
                <el-input
                  v-model="editForm.body"
                  type="textarea"
                  :rows="12"
                  class="body-textarea"
                  placeholder="支持 {{变量}}"
                />
              </div>
            </template>
            <template v-else>
              <div class="edit-field">
                <label class="edit-label">layout_json</label>
                <el-input
                  v-model="editForm.layout_json"
                  type="textarea"
                  :rows="14"
                  class="body-textarea mono"
                  placeholder="{ ... }"
                />
              </div>
            </template>
          </template>

          <template v-else>
            <div class="view-block">
              <div class="field-label">名称</div>
              <div class="view-text strong">{{ item.name }}</div>
            </div>
            <div class="view-block">
              <div class="field-label">场景</div>
              <div class="view-text">{{ sceneLabel(item.scene) }}（{{ item.scene }}）</div>
            </div>
            <div v-if="isCopy" class="view-block">
              <div class="field-label">正文模板</div>
              <pre class="content-pre">{{ copyItem?.body || '（空）' }}</pre>
            </div>
            <div v-else class="view-block">
              <div class="field-label">版式 JSON</div>
              <pre class="content-pre mono">{{ prettyLayout || '（空）' }}</pre>
            </div>
          </template>
        </section>

        <aside class="side-col">
          <section class="panel meta-panel">
            <div class="panel-head">
              <h2 class="panel-title">基础信息</h2>
            </div>
            <dl class="meta-list">
              <div class="meta-row">
                <dt>类型</dt>
                <dd>{{ kindLabel }}</dd>
              </div>
              <div class="meta-row">
                <dt>来源</dt>
                <dd>{{ item.is_system ? '系统内置' : '自定义' }}</dd>
              </div>
              <div class="meta-row">
                <dt>状态</dt>
                <dd>{{ item.is_active ? '启用' : '停用' }}</dd>
              </div>
              <div class="meta-row">
                <dt>创建时间</dt>
                <dd>{{ createdAtText }}</dd>
              </div>
              <div v-if="isCopy && copyItem?.created_by" class="meta-row">
                <dt>创建人</dt>
                <dd>#{{ copyItem.created_by }}</dd>
              </div>
              <div v-if="!isCopy && posterItem?.preview_path" class="meta-row">
                <dt>预览路径</dt>
                <dd>{{ posterItem.preview_path }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="isCopy" class="panel">
            <div class="panel-head">
              <h2 class="panel-title">已用变量</h2>
            </div>
            <div v-if="usedCopyParams.length" class="hint-list">
              <div v-for="p in usedCopyParams" :key="p.key" class="hint-item">
                <code>{{ copyParamPlaceholder(p.key) }}</code>
                <span>{{ p.label }}</span>
                <small>{{ p.source }}</small>
              </div>
            </div>
            <p v-else class="empty-hint">正文中尚未使用已知变量</p>
            <div class="all-params">
              <div class="field-label">全部可用变量</div>
              <div class="param-row">
                <el-tooltip
                  v-for="p in COPY_TEMPLATE_PARAMS"
                  :key="p.key"
                  :content="p.source"
                  placement="top"
                >
                  <span class="param-chip static">{{ p.label }}</span>
                </el-tooltip>
              </div>
            </div>
          </section>

          <section v-else class="panel">
            <div class="panel-head">
              <h2 class="panel-title">版式字段说明</h2>
            </div>
            <div class="hint-list">
              <div v-for="p in POSTER_LAYOUT_META" :key="p.key" class="hint-item">
                <code>{{ p.key }}</code>
                <span>{{ p.label }}</span>
                <small>{{ p.source }}</small>
              </div>
              <div v-for="p in POSTER_FIELD_META" :key="`f-${p.key}`" class="hint-item">
                <code>fields[].{{ p.key }}</code>
                <span>{{ p.label }}</span>
                <small>{{ p.source }}</small>
              </div>
            </div>
          </section>

          <section class="panel danger-panel">
            <div class="panel-head">
              <h2 class="panel-title">危险操作</h2>
            </div>
            <el-button type="danger" plain :disabled="item.is_system" @click="onDelete">
              {{ item.is_system ? '系统模板不可删除' : '删除模板' }}
            </el-button>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 内容宽度：全局 .oc-page-shell（与工作台一致，见 docs/ui-detail-page-pattern.md） */
.tpl-detail {
  padding-bottom: 16px;
}

.page-title {
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn-ico {
  margin-right: 4px;
}

.hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(135deg, #fffdf8 0%, #faf6ee 45%, #f5e6c8 120%);
  box-shadow: 0 10px 28px rgba(41, 37, 36, 0.05);
  margin-bottom: 14px;
}

.hero-ornament {
  position: absolute;
  width: 240px;
  height: 240px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.12);
  right: -48px;
  top: -80px;
  pointer-events: none;
}

.hero-body {
  position: relative;
  z-index: 1;
  padding: 20px 22px;
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
  margin-bottom: 8px;
}

.hero-title {
  margin: 0;
  font-size: clamp(1.2rem, 1.1vw + 0.8rem, 1.55rem);
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
  word-break: break-word;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.75);
  border: 1px solid rgba(232, 224, 208, 0.95);
  font-size: 12px;
}

.meta-chip.muted {
  color: var(--oc-muted, #78716c);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  align-items: start;
}

.side-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  padding: 16px 18px;
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  min-width: 0;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
}

.field-label,
.edit-label {
  display: block;
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-muted, #78716c);
  margin-bottom: 6px;
  letter-spacing: 0.04em;
}

.view-block {
  margin-bottom: 16px;
}

.view-block:last-child {
  margin-bottom: 0;
}

.view-text {
  font-size: 14px;
  color: var(--oc-ink, #44403c);
  line-height: 1.5;
  word-break: break-word;
}

.view-text.strong {
  font-size: 16px;
  font-weight: 650;
}

.content-pre {
  margin: 0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.7;
  color: var(--oc-ink, #44403c);
  white-space: pre-wrap;
  word-break: break-word;
  background: #fff;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 14px 16px;
  max-height: min(62vh, 640px);
  overflow: auto;
}

.content-pre.mono,
.mono :deep(.el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.edit-field {
  margin-bottom: 14px;
}

.body-textarea :deep(.el-textarea__inner) {
  height: auto !important;
  min-height: 260px !important;
  max-height: min(60vh, 560px) !important;
  line-height: 1.65;
  resize: vertical !important;
  background: #fff;
}

.param-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.param-chip {
  appearance: none;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #faf6ee;
  color: var(--oc-primary, #a16207);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.param-chip:hover:not(.static) {
  border-color: var(--el-color-primary-light-5);
  background: #f5e6c8;
}

.param-chip.static {
  cursor: default;
}

.meta-list {
  margin: 0;
}

.meta-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  font-size: 13px;
}

.meta-row:first-child {
  padding-top: 0;
}

.meta-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.meta-row dt {
  margin: 0;
  color: var(--oc-muted, #78716c);
  font-weight: 550;
}

.meta-row dd {
  margin: 0;
  color: var(--oc-ink, #44403c);
  word-break: break-word;
}

.hint-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hint-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #faf6ee;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.hint-item code {
  font-size: 12px;
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.hint-item span {
  font-size: 13px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.hint-item small {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.empty-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.all-params {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.danger-panel {
  background: #fef7f7;
  border-color: #f3d4d4;
}

@media (min-width: 992px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.8fr);
    gap: 16px;
  }

  .hero-body {
    padding: 24px 26px;
  }
}

@media (max-width: 767px) {
  .toolbar-actions {
    width: 100%;
  }

  .toolbar-actions .el-button {
    flex: 1;
  }

  .content-pre {
    max-height: none;
  }
}
</style>
