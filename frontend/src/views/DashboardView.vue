<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getSummary, type DashboardSummary } from '../api/dashboard'
import { getIntegrationsStatus, type IntegrationsStatus } from '../api/system'
import { listMaterialsApi, type Material } from '../api/materials'
import { useAuthStore } from '../stores/auth'
import TodayTodos from '../components/TodayTodos.vue'
import AppSheet from '../components/AppSheet.vue'
import { useBreakpoint } from '../composables/useBreakpoint'
import {
  defaultSelectedIds,
  filterCatalogForRole,
  groupCatalog,
  loadQuickLinkIds,
  quickLinksStorageKey,
  resolveQuickLinks,
  saveQuickLinkIds,
  type QuickLinkDef,
} from '../constants/quickLinks'

const auth = useAuthStore()
const router = useRouter()
const { isMobile, isApp } = useBreakpoint()
const summary = ref<DashboardSummary | null>(null)
const integrations = ref<IntegrationsStatus | null>(null)
const pending = ref<Material[]>([])
const loading = ref(false)

const roleLabel: Record<string, string> = {
  admin: '负责人',
  operator: '运营',
  teacher: '老师',
  cr: 'CR（班主任，学管师）',
  academic_manager: 'CR（班主任，学管师）',
}

const displayName = computed(
  () => auth.user?.display_name || auth.user?.username || '同事',
)

const roleText = computed(() => roleLabel[auth.user?.role || ''] || auth.user?.role || '')

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayLabel = computed(() => {
  const d = new Date()
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 · 周${week}`
})

const stats = computed(() => {
  const all = [
    {
      key: 'materials',
      title: '待处理素材',
      value: summary.value?.materials_new ?? 0,
      hint: '进入素材库处理',
      path: '/materials',
      icon: 'Picture',
      tone: 'amber',
      permission: 'materials.read',
    },
    {
      key: 'leads',
      title: '今日待跟进',
      value: summary.value?.leads_follow_today ?? 0,
      hint: '查看线索跟进',
      path: '/leads',
      icon: 'Phone',
      tone: 'rose',
      permission: 'leads.read',
    },
    {
      key: 'copies',
      title: '已生成文案',
      value: summary.value?.recent_copies ?? 0,
      hint: '查看文案列表',
      path: '/copies',
      icon: 'Document',
      tone: 'sage',
      permission: 'copies.use',
    },
  ]
  return all.filter((s) => auth.hasPermission(s.permission))
})

/** 顶栏是否展示 AI 侧栏（无权限时欢迎区拉满） */
const showAiPanel = computed(
  () => !auth.isTeacher && auth.hasPermission('system.read') && Boolean(integrations.value),
)

/** 是否展示待处理素材（无权限时工作区两列拉伸，不留空位） */
const showPendingPanel = computed(
  () => !auth.isTeacher && auth.hasPermission('materials.read'),
)

/**
 * 主工作区布局：
 * - teacher：待办 | 快捷
 * - ops-full：待办 + 快捷 + 素材
 * - ops-simple：待办 + 快捷（无素材权限时两列铺满）
 */
const workLayout = computed(() => {
  if (auth.isTeacher) return 'teacher'
  return showPendingPanel.value ? 'ops-full' : 'ops-simple'
})

const catalog = computed(() =>
  filterCatalogForRole({
    isAdmin: auth.isAdmin,
    isTeacher: auth.isTeacher,
    hasPermission: (code) => auth.hasPermission(code),
  }),
)

const storageKey = computed(() =>
  quickLinksStorageKey(auth.user?.id, auth.user?.role || ''),
)

const selectedIds = ref<string[]>([])

function reloadQuickSelection() {
  selectedIds.value = loadQuickLinkIds(storageKey.value, catalog.value).slice(0, MAX_QUICK)
}

const quickLinks = computed((): QuickLinkDef[] =>
  resolveQuickLinks(selectedIds.value, catalog.value),
)

const compactQuickLinks = computed(() =>
  quickLinks.value.slice(0, isMobile.value ? 8 : 12),
)

/** 自定义弹窗：图标勾选 + 拖拽排序（无长列表） */
const customVisible = ref(false)
const draftIds = ref<string[]>([])
const MAX_QUICK = 12

const draftSelected = computed(() => resolveQuickLinks(draftIds.value, catalog.value))
const catalogGroups = computed(() => groupCatalog(catalog.value))

/** 正在拖拽的已选 id（PC HTML5 / 触控 pointer 共用） */
const draggingId = ref<string | null>(null)
const dragOverId = ref<string | null>(null)
/** 触控待激活：按下但未超过位移阈值（避免挡弹层滚动） */
const touchPendingId = ref<string | null>(null)
const touchStart = ref<{ x: number; y: number } | null>(null)
const TOUCH_DRAG_PX = 8

function openCustomQuick() {
  draftIds.value = selectedIds.value.slice(0, MAX_QUICK)
  draggingId.value = null
  dragOverId.value = null
  touchPendingId.value = null
  touchStart.value = null
  customVisible.value = true
}

function isDraftSelected(id: string) {
  return draftIds.value.includes(id)
}

function toggleDraft(id: string) {
  const idx = draftIds.value.indexOf(id)
  if (idx >= 0) {
    draftIds.value = draftIds.value.filter((x) => x !== id)
    return
  }
  if (draftIds.value.length >= MAX_QUICK) {
    ElMessage.warning(`最多选择 ${MAX_QUICK} 个快捷入口`)
    return
  }
  draftIds.value = [...draftIds.value, id]
}

function removeDraft(id: string, e?: Event) {
  e?.stopPropagation()
  e?.preventDefault()
  draftIds.value = draftIds.value.filter((x) => x !== id)
  if (draggingId.value === id) {
    draggingId.value = null
    dragOverId.value = null
  }
}

/** 把 fromId 插到 toId 的位置（保持相对顺序） */
function reorderDraft(fromId: string, toId: string) {
  if (fromId === toId) return
  const from = draftIds.value.indexOf(fromId)
  const to = draftIds.value.indexOf(toId)
  if (from < 0 || to < 0) return
  const arr = [...draftIds.value]
  arr.splice(from, 1)
  arr.splice(to, 0, fromId)
  draftIds.value = arr
}

function onSelDragStart(id: string, e: DragEvent) {
  draggingId.value = id
  e.dataTransfer?.setData('text/plain', id)
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
  }
}

function onSelDragOver(id: string, e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  if (!draggingId.value || draggingId.value === id) return
  dragOverId.value = id
  reorderDraft(draggingId.value, id)
}

function onSelDragEnd() {
  draggingId.value = null
  dragOverId.value = null
}

function onSelDrop(e: DragEvent) {
  e.preventDefault()
  onSelDragEnd()
}

/** 触控：超过位移阈值后才拖拽换序，短滑仍可滚弹层 */
function onSelPointerDown(id: string, e: PointerEvent) {
  if ((e.target as HTMLElement | null)?.closest?.('.qc-sel-x')) return
  // 仅触控 / 笔；鼠标走 HTML5 drag
  if (e.pointerType === 'mouse') return
  touchPendingId.value = id
  touchStart.value = { x: e.clientX, y: e.clientY }
  const el = e.currentTarget as HTMLElement
  try {
    el.setPointerCapture(e.pointerId)
  } catch {
    /* ignore */
  }
}

function onSelPointerMove(e: PointerEvent) {
  if (e.pointerType === 'mouse') return
  if (!touchPendingId.value && !draggingId.value) return

  if (touchPendingId.value && touchStart.value && !draggingId.value) {
    const dx = e.clientX - touchStart.value.x
    const dy = e.clientY - touchStart.value.y
    if (Math.hypot(dx, dy) < TOUCH_DRAG_PX) return
    // 以横向为主才开启排序，竖向优先交给弹层滚动
    if (Math.abs(dy) > Math.abs(dx) * 1.2) {
      touchPendingId.value = null
      touchStart.value = null
      try {
        ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
      } catch {
        /* ignore */
      }
      return
    }
    draggingId.value = touchPendingId.value
    touchPendingId.value = null
  }

  if (!draggingId.value) return
  e.preventDefault()
  const under = document.elementFromPoint(e.clientX, e.clientY)
  const hit = under?.closest?.('[data-qc-id]') as HTMLElement | null
  const toId = hit?.dataset?.qcId
  if (!toId || toId === draggingId.value) return
  dragOverId.value = toId
  reorderDraft(draggingId.value, toId)
}

function onSelPointerUp() {
  draggingId.value = null
  dragOverId.value = null
  touchPendingId.value = null
  touchStart.value = null
}

function resetDraftDefaults() {
  draftIds.value = defaultSelectedIds(catalog.value).slice(0, MAX_QUICK)
}

function saveCustomQuick() {
  if (!draftIds.value.length) {
    ElMessage.warning('请至少保留一个快捷入口')
    return
  }
  const nextIds = draftIds.value.slice(0, MAX_QUICK)
  saveQuickLinkIds(storageKey.value, nextIds)
  selectedIds.value = [...nextIds]
  customVisible.value = false
  ElMessage.success('快捷入口已保存')
}

const authStatusLabel: Record<string, string> = {
  pending: '待授权',
  authorized: '已授权',
  denied: '拒绝',
  anonymized: '已脱敏',
}

const llmOk = computed(() => !!integrations.value?.llm.configured)
const imageOk = computed(() => !!integrations.value?.image.configured)

async function load() {
  if (auth.isTeacher) return
  loading.value = true
  try {
    // system.integrations 需 system.read；学管师默认无此权限，勿请求以免弹「无权限」
    const canSystem = auth.hasPermission('system.read')
    const canMaterials = auth.hasPermission('materials.read')
    const canDashboard = auth.hasPermission('dashboard.read')

    const [s, pendingPage, integ] = await Promise.all([
      canDashboard ? getSummary().catch(() => null) : Promise.resolve(null),
      canMaterials
        ? listMaterialsApi({ status: 'new', page: 1, page_size: 8 }).catch(() => ({
            items: [] as Material[],
          }))
        : Promise.resolve({ items: [] as Material[] }),
      canSystem
        ? getIntegrationsStatus({ silent: true }).catch(() => null)
        : Promise.resolve(null),
    ])
    summary.value = s
    integrations.value = integ
    pending.value = pendingPage.items
  } finally {
    loading.value = false
  }
}

watch(
  () => [auth.user?.id, auth.user?.role, auth.isAdmin, auth.isTeacher] as const,
  () => reloadQuickSelection(),
  { immediate: true },
)

onMounted(load)
</script>

<template>
  <div
    class="dashboard oc-page-shell"
    :class="{
      'is-ops': !auth.isTeacher,
      'is-teacher': auth.isTeacher,
      'is-compact': isApp,
      [`work-${workLayout}`]: true,
    }"
  >
    <div v-if="isApp" class="compact-home">
      <header class="compact-welcome">
        <div>
          <p>{{ todayLabel }}</p>
          <h1>{{ greeting }}，{{ displayName }}</h1>
        </div>
        <span class="compact-role">{{ roleText }}</span>
      </header>

      <section v-if="stats.length" class="compact-stats" v-loading="loading" aria-label="运营概览">
        <button
          v-for="s in stats"
          :key="s.key"
          type="button"
          class="compact-stat"
          :class="`tone-${s.tone}`"
          @click="router.push(s.path)"
        >
          <el-icon><component :is="s.icon" /></el-icon>
          <strong>{{ s.value }}</strong>
          <span>{{ s.title }}</span>
        </button>
      </section>

      <section class="compact-section compact-quick">
        <div class="compact-section-head">
          <h2>快捷入口</h2>
          <el-button
            text
            circle
            class="compact-setting"
            aria-label="自定义快捷入口"
            title="自定义快捷入口"
            @click="openCustomQuick"
          >
            <el-icon><Setting /></el-icon>
          </el-button>
        </div>
        <div class="compact-quick-grid">
          <button
            v-for="link in compactQuickLinks"
            :key="link.id"
            type="button"
            class="compact-quick-item"
            @click="router.push(link.path)"
          >
            <span class="compact-quick-icon">
              <el-icon><component :is="link.icon" /></el-icon>
            </span>
            <span>{{ link.title }}</span>
          </button>
        </div>
      </section>

      <section class="compact-section compact-todo-section">
        <TodayTodos compact class="compact-todos" />
      </section>

      <section v-if="showPendingPanel" class="compact-section compact-pending">
        <div class="compact-section-head">
          <h2>待处理素材 <span v-if="pending.length">{{ pending.length }}</span></h2>
          <el-button link type="primary" @click="router.push('/materials')">全部</el-button>
        </div>
        <button
          v-for="row in pending.slice(0, 3)"
          :key="row.id"
          type="button"
          class="compact-pending-item"
          @click="router.push(`/materials/${row.id}`)"
        >
          <span class="compact-pending-title">{{ row.title }}</span>
          <span class="compact-pending-meta">
            {{ [row.grade, row.subject].filter(Boolean).join(' · ') || '素材' }}
          </span>
          <el-icon><ArrowRight /></el-icon>
        </button>
        <p v-if="!loading && !pending.length" class="compact-empty">暂无待处理素材</p>
      </section>
    </div>

    <!-- 顶栏：欢迎 + AI（有 AI 时并排，无则欢迎区拉满） -->
    <header v-if="!isApp" class="top-band" :class="{ 'has-ai': showAiPanel }">
      <section class="hero">
        <div class="hero-ornament" aria-hidden="true" />
        <div class="hero-body">
          <div class="hero-text">
            <p class="hero-kicker">嘉壹启航 · 工作台</p>
            <h1 class="hero-title">{{ greeting }}，{{ displayName }}</h1>
            <p class="hero-sub">
              {{ todayLabel }}
              <span v-if="roleText" class="hero-dot">·</span>
              <span v-if="roleText">{{ roleText }}</span>
            </p>
          </div>
          <div class="hero-badge" :title="auth.user?.username">
            <el-avatar class="hero-avatar" :size="48">
              {{ (displayName || '?').slice(0, 1) }}
            </el-avatar>
            <div class="hero-badge-meta">
              <div class="hero-badge-name">{{ displayName }}</div>
              <div class="hero-badge-role">{{ roleText || '已登录' }}</div>
            </div>
          </div>
        </div>
      </section>

      <section
        v-if="!auth.isTeacher && auth.hasPermission('system.read') && integrations"
        class="ai-panel"
      >
        <div class="ai-panel-head">
          <el-icon :size="18"><MagicStick /></el-icon>
          <span>AI 能力</span>
        </div>
        <div class="ai-pills">
          <div class="ai-pill" :class="llmOk ? 'is-on' : 'is-off'">
            <span class="ai-dot" />
            <div class="ai-pill-text">
              <span class="ai-pill-title">文案大模型</span>
              <span class="ai-pill-meta">
                {{ llmOk ? integrations.llm.model || '已配置' : '未配置 · 可用模板' }}
              </span>
            </div>
          </div>
          <div class="ai-pill" :class="imageOk ? 'is-on' : 'is-off'">
            <span class="ai-dot" />
            <div class="ai-pill-text">
              <span class="ai-pill-title">海报生图</span>
              <span class="ai-pill-meta">
                {{ imageOk ? integrations.image.model || '已配置' : '未配置 · 可用版式' }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </header>

    <!-- 运营：数据概览（全宽；按权限展示卡片） -->
    <section
      v-if="!isApp && !auth.isTeacher && stats.length"
      class="section stats-section"
      v-loading="loading"
    >
      <div class="section-head">
        <h2 class="section-title">运营概览</h2>
        <p class="section-desc">点击卡片可直达对应模块</p>
      </div>
      <div class="stats-grid">
        <button
          v-for="s in stats"
          :key="s.key"
          type="button"
          class="stat-card"
          :class="`tone-${s.tone}`"
          @click="router.push(s.path)"
        >
          <div class="stat-icon-wrap" aria-hidden="true">
            <el-icon :size="22"><component :is="s.icon" /></el-icon>
          </div>
          <div class="stat-body">
            <div class="stat-label">{{ s.title }}</div>
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-hint">
              {{ s.hint }}
              <el-icon class="stat-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </button>
      </div>
    </section>

    <!-- 主工作区：按可见模块自适应列数，避免权限缺口留白 -->
    <div v-if="!isApp" class="work-grid" :class="`layout-${workLayout}`">
      <TodayTodos class="todo-block" />

      <section class="panel quick-panel">
        <div class="panel-head">
          <h2 class="panel-title">快捷入口</h2>
          <div class="panel-head-actions">
            <span class="panel-extra">常用功能一键直达</span>
            <el-button
              class="quick-customize-btn"
              text
              type="primary"
              @click="openCustomQuick"
            >
              <el-icon><Setting /></el-icon>
              自定义
            </el-button>
          </div>
        </div>
        <div class="quick-grid" :class="`count-${Math.min(quickLinks.length, 6)}`">
          <button
            v-for="link in quickLinks"
            :key="link.id"
            type="button"
            class="quick-item"
            @click="router.push(link.path)"
          >
            <span class="quick-icon" aria-hidden="true">
              <el-icon :size="20"><component :is="link.icon" /></el-icon>
            </span>
            <span class="quick-text">
              <span class="quick-title">{{ link.title }}</span>
              <span class="quick-desc">{{ link.desc }}</span>
            </span>
          </button>
        </div>
      </section>

      <section v-if="showPendingPanel" class="panel pending-panel">
        <div class="panel-head">
          <h2 class="panel-title">
            待处理素材
            <el-tag v-if="pending.length" size="small" effect="plain" class="count-tag">
              {{ pending.length }}
            </el-tag>
          </h2>
          <el-button link type="primary" @click="router.push('/materials')">查看全部</el-button>
        </div>

        <el-empty
          v-if="!loading && !pending.length"
          description="暂无待处理素材，辛苦啦"
          :image-size="72"
        />

        <div v-else class="pending-list">
          <button
            v-for="row in pending"
            :key="row.id"
            type="button"
            class="pending-item"
            @click="router.push(`/materials/${row.id}`)"
          >
            <span class="pending-mark" aria-hidden="true" />
            <span class="pending-main">
              <span class="pending-title">{{ row.title }}</span>
              <span class="pending-meta">
                <span v-if="row.grade">{{ row.grade }}</span>
                <span v-if="row.subject">{{ row.subject }}</span>
                <span>{{ authStatusLabel[row.auth_status] || row.auth_status }}</span>
              </span>
            </span>
            <el-icon class="pending-go"><ArrowRight /></el-icon>
          </button>
        </div>
      </section>
    </div>

    <!-- 自定义快捷入口：App 用底部 Sheet，PC 用居中 Dialog -->
    <AppSheet
      v-if="isApp"
      v-model="customVisible"
      title="自定义快捷入口"
      compact-size="min(92%, 820px)"
      force-bottom
      modal-class="quick-custom-sheet"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="qc-body">
        <p class="qc-intro">点选下方功能加入首页；已选可拖动排序，最多 {{ MAX_QUICK }} 个。</p>
        <section class="qc-section qc-section--selected">
          <div class="qc-section-title">
            <span class="qc-section-label">已选功能</span>
            <span class="qc-section-hint">拖拽排序 · {{ draftIds.length }}/{{ MAX_QUICK }}</span>
          </div>
          <div v-if="!draftSelected.length" class="qc-empty">尚未选择，请从下方添加</div>
          <div v-else class="qc-sel-grid" @dragover.prevent>
            <div
              v-for="item in draftSelected"
              :key="item.id"
              class="qc-sel"
              :class="{
                'is-dragging': draggingId === item.id,
                'is-over': dragOverId === item.id && draggingId !== item.id,
              }"
              :data-qc-id="item.id"
              draggable="true"
              @dragstart="onSelDragStart(item.id, $event)"
              @dragover="onSelDragOver(item.id, $event)"
              @dragend="onSelDragEnd"
              @drop="onSelDrop"
              @pointerdown="onSelPointerDown(item.id, $event)"
              @pointermove="onSelPointerMove"
              @pointerup="onSelPointerUp"
              @pointercancel="onSelPointerUp"
            >
              <button
                type="button"
                class="qc-sel-x"
                title="移除"
                aria-label="移除"
                @click="removeDraft(item.id, $event)"
                @pointerdown.stop
              >
                <el-icon :size="12"><Close /></el-icon>
              </button>
              <span class="qc-sel-icon" aria-hidden="true">
                <el-icon :size="20"><component :is="item.icon" /></el-icon>
              </span>
              <span class="qc-sel-title">{{ item.title }}</span>
            </div>
          </div>
        </section>

        <section v-for="g in catalogGroups" :key="g.group" class="qc-section">
          <div class="qc-section-title">
            <span class="qc-section-label">{{ g.group }}</span>
          </div>
          <div class="qc-catalog-grid">
            <button
              v-for="item in g.items"
              :key="item.id"
              type="button"
              class="qc-pick"
              :class="{ 'is-on': isDraftSelected(item.id) }"
              @click="toggleDraft(item.id)"
            >
              <span class="qc-pick-icon">
                <el-icon :size="18"><component :is="item.icon" /></el-icon>
              </span>
              <span class="qc-pick-title">{{ item.title }}</span>
              <span v-if="isDraftSelected(item.id)" class="qc-pick-check" aria-hidden="true">
                <el-icon :size="11"><Check /></el-icon>
              </span>
            </button>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="qc-footer">
          <button type="button" class="qc-footer-reset" @click="resetDraftDefaults">恢复默认</button>
          <el-button class="qc-footer-cancel" @click="customVisible = false">取消</el-button>
          <el-button type="primary" class="qc-footer-save" @click="saveCustomQuick">保存</el-button>
        </div>
      </template>
    </AppSheet>

    <el-dialog
      v-else
      v-model="customVisible"
      title="自定义快捷入口"
      width="560px"
      align-center
      destroy-on-close
      append-to-body
      class="quick-custom-dialog"
      :close-on-click-modal="false"
    >
      <div class="qc-body">
        <p class="qc-intro">点选下方功能加入首页；已选可拖动排序，最多 {{ MAX_QUICK }} 个。</p>
        <section class="qc-section qc-section--selected">
          <div class="qc-section-title">
            <span class="qc-section-label">已选功能</span>
            <span class="qc-section-hint">拖拽排序 · {{ draftIds.length }}/{{ MAX_QUICK }}</span>
          </div>
          <div v-if="!draftSelected.length" class="qc-empty">尚未选择，请从下方添加</div>
          <div v-else class="qc-sel-grid" @dragover.prevent>
            <div
              v-for="item in draftSelected"
              :key="item.id"
              class="qc-sel"
              :class="{
                'is-dragging': draggingId === item.id,
                'is-over': dragOverId === item.id && draggingId !== item.id,
              }"
              :data-qc-id="item.id"
              draggable="true"
              @dragstart="onSelDragStart(item.id, $event)"
              @dragover="onSelDragOver(item.id, $event)"
              @dragend="onSelDragEnd"
              @drop="onSelDrop"
              @pointerdown="onSelPointerDown(item.id, $event)"
              @pointermove="onSelPointerMove"
              @pointerup="onSelPointerUp"
              @pointercancel="onSelPointerUp"
            >
              <button
                type="button"
                class="qc-sel-x"
                title="移除"
                aria-label="移除"
                @click="removeDraft(item.id, $event)"
                @pointerdown.stop
              >
                <el-icon :size="12"><Close /></el-icon>
              </button>
              <span class="qc-sel-icon" aria-hidden="true">
                <el-icon :size="20"><component :is="item.icon" /></el-icon>
              </span>
              <span class="qc-sel-title">{{ item.title }}</span>
            </div>
          </div>
        </section>

        <section v-for="g in catalogGroups" :key="g.group" class="qc-section">
          <div class="qc-section-title">
            <span class="qc-section-label">{{ g.group }}</span>
          </div>
          <div class="qc-catalog-grid">
            <button
              v-for="item in g.items"
              :key="item.id"
              type="button"
              class="qc-pick"
              :class="{ 'is-on': isDraftSelected(item.id) }"
              @click="toggleDraft(item.id)"
            >
              <span class="qc-pick-icon">
                <el-icon :size="18"><component :is="item.icon" /></el-icon>
              </span>
              <span class="qc-pick-title">{{ item.title }}</span>
              <span v-if="isDraftSelected(item.id)" class="qc-pick-check" aria-hidden="true">
                <el-icon :size="11"><Check /></el-icon>
              </span>
            </button>
          </div>
        </section>
      </div>

      <template #footer>
        <div class="qc-footer">
          <button type="button" class="qc-footer-reset" @click="resetDraftDefaults">恢复默认</button>
          <div class="qc-footer-right">
            <el-button @click="customVisible = false">取消</el-button>
            <el-button type="primary" @click="saveCustomQuick">保存</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/*
 * 宽屏策略（内容宽度见 .dashboard.oc-page-shell / --oc-content-max）：
 * - ≥1280：待办 | 快捷+素材 两列
 * - ≥1480：待办 | 快捷 | 素材 三列铺满
 */
.dashboard {
  padding-bottom: 12px;
}

/* ── 顶栏：欢迎 + AI ── */
.top-band {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  margin-bottom: 18px;
}

.hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(135deg, #fffdf8 0%, #faf6ee 42%, #f5e6c8 100%);
  box-shadow: 0 10px 28px rgba(41, 37, 36, 0.05);
  min-width: 0;
}

.hero-ornament {
  position: absolute;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.12);
  right: -70px;
  top: -120px;
  pointer-events: none;
}

.hero-ornament::after {
  content: '';
  position: absolute;
  inset: 32px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.08);
}

.hero-body {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 28px;
  min-height: 108px;
}

.hero-kicker {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.12em;
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.hero-title {
  margin: 0;
  font-size: clamp(1.4rem, 1.6vw + 0.6rem, 1.85rem);
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
  line-height: 1.3;
}

.hero-sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.hero-dot {
  margin: 0 6px;
  opacity: 0.5;
}

.hero-badge {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px 10px 10px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.72);
  border: 1px solid rgba(232, 224, 208, 0.9);
  backdrop-filter: blur(6px);
  flex-shrink: 0;
}

.hero-avatar {
  background: var(--oc-primary, #a16207);
  color: #fffdf8;
  font-weight: 700;
}

.hero-badge-name {
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.hero-badge-role {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-top: 2px;
}

.ai-panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 16px;
  background: linear-gradient(160deg, #fffdf8, #faf6ee);
  padding: 16px 18px;
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  min-width: 0;
}

.ai-panel-head {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-primary, #a16207);
}

.ai-pills {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-pill {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fff;
}

.ai-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}

.ai-pill.is-on {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.ai-pill.is-on .ai-dot {
  background: #16a34a;
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
}

.ai-pill.is-off {
  border-color: #e7e5e4;
  background: #fafaf9;
}

.ai-pill.is-off .ai-dot {
  background: #a8a29e;
}

.ai-pill-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ai-pill-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.ai-pill-meta {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 概览 ── */
.section {
  margin-bottom: 18px;
}

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.section-title,
.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.section-desc,
.panel-extra {
  margin: 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

/* 按可见卡片数量自动拉伸，1/2/3 张都铺满不留空列 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 14px;
}

.stat-card {
  appearance: none;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  padding: 18px 20px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  width: 100%;
  font: inherit;
  color: inherit;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(41, 37, 36, 0.07);
  border-color: var(--el-color-primary-light-7);
}

.stat-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tone-amber .stat-icon-wrap {
  background: linear-gradient(145deg, #f5e6c8, #f2e8d6);
  color: #a16207;
}

.tone-rose .stat-icon-wrap {
  background: linear-gradient(145deg, #fde8e4, #fce7f3);
  color: #b45309;
}

.tone-sage .stat-icon-wrap {
  background: linear-gradient(145deg, #e8f0e6, #edf2e8);
  color: #4d7c0f;
}

.stat-body {
  min-width: 0;
  flex: 1;
}

.stat-label {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  font-weight: 500;
}

.stat-value {
  margin-top: 6px;
  font-size: clamp(1.6rem, 1.2vw + 1rem, 2rem);
  font-weight: 750;
  line-height: 1.1;
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}

.stat-hint {
  margin-top: 10px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.stat-arrow {
  transition: transform 0.15s ease;
}

.stat-card:hover .stat-arrow {
  transform: translateX(3px);
}

/* ── 主工作区 ── */
.work-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  /* 各模块按内容高度，避免快捷入口被待办列表「拉高」出大片空白 */
  align-items: start;
}

.todo-block {
  min-width: 0;
}

.todo-block :deep(.todo-panel) {
  box-sizing: border-box;
}

.panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  padding: 16px 18px 14px;
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  min-width: 0;
  height: auto;
  box-sizing: border-box;
}

/* 快捷入口：高度完全跟随内容（最多 12 个入口，不人为撑高） */
.quick-panel {
  height: auto;
  align-self: start;
}

.quick-panel .quick-grid {
  flex: none;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 14px;
}

.panel-head-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.quick-customize-btn {
  font-weight: 600;
  padding: 4px 6px !important;
}

.quick-customize-btn .el-icon {
  margin-right: 2px;
}

/* 自定义快捷入口：内容区 */
.qc-body {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.qc-intro {
  margin: 0;
  padding: 10px 12px;
  border: 1px dashed rgba(161, 98, 7, 0.28);
  border-radius: 12px;
  background: linear-gradient(180deg, #fff9eb, #fffdf8);
  color: #8b5406;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.45;
}

.qc-section {
  margin: 0;
  padding: 12px;
  border: 1px solid rgba(181, 145, 83, 0.2);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 254, 251, 0.96), rgba(250, 246, 238, 0.72));
}

.qc-section--selected {
  border-color: rgba(161, 98, 7, 0.28);
  background: linear-gradient(160deg, #fffefb, #faf3e6);
}

.qc-section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.qc-section-label {
  font-size: 13px;
  font-weight: 720;
  color: #6b4f25;
}

.qc-section-hint {
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-muted, #78716c);
  font-variant-numeric: tabular-nums;
}

.qc-empty {
  padding: 18px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  border: 1px dashed rgba(181, 145, 83, 0.35);
  border-radius: 12px;
  background: rgba(255, 253, 248, 0.8);
}

/* 固定 4 列，避免 auto-fill 在窄屏形变 */
.qc-sel-grid,
.qc-catalog-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.qc-sel {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  min-width: 0;
  min-height: 86px;
  padding: 12px 4px 10px;
  border-radius: 14px;
  border: 1px solid rgba(181, 145, 83, 0.28);
  background: linear-gradient(160deg, #fffdf8, #f5e6c8);
  box-shadow: 0 4px 12px rgba(88, 60, 24, 0.06);
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  box-sizing: border-box;
  transition: box-shadow 0.15s, transform 0.15s, border-color 0.15s, opacity 0.15s;
}

.qc-sel:active {
  cursor: grabbing;
}

.qc-sel.is-dragging {
  touch-action: none;
  opacity: 0.55;
  box-shadow: 0 10px 22px rgba(41, 37, 36, 0.14);
  transform: scale(1.03);
  z-index: 2;
}

.qc-sel.is-over {
  border-color: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 2px rgba(161, 98, 7, 0.2);
}

.qc-sel-icon {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #c07a12, #a16207);
  color: #fffdf8;
  pointer-events: none;
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.22);
}

.qc-sel-title {
  width: 100%;
  padding: 0 2px;
  font-size: 11px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  text-align: center;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
}

.qc-sel-x {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  min-width: 20px;
  min-height: 20px;
  border: 1.5px solid #fff;
  border-radius: 50%;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(68, 64, 60, 0.72);
  color: #fff;
  cursor: pointer;
  z-index: 3;
  box-sizing: border-box;
  line-height: 0;
}

.qc-sel-x:active {
  background: #b91c1c;
}

.qc-pick {
  appearance: none;
  position: relative;
  min-width: 0;
  min-height: 86px;
  padding: 12px 4px 10px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  border-radius: 14px;
  background: #fffefb;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 6px;
  cursor: pointer;
  font: inherit;
  color: inherit;
  box-sizing: border-box;
  box-shadow: 0 2px 8px rgba(88, 60, 24, 0.04);
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s, transform 0.15s;
}

.qc-pick:active {
  transform: scale(0.98);
}

.qc-pick.is-on {
  border-color: rgba(161, 98, 7, 0.42);
  background: linear-gradient(160deg, #fffdf8, #f5e6c8);
  box-shadow:
    0 0 0 1px rgba(161, 98, 7, 0.12),
    0 6px 14px rgba(161, 98, 7, 0.1);
}

.qc-pick-icon {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f0e6;
  color: var(--oc-primary, #a16207);
}

.qc-pick.is-on .qc-pick-icon {
  background: linear-gradient(145deg, #c07a12, #a16207);
  color: #fffdf8;
  box-shadow: 0 4px 10px rgba(161, 98, 7, 0.2);
}

.qc-pick-title {
  width: 100%;
  padding: 0 2px;
  font-size: 11px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  text-align: center;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.qc-pick-check {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 18px;
  height: 18px;
  min-width: 18px;
  min-height: 18px;
  border-radius: 50%;
  border: 1.5px solid #fff;
  background: linear-gradient(145deg, #c07a12, #a16207);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  line-height: 0;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.28);
}

.qc-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.qc-footer-reset {
  flex: 0 0 auto;
  height: 44px;
  padding: 0 10px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: #a16207;
  font: inherit;
  font-size: 13px;
  font-weight: 680;
  cursor: pointer;
  white-space: nowrap;
}

.qc-footer-reset:active {
  background: rgba(161, 98, 7, 0.08);
}

.qc-footer-right {
  display: flex;
  flex: 1 1 auto;
  gap: 8px;
  min-width: 0;
  margin-left: auto;
}

.qc-footer-cancel,
.qc-footer-save,
.qc-footer-right .el-button {
  flex: 1 1 0;
  min-width: 0;
  min-height: 44px;
  margin: 0 !important;
  border-radius: 12px !important;
  font-weight: 700 !important;
}

.qc-footer-cancel {
  flex: 0 0 88px;
}

.count-tag {
  border-color: var(--oc-border, #e8e0d0);
  color: var(--oc-primary, #a16207);
  background: #f2e8d6;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-content: start;
}

/* 入口很少时单列拉满，避免半边空 */
.quick-grid.count-1 {
  grid-template-columns: 1fr;
}

/*
 * 老师右栏比运营窄：始终最多 2 列，且单卡有最小宽度，
 * 避免被运营的 3 列规则挤成「一字一行」竖排。
 */
.is-teacher .quick-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.is-teacher .quick-grid.count-1 {
  grid-template-columns: 1fr;
}

.quick-item {
  appearance: none;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s, box-shadow 0.15s;
  font: inherit;
  color: inherit;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.quick-item:hover {
  border-color: var(--el-color-primary-light-5);
  background: #faf6ee;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(41, 37, 36, 0.05);
}

.quick-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #faf3e6, #f0e4d0);
  color: var(--oc-primary, #a16207);
  flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.08);
}

.quick-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
}

.quick-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  /* 窄卡时省略，绝不竖排拆字 */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: keep-all;
}

.quick-desc {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: keep-all;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* 宽屏下列表可拉高，避免右侧空荡 */
  max-height: none;
}

.pending-item {
  appearance: none;
  width: 100%;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 11px;
  background: #fff;
  padding: 12px 12px 12px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}

.pending-item:hover {
  border-color: var(--el-color-primary-light-5);
  background: #faf6ee;
  transform: translateX(2px);
}

.pending-mark {
  width: 4px;
  align-self: stretch;
  min-height: 28px;
  border-radius: 4px;
  background: linear-gradient(180deg, #c9a066, #a16207);
  flex-shrink: 0;
}

.pending-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pending-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pending-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.pending-go {
  color: var(--oc-muted, #78716c);
  flex-shrink: 0;
  transition: transform 0.15s, color 0.15s;
}

.pending-item:hover .pending-go {
  color: var(--oc-primary, #a16207);
  transform: translateX(2px);
}

/* ── ≥1100：顶栏 / 工作区按可见模块自适应 ── */
@media (min-width: 1100px) {
  /* 有 AI 侧栏才两列；无权限时欢迎区整行拉满 */
  .is-ops .top-band.has-ai {
    grid-template-columns: minmax(0, 1.55fr) minmax(260px, 0.55fr);
    align-items: stretch;
  }

  .is-ops .top-band:not(.has-ai),
  .is-teacher .top-band {
    grid-template-columns: 1fr;
  }

  .is-ops .top-band:not(.has-ai) .hero-body,
  .is-teacher .hero-body {
    padding: 24px 32px;
    min-height: 120px;
  }

  .ai-panel {
    min-height: 100%;
  }

  /* 完整：待办 | 右栏（快捷+素材上下叠） */
  .work-grid.layout-ops-full {
    grid-template-columns: minmax(320px, 0.92fr) minmax(0, 1.28fr);
    gap: 16px;
  }

  .work-grid.layout-ops-full .todo-block {
    grid-row: 1 / span 2;
  }

  .work-grid.layout-ops-full .quick-panel {
    grid-column: 2;
    grid-row: 1;
    height: auto;
    align-self: start;
  }

  .work-grid.layout-ops-full .pending-panel {
    grid-column: 2;
    grid-row: 2;
    align-self: start;
  }

  /* 无素材权限：待办 | 快捷 两列等分拉满，不留第三空列 */
  .work-grid.layout-ops-simple {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
    gap: 16px;
  }

  .work-grid.layout-ops-simple .todo-block,
  .work-grid.layout-ops-simple .quick-panel {
    grid-row: auto;
    grid-column: auto;
  }

  /* 老师：待办 | 快捷 */
  .work-grid.layout-teacher {
    grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.85fr);
  }

  /* 运营右栏较宽可用 3 列；入口少时由 count-* 覆盖 */
  .work-grid.layout-ops-full .quick-grid:not(.count-1):not(.count-2) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .work-grid.layout-ops-simple .quick-grid:not(.count-1) {
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  }

  .work-grid.layout-ops-full .quick-grid.count-2,
  .work-grid.layout-teacher .quick-grid:not(.count-1) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* ── ≥1480：宽屏 ── */
@media (min-width: 1480px) {
  .is-ops .top-band.has-ai {
    grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.5fr);
    gap: 16px;
  }

  .is-ops .hero-body {
    padding: 26px 32px;
    min-height: 120px;
  }

  .is-ops .top-band:not(.has-ai) .hero-body,
  .is-teacher .hero-body {
    padding: 28px 36px;
    min-height: 128px;
  }

  .stats-grid {
    gap: 16px;
  }

  .stat-card {
    padding: 22px 24px;
  }

  /* 三模块：真正三列横铺 */
  .work-grid.layout-ops-full {
    grid-template-columns: minmax(340px, 0.9fr) minmax(0, 1.15fr) minmax(300px, 0.85fr);
    gap: 16px;
  }

  .work-grid.layout-ops-full .todo-block {
    grid-row: 1;
    grid-column: 1;
  }

  .work-grid.layout-ops-full .quick-panel {
    grid-column: 2;
    grid-row: 1;
    height: auto;
    align-self: start;
  }

  .work-grid.layout-ops-full .pending-panel {
    grid-column: 3;
    grid-row: 1;
    align-self: start;
  }

  /* 两模块：两列更均衡拉满 */
  .work-grid.layout-ops-simple {
    grid-template-columns: minmax(360px, 0.95fr) minmax(0, 1.25fr);
    gap: 16px;
  }

  .work-grid.layout-ops-full .quick-grid:not(.count-1):not(.count-2) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .work-grid.layout-ops-simple .quick-grid:not(.count-1) {
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  }

  .work-grid.layout-teacher {
    grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
  }

  .work-grid.layout-ops-full .pending-list {
    max-height: min(62vh, 560px);
    overflow-y: auto;
    padding-right: 2px;
  }
}

/* ── ≥1720：超宽再拉开 ── */
@media (min-width: 1720px) {
  .work-grid.layout-ops-full {
    grid-template-columns: minmax(360px, 0.85fr) minmax(0, 1.2fr) minmax(320px, 0.9fr);
    gap: 18px;
  }

  .work-grid.layout-ops-simple {
    grid-template-columns: minmax(380px, 0.9fr) minmax(0, 1.3fr);
    gap: 18px;
  }

  .work-grid.layout-ops-full .quick-grid:not(.count-1):not(.count-2),
  .work-grid.layout-ops-simple .quick-grid:not(.count-1):not(.count-2) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .work-grid.layout-teacher .quick-grid:not(.count-1) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero-title {
    font-size: 1.9rem;
  }
}

/* ── 平板 / 窄屏 ── */
@media (max-width: 1099px) {
  /* 窄屏仍 auto-fit：两张卡可并排，一张则拉满 */
  .stats-grid {
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 260px), 1fr));
  }
}

@media (max-width: 1199px) {
  .top-band {
    margin-bottom: 14px;
  }

  .hero-body {
    padding: 18px 16px;
    min-height: 0;
  }
}

@media (max-width: 767px) {
  .hero-badge {
    display: none;
  }

  .hero-body {
    padding: 16px 14px;
  }

  .quick-grid {
    grid-template-columns: 1fr;
  }

  .stat-card {
    padding: 16px;
  }

  .stat-value {
    font-size: 1.5rem;
  }
}

/* WAP / Pad 工作台：App 信息架构 */
.dashboard.is-compact {
  max-width: none;
}

.compact-home {
  display: grid;
  gap: 12px;
}

.compact-welcome {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 14px 12px;
  border: 1px solid rgba(181, 145, 83, 0.26);
  border-radius: 18px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.92), transparent 48%),
    linear-gradient(160deg, #fffdf8, #f5e6c8);
  box-shadow: 0 10px 24px rgba(88, 60, 24, 0.08);
}

.compact-welcome p {
  margin: 0 0 4px;
  color: #8b5406;
  font-size: 11px;
  font-weight: 650;
}

.compact-welcome h1 {
  margin: 0;
  color: var(--oc-ink, #44403c);
  font-size: 20px;
  font-weight: 760;
  line-height: 1.25;
}

.compact-role {
  flex-shrink: 0;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(161, 98, 7, 0.22);
  background: rgba(255, 253, 248, 0.88);
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  font-weight: 680;
}

.compact-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  min-height: 0;
  overflow: visible;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.compact-stat {
  appearance: none;
  min-width: 0;
  min-height: 84px;
  padding: 12px 10px;
  border: 1px solid rgba(181, 145, 83, 0.24);
  border-radius: 16px;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.9), transparent 50%),
    #fffdf8;
  color: var(--oc-muted, #78716c);
  display: grid;
  grid-template-columns: 28px 1fr;
  grid-template-rows: auto auto;
  align-content: center;
  align-items: center;
  gap: 2px 8px;
  text-align: left;
  box-shadow: 0 8px 18px rgba(88, 60, 24, 0.06);
}

.compact-stat:last-child {
  border-right: 1px solid rgba(181, 145, 83, 0.24);
}

.compact-stat .el-icon {
  grid-row: 1 / -1;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  background: #f5f0e6;
  color: var(--oc-primary, #a16207);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.compact-stat.tone-rose .el-icon {
  color: #c4515f;
  background: #fdf0f1;
}

.compact-stat.tone-sage .el-icon {
  color: #438a6b;
  background: #eef7f2;
}

.compact-stat strong {
  color: var(--oc-ink, #44403c);
  font-size: 20px;
  font-weight: 760;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.compact-stat span {
  overflow: hidden;
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-section {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(181, 145, 83, 0.24);
  border-radius: 18px;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.78), transparent 42%),
    #fffdf8;
  box-shadow: 0 10px 24px rgba(88, 60, 24, 0.07);
}

.compact-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 36px;
  margin-bottom: 10px;
}

.compact-section-head h2 {
  margin: 0;
  color: var(--oc-ink, #44403c);
  font-size: 15px;
  font-weight: 720;
}

.compact-section-head h2 span {
  margin-left: 4px;
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  font-weight: 700;
}

.compact-setting {
  min-width: 40px;
  min-height: 40px;
  border-radius: 12px !important;
  border: 1px solid rgba(161, 98, 7, 0.2) !important;
  background: linear-gradient(180deg, #fffefb, #f5e6c8) !important;
  color: #6b4f25 !important;
}

.compact-quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.compact-quick-item {
  appearance: none;
  min-width: 0;
  min-height: 78px;
  height: auto;
  padding: 10px 4px 8px;
  border: 1px solid rgba(181, 145, 83, 0.2);
  border-radius: 14px;
  background: #fffefb;
  color: var(--oc-ink, #44403c);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 650;
  line-height: 1.2;
  box-shadow: 0 2px 8px rgba(88, 60, 24, 0.04);
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    transform 0.15s ease;
}

.compact-quick-item:active {
  background: linear-gradient(160deg, #fffdf8, #f5e6c8);
  border-color: rgba(161, 98, 7, 0.28);
  transform: scale(0.98);
}

.compact-quick-item > span:last-child {
  width: 100%;
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 全部入口统一：浅金图标底 + 金色图标，不再区分 primary 实心块 */
.compact-quick-icon {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: linear-gradient(160deg, #faf3e6, #f0e4d0);
  color: var(--oc-primary, #a16207);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.08);
}

.compact-pending-item {
  appearance: none;
  width: 100%;
  min-height: 52px;
  margin-top: 6px;
  padding: 10px 12px;
  border: 1px solid rgba(181, 145, 83, 0.16);
  border-radius: 12px;
  background: linear-gradient(180deg, #fffefb, #faf6ee);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 18px;
  align-items: center;
  gap: 8px;
  color: var(--oc-ink, #44403c);
  text-align: left;
}

.compact-pending-title {
  overflow: hidden;
  font-size: 13px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact-pending-meta,
.compact-pending-item .el-icon {
  color: var(--oc-muted, #78716c);
  font-size: 11px;
}

.compact-empty {
  margin: 8px 0 0;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  text-align: center;
}

@media (min-width: 768px) and (max-width: 1199px) {
  .compact-home {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
    gap: 14px;
  }

  .compact-welcome,
  .compact-stats,
  .compact-pending {
    grid-column: 1 / -1;
  }

  .compact-quick-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 380px) {
  .compact-quick-grid,
  .qc-sel-grid,
  .qc-catalog-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>

<!-- append-to-body 弹层：壳层样式必须非 scoped -->
<style>
/* PC：自定义快捷入口居中 Dialog */
.el-overlay-dialog:has(.quick-custom-dialog) {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
}

.quick-custom-dialog.el-dialog {
  max-width: min(560px, calc(100vw - 24px));
  margin: auto !important;
  border-radius: 16px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: min(86vh, 86dvh);
  position: relative;
  top: auto;
  border: 1px solid rgba(181, 145, 83, 0.28);
  background: linear-gradient(165deg, #fffefb, #fffdf8 40%, #faf6ee);
  box-shadow: 0 22px 52px rgba(41, 37, 36, 0.16);
}

.quick-custom-dialog .el-dialog__header {
  flex-shrink: 0;
  padding: 16px 18px 12px;
  margin-right: 0;
  border-bottom: 1px solid rgba(181, 145, 83, 0.18);
  background: linear-gradient(180deg, #fffdf9, #f8f0e0);
}

.quick-custom-dialog .el-dialog__body {
  flex: 1 1 auto;
  min-height: 0;
  max-height: none;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  padding: 12px 16px 14px;
  touch-action: pan-y;
}

.quick-custom-dialog .el-dialog__footer {
  flex-shrink: 0;
  padding: 12px 16px 14px;
  border-top: 1px solid rgba(181, 145, 83, 0.2);
  background: linear-gradient(180deg, #faf3e6, #fffdf8);
}

.quick-custom-dialog .qc-footer-right .el-button {
  min-width: 96px;
  min-height: 40px;
  margin: 0 !important;
  border-radius: 12px !important;
  font-weight: 680 !important;
}

/* AppSheet：快捷入口自定义 */
.el-drawer.oc-app-sheet.quick-custom-sheet .el-drawer__body {
  padding: 12px 14px 8px !important;
}

.el-drawer.oc-app-sheet.quick-custom-sheet .el-drawer__footer {
  padding: 10px 14px calc(12px + env(safe-area-inset-bottom, 0px)) !important;
}

.el-drawer.oc-app-sheet.quick-custom-sheet .qc-footer {
  display: flex !important;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.el-drawer.oc-app-sheet.quick-custom-sheet .qc-footer .el-button {
  flex: 1 1 0;
  min-width: 0;
  min-height: 46px !important;
  margin: 0 !important;
  border-radius: 13px !important;
  font-weight: 720 !important;
}

.el-drawer.oc-app-sheet.quick-custom-sheet .qc-footer-cancel {
  flex: 0 0 92px !important;
}

.el-drawer.oc-app-sheet.quick-custom-sheet .qc-footer-reset {
  flex: 0 0 auto;
  height: 46px;
  padding: 0 8px;
  border: 0;
  border-radius: 12px;
  background: transparent;
  color: #a16207;
  font-size: 13px;
  font-weight: 700;
}
</style>
