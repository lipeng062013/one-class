<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadUserFile,
} from 'element-plus'
import {
  createMaterialApi,
  deleteMaterialApi,
  listMaterialsApi,
  patchMaterialApi,
  uploadMaterialFileApi,
  type Material,
} from '../../api/materials'
import { useAuthStore } from '../../stores/auth'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useListScrollRestore } from '../../composables/useListScrollRestore'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'

const LIST_STATE_KEY = 'oc-material-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isApp } = useBreakpoint()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const loading = ref(false)
const loadingMore = ref(false)
/** PC：当前页；WAP/Pad：已加载累计 */
const rows = ref<Material[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterExpanded = ref(false)
const sentinelRef = ref<HTMLElement | null>(null)
/** 供从详情返回时恢复「已展开条数」 */
const visibleCount = computed(() => rows.value.length)
let scrollObserver: IntersectionObserver | null = null

const filters = reactive({
  status: '',
  q: '',
  grade: '',
  subject: '',
})

const uploadDialog = ref(false)
const uploadFormRef = ref<FormInstance>()
const saving = ref(false)
const fileList = ref<UploadUserFile[]>([])

const uploadForm = reactive({
  title: '',
  grade: '',
  subject: '',
  pain_point: '',
  teacher_action: '',
  next_step: '',
  auth_status: 'authorized',
})

const uploadRules: FormRules = {
  title: [{ required: true, message: '请填写场景标题', trigger: 'blur' }],
  auth_status: [{ required: true, message: '请选择授权状态', trigger: 'change' }],
}

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

function authTagType(auth: string): 'success' | 'warning' | 'info' | 'danger' {
  if (auth === 'authorized') return 'success'
  if (auth === 'pending') return 'warning'
  if (auth === 'denied') return 'danger'
  return 'info'
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.status) n += 1
  if (filters.q.trim()) n += 1
  if (filters.grade.trim()) n += 1
  if (filters.subject.trim()) n += 1
  return n
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value) || 1))
/** PC 表格：服务端当前页 */
const pagedRows = computed(() => rows.value)
/** WAP/Pad 卡片：累计已加载 */
const infiniteRows = computed(() => rows.value)
const hasMoreInfinite = computed(() => rows.value.length < total.value)

const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()
const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('materials', {
  visibleCount,
  enabled: isApp,
  stateStorageKey: LIST_STATE_KEY,
})

function listQuery(pageNum: number, size: number) {
  return {
    page: pageNum,
    page_size: size,
    status: filters.status || undefined,
    grade: filters.grade.trim() || undefined,
    subject: filters.subject.trim() || undefined,
    q: filters.q.trim() || undefined,
  }
}

function goFirstPage() {
  page.value = 1
  saveListState()
  void load()
}

function goLastPage() {
  page.value = totalPages.value
  saveListState()
  void load()
}

function onPageChange() {
  saveListState()
  void load()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
  void load()
}

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY)
    if (!raw) return
    const s = JSON.parse(raw) as {
      filters?: Partial<typeof filters>
      page?: number
      pageSize?: number
    }
    if (s.filters) {
      filters.status = s.filters.status ?? ''
      filters.q = s.filters.q ?? ''
      filters.grade = s.filters.grade ?? ''
      filters.subject = s.filters.subject ?? ''
    }
    if (typeof s.page === 'number' && s.page > 0) page.value = s.page
    if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
      pageSize.value = s.pageSize
    }
  } catch {
    /* ignore */
  }
}

function saveListState() {
  try {
    sessionStorage.setItem(
      LIST_STATE_KEY,
      JSON.stringify({
        filters: { ...filters },
        page: page.value,
        pageSize: pageSize.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

function runQuery() {
  clearSnapshot()
  collapseAll()
  page.value = 1
  filterExpanded.value = false
  saveListState()
  void load({ fromQuery: true })
}

function resetFilters() {
  clearSnapshot()
  collapseAll()
  filters.status = ''
  filters.q = ''
  filters.grade = ''
  filters.subject = ''
  page.value = 1
  filterExpanded.value = false
  saveListState()
  void load({ fromQuery: true })
}

function resetUploadForm() {
  uploadForm.title = ''
  uploadForm.grade = ''
  uploadForm.subject = ''
  uploadForm.pain_point = ''
  uploadForm.teacher_action = ''
  uploadForm.next_step = ''
  uploadForm.auth_status = 'authorized'
  fileList.value = []
}

async function openUpload() {
  // 长表单：WAP/Pad 走独立上传页，避免小弹窗双层滚动
  if (isApp.value) {
    await router.push('/upload')
    return
  }
  resetUploadForm()
  uploadDialog.value = true
  await nextTick()
  uploadFormRef.value?.clearValidate()
}

function goDetail(row: Material) {
  void router.push(`/materials/${row.id}`)
}

function cardSub(row: Material) {
  const parts = [row.grade, row.subject].filter(Boolean)
  const auth = authLabel[row.auth_status] || row.auth_status
  const files = row.files?.length || 0
  parts.push(auth)
  parts.push(`${files} 图`)
  return parts.join(' · ')
}

function formatShortTime(v?: string | null) {
  if (!v) return ''
  try {
    const d = new Date(v)
    if (Number.isNaN(d.getTime())) return ''
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${m}-${day}`
  } catch {
    return ''
  }
}

async function load(opts?: { fromQuery?: boolean; append?: boolean }) {
  const append = !!opts?.append && isApp.value
  const snap = opts?.fromQuery || append ? null : takeSnapshotForLoad(route.path)
  if (opts?.fromQuery) clearSnapshot()

  if (append) loadingMore.value = true
  else loading.value = true
  try {
    if (isApp.value) {
      // 移动端：按 chunk 拉取；append 时 page 已 +1
      if (!append) page.value = 1
      const res = await listMaterialsApi(listQuery(page.value, SCROLL_CHUNK))
      rows.value = append ? [...rows.value, ...res.items] : res.items
      total.value = res.total
      // 从详情返回：补拉到快照条数
      if (!append && snap?.visibleCount != null) {
        const need = Math.max(SCROLL_CHUNK, snap.visibleCount)
        while (rows.value.length < need && rows.value.length < total.value) {
          page.value += 1
          const more = await listMaterialsApi(listQuery(page.value, SCROLL_CHUNK))
          rows.value = [...rows.value, ...more.items]
          total.value = more.total
          if (!more.items.length) break
        }
      }
    } else {
      const res = await listMaterialsApi(listQuery(page.value, pageSize.value))
      rows.value = res.items
      total.value = res.total
      if (page.value > 1 && res.items.length === 0 && res.total > 0) {
        page.value = Math.max(1, Math.ceil(res.total / pageSize.value))
        const again = await listMaterialsApi(listQuery(page.value, pageSize.value))
        rows.value = again.items
        total.value = again.total
      }
    }
    saveListState()
  } finally {
    loading.value = false
    loadingMore.value = false
  }
  if (!append) void finishListEnter({ snap, forceTop: !!opts?.fromQuery })
}

async function loadMore() {
  if (!isApp.value || loadingMore.value || loading.value || !hasMoreInfinite.value) return
  page.value += 1
  await load({ append: true })
}

function setupScrollObserver() {
  teardownScrollObserver()
  if (!isApp.value) return
  const el = sentinelRef.value
  if (!el) return
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) void loadMore()
    },
    { root: null, rootMargin: '160px 0px', threshold: 0 },
  )
  scrollObserver.observe(el)
}

function teardownScrollObserver() {
  scrollObserver?.disconnect()
  scrollObserver = null
}

async function submitUpload() {
  const ok = await uploadFormRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const material = await createMaterialApi({ ...uploadForm })
    for (const item of fileList.value) {
      const raw = item.raw
      if (raw) {
        await uploadMaterialFileApi(material.id, raw as File)
      }
    }
    ElMessage.success('素材已上传')
    uploadDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    saving.value = false
  }
}

async function markUsable(row: Material) {
  await patchMaterialApi(row.id, { status: 'usable', auth_status: 'authorized' })
  ElMessage.success('已标为可用')
  await load()
}

async function onDelete(row: Material) {
  try {
    await ElMessageBox.confirm(`确定删除素材「${row.title}」？`, '删除确认', { type: 'warning' })
    await deleteMaterialApi(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}

watch(isApp, async (compact, wasCompact) => {
  if (compact === wasCompact) return
  page.value = 1
  await load({ fromQuery: true })
  await nextTick()
  setupScrollObserver()
})

watch(sentinelRef, () => {
  if (isApp.value) setupScrollObserver()
})

onMounted(async () => {
  restoreListState()
  await load()
  await nextTick()
  setupScrollObserver()
})

onUnmounted(() => teardownScrollObserver())
</script>

<template>
  <div class="material-page">
    <div class="page-toolbar" :class="{ 'is-compact': isApp }">
      <el-page-header class="is-title-only" content="素材管理" />
      <el-button class="tb-btn tb-btn--primary" type="primary" @click="openUpload">
        <el-icon><Plus /></el-icon>
        上传素材
      </el-button>
    </div>

    <!-- PC 筛选 -->
    <div class="mat-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">教学素材</span>
            <span class="pc-list-summary__count">
              共 <strong>{{ total }}</strong> 条
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
              <el-option v-for="(label, key) in statusLabel" :key="key" :label="label" :value="key" />
            </el-select>
          </el-form-item>
          <el-form-item label="关键词">
            <el-input
              v-model="filters.q"
              clearable
              placeholder="标题 / 痛点"
              style="width: 160px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item label="年级">
            <el-input v-model="filters.grade" clearable placeholder="年级" style="width: 110px" />
          </el-form-item>
          <el-form-item label="科目">
            <el-input v-model="filters.subject" clearable placeholder="科目" style="width: 110px" />
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="runQuery">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <CompactFilterBar
      class="mat-m"
      :active-count="activeFilterCount"
      :total="total"
      label="条素材"
      @open="filterExpanded = true"
    />
    <MobileFilterSheet
      v-model="filterExpanded"
      :active-count="activeFilterCount"
      @apply="runQuery"
      @reset="resetFilters"
    >
      <el-form label-position="top" @submit.prevent="runQuery">
        <el-form-item label="关键词">
          <el-input v-model="filters.q" clearable placeholder="标题 / 痛点" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态">
            <el-option v-for="(label, key) in statusLabel" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="filters.grade" clearable placeholder="全部年级" />
        </el-form-item>
        <el-form-item label="科目">
          <el-input v-model="filters.subject" clearable placeholder="全部科目" />
        </el-form-item>
      </el-form>
    </MobileFilterSheet>

    <!-- 移动卡片（互斥折叠） -->
    <div v-loading="loading" class="mat-m mat-card-list">
      <div v-if="!total && !loading" class="mat-card mat-card--empty">
        <div class="mat-empty-ico" aria-hidden="true">
          <el-icon :size="28"><Picture /></el-icon>
        </div>
        <p class="mat-empty-title">暂无素材</p>
        <p class="mat-empty-desc">上传课堂 / 试听场景，方便后续生成文案</p>
        <el-button type="primary" @click="openUpload">
          <el-icon><Plus /></el-icon>
          上传素材
        </el-button>
      </div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="mat-card"
        :class="{
          'is-expanded': isExpanded(row.id),
          'is-new': row.status === 'new',
          'is-usable': row.status === 'usable',
        }"
      >
        <div class="mat-card__top" @click="toggleCard(row.id, $event)">
          <div class="mat-card__thumb" :class="{ 'has-files': (row.files?.length || 0) > 0 }">
            <el-icon :size="18"><Picture /></el-icon>
            <span v-if="row.files?.length" class="mat-card__thumb-count">{{ row.files.length }}</span>
          </div>
          <div class="mat-card__main">
            <div class="mat-card__title">{{ row.title }}</div>
            <div class="mat-card__sub">{{ cardSub(row) }}</div>
          </div>
          <div class="mat-card__badges">
            <el-tag :type="statusTagType(row.status)" size="small" effect="plain" round>
              {{ statusLabel[row.status] || row.status }}
            </el-tag>
            <span v-if="formatShortTime(row.created_at)" class="mat-card__time">
              {{ formatShortTime(row.created_at) }}
            </span>
          </div>
          <button
            type="button"
            class="m-card-acc-toggle"
            :aria-expanded="isExpanded(row.id)"
            :aria-label="isExpanded(row.id) ? '收起素材详情' : '展开素材详情'"
            @click.stop="toggleForce(row.id)"
          >
            <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(row.id) }">
              <ArrowDown />
            </el-icon>
          </button>
        </div>
        <div v-show="isExpanded(row.id)" class="m-card-acc-body">
          <div class="mat-card__meta">
            <div v-if="row.grade || row.subject" class="mat-meta-item">
              <span class="mat-meta-k">年级科目</span>
              <span class="mat-meta-v">{{ [row.grade, row.subject].filter(Boolean).join(' · ') || '—' }}</span>
            </div>
            <div class="mat-meta-item">
              <span class="mat-meta-k">授权</span>
              <span class="mat-meta-v">
                <el-tag :type="authTagType(row.auth_status)" size="small" effect="plain" round>
                  {{ authLabel[row.auth_status] || row.auth_status }}
                </el-tag>
              </span>
            </div>
            <div class="mat-meta-item">
              <span class="mat-meta-k">图片</span>
              <span class="mat-meta-v">{{ row.files?.length || 0 }} 张</span>
            </div>
            <div v-if="row.pain_point" class="mat-meta-item mat-meta-item--full">
              <span class="mat-meta-k">痛点</span>
              <span class="mat-meta-v mat-meta-v--clip">{{ row.pain_point }}</span>
            </div>
          </div>
          <div class="mat-card__actions">
            <el-button type="primary" size="small" @click="goDetail(row)">查看详情</el-button>
            <el-button
              v-if="!auth.isTeacher && row.status === 'new'"
              size="small"
              type="success"
              plain
              @click="markUsable(row)"
            >
              标为可用
            </el-button>
            <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
          </div>
        </div>
      </div>
      <div ref="sentinelRef" class="list-load-sentinel">
        <ListLoadStatus
          :has-more="hasMoreInfinite"
          :loading="loadingMore"
          :loaded="rows.length"
          :total="total"
          @more="loadMore"
          @retry="loadMore"
        />
      </div>
    </div>

    <!-- PC 表格 -->
    <div class="mat-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <div class="table-scroll">
          <el-table
            :data="pagedRows"
            stripe
            class="pc-mat-table"
            style="width: 100%"
            empty-text="暂无素材"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="title" label="标题" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-title-text">{{ row.title }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="grade" label="年级" width="100">
              <template #default="{ row }">
                <span class="pc-muted">{{ row.grade || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="subject" label="科目" width="100">
              <template #default="{ row }">
                <span class="pc-muted">{{ row.subject || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="授权" width="100">
              <template #default="{ row }">
                <el-tag :type="authTagType(row.auth_status)" size="small" effect="plain" round>
                  {{ authLabel[row.auth_status] || row.auth_status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="92" align="center">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small" effect="plain" round>
                  {{ statusLabel[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="图片" width="72" align="center">
              <template #default="{ row }">
                <span class="pc-mono">{{ row.files?.length || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="router.push(`/materials/${row.id}`)">
                    详情
                  </el-button>
                  <el-button
                    v-if="!auth.isTeacher && row.status === 'new'"
                    link
                    type="success"
                    @click="markUsable(row)"
                  >
                    标为可用
                  </el-button>
                  <el-button link type="danger" @click="onDelete(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="!total && !loading" class="pc-table-empty">暂无素材，可点右上角「上传」</div>
      </el-card>

      <div v-if="total" class="pager-bar pc-pager">
        <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="total"
          :pager-count="5"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
        <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
      </div>
    </div>

    <!-- PC 快捷上传弹窗（WAP/Pad 已跳转 /upload） -->
    <el-dialog
      v-model="uploadDialog"
      title="上传素材"
      width="90%"
      class="mat-upload-dialog"
      align-center
      destroy-on-close
    >
      <el-form
        ref="uploadFormRef"
        class="mat-upload-form"
        :model="uploadForm"
        :rules="uploadRules"
        label-position="top"
      >
        <el-form-item label="场景标题" prop="title">
          <el-input v-model="uploadForm.title" placeholder="例如：课堂进步 / 试听反馈" />
        </el-form-item>
        <div class="mat-upload-row">
          <el-form-item label="年级">
            <el-input v-model="uploadForm.grade" placeholder="如 四年级" />
          </el-form-item>
          <el-form-item label="科目">
            <el-input v-model="uploadForm.subject" placeholder="如 数学" />
          </el-form-item>
        </div>
        <el-form-item label="家长痛点">
          <el-input v-model="uploadForm.pain_point" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="老师处理">
          <el-input v-model="uploadForm.teacher_action" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="下一步行动">
          <el-input v-model="uploadForm.next_step" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="家长授权" prop="auth_status">
          <el-select v-model="uploadForm.auth_status" style="width: 100%">
            <el-option label="已授权可发" value="authorized" />
            <el-option label="待确认" value="pending" />
            <el-option label="已脱敏" value="anonymized" />
            <el-option label="不可用" value="denied" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片（可多选）">
          <el-upload
            v-model:file-list="fileList"
            list-type="picture-card"
            :auto-upload="false"
            accept="image/*"
            multiple
            aria-label="添加素材图片"
          >
            <el-icon><Plus /></el-icon>
            <span class="oc-visually-hidden">添加素材图片</span>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitUpload">提交素材</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.material-page {
  min-width: 0;
}

.mat-pc {
  display: none;
}

.mat-m {
  display: block;
}

@media (min-width: 1200px) {
  .mat-pc {
    display: block;
  }

  .mat-m {
    display: none !important;
  }
}

.page-toolbar.is-compact {
  gap: 10px;
}

.mat-card-list {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 8px;
}

.mat-card {
  padding: 14px;
  border-radius: 14px;
  border: 2px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.mat-card.is-new {
  border-color: rgba(64, 158, 255, 0.28);
}

.mat-card.is-usable {
  border-color: rgba(103, 194, 58, 0.28);
}

.mat-card--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  padding: 36px 18px;
  border-style: dashed;
  border-color: rgba(181, 145, 83, 0.35);
  background: linear-gradient(180deg, #fffefb, #faf6ee);
}

.mat-empty-ico {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--oc-primary, #a16207);
  background: linear-gradient(145deg, #f5e6c8, #e8d5b0);
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.14);
  margin-bottom: 4px;
}

.mat-empty-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
}

.mat-empty-desc {
  margin: 0 0 8px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
  max-width: 16rem;
}

.mat-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

.mat-card__thumb {
  position: relative;
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a8a29e;
  background: linear-gradient(145deg, #f5f0e6, #ebe4d6);
  border: 1px solid rgba(232, 224, 208, 0.95);
}

.mat-card__thumb.has-files {
  color: #fffdf8;
  background: linear-gradient(145deg, #c98718, #a16207);
  border-color: transparent;
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.22);
}

.mat-card__thumb-count {
  position: absolute;
  right: -4px;
  bottom: -4px;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 999px;
  background: #44403c;
  color: #fffdf8;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1.5px solid #fffdf8;
}

.mat-card__main {
  flex: 1;
  min-width: 0;
}

.mat-card__title {
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mat-card__sub {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mat-card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.mat-card__time {
  font-size: 11px;
  color: #a8a29e;
  font-variant-numeric: tabular-nums;
}

.mat-card__meta {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-top: 0;
  padding: 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #faf6ee, #f7f2e9);
  border: 1px solid rgba(232, 224, 208, 0.85);
}

.mat-meta-item {
  display: flex;
  gap: 10px;
  font-size: 13px;
  line-height: 1.45;
  min-width: 0;
  align-items: flex-start;
}

.mat-meta-k {
  flex-shrink: 0;
  min-width: 3.6em;
  color: #a8a29e;
  font-size: 12px;
  font-weight: 550;
  padding-top: 1px;
}

.mat-meta-v {
  min-width: 0;
  color: var(--oc-ink, #44403c);
  word-break: break-word;
}

.mat-meta-v--clip {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 12px;
  line-height: 1.55;
  color: #57534e;
}

.mat-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.mat-card__actions .el-button {
  margin: 0;
  flex: 1 1 calc(33% - 6px);
  min-width: 0;
}

.pc-mat-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee !important;
}

@media (max-width: 1199px) {
  .page-toolbar {
    flex-wrap: wrap;
  }

  .tb-btn--primary {
    width: auto;
    min-height: 40px;
    border-radius: 12px;
    font-weight: 650;
  }
}

@media (min-width: 768px) and (max-width: 1199px) {
  .mat-card-list {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
    gap: 14px;
  }

  .mat-card--empty,
  .list-load-sentinel {
    grid-column: 1 / -1;
  }
}

@media (min-width: 992px) {
  .mat-upload-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 12px;
  }
}
</style>

<!-- dialog 传送到 body，需非 scoped -->
<style>
.mat-upload-dialog.el-dialog {
  max-width: 560px;
  width: min(90vw, 560px);
  border-radius: 16px;
  overflow: hidden;
}

.mat-upload-dialog .el-dialog__header {
  padding: 16px 20px 12px;
  border-bottom: 1px solid rgba(232, 224, 208, 0.9);
  margin-right: 0;
}

.mat-upload-dialog .el-dialog__title {
  font-weight: 700;
  color: #44403c;
}

.mat-upload-dialog .el-dialog__body {
  padding: 16px 20px;
}

.mat-upload-dialog .el-dialog__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(232, 224, 208, 0.9);
}

.mat-upload-form .el-form-item {
  margin-bottom: 14px;
}

.mat-upload-form .el-form-item__label {
  font-weight: 600;
  color: #44403c;
}

.mat-upload-dialog .el-upload--picture-card,
.mat-upload-dialog .el-upload-list--picture-card .el-upload-list__item {
  width: 88px;
  height: 88px;
  border-radius: 12px;
}
</style>
