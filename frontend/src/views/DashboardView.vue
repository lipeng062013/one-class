<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSummary, type DashboardSummary } from '../api/dashboard'
import { getIntegrationsStatus, type IntegrationsStatus } from '../api/system'
import { listMaterialsApi, type Material } from '../api/materials'
import { useAuthStore } from '../stores/auth'
import TodayTodos from '../components/TodayTodos.vue'

const auth = useAuthStore()
const router = useRouter()
const summary = ref<DashboardSummary | null>(null)
const integrations = ref<IntegrationsStatus | null>(null)
const pending = ref<Material[]>([])
const loading = ref(false)

const roleLabel: Record<string, string> = {
  admin: '负责人',
  operator: '运营',
  teacher: '老师',
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

const stats = computed(() => [
  {
    key: 'materials',
    title: '待处理素材',
    value: summary.value?.materials_new ?? 0,
    hint: '进入素材库处理',
    path: '/materials',
    icon: 'Picture',
    tone: 'amber',
  },
  {
    key: 'leads',
    title: '今日待跟进',
    value: summary.value?.leads_follow_today ?? 0,
    hint: '查看线索跟进',
    path: '/leads',
    icon: 'Phone',
    tone: 'rose',
  },
  {
    key: 'copies',
    title: '已生成文案',
    value: summary.value?.recent_copies ?? 0,
    hint: '查看文案列表',
    path: '/copies',
    icon: 'Document',
    tone: 'sage',
  },
])

type QuickLink = {
  title: string
  desc: string
  path: string
  icon: string
  primary?: boolean
  adminOnly?: boolean
}

const quickLinks = computed((): QuickLink[] => {
  const links: QuickLink[] = [
    { title: '素材', desc: '上传与管理', path: '/materials', icon: 'Picture', primary: true },
    { title: '生成文案', desc: '模板 / AI', path: '/copies/generate', icon: 'EditPen' },
    { title: '生成海报', desc: '版式 / 生图', path: '/posters/generate', icon: 'PictureFilled' },
    { title: '线索', desc: '跟进转化', path: '/leads', icon: 'Phone' },
    { title: '成长中心', desc: '话术与异议', path: '/knowledge/scripts', icon: 'Reading' },
    { title: '综合办公', desc: '表格协作', path: '/office', icon: 'Grid' },
    { title: '用户管理', desc: '账号权限', path: '/users', icon: 'User', adminOnly: true },
    { title: '学生信息', desc: '学员档案', path: '/students', icon: 'Avatar', adminOnly: true },
  ]
  return links.filter((l) => !l.adminOnly || auth.isAdmin)
})

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
    const [s, all, integ] = await Promise.all([
      getSummary(),
      listMaterialsApi(),
      getIntegrationsStatus().catch(() => null),
    ])
    summary.value = s
    integrations.value = integ
    pending.value = all.filter((m) => m.status === 'new').slice(0, 8)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div
    class="dashboard oc-page-shell"
    :class="{ 'is-ops': !auth.isTeacher, 'is-teacher': auth.isTeacher }"
  >
    <!-- 顶栏：欢迎 + AI（宽屏并排） -->
    <header class="top-band">
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

      <section v-if="!auth.isTeacher && integrations" class="ai-panel">
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

    <!-- 运营：数据概览（全宽） -->
    <section v-if="!auth.isTeacher" class="section stats-section" v-loading="loading">
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

    <!-- 主工作区：宽屏多列铺开 -->
    <div class="work-grid">
      <TodayTodos class="todo-block" />

      <template v-if="!auth.isTeacher">
        <section class="panel quick-panel">
          <div class="panel-head">
            <h2 class="panel-title">快捷入口</h2>
            <span class="panel-extra">常用功能一键直达</span>
          </div>
          <div class="quick-grid">
            <button
              v-for="link in quickLinks"
              :key="link.path"
              type="button"
              class="quick-item"
              :class="{ 'is-primary': link.primary }"
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

        <section class="panel pending-panel">
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
      </template>

      <section v-else class="teacher-tip panel">
        <div class="teacher-tip-icon" aria-hidden="true">
          <el-icon :size="28"><Reading /></el-icon>
        </div>
        <div>
          <h2 class="panel-title">今日重点</h2>
          <p class="teacher-tip-text">
            可在待办中规划跟进事项；手机端支持上传素材、查看学员与学情。
          </p>
          <div class="teacher-actions">
            <el-button type="primary" @click="router.push('/materials')">素材库</el-button>
            <el-button @click="router.push('/m/upload')">手机上传</el-button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/*
 * 宽屏策略（内容宽度见全局 .oc-page-shell / --oc-content-max）：
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
  align-items: start;
}

.todo-block {
  min-width: 0;
  height: 100%;
}

/* 待办卡片在宽屏列中拉满高度，避免左侧「半截空」 */
.todo-block :deep(.todo-panel) {
  height: 100%;
  box-sizing: border-box;
}

.panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  padding: 16px 18px 14px;
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

.count-tag {
  border-color: var(--oc-border, #e8e0d0);
  color: var(--oc-primary, #a16207);
  background: #f2e8d6;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.quick-item {
  appearance: none;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s, box-shadow 0.15s;
  font: inherit;
  color: inherit;
  width: 100%;
}

.quick-item:hover {
  border-color: var(--el-color-primary-light-5);
  background: #faf6ee;
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(41, 37, 36, 0.05);
}

.quick-item.is-primary {
  border-color: var(--el-color-primary-light-7);
  background: linear-gradient(145deg, #fffdf8, #f5e6c8);
}

.quick-item.is-primary .quick-icon {
  background: var(--oc-primary, #a16207);
  color: #fffdf8;
}

.quick-icon {
  width: 40px;
  height: 40px;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f0e6;
  color: var(--oc-primary, #a16207);
  flex-shrink: 0;
}

.quick-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.quick-title {
  font-size: 14px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.quick-desc {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
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

.teacher-tip {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.teacher-tip-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #f5e6c8, #f2e8d6);
  color: var(--oc-primary, #a16207);
  flex-shrink: 0;
}

.teacher-tip-text {
  margin: 6px 0 12px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--oc-muted, #78716c);
}

.teacher-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* ── ≥1100：顶栏欢迎+AI 并排；工作区 待办 | 右侧堆叠 ── */
@media (min-width: 1100px) {
  .top-band {
    grid-template-columns: minmax(0, 1.55fr) minmax(260px, 0.55fr);
    align-items: stretch;
  }

  .ai-panel {
    min-height: 100%;
  }

  .is-ops .work-grid {
    grid-template-columns: minmax(320px, 0.92fr) minmax(0, 1.28fr);
    gap: 16px;
  }

  /* 快捷 + 待处理 叠在右栏 */
  .is-ops .todo-block {
    grid-row: 1 / span 2;
  }

  .is-ops .quick-panel {
    grid-column: 2;
    grid-row: 1;
  }

  .is-ops .pending-panel {
    grid-column: 2;
    grid-row: 2;
  }

  .is-teacher .work-grid {
    grid-template-columns: minmax(0, 1.1fr) minmax(280px, 0.7fr);
  }

  .quick-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

/* ── ≥1480：真正的宽屏三列 ── */
@media (min-width: 1480px) {
  .top-band {
    grid-template-columns: minmax(0, 1.7fr) minmax(300px, 0.5fr);
    gap: 16px;
  }

  .hero-body {
    padding: 26px 32px;
    min-height: 120px;
  }

  .stats-grid {
    gap: 16px;
  }

  .stat-card {
    padding: 22px 24px;
  }

  .is-ops .work-grid {
    grid-template-columns: minmax(340px, 0.9fr) minmax(0, 1.15fr) minmax(300px, 0.85fr);
    gap: 16px;
  }

  .is-ops .todo-block {
    grid-row: 1;
    grid-column: 1;
  }

  .is-ops .quick-panel {
    grid-column: 2;
    grid-row: 1;
  }

  .is-ops .pending-panel {
    grid-column: 3;
    grid-row: 1;
  }

  .quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  /* 三列时快捷入口用 2×n，视觉更稳；超宽再 3 列 */
  .pending-list {
    max-height: min(62vh, 560px);
    overflow-y: auto;
    padding-right: 2px;
  }
}

/* ── ≥1720：超宽再拉开（内容 max-width 由 .oc-page-shell 统一） ── */
@media (min-width: 1720px) {
  .is-ops .work-grid {
    grid-template-columns: minmax(360px, 0.85fr) minmax(0, 1.2fr) minmax(320px, 0.9fr);
    gap: 18px;
  }

  .quick-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .hero-title {
    font-size: 1.9rem;
  }
}

/* ── 平板 / 窄屏 ── */
@media (max-width: 1099px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 991px) {
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
</style>
