<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createCopyTemplate,
  createPosterTemplate,
  deleteCopyTemplate,
  deletePosterTemplate,
  listCopyTemplates,
  listPosterTemplates,
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
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'

const LIST_STATE_KEY = 'oc-template-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const DEFAULT_COPY_BODY =
  '痛点：{{pain_point}}\n处理：{{teacher_action}}\n下一步：{{next_step}}'

const DEFAULT_POSTER_LAYOUT = JSON.stringify(
  {
    width: 750,
    height: 1000,
    background: '#176b4d',
    fields: [
      { key: 'title', x: 40, y: 80, font_size: 48, fill: '#ffffff' },
      { key: 'subtitle', x: 40, y: 180, font_size: 28, fill: '#e8f2ed' },
      { key: 'footer', x: 40, y: 900, font_size: 24, fill: '#ffffff' },
    ],
  },
  null,
  2,
)

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
const { isApp } = useBreakpoint()
const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const tab = ref<'copies' | 'posters'>('copies')
const loading = ref(false)
const copies = ref<CopyTemplate[]>([])
const posters = ref<PosterTemplate[]>([])
const page = ref(1)
const pageSize = ref(20)
const filterExpanded = ref(false)

const filters = reactive({
  q: '',
  status: '' as '' | 'active' | 'inactive',
  system: '' as '' | 'system' | 'custom',
})

const copyDialog = ref(false)
const posterDialog = ref(false)
const editingCopyId = ref<number | null>(null)
const editingPosterId = ref<number | null>(null)
const copyFormRef = ref<FormInstance>()
const posterFormRef = ref<FormInstance>()
const saving = ref(false)

const copyForm = reactive({
  name: '',
  scene: 'xhs_script',
  body: DEFAULT_COPY_BODY,
  is_active: true,
})
const posterForm = reactive({
  name: '',
  scene: 'xhs_poster',
  layout_json: DEFAULT_POSTER_LAYOUT,
  is_active: true,
})

const copyDialogTitle = computed(() => (editingCopyId.value ? '编辑文案模板' : '新建文案模板'))
const posterDialogTitle = computed(() =>
  editingPosterId.value ? '编辑海报模板' : '新建海报模板',
)

const copyRules: FormRules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  scene: [{ required: true, message: '请填写场景', trigger: 'blur' }],
  body: [{ required: true, message: '请填写正文模板', trigger: 'blur' }],
}
const posterRules: FormRules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  scene: [{ required: true, message: '请填写场景', trigger: 'blur' }],
  layout_json: [{ required: true, message: '请填写 layout_json', trigger: 'blur' }],
}

function sceneLabel(scene?: string | null) {
  if (!scene) return '—'
  return SCENE_LABELS[scene] || scene
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.q.trim()) n += 1
  if (filters.status) n += 1
  if (filters.system) n += 1
  return n
})

const sourceRows = computed(() => (tab.value === 'copies' ? copies.value : posters.value))

const filtered = computed(() => {
  const q = filters.q.trim().toLowerCase()
  return sourceRows.value.filter((row) => {
    if (filters.status === 'active' && !row.is_active) return false
    if (filters.status === 'inactive' && row.is_active) return false
    if (filters.system === 'system' && !row.is_system) return false
    if (filters.system === 'custom' && row.is_system) return false
    if (!q) return true
    const extra = 'body' in row ? String((row as CopyTemplate).body || '') : String((row as PosterTemplate).layout_json || '')
    const hay = `${row.name} ${row.scene} ${extra}`.toLowerCase()
    return hay.includes(q)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const pagedCopies = computed(() => pagedRows.value as CopyTemplate[])
const pagedPosters = computed(() => pagedRows.value as PosterTemplate[])

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  ensureVisible,
} = useInfiniteScroll(filtered, {
  chunk: SCROLL_CHUNK,
    enabled: isApp,
  sentinelRef,
})

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('templates', {
  visibleCount,
  enabled: isApp,
  stateStorageKey: LIST_STATE_KEY,
})

const infiniteCopies = computed(() => infiniteRows.value as CopyTemplate[])
const infinitePosters = computed(() => infiniteRows.value as PosterTemplate[])

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

function onPageChange() {
  saveListState()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
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
    // 文案/海报 tab：每次进入默认「文案模板」，不恢复历史选中
    if (s.filters) {
      filters.q = s.filters.q ?? ''
      filters.status = s.filters.status ?? ''
      filters.system = s.filters.system ?? ''
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
  resetInfinite()
  clampPage()
  saveListState()
}

function resetFilters() {
  clearSnapshot()
  collapseAll()
  filters.q = ''
  filters.status = ''
  filters.system = ''
  page.value = 1
  filterExpanded.value = false
  resetInfinite()
  saveListState()
}

function onTabChange() {
  page.value = 1
  collapseAll()
  resetInfinite()
  saveListState()
}

function insertCopyParam(key: string) {
  const token = copyParamPlaceholder(key)
  const el = document.querySelector('.copy-body-input textarea') as HTMLTextAreaElement | null
  if (el && typeof el.selectionStart === 'number') {
    const start = el.selectionStart
    const end = el.selectionEnd
    const before = copyForm.body.slice(0, start)
    const after = copyForm.body.slice(end)
    copyForm.body = `${before}${token}${after}`
    nextTick(() => {
      el.focus()
      const pos = start + token.length
      el.setSelectionRange(pos, pos)
    })
    return
  }
  copyForm.body = `${copyForm.body || ''}${token}`
}

function resetCopyForm() {
  copyForm.name = ''
  copyForm.scene = 'xhs_script'
  copyForm.body = DEFAULT_COPY_BODY
  copyForm.is_active = true
}

function resetPosterForm() {
  posterForm.name = ''
  posterForm.scene = 'xhs_poster'
  posterForm.layout_json = DEFAULT_POSTER_LAYOUT
  posterForm.is_active = true
}

async function clearFormValidate(formRef: FormInstance | undefined) {
  await nextTick()
  formRef?.clearValidate()
}

function openCreateCopy() {
  editingCopyId.value = null
  resetCopyForm()
  copyDialog.value = true
  clearFormValidate(copyFormRef.value)
}

function openEditCopy(row: CopyTemplate) {
  editingCopyId.value = row.id
  copyForm.name = row.name
  copyForm.scene = row.scene
  copyForm.body = row.body
  copyForm.is_active = row.is_active
  copyDialog.value = true
  clearFormValidate(copyFormRef.value)
}

function openCreatePoster() {
  editingPosterId.value = null
  resetPosterForm()
  posterDialog.value = true
  clearFormValidate(posterFormRef.value)
}

function openEditPoster(row: PosterTemplate) {
  editingPosterId.value = row.id
  posterForm.name = row.name
  posterForm.scene = row.scene
  try {
    posterForm.layout_json = JSON.stringify(JSON.parse(row.layout_json || '{}'), null, 2)
  } catch {
    posterForm.layout_json = row.layout_json || '{}'
  }
  posterForm.is_active = row.is_active
  posterDialog.value = true
  clearFormValidate(posterFormRef.value)
}

function openCreate() {
  if (tab.value === 'copies') openCreateCopy()
  else openCreatePoster()
}

function goCopyDetail(row: CopyTemplate) {
  router.push(`/templates/copies/${row.id}`)
}

function goPosterDetail(row: PosterTemplate) {
  router.push(`/templates/posters/${row.id}`)
}

async function load(opts?: { fromQuery?: boolean }) {
  const snap = opts?.fromQuery ? null : takeSnapshotForLoad(route.path)
  if (opts?.fromQuery) clearSnapshot()

  loading.value = true
  try {
    ;[copies.value, posters.value] = await Promise.all([listCopyTemplates(), listPosterTemplates()])
    if (snap?.visibleCount != null && isApp.value) {
      ensureVisible(snap.visibleCount)
    } else {
      resetInfinite()
    }
    clampPage()
  } finally {
    loading.value = false
  }
  void finishListEnter({ snap, forceTop: !!opts?.fromQuery })
}

async function submitCopy() {
  const ok = await copyFormRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const payload = {
      name: copyForm.name.trim(),
      scene: copyForm.scene.trim(),
      body: copyForm.body,
      is_active: copyForm.is_active,
    }
    if (editingCopyId.value) {
      await updateCopyTemplate(editingCopyId.value, payload)
      ElMessage.success('文案模板已更新')
    } else {
      await createCopyTemplate(payload)
      ElMessage.success('文案模板已创建')
    }
    copyDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function submitPoster() {
  const ok = await posterFormRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    const parsed = JSON.parse(posterForm.layout_json)
    const payload = {
      name: posterForm.name.trim(),
      scene: posterForm.scene.trim(),
      layout_json: JSON.stringify(parsed),
      is_active: posterForm.is_active,
    }
    if (editingPosterId.value) {
      await updatePosterTemplate(editingPosterId.value, payload)
      ElMessage.success('海报模板已更新')
    } else {
      await createPosterTemplate(payload)
      ElMessage.success('海报模板已创建')
    }
    posterDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败（请检查 JSON 格式）')
  } finally {
    saving.value = false
  }
}

async function removeCopy(row: CopyTemplate) {
  if (row.is_system) {
    ElMessage.warning('系统模板不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`删除文案模板「${row.name}」？`, '确认', { type: 'warning' })
    await deleteCopyTemplate(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}

async function removePoster(row: PosterTemplate) {
  if (row.is_system) {
    ElMessage.warning('系统模板不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`删除海报模板「${row.name}」？`, '确认', { type: 'warning' })
    await deletePosterTemplate(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}

watch(tab, onTabChange)
watch(filtered, () => clampPage())
watch(pageSize, () => clampPage())

onMounted(() => {
  restoreListState()
  // 每次进入固定默认「文案模板」，不记忆上次 tab
  tab.value = 'copies'
  load()
})
</script>

<template>
  <div class="tpl-page">
    <div class="page-toolbar" :class="{ 'is-compact': isApp }">
      <el-page-header class="is-title-only" content="模板管理" />
      <el-button class="tb-btn tb-btn--primary" type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        {{ tab === 'copies' ? '新建文案模板' : '新建海报模板' }}
      </el-button>
    </div>

    <div class="tpl-tabs">
      <button
        type="button"
        class="tpl-tab"
        :class="{ 'is-active': tab === 'copies' }"
        @click="tab = 'copies'"
      >
        文案模板
      </button>
      <button
        type="button"
        class="tpl-tab"
        :class="{ 'is-active': tab === 'posters' }"
        @click="tab = 'posters'"
      >
        海报模板
      </button>
    </div>

    <div class="tpl-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">
              {{ tab === 'copies' ? '文案模板' : '海报模板' }}
            </span>
            <span class="pc-list-summary__count">
              共 <strong>{{ filtered.length }}</strong> 条
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="关键词">
            <el-input
              v-model="filters.q"
              clearable
              placeholder="名称 / 场景"
              style="width: 160px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.status" clearable placeholder="全部" style="width: 110px">
              <el-option label="启用" value="active" />
              <el-option label="停用" value="inactive" />
            </el-select>
          </el-form-item>
          <el-form-item label="类型">
            <el-select v-model="filters.system" clearable placeholder="全部" style="width: 110px">
              <el-option label="系统" value="system" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="runQuery">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <CompactFilterBar class="tpl-m" :active-count="activeFilterCount" :total="filtered.length" label="条模板" @open="filterExpanded = true" />
    <MobileFilterSheet v-model="filterExpanded" :active-count="activeFilterCount" @apply="runQuery" @reset="resetFilters">
      <el-form label-position="top" @submit.prevent="runQuery">
        <el-form-item label="关键词"><el-input v-model="filters.q" clearable placeholder="名称 / 场景" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="filters.status" clearable placeholder="全部状态"><el-option label="启用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item>
        <el-form-item label="类型"><el-select v-model="filters.system" clearable placeholder="全部类型"><el-option label="系统" value="system" /><el-option label="自定义" value="custom" /></el-select></el-form-item>
      </el-form>
    </MobileFilterSheet>

    <!-- 移动卡片（互斥折叠） -->
    <div v-loading="loading" class="tpl-m tpl-card-list">
      <div v-if="!filtered.length && !loading" class="tpl-card tpl-card--empty">暂无模板</div>
      <template v-if="tab === 'copies'">
        <div
          v-for="row in infiniteCopies"
          :key="`c-${row.id}`"
          class="tpl-card"
          :class="{ 'is-expanded': isExpanded(`c-${row.id}`) }"
        >
          <div class="tpl-card__top" @click="toggleCard(`c-${row.id}`, $event)">
            <span class="tpl-card__name">{{ row.name }}</span>
            <div class="tpl-card__badges">
              <el-tag :type="row.is_system ? 'warning' : 'info'" size="small" effect="plain" round>
                {{ row.is_system ? '系统' : '自定义' }}
              </el-tag>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </div>
            <button
              type="button"
              class="m-card-acc-toggle"
              :aria-expanded="isExpanded(`c-${row.id}`)"
              :aria-label="isExpanded(`c-${row.id}`) ? '收起文案模板详情' : '展开文案模板详情'"
              @click.stop="toggleForce(`c-${row.id}`)"
            >
              <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(`c-${row.id}`) }">
                <ArrowDown />
              </el-icon>
            </button>
          </div>
          <div v-show="isExpanded(`c-${row.id}`)" class="m-card-acc-body">
            <div class="tpl-card__meta">
              <span><span class="k">场景</span>{{ sceneLabel(row.scene) }}</span>
            </div>
            <p class="tpl-card__body">{{ row.body }}</p>
            <div class="tpl-card__actions">
              <el-button size="small" type="primary" @click="goCopyDetail(row)">详情</el-button>
              <el-button size="small" @click="openEditCopy(row)">编辑</el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="row.is_system"
                @click="removeCopy(row)"
              >
                删除
              </el-button>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <div
          v-for="row in infinitePosters"
          :key="`p-${row.id}`"
          class="tpl-card"
          :class="{ 'is-expanded': isExpanded(`p-${row.id}`) }"
        >
          <div class="tpl-card__top" @click="toggleCard(`p-${row.id}`, $event)">
            <span class="tpl-card__name">{{ row.name }}</span>
            <div class="tpl-card__badges">
              <el-tag :type="row.is_system ? 'warning' : 'info'" size="small" effect="plain" round>
                {{ row.is_system ? '系统' : '自定义' }}
              </el-tag>
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </div>
            <button
              type="button"
              class="m-card-acc-toggle"
              :aria-expanded="isExpanded(`p-${row.id}`)"
              :aria-label="isExpanded(`p-${row.id}`) ? '收起海报模板详情' : '展开海报模板详情'"
              @click.stop="toggleForce(`p-${row.id}`)"
            >
              <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(`p-${row.id}`) }">
                <ArrowDown />
              </el-icon>
            </button>
          </div>
          <div v-show="isExpanded(`p-${row.id}`)" class="m-card-acc-body">
            <div class="tpl-card__meta">
              <span><span class="k">场景</span>{{ sceneLabel(row.scene) }}</span>
            </div>
            <div class="tpl-card__actions">
              <el-button size="small" type="primary" @click="goPosterDetail(row)">详情</el-button>
              <el-button size="small" @click="openEditPoster(row)">编辑</el-button>
              <el-button
                size="small"
                type="danger"
                plain
                :disabled="row.is_system"
                @click="removePoster(row)"
              >
                删除
              </el-button>
            </div>
          </div>
        </div>
      </template>
      <div v-if="filtered.length" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ filtered.length }} 条</span>
      </div>
    </div>

    <!-- PC 表格 -->
    <div class="tpl-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <div class="table-scroll">
          <el-table
            v-if="tab === 'copies'"
            :data="pagedCopies"
            stripe
            empty-text="暂无文案模板"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <button type="button" class="pc-title-link" @click="goCopyDetail(row)">
                  {{ row.name }}
                </button>
              </template>
            </el-table-column>
            <el-table-column label="场景" width="130">
              <template #default="{ row }">
                <span class="pc-muted">{{ sceneLabel(row.scene) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="96" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_system ? 'warning' : 'info'" size="small" effect="plain" round>
                  {{ row.is_system ? '系统' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="body" label="正文" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="180" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="goCopyDetail(row)">详情</el-button>
                  <el-button link type="primary" @click="openEditCopy(row)">编辑</el-button>
                  <el-button
                    link
                    type="danger"
                    :disabled="row.is_system"
                    @click="removeCopy(row)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>

          <el-table
            v-else
            :data="pagedPosters"
            stripe
            empty-text="暂无海报模板"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <button type="button" class="pc-title-link" @click="goPosterDetail(row)">
                  {{ row.name }}
                </button>
              </template>
            </el-table-column>
            <el-table-column label="场景" width="130">
              <template #default="{ row }">
                <span class="pc-muted">{{ sceneLabel(row.scene) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="类型" width="96" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_system ? 'warning' : 'info'" size="small" effect="plain" round>
                  {{ row.is_system ? '系统' : '自定义' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="layout_json"
              label="版式 JSON"
              min-width="220"
              show-overflow-tooltip
            />
            <el-table-column label="操作" width="180" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="goPosterDetail(row)">详情</el-button>
                  <el-button link type="primary" @click="openEditPoster(row)">编辑</el-button>
                  <el-button
                    link
                    type="danger"
                    :disabled="row.is_system"
                    @click="removePoster(row)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <div v-if="!filtered.length && !loading" class="pc-table-empty">暂无模板，可点右上角新建</div>
      </el-card>

      <div v-if="filtered.length" class="pager-bar pc-pager">
        <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="filtered.length"
          :pager-count="5"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
        <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
      </div>
    </div>

    <el-dialog
      v-model="copyDialog"
      :title="copyDialogTitle"
      width="90%"
      style="max-width: 640px"
      destroy-on-close
    >
      <el-form ref="copyFormRef" :model="copyForm" :rules="copyRules" label-position="top">
        <el-form-item label="名称" prop="name">
          <el-input v-model="copyForm.name" placeholder="例如：小红书种草话术" />
        </el-form-item>
        <el-form-item label="场景" prop="scene">
          <el-input v-model="copyForm.scene" placeholder="例如：xhs_script" />
          <p class="field-hint">场景编码，用于分类；生成文案时按模板选择，不自动按场景过滤</p>
        </el-form-item>
        <el-form-item :label="'正文（支持 {{变量}}）'" prop="body">
          <el-input
            v-model="copyForm.body"
            class="copy-body-input"
            type="textarea"
            :rows="8"
            placeholder="在正文中写入 {{pain_point}} 等变量，生成时会替换为实际内容"
          />
          <div class="param-panel">
            <div class="param-panel-title">可用参数（点击插入）</div>
            <div class="param-list">
              <button
                v-for="p in COPY_TEMPLATE_PARAMS"
                :key="p.key"
                type="button"
                class="param-chip"
                :title="p.source"
                @click="insertCopyParam(p.key)"
              >
                <code>{{ copyParamPlaceholder(p.key) }}</code>
                <span class="param-label">{{ p.label }}</span>
              </button>
            </div>
            <ul class="param-sources">
              <li v-for="p in COPY_TEMPLATE_PARAMS" :key="`src-${p.key}`">
                <code>{{ copyParamPlaceholder(p.key) }}</code>
                <span class="param-name">{{ p.label }}</span>
                <span class="param-source">{{ p.source }}</span>
              </li>
            </ul>
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="copyForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="copyDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCopy">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="posterDialog"
      :title="posterDialogTitle"
      width="90%"
      style="max-width: 640px"
      destroy-on-close
    >
      <el-form ref="posterFormRef" :model="posterForm" :rules="posterRules" label-position="top">
        <el-form-item label="名称" prop="name">
          <el-input v-model="posterForm.name" placeholder="例如：小红书竖版海报" />
        </el-form-item>
        <el-form-item label="场景" prop="scene">
          <el-input v-model="posterForm.scene" placeholder="例如：xhs_poster" />
          <p class="field-hint">场景编码，用于分类；生成海报时按模板选择</p>
        </el-form-item>
        <el-form-item label="版式 layout_json" prop="layout_json">
          <el-input
            v-model="posterForm.layout_json"
            type="textarea"
            :rows="10"
            placeholder='{"width":750,"height":1000,"background":"#176b4d","fields":[...]}'
          />
          <div class="param-panel">
            <div class="param-panel-title">画布参数</div>
            <ul class="param-sources">
              <li v-for="p in POSTER_LAYOUT_META" :key="p.key">
                <code>{{ p.key }}</code>
                <span class="param-name">{{ p.label }}</span>
                <span class="param-source">{{ p.source }}</span>
              </li>
            </ul>
            <div class="param-panel-title" style="margin-top: 12px">fields[] 字段属性</div>
            <ul class="param-sources">
              <li v-for="p in POSTER_FIELD_META" :key="p.key">
                <code>{{ p.key }}</code>
                <span class="param-name">{{ p.label }}</span>
                <span class="param-source">{{ p.source }}</span>
              </li>
            </ul>
            <p class="field-hint" style="margin-top: 10px">
              使用处：生成海报页的「标题 / 副标题 / 页脚」会写入对应
              <code>fields.key</code>（默认 title、subtitle、footer）
            </p>
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="posterForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="posterDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPoster">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tpl-page {
  min-width: 0;
}

.tpl-pc {
  display: none;
}

.tpl-m {
  display: block;
}

@media (min-width: 1200px) {
  .tpl-pc {
    display: block;
  }

  .tpl-m {
    display: none !important;
  }
}

.tpl-tabs {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  margin-bottom: 4px;
}

.tpl-tab {
  height: 34px;
  padding: 0 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 999px;
  background: #fffdf8;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.tpl-tab.is-active {
  background: var(--oc-primary, #a16207);
  border-color: var(--oc-primary, #a16207);
  color: #fff;
  font-weight: 600;
}

.m-filter {
  position: relative;
  z-index: 20;
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
}

.m-filter-search {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 4px 0 12px;
  background: #f5f0e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
}

.m-filter-search__icon {
  color: #a8a29e;
  flex-shrink: 0;
}

.m-filter-search__input {
  flex: 1;
  min-width: 0;
  height: 100%;
  margin: 0 8px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
}

.m-filter-search__btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.m-filter-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.m-filter-select {
  flex: 1 1 0;
  min-width: 0;
}

.m-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 8px;
  background: #faf6ef !important;
  box-shadow: 0 0 0 1px var(--oc-border, #e8e0d0) inset !important;
}

.m-filter-more {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fffdf8;
  font-size: 12px;
  cursor: pointer;
}

.m-filter-more.is-active {
  border-color: #d4b483;
  color: var(--oc-primary, #a16207);
  background: #faf3e6;
}

.m-filter-more .el-icon.is-open {
  transform: rotate(180deg);
}

.m-filter-panel {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
}

.m-filter-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.m-filter-link {
  border: none;
  background: transparent;
  color: var(--oc-muted, #78716c);
  cursor: pointer;
}

.m-filter-apply {
  height: 32px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

.tpl-card-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tpl-card {
  padding: 14px;
  border-radius: 14px;
  border: 2px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.tpl-card--empty {
  text-align: center;
  color: var(--oc-muted, #78716c);
  padding: 28px;
  border-style: dashed;
}

.tpl-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

.tpl-card__name {
  flex: 1;
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  word-break: break-word;
  text-align: left;
}

.tpl-card__name--link {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font: inherit;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.tpl-card__name--link:hover {
  color: var(--oc-primary, #a16207);
}

.tpl-card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.tpl-card__meta {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #faf6ee;
  font-size: 13px;
  cursor: pointer;
}

.tpl-card__meta .k {
  color: var(--oc-muted, #78716c);
  margin-right: 4px;
  font-size: 12px;
}

.tpl-card__body {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  line-height: 1.5;
  max-height: 4.5em;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
  cursor: pointer;
}

.tpl-card__actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.tpl-card__actions .el-button {
  margin: 0;
  width: 100%;
}

.pc-title-link {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  text-align: left;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pc-title-link:hover {
  color: var(--oc-primary, #a16207);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.pc-ops {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  flex-wrap: wrap;
}

.scroll-sentinel {
  padding: 12px 0 4px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.param-panel {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #f5f0e6;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.param-panel-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  margin-bottom: 8px;
}

.param-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.param-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 6px;
  background: #fffdf8;
  cursor: pointer;
  font-size: 12px;
  color: var(--oc-ink, #44403c);
}

.param-chip:hover {
  border-color: var(--oc-primary, #a16207);
  color: var(--oc-primary, #a16207);
}

.param-chip code {
  font-size: 11px;
  color: var(--oc-primary, #a16207);
}

.param-label {
  color: var(--oc-muted, #78716c);
}

.param-sources {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-sources li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 8px;
  font-size: 12px;
}

.param-sources code {
  flex-shrink: 0;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(161, 98, 7, 0.08);
  color: var(--oc-primary, #a16207);
  font-size: 11px;
}

.param-name {
  flex-shrink: 0;
  color: var(--oc-ink, #44403c);
  font-weight: 500;
}

.param-source {
  color: var(--oc-muted, #78716c);
  flex: 1 1 160px;
}

@media (max-width: 1199px) {
  .tb-btn--primary {
    width: auto;
    height: 40px;
  }
}
</style>

<style>
.tpl-m-select-popper {
  z-index: 5000 !important;
}
</style>
