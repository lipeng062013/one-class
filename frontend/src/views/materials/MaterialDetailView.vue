<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type UploadRequestOptions } from 'element-plus'
import {
  deleteMaterialApi,
  getMaterialApi,
  materialFileObjectUrl,
  patchMaterialApi,
  uploadMaterialFileApi,
  type Material,
} from '../../api/materials'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useListDetailStateCleanup } from '../../composables/useListScrollRestore'
import { usePageBack } from '../../composables/usePageBack'
import { asyncPool } from '../../utils/asyncPool'
import MobileActionBar from '../../components/MobileActionBar.vue'

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/materials')
useListDetailStateCleanup('materials', 'oc-material-list-state')
const auth = useAuthStore()
const { isApp } = useBreakpoint()
const loading = ref(false)
const uploading = ref(false)
const item = ref<Material | null>(null)
const previewUrls = ref<Record<number, string>>({})
const previewLoading = ref(false)
/** 手机端：内容 / 图库分段 */
const detailSection = ref<'content' | 'gallery'>('content')

/** 负责人/运营可补图任意素材；老师仅可给自己上传的素材补图 */
const canUploadMore = computed(() => {
  if (!item.value || !auth.user) return false
  if (auth.user.role === 'admin' || auth.user.role === 'operator') return true
  return item.value.uploader_id === auth.user.id
})

const canManage = computed(() => !auth.isTeacher)

const statusLabel: Record<string, string> = {
  new: '新建',
  usable: '可用',
  used: '已用',
  archived: '归档',
}
const authLabel: Record<string, string> = {
  pending: '待授权',
  authorized: '已授权',
  denied: '拒绝',
  anonymized: '已脱敏',
}

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  if (status === 'usable') return 'success'
  if (status === 'new') return 'primary'
  if (status === 'used') return 'warning'
  return 'info'
}

function authTagType(a: string): 'success' | 'warning' | 'info' | 'danger' {
  if (a === 'authorized') return 'success'
  if (a === 'pending') return 'warning'
  if (a === 'denied') return 'danger'
  return 'info'
}

const fileCount = computed(() => item.value?.files?.length ?? 0)

const loadedPreviewCount = computed(
  () => Object.keys(previewUrls.value).filter((k) => previewUrls.value[Number(k)]).length,
)

const createdAtText = computed(() => formatTime(item.value?.created_at))

const contentBlocks = computed(() => {
  if (!item.value) return []
  return [
    {
      key: 'pain',
      label: '家长痛点',
      icon: 'ChatDotRound',
      value: item.value.pain_point,
      tone: 'rose',
    },
    {
      key: 'action',
      label: '老师处理',
      icon: 'Reading',
      value: item.value.teacher_action,
      tone: 'amber',
    },
    {
      key: 'next',
      label: '下一步',
      icon: 'Right',
      value: item.value.next_step,
      tone: 'sage',
    },
  ]
})

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function revokePreviews() {
  Object.values(previewUrls.value).forEach((u) => URL.revokeObjectURL(u))
  previewUrls.value = {}
}

function materialPreviewList(): string[] {
  if (!item.value?.files?.length) return []
  return item.value.files.map((f) => previewUrls.value[f.id]).filter(Boolean) as string[]
}

function materialPreviewIndex(fileId: number): number {
  const list = materialPreviewList()
  const url = previewUrls.value[fileId]
  if (!url) return 0
  const idx = list.indexOf(url)
  return idx >= 0 ? idx : 0
}

const PREVIEW_CONCURRENCY = 4

async function loadPreviews(material: Material) {
  revokePreviews()
  const files = material.files || []
  if (!files.length) return
  previewLoading.value = true
  try {
    await asyncPool(files, PREVIEW_CONCURRENCY, async (f) => {
      try {
        const url = await materialFileObjectUrl(f.id, { thumb: true })
        previewUrls.value[f.id] = url
      } catch {
        /* skip broken file */
      }
    })
  } finally {
    previewLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    item.value = await getMaterialApi(Number(route.params.id))
  } catch {
    ElMessage.error('加载失败')
    goBack()
    return
  } finally {
    loading.value = false
  }
  if (item.value) void loadPreviews(item.value)
}

async function setStatus(status: string) {
  if (!item.value) return
  item.value = await patchMaterialApi(item.value.id, { status })
  ElMessage.success('状态已更新')
}

async function setAuth(auth_status: string) {
  if (!item.value) return
  item.value = await patchMaterialApi(item.value.id, { auth_status })
  ElMessage.success('授权已更新')
}

async function onDelete() {
  if (!item.value) return
  try {
    await ElMessageBox.confirm(`确定删除素材「${item.value.title}」？`, '删除确认', {
      type: 'warning',
    })
    await deleteMaterialApi(item.value.id)
    ElMessage.success('已删除')
    goBack()
  } catch {
    /* cancel */
  }
}

async function onUploadMore(options: UploadRequestOptions) {
  if (!item.value) return
  uploading.value = true
  try {
    await uploadMaterialFileApi(item.value.id, options.file as File)
    ElMessage.success('图片已上传')
    await load()
    options.onSuccess?.({})
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '上传失败'
    ElMessage.error(msg)
    // el-upload http-request 的 onError 需要 UploadAjaxError 形态（status/method/url）
    options.onError?.(
      Object.assign(new Error(msg), {
        status: 500,
        method: 'POST',
        url: '',
      }) as Parameters<UploadRequestOptions['onError']>[0],
    )
  } finally {
    uploading.value = false
  }
}

function goGenerateCopy() {
  if (!item.value) return
  // 素材仅用于生成文案，不进入海报流程
  router.push({ path: '/copies/generate', query: { material_id: String(item.value.id) } })
}

watch(
  () => route.params.id,
  () => load(),
)

onMounted(load)
onUnmounted(revokePreviews)
</script>

<template>
  <div v-loading="loading" class="mat-detail oc-page-shell" :class="{ 'is-app': isApp }">
    <!-- 顶栏 -->
    <div class="page-toolbar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">{{ isApp && item ? item.title : '素材详情' }}</span>
        </template>
      </el-page-header>
      <div v-if="item && canManage && !isApp" class="toolbar-actions">
        <el-button type="primary" @click="goGenerateCopy">
          <el-icon class="btn-ico"><EditPen /></el-icon>
          生成文案
        </el-button>
      </div>
    </div>

    <template v-if="item">
      <!-- Hero -->
      <section class="hero">
        <div class="hero-ornament" aria-hidden="true" />
        <div class="hero-body">
          <div class="hero-main">
            <div class="hero-kicker">
              <el-icon><Picture /></el-icon>
              <span>素材 #{{ item.id }}</span>
            </div>
            <h1 class="hero-title" :class="{ 'is-app-hidden': isApp }">{{ item.title }}</h1>
            <div class="hero-tags">
              <el-tag
                size="small"
                effect="dark"
                :type="statusTagType(item.status)"
                class="hero-tag"
              >
                {{ statusLabel[item.status] || item.status }}
              </el-tag>
              <el-tag
                size="small"
                effect="plain"
                :type="authTagType(item.auth_status)"
                class="hero-tag"
              >
                {{ authLabel[item.auth_status] || item.auth_status }}
              </el-tag>
              <span v-if="item.grade" class="meta-chip">
                <el-icon><CollectionTag /></el-icon>
                {{ item.grade }}
              </span>
              <span v-if="item.subject" class="meta-chip">
                <el-icon><Notebook /></el-icon>
                {{ item.subject }}
              </span>
              <span class="meta-chip muted">
                <el-icon><Clock /></el-icon>
                {{ createdAtText }}
              </span>
            </div>
          </div>
          <div class="hero-stats">
            <div class="stat-pill">
              <div class="stat-num">{{ fileCount }}</div>
              <div class="stat-label">张图片</div>
            </div>
            <div class="stat-pill">
              <div class="stat-num">{{ loadedPreviewCount }}</div>
              <div class="stat-label">已预览</div>
            </div>
          </div>
        </div>
      </section>

      <!-- WAP/Pad：内容 / 图库分段 -->
      <el-segmented
        v-if="isApp"
        v-model="detailSection"
        class="detail-section-switch"
        :options="[
          { label: '场景内容', value: 'content' },
          { label: `图片${fileCount ? ` · ${fileCount}` : ''}`, value: 'gallery' },
        ]"
      />

      <div class="detail-grid">
        <!-- 左：内容与操作 -->
        <div v-show="!isApp || detailSection === 'content'" class="col-main">
          <!-- 内容块 -->
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">场景内容</h2>
              <span class="panel-extra">痛点 · 处理 · 下一步</span>
            </div>
            <div class="content-blocks">
              <div
                v-for="block in contentBlocks"
                :key="block.key"
                class="content-block"
                :class="`tone-${block.tone}`"
              >
                <div class="block-head">
                  <span class="block-icon" aria-hidden="true">
                    <el-icon :size="16"><component :is="block.icon" /></el-icon>
                  </span>
                  <span class="block-label">{{ block.label }}</span>
                </div>
                <p class="block-value" :class="{ 'is-empty': !block.value?.trim() }">
                  {{ block.value?.trim() || '暂无填写' }}
                </p>
              </div>
            </div>
          </section>

          <!-- 运营操作 -->
          <section v-if="canManage" class="panel actions-panel">
            <div class="panel-head">
              <h2 class="panel-title">运营操作</h2>
              <span class="panel-extra">状态与授权</span>
            </div>
            <div class="action-groups">
              <div class="action-group">
                <div class="group-label">素材状态</div>
                <div class="status-chips" role="group" aria-label="素材状态">
                  <button
                    type="button"
                    class="status-chip"
                    :class="{ active: item.status === 'usable', tone: 'success' }"
                    @click="setStatus('usable')"
                  >
                    可用
                  </button>
                  <button
                    type="button"
                    class="status-chip"
                    :class="{ active: item.status === 'used', tone: 'warning' }"
                    @click="setStatus('used')"
                  >
                    已用
                  </button>
                  <button
                    type="button"
                    class="status-chip"
                    :class="{ active: item.status === 'archived', tone: 'info' }"
                    @click="setStatus('archived')"
                  >
                    归档
                  </button>
                </div>
              </div>
              <div class="action-group">
                <div class="group-label">授权状态</div>
                <div class="status-chips" role="group" aria-label="授权状态">
                  <button
                    type="button"
                    class="status-chip"
                    :class="{ active: item.auth_status === 'authorized', tone: 'primary' }"
                    @click="setAuth('authorized')"
                  >
                    已授权
                  </button>
                  <button
                    type="button"
                    class="status-chip"
                    :class="{ active: item.auth_status === 'anonymized', tone: 'muted' }"
                    @click="setAuth('anonymized')"
                  >
                    已脱敏
                  </button>
                </div>
              </div>
              <div class="action-group danger-group">
                <div class="group-label">危险操作</div>
                <div class="group-btns">
                  <el-button type="danger" plain @click="onDelete">删除素材</el-button>
                </div>
              </div>
            </div>
          </section>

          <!-- 老师仅删除 -->
          <section v-else class="panel actions-panel">
            <div class="panel-head">
              <h2 class="panel-title">操作</h2>
            </div>
            <el-button type="danger" plain class="teacher-delete-btn" @click="onDelete">
              删除素材
            </el-button>
          </section>
        </div>

        <!-- 右：图库 -->
        <section v-show="!isApp || detailSection === 'gallery'" class="panel gallery-panel">
          <div class="panel-head">
            <h2 class="panel-title">
              图片预览
              <el-tag v-if="fileCount" size="small" effect="plain" class="count-tag">
                {{ fileCount }}
              </el-tag>
            </h2>
            <span v-if="previewLoading" class="panel-extra">加载缩略图…</span>
          </div>

          <div v-if="canUploadMore" class="upload-zone" v-loading="uploading">
            <el-upload
              class="upload-trigger"
              drag
              :show-file-list="false"
              :http-request="onUploadMore"
              accept="image/*"
              multiple
            >
              <div class="upload-inner">
                <el-icon class="upload-ico" :size="28"><UploadFilled /></el-icon>
                <div class="upload-text">
                  <span class="upload-title">继续上传图片</span>
                  <span class="upload-hint">
                    {{ isApp ? '点击添加 · 支持多选 · 单张 ≤ 8MB' : '拖拽或点击 · 支持多选 · 单张 ≤ 8MB' }}
                  </span>
                </div>
              </div>
            </el-upload>
          </div>

          <div v-if="!item.files?.length" class="gallery-empty">
            <div class="gallery-empty-ico" aria-hidden="true">
              <el-icon :size="26"><Picture /></el-icon>
            </div>
            <p class="gallery-empty-title">暂无图片</p>
            <p class="gallery-empty-desc">可上传课堂 / 作业相关照片</p>
          </div>

          <div v-else class="preview-grid">
            <div v-for="(f, idx) in item.files" :key="f.id" class="thumb-wrap">
              <el-image
                :src="previewUrls[f.id]"
                :preview-src-list="materialPreviewList()"
                :initial-index="materialPreviewIndex(f.id)"
                preview-teleported
                lazy
                fit="cover"
                class="thumb"
              >
                <template #placeholder>
                  <div class="thumb-ph">加载中…</div>
                </template>
                <template #error>
                  <div class="thumb-error">
                    <el-icon :size="20"><Picture /></el-icon>
                    <span>无法预览</span>
                  </div>
                </template>
              </el-image>
              <div class="thumb-idx">{{ idx + 1 }}</div>
            </div>
          </div>
        </section>
      </div>

      <MobileActionBar v-if="isApp">
        <el-button
          :type="canManage ? 'default' : 'primary'"
          @click="detailSection = detailSection === 'content' ? 'gallery' : 'content'"
        >
          <el-icon><Picture /></el-icon>
          {{ detailSection === 'content' ? '查看图片' : '场景内容' }}
        </el-button>
        <el-button v-if="canManage" type="primary" @click="goGenerateCopy">
          <el-icon><EditPen /></el-icon>
          生成文案
        </el-button>
      </MobileActionBar>
    </template>
  </div>
</template>

<style scoped>
/* 内容宽度：.oc-page-shell 吃满主区（docs/ui-detail-page-pattern.md） */
.mat-detail {
  padding-bottom: 12px;
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

/* ── Hero ── */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(135deg, #fffdf8 0%, #faf6ee 45%, #f5e6c8 120%);
  box-shadow: 0 10px 28px rgba(41, 37, 36, 0.05);
  margin-bottom: 16px;
}

.hero-ornament {
  position: absolute;
  width: 260px;
  height: 260px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.12);
  right: -50px;
  top: -90px;
  pointer-events: none;
}

.hero-ornament::after {
  content: '';
  position: absolute;
  inset: 28px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.08);
}

.hero-body {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
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
  letter-spacing: 0.04em;
  color: var(--oc-primary, #a16207);
  margin-bottom: 8px;
}

.hero-title {
  margin: 0;
  font-size: clamp(1.25rem, 1.2vw + 0.8rem, 1.65rem);
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
  letter-spacing: 0.01em;
  word-break: break-word;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}

.hero-tag {
  border-radius: 999px;
  font-weight: 550;
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
  backdrop-filter: blur(6px);
}

.stat-num {
  font-size: 1.35rem;
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

/* ── 布局 ── */
.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  align-items: start;
}

.col-main {
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
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  letter-spacing: 0.02em;
}

.panel-extra {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.count-tag {
  border-color: var(--oc-border, #e8e0d0);
  color: var(--oc-primary, #a16207);
  background: #f2e8d6;
}

/* ── 内容块 ── */
.content-blocks {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.content-block {
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  padding: 12px 14px;
  background: #fff;
}

.content-block.tone-rose {
  background: linear-gradient(145deg, #fff, #fdf6f4);
  border-color: #f0e0da;
}

.content-block.tone-amber {
  background: linear-gradient(145deg, #fff, #faf6ee);
  border-color: #ebe0cc;
}

.content-block.tone-sage {
  background: linear-gradient(145deg, #fff, #f4f7f2);
  border-color: #dde6d8;
}

.block-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.block-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tone-rose .block-icon {
  background: #fde8e4;
  color: #b45309;
}

.tone-amber .block-icon {
  background: #f5e6c8;
  color: #a16207;
}

.tone-sage .block-icon {
  background: #e8f0e6;
  color: #4d7c0f;
}

.block-label {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.block-value {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--oc-ink, #44403c);
  white-space: pre-wrap;
  word-break: break-word;
}

.content-block .block-value {
  min-height: 1.3em;
}

/* ── 操作 ── */
.action-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.action-group {
  padding: 12px 14px;
  border-radius: 12px;
  background: #faf6ee;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.action-group.danger-group {
  background: #fef7f7;
  border-color: #f3d4d4;
}

.group-label {
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-muted, #78716c);
  margin-bottom: 10px;
  letter-spacing: 0.04em;
}

.group-btns {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* 清掉 EP 相邻按钮默认 margin-left，避免换行后错位 */
.group-btns :deep(.el-button) {
  margin: 0 !important;
}

.status-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-chip {
  flex: 1 1 calc(33.33% - 6px);
  min-width: 72px;
  min-height: 40px;
  padding: 8px 12px;
  border-radius: 12px;
  border: 1.5px solid var(--oc-border, #e8e0d0);
  background: #fffdfb;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s;
  -webkit-tap-highlight-color: transparent;
}

.status-chip:hover {
  border-color: #dbbf94;
}

.status-chip.active {
  border-color: var(--oc-primary, #a16207);
  background: linear-gradient(180deg, #faf6ee, #f2e8d6);
  color: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.12);
}

.status-chip.active.tone-success {
  border-color: #67c23a;
  color: #3f8618;
  background: linear-gradient(180deg, #f3faf0, #e8f5e0);
}

.status-chip.active.tone-warning {
  border-color: #e6a23c;
  color: #b8821a;
  background: linear-gradient(180deg, #fdf6ec, #faecd8);
}

.status-chip.active.tone-info {
  border-color: #909399;
  color: #606266;
  background: linear-gradient(180deg, #f4f4f5, #e9e9eb);
}

.status-chip.active.tone-primary {
  border-color: var(--oc-primary, #a16207);
  color: #86530a;
  background: linear-gradient(180deg, #faf6ee, #f2e8d6);
}

.block-value.is-empty {
  color: var(--oc-muted, #78716c);
  font-style: italic;
}

.detail-section-switch {
  display: flex;
  width: 100%;
  margin: 0 0 14px;
}

.detail-section-switch :deep(.el-segmented__group) {
  width: 100%;
}

.detail-section-switch :deep(.el-segmented__item) {
  flex: 1;
}

.hero-title.is-app-hidden {
  /* 标题已在顶栏展示，hero 内隐藏避免重复 */
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.gallery-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 28px 16px;
  border-radius: 12px;
  border: 1.5px dashed rgba(181, 145, 83, 0.35);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
  text-align: center;
}

.gallery-empty-ico {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--oc-primary, #a16207);
  background: linear-gradient(145deg, #f5e6c8, #e8d5b0);
  margin-bottom: 4px;
}

.gallery-empty-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
}

.gallery-empty-desc {
  margin: 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.teacher-delete-btn {
  width: 100%;
  min-height: 40px;
  border-radius: 10px;
}

/* ── 图库 ── */
.upload-zone {
  margin-bottom: 14px;
}

.upload-trigger {
  width: 100%;
}

.upload-trigger :deep(.el-upload) {
  width: 100%;
}

.upload-trigger :deep(.el-upload-dragger) {
  width: 100%;
  padding: 18px 16px;
  border-radius: 12px;
  border: 1.5px dashed var(--el-color-primary-light-5);
  background: linear-gradient(145deg, #fffdf8, #faf6ee);
  transition: border-color 0.15s, background 0.15s;
}

.upload-trigger :deep(.el-upload-dragger:hover) {
  border-color: var(--oc-primary, #a16207);
  background: #f5e6c8;
}

.upload-inner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  text-align: left;
}

.upload-ico {
  color: var(--oc-primary, #a16207);
  flex-shrink: 0;
}

.upload-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.upload-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.upload-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
  gap: 12px;
}

.thumb-wrap {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #f5f0e6;
  aspect-ratio: 1;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}

.thumb-wrap:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 22px rgba(41, 37, 36, 0.1);
  border-color: var(--el-color-primary-light-5);
}

.thumb {
  width: 100%;
  height: 100%;
  display: block;
}

.thumb :deep(.el-image__inner) {
  transition: transform 0.25s ease;
}

.thumb-wrap:hover .thumb :deep(.el-image__inner) {
  transform: scale(1.04);
}

.thumb-idx {
  position: absolute;
  left: 8px;
  top: 8px;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(41, 37, 36, 0.55);
  color: #fffdf8;
  font-size: 11px;
  font-weight: 650;
  display: flex;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
  pointer-events: none;
}

.thumb-ph,
.thumb-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 100%;
  min-height: 100px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  background: #f5f0e6;
  padding: 8px;
  text-align: center;
}

/* ── PC 宽屏：内容 | 图库 ── */
@media (min-width: 992px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
    gap: 16px;
  }

  .gallery-panel {
    position: sticky;
    top: 12px;
  }

  .content-blocks {
    grid-template-columns: 1fr;
  }

  .preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  }

  .hero-body {
    padding: 24px 26px;
  }
}

@media (min-width: 1280px) {
  .content-blocks {
    /* 三块并排，宽屏更舒展 */
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 14px;
  }
}

/* ── pad / wap ── */
@media (max-width: 1199px) {
  .mat-detail.is-app {
    padding-bottom: 4px;
  }

  .page-title {
    display: block;
    max-width: min(58vw, 280px);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .hero {
    border-color: rgba(181, 145, 83, 0.36);
    border-radius: 16px;
    background:
      linear-gradient(120deg, #fffefb 0%, #faf3e6 55%, #f5e6c8 140%);
    box-shadow:
      0 10px 24px rgba(88, 60, 24, 0.1),
      0 1px 0 rgba(255, 255, 255, 0.85) inset;
    margin-bottom: 12px;
  }

  .hero-ornament {
    display: none;
  }

  .hero-body {
    padding: 14px 16px;
    gap: 12px;
  }

  .hero-kicker,
  .stat-num {
    color: #8b5406;
  }

  .hero-title {
    color: #3f3a34;
  }

  .hero-stats .stat-pill {
    min-width: 64px;
    padding: 10px 12px;
  }

  .meta-chip,
  .stat-pill {
    border-color: rgba(181, 145, 83, 0.24);
    border-radius: 10px;
    background: rgba(255, 253, 248, 0.78);
    color: #44403c;
    backdrop-filter: none;
  }

  .meta-chip.muted,
  .stat-label {
    color: #78716c;
  }

  .panel {
    padding: 14px;
    border-color: rgba(181, 145, 83, 0.28);
    border-radius: 16px;
    background:
      linear-gradient(155deg, rgba(255, 255, 255, 0.88) 0%, transparent 46%),
      #fffdf8;
    box-shadow:
      0 12px 28px rgba(88, 60, 24, 0.08),
      0 2px 0 rgba(255, 255, 255, 0.9) inset;
  }

  .preview-grid {
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 10px;
  }

  .group-btns {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }

  .group-btns :deep(.el-button) {
    width: 100%;
    margin: 0 !important;
    min-height: 42px;
    border-radius: 12px;
    justify-content: center;
    font-weight: 650;
  }

  .status-chip {
    min-height: 44px;
    border-radius: 12px;
    font-weight: 700;
  }

  .content-block {
    border-radius: 12px;
  }

  .content-block.tone-rose {
    border-color: #edc7c3;
    border-left: 3px solid #c2413b;
    background: #fdf5f4;
  }

  .content-block.tone-amber {
    border-color: #ead39e;
    border-left: 3px solid #b7791f;
    background: #fff8e8;
  }

  .content-block.tone-sage {
    border-color: #b9dcc7;
    border-left: 3px solid #2f855a;
    background: #f2faf5;
  }

  .upload-trigger :deep(.el-upload-dragger) {
    padding: 20px 14px;
    border-radius: 14px;
    min-height: 88px;
  }

  .thumb-wrap {
    border-radius: 14px;
  }

  .thumb-wrap:active {
    transform: scale(0.98);
  }
}

/* ── wap ── */
@media (max-width: 767px) {
  .hero-body {
    flex-direction: column;
    gap: 12px;
  }

  .hero-stats {
    width: 100%;
  }

  .stat-pill {
    flex: 1;
  }

  .upload-inner {
    flex-direction: column;
    text-align: center;
    gap: 8px;
  }

  .preview-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .status-chips {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .action-group:nth-child(2) .status-chips {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
