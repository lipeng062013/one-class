<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile, UploadRawFile } from 'element-plus'
import {
  bulkDeletePosters,
  deletePoster,
  listPosters,
  openPosterDownload,
  posterModeLabel,
  posterObjectUrl,
  uploadPoster,
  type GeneratedPoster,
} from '../../api/posters'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'
import { asyncPool } from '../../utils/asyncPool'

const LIST_STATE_KEY = 'oc-poster-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

type ViewMode = 'table' | 'grid'

const route = useRoute()
const router = useRouter()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const bulkLoading = ref(false)
const rows = ref<GeneratedPoster[]>([])
const page = ref(1)
const pageSize = ref(20)
const viewMode = ref<ViewMode>('table')
const selectedIds = ref<number[]>([])
const previewMap = ref<Record<number, string>>({})
/** ids whose file is missing or failed to load (show 文件缺失, no toast spam) */
const failedPreviewIds = ref<Record<number, true>>({})
const previewLoading = ref(false)

const uploadVisible = ref(false)
const uploadLoading = ref(false)
const uploadTitle = ref('')
const uploadFileList = ref<UploadFile[]>([])
const uploadPreviewUrl = ref('')
const uploadTitleError = ref('')
const uploadFileError = ref('')

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  ensureVisible,
} = useInfiniteScroll(rows, { chunk: SCROLL_CHUNK, enabled: isCompact, sentinelRef })

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('posters', {
  visibleCount,
  enabled: isCompact,
})

const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

/** Desktop grid uses current page; compact always uses infinite rows. */
const gridRows = computed(() => (isCompact.value ? infiniteRows.value : pagedRows.value))

const previewSrcList = computed(() =>
  gridRows.value.map((r) => previewMap.value[r.id]).filter(Boolean),
)

const selectedCount = computed(() => selectedIds.value.length)

function revokeAllPreviews() {
  Object.values(previewMap.value).forEach((u) => URL.revokeObjectURL(u))
  previewMap.value = {}
  failedPreviewIds.value = {}
}

function clearPreviewForIds(ids: number[]) {
  const next = { ...previewMap.value }
  const failed = { ...failedPreviewIds.value }
  for (const id of ids) {
    if (next[id]) {
      URL.revokeObjectURL(next[id])
      delete next[id]
    }
    delete failed[id]
  }
  previewMap.value = next
  failedPreviewIds.value = failed
}

function thumbLabel(row: GeneratedPoster): string {
  if (failedPreviewIds.value[row.id]) return '文件缺失'
  if (row.file_path) return '加载中…'
  return '无图'
}

/** 列表缩略图并发上限，避免一次打满 N 张原图请求 */
const PREVIEW_CONCURRENCY = 6

async function loadPreviewsFor(items: GeneratedPoster[]) {
  const need = items.filter(
    (r) => r.file_path && !previewMap.value[r.id] && !failedPreviewIds.value[r.id],
  )
  if (!need.length) return
  previewLoading.value = true
  try {
    // thumb=true：后端返回 JPEG 缩略图；边下边显示，不阻塞整页
    await asyncPool(need, PREVIEW_CONCURRENCY, async (r) => {
      try {
        const url = await posterObjectUrl(r.id, true, true)
        previewMap.value[r.id] = url
        if (failedPreviewIds.value[r.id]) {
          const failed = { ...failedPreviewIds.value }
          delete failed[r.id]
          failedPreviewIds.value = failed
        }
      } catch {
        failedPreviewIds.value[r.id] = true
      }
    })
  } finally {
    previewLoading.value = false
  }
}

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY)
    if (!raw) return
    const s = JSON.parse(raw) as { page?: number; pageSize?: number; viewMode?: ViewMode }
    if (typeof s.page === 'number' && s.page > 0) page.value = s.page
    if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
      pageSize.value = s.pageSize
    }
    if (s.viewMode === 'table' || s.viewMode === 'grid') viewMode.value = s.viewMode
  } catch {
    /* ignore */
  }
}

function saveListState() {
  try {
    sessionStorage.setItem(
      LIST_STATE_KEY,
      JSON.stringify({
        page: page.value,
        pageSize: pageSize.value,
        viewMode: viewMode.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

function clampPage() {
  if (page.value > totalPages.value) page.value = totalPages.value
  if (page.value < 1) page.value = 1
}

function goFirstPage() {
  page.value = 1
  saveListState()
}

function goLastPage() {
  page.value = totalPages.value
  saveListState()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
}

function onPageChange() {
  saveListState()
}

function setViewMode(mode: ViewMode) {
  viewMode.value = mode
  saveListState()
}

function onSelectionChange(selection: GeneratedPoster[]) {
  selectedIds.value = selection.map((s) => s.id)
}

function toggleCardSelect(id: number, checked: boolean | string | number) {
  const on = checked === true || checked === 'true'
  if (on) {
    if (!selectedIds.value.includes(id)) selectedIds.value = [...selectedIds.value, id]
  } else {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }
}

function isSelected(id: number) {
  return selectedIds.value.includes(id)
}

async function load(opts?: { fromQuery?: boolean }) {
  const snap = opts?.fromQuery ? null : takeSnapshotForLoad(route.path)
  if (opts?.fromQuery) clearSnapshot()

  loading.value = true
  try {
    rows.value = await listPosters()
    selectedIds.value = selectedIds.value.filter((id) => rows.value.some((r) => r.id === id))
    if (snap?.visibleCount != null && isCompact.value) {
      ensureVisible(snap.visibleCount)
    } else if (isCompact.value) {
      resetInfinite()
    }
    clampPage()
    saveListState()
  } finally {
    loading.value = false
  }
  void finishListEnter({ snap, forceTop: !!opts?.fromQuery })
}

async function download(row: GeneratedPoster) {
  try {
    await openPosterDownload(row.id, `${row.title || 'poster'}-${row.id}.png`)
    ElMessage.success('开始下载')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '下载失败'
    ElMessage.error(
      /not found|找不到|缺失/i.test(msg) ? '海报文件不存在或已丢失，可删除后重新生成' : msg,
    )
  }
}

async function onDelete(row: GeneratedPoster) {
  try {
    await ElMessageBox.confirm(`删除海报「${row.title || row.id}」？`, '确认', { type: 'warning' })
    clearPreviewForIds([row.id])
    await deletePoster(row.id)
    ElMessage.success('已删除')
    selectedIds.value = selectedIds.value.filter((id) => id !== row.id)
    await load()
  } catch {
    /* cancel */
  }
}

function revokeUploadPreview() {
  if (uploadPreviewUrl.value) {
    URL.revokeObjectURL(uploadPreviewUrl.value)
    uploadPreviewUrl.value = ''
  }
}

function openUploadDialog() {
  uploadTitle.value = ''
  uploadFileList.value = []
  uploadTitleError.value = ''
  uploadFileError.value = ''
  revokeUploadPreview()
  uploadVisible.value = true
}

function closeUploadDialog() {
  if (uploadLoading.value) return
  uploadVisible.value = false
  revokeUploadPreview()
}

function onUploadChange(file: UploadFile, files: UploadFile[]) {
  // Keep only the latest selected file
  uploadFileList.value = files.slice(-1)
  uploadFileError.value = ''
  revokeUploadPreview()
  const raw = files.slice(-1)[0]?.raw
  if (raw) {
    uploadPreviewUrl.value = URL.createObjectURL(raw)
  }
  // 仅在标题仍为空时用文件名预填，方便填写
  if (!uploadTitle.value.trim() && file.name) {
    const base = file.name.replace(/\.[^.]+$/, '')
    if (base) uploadTitle.value = base
  }
}

function onUploadRemove() {
  uploadFileList.value = []
  uploadFileError.value = ''
  revokeUploadPreview()
}

function beforeUpload(raw: UploadRawFile) {
  const okType = raw.type.startsWith('image/')
  if (!okType) {
    ElMessage.warning('请选择图片文件（PNG / JPG / WebP / GIF）')
    return false
  }
  if (raw.size > 12 * 1024 * 1024) {
    ElMessage.warning('单文件不能超过 12MB')
    return false
  }
  return true
}

function validateUploadForm(): boolean {
  let ok = true
  if (!uploadTitle.value.trim()) {
    uploadTitleError.value = '请填写海报标题'
    ok = false
  } else {
    uploadTitleError.value = ''
  }
  if (!uploadFileList.value[0]?.raw) {
    uploadFileError.value = '请上传海报图片'
    ok = false
  } else {
    uploadFileError.value = ''
  }
  return ok
}

async function submitUpload() {
  if (!validateUploadForm()) return
  const raw = uploadFileList.value[0]?.raw
  if (!raw) return
  uploadLoading.value = true
  try {
    const created = await uploadPoster(raw, uploadTitle.value.trim())
    ElMessage.success(`已添加海报「${created.title || created.id}」`)
    uploadVisible.value = false
    revokeUploadPreview()
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploadLoading.value = false
  }
}

async function onBulkDelete() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要删除的海报')
    return
  }
  const titles = rows.value
    .filter((r) => selectedIds.value.includes(r.id))
    .map((r) => r.title || `#${r.id}`)
  const preview =
    titles.length <= 5
      ? titles.join('、')
      : `${titles.slice(0, 5).join('、')} 等 ${titles.length} 条`
  try {
    await ElMessageBox.confirm(
      `确定批量删除 ${selectedIds.value.length} 张海报（${preview}）？不可恢复。`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
    bulkLoading.value = true
    const ids = [...selectedIds.value]
    const result = await bulkDeletePosters(ids)
    clearPreviewForIds(ids)
    ElMessage.success(`已删除 ${result.deleted_count} 张海报`)
    selectedIds.value = []
    await load()
  } catch {
    /* cancel */
  } finally {
    bulkLoading.value = false
  }
}

watch(
  [viewMode, gridRows, isCompact],
  () => {
    const needGrid = isCompact.value || viewMode.value === 'grid'
    if (needGrid) loadPreviewsFor(gridRows.value)
  },
  { immediate: true },
)

watch(pageSize, () => clampPage())

onMounted(() => {
  restoreListState()
  load()
})

onUnmounted(() => {
  revokeAllPreviews()
})
</script>

<template>
  <div>
    <div class="page-toolbar poster-toolbar">
      <el-page-header content="海报列表" />
      <div class="toolbar-right">
        <div v-if="!isCompact" class="view-switch" role="group" aria-label="视图切换">
          <button
            type="button"
            class="view-switch__btn"
            :class="{ 'is-active': viewMode === 'table' }"
            @click="setViewMode('table')"
          >
            <el-icon><List /></el-icon>
            <span>列表</span>
          </button>
          <button
            type="button"
            class="view-switch__btn"
            :class="{ 'is-active': viewMode === 'grid' }"
            @click="setViewMode('grid')"
          >
            <el-icon><Grid /></el-icon>
            <span>图片</span>
          </button>
        </div>

        <span v-if="!isCompact" class="toolbar-sep" aria-hidden="true" />

        <el-button
          class="toolbar-btn"
          :class="{ 'is-danger-ready': selectedCount > 0 }"
          plain
          type="danger"
          :disabled="!selectedCount"
          :loading="bulkLoading"
          @click="onBulkDelete"
        >
          <el-icon><Delete /></el-icon>
          <span>删除所选{{ selectedCount ? ` ${selectedCount}` : '' }}</span>
        </el-button>

        <el-button class="toolbar-btn" plain @click="openUploadDialog">
          <el-icon><Upload /></el-icon>
          <span>手动添加</span>
        </el-button>

        <el-button class="toolbar-btn toolbar-btn--primary" type="primary" @click="router.push('/posters/generate')">
          <el-icon><Plus /></el-icon>
          <span>生成海报</span>
        </el-button>
      </div>
    </div>

    <el-dialog
      v-model="uploadVisible"
      title="手动添加海报"
      width="520px"
      class="upload-poster-dialog"
      align-center
      destroy-on-close
      :close-on-click-modal="!uploadLoading"
      @closed="revokeUploadPreview"
    >
      <el-form class="upload-form" label-position="top" @submit.prevent>
        <el-form-item label="标题" required :error="uploadTitleError">
          <el-input
            v-model="uploadTitle"
            placeholder="请输入海报标题"
            maxlength="100"
            show-word-limit
            clearable
            @input="uploadTitleError = ''"
          />
        </el-form-item>
        <el-form-item label="海报图片" required :error="uploadFileError" class="upload-form-item">
          <div class="upload-zone" :class="{ 'has-file': !!uploadPreviewUrl, 'is-error': !!uploadFileError }">
            <!-- 预览与上传分离，避免大图撑破 el-upload-dragger -->
            <div v-if="uploadPreviewUrl" class="upload-preview-box">
              <img class="upload-preview-img" :src="uploadPreviewUrl" alt="预览" />
              <div class="upload-preview-actions">
                <el-button type="primary" plain size="small" @click="onUploadRemove">更换图片</el-button>
              </div>
            </div>
            <el-upload
              v-else
              v-model:file-list="uploadFileList"
              class="upload-full"
              drag
              :auto-upload="false"
              :limit="1"
              :show-file-list="false"
              accept="image/png,image/jpeg,image/jpg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
              :before-upload="beforeUpload"
              :on-change="onUploadChange"
              :on-remove="onUploadRemove"
              :on-exceed="() => ElMessage.warning('一次只能上传一张')"
            >
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div class="upload-text">将图片拖到此处，或 <em>点击选择</em></div>
              <div class="upload-hint">PNG / JPG / WebP / GIF，不超过 12MB</div>
            </el-upload>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="upload-footer">
          <el-button :disabled="uploadLoading" @click="closeUploadDialog">取消</el-button>
          <el-button type="primary" :loading="uploadLoading" @click="submitUpload">上传并添加</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Mobile / pad: 卡片列表（含缩略图） -->
    <div v-if="isCompact" v-loading="loading" class="m-card-list">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无海报</div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="m-card"
        :class="{ 'is-selected': isSelected(row.id) }"
      >
        <div class="poster-check m-poster-check" @click.stop>
          <el-checkbox
            :model-value="isSelected(row.id)"
            @update:model-value="(v: boolean | string | number) => toggleCardSelect(row.id, v)"
          />
        </div>
        <div class="m-preview-wrap">
          <el-image
            v-if="previewMap[row.id]"
            :src="previewMap[row.id]"
            fit="contain"
            class="m-preview"
            lazy
            :preview-src-list="previewSrcList"
            :initial-index="previewSrcList.indexOf(previewMap[row.id])"
            preview-teleported
            hide-on-click-modal
          />
          <div v-else class="m-preview-empty">{{ thumbLabel(row) }}</div>
        </div>
        <div class="m-card-body">
          <div class="m-card-title" :title="row.title || `海报 #${row.id}`">
            {{ row.title || `海报 #${row.id}` }}
          </div>
          <div class="m-card-meta-row">
            <span class="m-mode">{{ posterModeLabel(row.mode) }}</span>
          </div>
          <div class="m-card-actions">
            <el-button type="primary" size="small" @click="download(row)">下载</el-button>
            <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
          </div>
        </div>
      </div>
      <div ref="sentinelRef" class="scroll-sentinel">
        <span v-if="loadingMore" class="scroll-hint">加载中…</span>
        <span v-else-if="hasMoreInfinite" class="scroll-hint">上滑加载更多</span>
        <span v-else-if="rows.length" class="scroll-hint">已全部加载</span>
      </div>
    </div>

    <!-- PC 摘要条（内容类列表：无 pc-avatar） -->
    <el-card v-if="!isCompact" class="filters pc-filters poster-summary-card" shadow="never">
      <div class="pc-filters-head" style="margin-bottom: 0">
        <div class="pc-filters-head-main">
          <span class="pc-filters-title">海报作品</span>
        </div>
        <div class="pc-list-summary">
          <span class="pc-list-summary__label">生成海报</span>
          <span class="pc-list-summary__count">
            共 <strong>{{ rows.length }}</strong> 条
          </span>
          <span v-if="selectedCount" class="pc-list-summary__sel">
            已选 <strong>{{ selectedCount }}</strong>
          </span>
        </div>
      </div>
    </el-card>

    <!-- Desktop table -->
    <template v-if="!isCompact && viewMode === 'table'">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <div v-if="selectedCount" class="pc-selection-bar">
          <span>
            已选择 <strong>{{ selectedCount }}</strong> 张海报
          </span>
          <div class="pc-selection-actions">
            <el-button size="small" type="danger" plain :loading="bulkLoading" @click="onBulkDelete">
              批量删除
            </el-button>
          </div>
        </div>
        <div class="table-scroll">
          <el-table
            :data="pagedRows"
            stripe
            class="pc-poster-table"
            :header-cell-style="{
              background: '#f5f0e6',
              color: '#44403c',
              fontWeight: '600',
              borderBottomColor: '#e8e0d0',
            }"
            empty-text="暂无海报"
            @selection-change="onSelectionChange"
          >
            <el-table-column type="selection" width="48" />
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-title-text">{{ row.title || `海报 #${row.id}` }}</span>
              </template>
            </el-table-column>
            <el-table-column label="模式" width="120">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" round type="info">
                  {{ posterModeLabel(row.mode) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="file_path" label="文件" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-muted">{{ row.file_path || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="download(row)">下载</el-button>
                  <el-button link type="danger" @click="onDelete(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="!rows.length && !loading" class="pc-table-empty">暂无海报，可生成或手动添加</div>
      </el-card>
    </template>

    <!-- Desktop image grid -->
    <template v-if="!isCompact && viewMode === 'grid'">
      <div v-loading="loading || previewLoading" class="poster-grid">
        <div v-if="!rows.length && !loading" class="grid-empty">暂无海报</div>
        <div
          v-for="row in pagedRows"
          :key="row.id"
          class="poster-card"
          :class="{ 'is-selected': isSelected(row.id) }"
        >
          <div class="poster-check">
            <el-checkbox
              :model-value="isSelected(row.id)"
              @update:model-value="(v: boolean | string | number) => toggleCardSelect(row.id, v)"
              @click.stop
            />
          </div>
          <div class="poster-thumb">
            <el-image
              v-if="previewMap[row.id]"
              :src="previewMap[row.id]"
              fit="contain"
              class="thumb-img"
              lazy
              :preview-src-list="previewSrcList"
              :initial-index="previewSrcList.indexOf(previewMap[row.id])"
              preview-teleported
            />
            <div v-else class="thumb-placeholder" :class="{ 'is-missing': failedPreviewIds[row.id] }">
              {{ thumbLabel(row) }}
            </div>
          </div>
          <div class="poster-meta">
            <div class="poster-title" :title="row.title || `海报 #${row.id}`">
              {{ row.title || `海报 #${row.id}` }}
            </div>
            <el-tag size="small" type="info">{{ posterModeLabel(row.mode) }}</el-tag>
          </div>
          <div class="poster-actions">
            <el-button type="primary" size="small" @click="download(row)">下载</el-button>
            <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
          </div>
        </div>
      </div>
    </template>

    <div v-if="!isCompact && rows.length" class="pager-bar pc-pager">
      <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="PAGE_SIZES"
        :total="rows.length"
        :pager-count="5"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="onPageChange"
        @size-change="onPageSizeChange"
      />
      <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
    </div>
  </div>
</template>

<style scoped>
.upload-form {
  margin-top: 4px;
  width: 100%;
}

.upload-form :deep(.el-form-item) {
  width: 100%;
  margin-bottom: 18px;
}

.upload-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

/* 表单项内容区占满弹窗 body 宽度 */
.upload-form :deep(.el-form-item__content),
.upload-form-item :deep(.el-form-item__content) {
  width: 100% !important;
  max-width: 100%;
  display: block;
  line-height: normal;
}

.upload-zone {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
}

.upload-zone.is-error .upload-preview-box,
.upload-zone.is-error :deep(.el-upload-dragger) {
  border-color: var(--el-color-danger);
}

.upload-full {
  display: block;
  width: 100%;
  max-width: 100%;
}

.upload-full :deep(.el-upload),
.upload-full :deep(.el-upload-dragger) {
  box-sizing: border-box;
  width: 100% !important;
  max-width: 100%;
}

.upload-full :deep(.el-upload-dragger) {
  height: 200px;
  min-height: 200px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #faf6ef;
  border: 1.5px dashed var(--oc-border, #e8e0d0);
  border-radius: 12px;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.upload-full :deep(.el-upload-dragger:hover) {
  border-color: var(--oc-primary, #a16207);
  background: #f5efe3;
}

.upload-icon {
  font-size: 42px;
  color: #c4b5a0;
  margin-bottom: 10px;
}

.upload-text {
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  line-height: 1.5;
  text-align: center;
}

.upload-text em {
  color: var(--oc-primary, #a16207);
  font-style: normal;
  font-weight: 600;
}

.upload-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  text-align: center;
}

/* 预览：固定高度 + 裁剪，二维码等大图不会撑破弹窗 */
.upload-preview-box {
  box-sizing: border-box;
  position: relative;
  width: 100%;
  max-width: 100%;
  height: 240px;
  border: 1.5px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: #f5f0e6;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-preview-img {
  display: block;
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  object-position: center;
}

.upload-preview-actions {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 10px;
  display: flex;
  justify-content: center;
  background: linear-gradient(transparent, rgba(41, 37, 36, 0.55));
}

.upload-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/* dialog 传送到 body，用 :global 限制内容宽度，防止预览溢出 */
:global(.upload-poster-dialog.el-dialog) {
  max-width: calc(100vw - 32px);
}

:global(.upload-poster-dialog .el-dialog__body) {
  box-sizing: border-box;
  overflow-x: hidden;
  max-width: 100%;
}

.poster-toolbar {
  gap: 12px;
  padding-bottom: 4px;
}

.toolbar-right {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex: 0 1 auto;
}

/* 视图切换：米金分段控件 */
.view-switch {
  display: inline-flex;
  align-items: stretch;
  padding: 3px;
  background: #f3eee4;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
  box-shadow: inset 0 1px 2px rgba(41, 37, 36, 0.04);
}

.view-switch__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 76px;
  height: 30px;
  padding: 0 12px;
  margin: 0;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}

.view-switch__btn:hover {
  color: var(--oc-ink, #44403c);
  background: rgba(255, 253, 248, 0.7);
}

.view-switch__btn.is-active {
  background: #fffdf8;
  color: var(--oc-primary, #a16207);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(41, 37, 36, 0.1);
}

.view-switch__btn .el-icon {
  font-size: 15px;
}

.toolbar-sep {
  width: 1px;
  height: 22px;
  margin: 0 4px;
  background: var(--oc-border, #e8e0d0);
  flex-shrink: 0;
}

.toolbar-btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 9px;
  font-weight: 500;
}

.toolbar-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.toolbar-btn.is-disabled,
.toolbar-btn:disabled {
  opacity: 0.45;
}

/* 未选中时弱化删除；有选中时更醒目 */
.toolbar-btn.is-danger-ready {
  border-color: #f3c1c1;
  background: #fff7f7;
  color: #c45656;
}

.toolbar-btn.is-danger-ready:hover {
  border-color: #e89a9a;
  background: #ffefef;
  color: #b33b3b;
}

.toolbar-btn--primary {
  min-width: 108px;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.22);
}

.toolbar-btn--primary:hover {
  box-shadow: 0 3px 10px rgba(161, 98, 7, 0.28);
}

@media (max-width: 991px) {
  .poster-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .poster-toolbar :deep(.el-page-header) {
    flex: 0 0 auto;
  }

  .toolbar-right {
    width: 100%;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  /* 删除占满一行；手动添加 + 生成海报并排 */
  .toolbar-right > .el-button:first-of-type {
    grid-column: 1 / -1;
  }

  .toolbar-btn {
    width: 100%;
    margin: 0 !important;
    justify-content: center;
  }

  .toolbar-btn :deep(span) {
    justify-content: center;
  }

  .toolbar-sep,
  .view-switch {
    display: none;
  }
}

@media (max-width: 720px) {
  .toolbar-right {
    grid-template-columns: 1fr 1fr;
  }
}

.poster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  min-height: 120px;
  margin-top: 14px;
}

.poster-summary-card {
  margin-bottom: 0;
}

.pc-poster-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee !important;
}

.grid-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--oc-muted, #78716c);
  padding: 48px 12px;
  background: var(--oc-card, #fffdf8);
  border: 1px dashed var(--oc-border, #e8e0d0);
  border-radius: 12px;
}

.poster-card {
  position: relative;
  background: var(--oc-card, #fffdf8);
  /* 固定 2px，选中只改颜色，避免 box-shadow 描边取消后底部残留细线 */
  border: 2px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  box-shadow: none;
  outline: none;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.poster-card.is-selected {
  border-color: var(--oc-primary, #a16207);
  box-shadow: none;
}

/* 多选：透明底 + 灰色圆框；选中填主题色、无对勾；卡片描边见 .is-selected */
.poster-check {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0;
  padding: 0;
  line-height: 1;
  background: transparent;
  border-radius: 50%;
  box-shadow: none;
}

.poster-check :deep(.el-checkbox) {
  height: 20px;
  margin: 0;
}

.poster-check :deep(.el-checkbox__label) {
  display: none;
}

.poster-check :deep(.el-checkbox__inner) {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid rgba(120, 113, 108, 0.85);
  background-color: transparent !important;
  background-image: none !important;
  box-shadow: none;
  transition:
    background-color 0.15s ease,
    border-color 0.15s ease;
}

.poster-check :deep(.el-checkbox__inner:hover) {
  border-color: var(--oc-primary, #a16207);
}

.poster-check :deep(.el-checkbox__input.is-checked .el-checkbox__inner),
.poster-check :deep(.el-checkbox__input.is-indeterminate .el-checkbox__inner) {
  background-color: var(--oc-primary, #a16207) !important;
  border-color: var(--oc-primary, #a16207);
}

/* 选中：白色对勾（圆形框内居中） */
.poster-check :deep(.el-checkbox__inner::after) {
  display: none;
  box-sizing: content-box;
  content: '';
  border: 2px solid #fff;
  border-left: 0;
  border-top: 0;
  height: 8px;
  width: 4px;
  left: 6px;
  top: 2px;
  position: absolute;
  transform: rotate(45deg) scaleY(0);
  transform-origin: center;
  transition: transform 0.12s ease-in;
}

.poster-check :deep(.el-checkbox__input.is-checked .el-checkbox__inner::after) {
  display: block;
  transform: rotate(45deg) scaleY(1);
}

/* 取消勾选后去掉 Element Plus focus 环，避免底部/角落残留线影 */
.poster-check :deep(.el-checkbox__input.is-focus .el-checkbox__inner),
.poster-check :deep(.el-checkbox__input .el-checkbox__inner:hover),
.poster-check :deep(.el-checkbox:focus-within .el-checkbox__inner) {
  box-shadow: none !important;
  outline: none;
}

.poster-thumb {
  /* 固定预览框高度，contain 完整显示不裁切（与 wap 一致） */
  height: 200px;
  aspect-ratio: auto;
  background: #f5f0e6;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb-img {
  width: 100%;
  height: 100%;
  display: block;
}

.thumb-img :deep(.el-image__wrapper) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thumb-img :deep(.el-image__inner),
.thumb-img :deep(img) {
  width: 100%;
  height: 100%;
  max-width: 100%;
  max-height: 100%;
  object-fit: contain !important;
  object-position: center;
}

.thumb-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.thumb-placeholder.is-missing {
  color: #b45309;
  background: #fff7ed;
}

/* ── wap/pad：每行至少 2 张；小屏预览高度封顶，不再无限等比缩小 ── */
.m-card-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 8px;
  padding-bottom: 8px;
}

/* 平板稍宽：仍保持 2 列，间距略大 */
@media (min-width: 600px) and (max-width: 991px) {
  .m-card-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
}

.m-card {
  position: relative;
  min-width: 0;
  background: var(--oc-card, #fffdf8);
  /* 与 PC .poster-card 一致：固定 2px 边框，选中只改颜色 */
  border: 2px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 0;
  overflow: hidden;
  box-shadow: none;
  outline: none;
  transition: border-color 0.15s ease;
}

/* 与 PC .poster-card.is-selected 一致：只改描边色 */
.m-card.is-selected {
  border-color: var(--oc-primary, #a16207);
  box-shadow: none;
}

.m-card-empty {
  grid-column: 1 / -1;
  padding: 36px 16px;
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 14px;
  border-style: dashed;
  box-shadow: none;
}

/* 复用 PC .poster-check 样式；仅微调叠在小卡上的位置 */
.m-poster-check {
  top: 8px;
  left: 8px;
  z-index: 3;
}

/*
 * wap/pad 预览：固定高度画布 + contain 完整显示
 * 不裁切、不随比例乱缩放；竖图/横图都在框内居中，底色留白
 */
.m-preview-wrap {
  box-sizing: border-box;
  width: 100%;
  height: 168px;
  min-height: 168px;
  max-height: 168px;
  margin: 0;
  border-radius: 0;
  overflow: hidden;
  aspect-ratio: auto;
  background: #f3eee4;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (min-width: 600px) and (max-width: 991px) {
  .m-preview-wrap {
    height: 180px;
    min-height: 180px;
    max-height: 180px;
  }
}

.m-preview {
  width: 100%;
  height: 100%;
  display: flex !important;
  align-items: center;
  justify-content: center;
  background: transparent;
}

.m-preview :deep(.el-image__wrapper) {
  width: 100% !important;
  height: 100% !important;
  display: flex !important;
  align-items: center;
  justify-content: center;
}

.m-preview :deep(.el-image__inner),
.m-preview :deep(img) {
  width: auto !important;
  height: auto !important;
  max-width: 100% !important;
  max-height: 100% !important;
  object-fit: contain !important;
  object-position: center center;
  display: block;
}

.m-preview-empty {
  width: 100%;
  height: 100%;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
  aspect-ratio: auto;
  max-height: none;
  padding: 8px;
  text-align: center;
}

.m-card-body {
  padding: 8px 8px 10px;
  background: var(--oc-card, #fffdf8);
}

.m-card-title {
  font-size: 12px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.m-card-meta-row {
  margin-bottom: 8px;
}

.m-mode {
  display: inline-block;
  max-width: 100%;
  padding: 1px 6px;
  border-radius: 999px;
  background: #f3eee4;
  color: var(--oc-muted, #78716c);
  font-size: 10px;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-card-actions {
  display: flex;
  gap: 4px;
  margin: 0;
  padding: 0;
  border-top: none;
}

.m-card-actions .el-button {
  flex: 1;
  margin: 0;
  height: 28px;
  padding: 0 4px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}

.poster-meta {
  padding: 10px 12px 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.poster-title {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.poster-actions {
  padding: 8px 12px 12px;
  display: flex;
  gap: 8px;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */

.scroll-sentinel {
  grid-column: 1 / -1;
  padding: 16px 8px 28px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}
</style>
