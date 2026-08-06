<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteCopy,
  getCopy,
  patchCopy,
  type GeneratedCopy,
} from '../../api/copies'
import { useListDetailStateCleanup } from '../../composables/useListScrollRestore'
import { usePageBack } from '../../composables/usePageBack'

const MODE_LABELS: Record<string, string> = {
  template: '仅模板',
  template_then_llm: '模板+润色',
  llm: '直接大模型',
}

const PLATFORM_LABELS: Record<string, string> = {
  xhs: '小红书',
  douyin: '抖音',
  wechat: '微信',
  moments: '朋友圈',
  video: '视频号',
}

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/copies')
useListDetailStateCleanup('copies', 'oc-copy-list-state')

const loading = ref(false)
const saving = ref(false)
const item = ref<GeneratedCopy | null>(null)
const editing = ref(false)
const showPrompt = ref(false)

const editForm = reactive({
  title: '',
  body: '',
})

const copyId = computed(() => Number(route.params.id))

const modeText = computed(() => {
  const m = item.value?.mode
  if (!m) return '—'
  return MODE_LABELS[m] || m
})

const platformText = computed(() => {
  const p = item.value?.platform
  if (!p) return '—'
  return PLATFORM_LABELS[p] || p
})

const createdAtText = computed(() => formatTime(item.value?.created_at))

const charCount = computed(() => {
  const t = editing.value ? editForm.title : item.value?.title || ''
  const b = editing.value ? editForm.body : item.value?.body || ''
  return (t + b).length
})

const bannedHits = computed(() => item.value?.banned_hits || [])

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function modeLabel(mode?: string | null) {
  if (!mode) return '—'
  return MODE_LABELS[mode] || mode
}

async function load() {
  if (!copyId.value || Number.isNaN(copyId.value)) {
    ElMessage.error('无效的文案 ID')
    goBack()
    return
  }
  loading.value = true
  editing.value = false
  showPrompt.value = false
  try {
    item.value = await getCopy(copyId.value)
    editForm.title = item.value.title || ''
    editForm.body = item.value.body || ''
  } catch {
    ElMessage.error('加载失败')
    goBack()
  } finally {
    loading.value = false
  }
}

function startEdit() {
  if (!item.value) return
  editForm.title = item.value.title || ''
  editForm.body = item.value.body || ''
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  if (item.value) {
    editForm.title = item.value.title || ''
    editForm.body = item.value.body || ''
  }
}

async function saveEdit() {
  if (!item.value) return
  const title = editForm.title.trim()
  const body = editForm.body.trim()
  if (!body) {
    ElMessage.warning('正文不能为空')
    return
  }
  saving.value = true
  try {
    item.value = await patchCopy(item.value.id, { title, body })
    editForm.title = item.value.title || ''
    editForm.body = item.value.body || ''
    editing.value = false
    ElMessage.success('已保存')
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

async function copyAll() {
  if (!item.value) return
  const text = `${item.value.title || ''}\n\n${item.value.body || ''}`.trim()
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制标题和正文')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function copyBodyOnly() {
  if (!item.value?.body) {
    ElMessage.warning('暂无正文')
    return
  }
  try {
    await navigator.clipboard.writeText(item.value.body)
    ElMessage.success('已复制正文')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function onDelete() {
  if (!item.value) return
  try {
    await ElMessageBox.confirm(`删除文案「${item.value.title || item.value.id}」？`, '确认', {
      type: 'warning',
    })
    await deleteCopy(item.value.id)
    ElMessage.success('已删除')
    goBack()
  } catch {
    /* cancel */
  }
}

function goMaterial() {
  if (!item.value?.material_id) return
  router.push(`/materials/${item.value.material_id}`)
}

watch(copyId, () => load())
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="copy-detail oc-page-shell">
    <div class="page-toolbar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">文案详情</span>
        </template>
      </el-page-header>
      <div v-if="item" class="toolbar-actions">
        <el-button type="primary" @click="copyAll">
          <el-icon class="btn-ico"><DocumentCopy /></el-icon>
          复制全文
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
      <!-- Hero -->
      <section class="hero">
        <div class="hero-ornament" aria-hidden="true" />
        <div class="hero-body">
          <div class="hero-main">
            <div class="hero-kicker">
              <el-icon><Document /></el-icon>
              <span>文案 #{{ item.id }}</span>
            </div>
            <h1 class="hero-title">{{ item.title || `文案 #${item.id}` }}</h1>
            <div class="hero-tags">
              <el-tag size="small" effect="plain" round type="info">{{ modeText }}</el-tag>
              <el-tag size="small" effect="plain" round>{{ platformText }}</el-tag>
              <el-tag
                v-if="bannedHits.length"
                size="small"
                effect="dark"
                type="danger"
                round
              >
                禁用词 {{ bannedHits.length }}
              </el-tag>
              <span v-if="item.model_name" class="meta-chip">
                <el-icon><Cpu /></el-icon>
                {{ item.model_name }}
              </span>
              <span class="meta-chip muted">
                <el-icon><Clock /></el-icon>
                {{ createdAtText }}
              </span>
            </div>
          </div>
          <div class="hero-stats">
            <div class="stat-pill">
              <div class="stat-num">{{ charCount }}</div>
              <div class="stat-label">字符</div>
            </div>
            <div class="stat-pill">
              <div class="stat-num">{{ bannedHits.length }}</div>
              <div class="stat-label">禁用命中</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 禁用词提醒 -->
      <el-alert
        v-if="bannedHits.length"
        class="banned-alert"
        type="warning"
        :closable="false"
        show-icon
        title="正文或标题命中禁用词，发布前请修改"
      >
        <div class="banned-list">
          <el-tag v-for="w in bannedHits" :key="w" type="danger" effect="plain" size="small" round>
            {{ w }}
          </el-tag>
        </div>
      </el-alert>

      <div class="detail-grid">
        <!-- 正文 -->
        <section class="panel content-panel">
          <div class="panel-head">
            <h2 class="panel-title">{{ editing ? '编辑文案' : '文案内容' }}</h2>
            <div class="panel-head-actions">
              <el-button v-if="!editing" link type="primary" @click="copyBodyOnly">仅复制正文</el-button>
            </div>
          </div>

          <template v-if="editing">
            <div class="edit-field">
              <label class="edit-label">标题</label>
              <el-input v-model="editForm.title" maxlength="200" show-word-limit placeholder="文案标题" />
            </div>
            <div class="edit-field">
              <label class="edit-label">正文</label>
              <el-input
                v-model="editForm.body"
                type="textarea"
                :rows="14"
                class="body-textarea"
                placeholder="文案正文"
              />
            </div>
          </template>

          <template v-else>
            <div class="copy-title-block">
              <div class="field-label">标题</div>
              <div class="copy-title-text">{{ item.title || '（无标题）' }}</div>
            </div>
            <div class="copy-body-block">
              <div class="field-label">正文</div>
              <pre class="copy-body-text">{{ item.body || '（无正文）' }}</pre>
            </div>
          </template>
        </section>

        <!-- 侧栏信息 -->
        <aside class="side-col">
          <section class="panel meta-panel">
            <div class="panel-head">
              <h2 class="panel-title">生成信息</h2>
            </div>
            <dl class="meta-list">
              <div class="meta-row">
                <dt>模式</dt>
                <dd>{{ modeLabel(item.mode) }}</dd>
              </div>
              <div class="meta-row">
                <dt>平台</dt>
                <dd>{{ platformText }}</dd>
              </div>
              <div class="meta-row">
                <dt>模型</dt>
                <dd>{{ item.model_name || '—' }}</dd>
              </div>
              <div class="meta-row">
                <dt>素材</dt>
                <dd>
                  <el-button
                    v-if="item.material_id"
                    link
                    type="primary"
                    @click="goMaterial"
                  >
                    #{{ item.material_id }} 查看素材
                  </el-button>
                  <span v-else>—</span>
                </dd>
              </div>
              <div class="meta-row">
                <dt>模板 ID</dt>
                <dd>{{ item.template_id ?? '—' }}</dd>
              </div>
              <div class="meta-row">
                <dt>创建时间</dt>
                <dd>{{ createdAtText }}</dd>
              </div>
              <div v-if="item.llm_error" class="meta-row">
                <dt>LLM 提示</dt>
                <dd class="meta-warn">{{ item.llm_error }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="item.prompt_snapshot" class="panel prompt-panel">
            <div class="panel-head">
              <h2 class="panel-title">提示词快照</h2>
              <el-button link type="primary" @click="showPrompt = !showPrompt">
                {{ showPrompt ? '收起' : '展开' }}
              </el-button>
            </div>
            <pre v-show="showPrompt" class="prompt-text">{{ item.prompt_snapshot }}</pre>
            <p v-show="!showPrompt" class="prompt-hint">生成时发送给大模型的完整提示（可展开查看）</p>
          </section>

          <section class="panel danger-panel">
            <div class="panel-head">
              <h2 class="panel-title">危险操作</h2>
            </div>
            <el-button type="danger" plain @click="onDelete">删除文案</el-button>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* 内容宽度：.oc-page-shell 吃满主区（docs/ui-detail-page-pattern.md） */
.copy-detail {
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

/* Hero */
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
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 22px;
}

.hero-main {
  min-width: 0;
  flex: 1;
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
  color: var(--oc-ink, #44403c);
}

.meta-chip.muted {
  color: var(--oc-muted, #78716c);
}

.hero-stats {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

.stat-pill {
  min-width: 72px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 253, 248, 0.78);
  border: 1px solid rgba(232, 224, 208, 0.95);
  text-align: center;
}

.stat-num {
  font-size: 1.3rem;
  font-weight: 750;
  color: var(--oc-primary, #a16207);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.stat-label {
  margin-top: 4px;
  font-size: 11px;
  color: var(--oc-muted, #78716c);
}

.banned-alert {
  margin-bottom: 14px;
  border-radius: 12px;
}

.banned-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
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

.field-label {
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-muted, #78716c);
  margin-bottom: 6px;
  letter-spacing: 0.04em;
}

.copy-title-block {
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.copy-title-text {
  font-size: 16px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.45;
  word-break: break-word;
}

.copy-body-text {
  margin: 0;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.75;
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

.edit-field {
  margin-bottom: 14px;
}

.edit-label {
  display: block;
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-muted, #78716c);
  margin-bottom: 6px;
}

/* 覆盖全局 textarea 固定 100px，详情编辑需要大编辑区 */
.body-textarea :deep(.el-textarea__inner) {
  height: auto !important;
  min-height: 280px !important;
  max-height: min(60vh, 560px) !important;
  line-height: 1.7;
  resize: vertical !important;
  background: #fff;
}

.meta-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.meta-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  font-size: 13px;
}

.meta-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.meta-row:first-child {
  padding-top: 0;
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

.meta-warn {
  color: #b45309 !important;
}

.prompt-text {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow: auto;
  padding: 12px;
  border-radius: 10px;
  background: #f5f0e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  color: var(--oc-ink, #44403c);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.prompt-hint {
  margin: 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.danger-panel {
  background: #fef7f7;
  border-color: #f3d4d4;
}

@media (min-width: 992px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.75fr);
    gap: 16px;
  }

  .side-col .meta-panel {
    position: sticky;
    top: 12px;
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

  .hero-body {
    flex-direction: column;
  }

  .hero-stats {
    width: 100%;
  }

  .stat-pill {
    flex: 1;
  }

  .copy-body-text {
    max-height: none;
  }
}
</style>
