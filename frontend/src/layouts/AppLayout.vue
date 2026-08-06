<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useBreakpoint } from '../composables/useBreakpoint'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'

/** 与 .aside width transition 对齐 */
const ASIDE_MS = 220
/** 折叠弹层选中后锁住 pointer，挡住 touch 残留 mouseenter 再打开 */
const POPPER_LOCK_MS = 420

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const brandMetaVisible = ref(true)
const drawer = ref(false)
const changePwdVisible = ref(false)
/** 折叠态选中子项后短暂锁侧栏交互，避免弹层闪回 */
const popperLock = ref(false)
const { isMobile } = useBreakpoint()

/** 侧栏菜单实例：用于强制关闭折叠弹层 */
const menuRef = ref<{ close: (index: string) => void } | null>(null)

const GROUP_MENU_INDEXES = ['crm', 'academic', 'finance', 'growth'] as const

let brandMetaTimer: ReturnType<typeof setTimeout> | null = null
let popperLockTimer: ReturnType<typeof setTimeout> | null = null

function clearBrandMetaTimer() {
  if (brandMetaTimer != null) {
    clearTimeout(brandMetaTimer)
    brandMetaTimer = null
  }
}

function clearPopperLockTimer() {
  if (popperLockTimer != null) {
    clearTimeout(popperLockTimer)
    popperLockTimer = null
  }
}

/** 强制关掉所有分组弹层（折叠态 EP 靠 hover 开关，touch 易残留） */
function closeCollapsedPoppers() {
  const menu = menuRef.value
  if (!menu?.close) return
  for (const idx of GROUP_MENU_INDEXES) {
    try {
      menu.close(idx)
    } catch {
      /* ignore */
    }
  }
}

/**
 * 折叠侧栏选中后：
 * 1) 立刻关弹层
 * 2) 短暂 pointer-events:none，挡住 touch 合成的 mouseenter 再 open
 * 3) showTimeout(默认 300) 后再关一次兜底
 */
function lockCollapsedPopper() {
  if (!collapsed.value) return
  popperLock.value = true
  closeCollapsedPoppers()
  void nextTick(() => closeCollapsedPoppers())
  clearPopperLockTimer()
  popperLockTimer = setTimeout(() => {
    closeCollapsedPoppers()
    popperLock.value = false
    popperLockTimer = null
  }, POPPER_LOCK_MS)
}

/** 宽度与 EP collapse 同步，避免两拍不同步导致箭头/弹层错乱 */
function toggleAside() {
  clearBrandMetaTimer()
  clearPopperLockTimer()
  popperLock.value = false
  const next = !collapsed.value
  collapsed.value = next
  if (next) {
    // 收起：文案立刻藏，不参与变窄挤压
    brandMetaVisible.value = false
    // 收起瞬间清掉可能还开着的 inline 子菜单状态
    void nextTick(() => closeCollapsedPoppers())
  } else {
    // 展开：等宽度到位再出 brand 文案
    brandMetaTimer = setTimeout(() => {
      brandMetaVisible.value = true
      brandMetaTimer = null
    }, ASIDE_MS)
  }
}

onUnmounted(() => {
  clearBrandMetaTimer()
  clearPopperLockTimer()
})

const roleLabel: Record<string, string> = {
  admin: '负责人',
  operator: '运营',
  teacher: '老师',
  cr: 'CR（班主任，学管师）',
  academic_manager: 'CR（班主任，学管师）',
}

const roleText = computed(
  () => roleLabel[auth.user?.role || ''] || auth.user?.role || '',
)

const displayName = computed(
  () => auth.user?.display_name || auth.user?.username || '用户',
)

const active = computed(() => {
  if (route.path.startsWith('/students')) return '/students'
  if (route.path.startsWith('/enrollments')) return '/enrollments'
  if (route.path.startsWith('/learning')) return '/learning'
  if (route.path.startsWith('/upload')) return '/upload'
  if (route.path.startsWith('/leads')) return '/leads' // 含 /leads/:id 详情
  if (route.path.startsWith('/knowledge')) return route.path
  if (route.path.startsWith('/copies')) return '/copies'
  if (route.path.startsWith('/posters')) return '/posters'
  if (route.path.startsWith('/materials')) return '/materials'
  if (route.path.startsWith('/templates')) return '/templates'
  // 教务 / 财务：新建/详情子页高亮父级列表
  if (route.path.startsWith('/academic/courses')) return '/academic/courses'
  if (route.path.startsWith('/academic/')) return route.path
  if (route.path.startsWith('/finance/orders')) return '/finance/orders'
  if (route.path.startsWith('/finance/')) return route.path
  return route.path
})

/** 老师手机底栏高亮（上传 / 素材 / 学生 / 课表 / 学情） */
const teacherTabActive = computed(() => {
  if (route.path.startsWith('/upload')) return '/upload'
  if (route.path.startsWith('/materials')) return '/materials'
  if (route.path.startsWith('/students')) return '/students'
  if (route.path.startsWith('/academic/schedule')) return '/academic/schedule'
  if (route.path.startsWith('/learning')) return '/learning'
  return ''
})

type MenuItem = { index: string; title: string; icon: string }
type MenuGroup = { type: 'group'; index: string; title: string; icon: string; children: MenuItem[] }
type MenuEntry = (MenuItem & { type?: 'item' }) | MenuGroup

const menus = computed((): MenuEntry[] => {
  const can = (code: string) => auth.hasPermission(code)

  // 纯老师默认包且无额外模块权限：精简菜单（手机友好）
  const hasOpsExtras =
    can('copies.use') ||
    can('posters.use') ||
    can('ai_image.use') ||
    can('knowledge.read') ||
    can('leads.read') ||
    can('finance.read') ||
    can('enrollments.manage') ||
    can('academic.write') ||
    can('users.manage')
  if (auth.isTeacher && !hasOpsExtras) {
    return [
      { index: '/', title: '工作台', icon: 'Odometer' },
      ...(can('materials.write') ? [{ index: '/upload', title: '上传素材', icon: 'Upload' }] : []),
      ...(can('materials.read') ? [{ index: '/materials', title: '素材', icon: 'Picture' }] : []),
      ...(can('students.read') ? [{ index: '/students', title: '学员', icon: 'Avatar' }] : []),
      // 默认 academic.read：老师可查看自己所带课表
      ...(can('academic.read')
        ? [{ index: '/academic/schedule', title: '我的课表', icon: 'Calendar' }]
        : []),
      ...(can('learning.write') ? [{ index: '/learning', title: '上传学情', icon: 'EditPen' }] : []),
    ]
  }

  const items: MenuEntry[] = [{ index: '/', title: '工作台', icon: 'Odometer' }]

  if (can('materials.write')) {
    items.push({ index: '/upload', title: '上传素材', icon: 'Upload' })
  }
  if (can('materials.read')) {
    items.push({ index: '/materials', title: '素材', icon: 'Picture' })
  }
  if (can('copies.use')) {
    items.push({ index: '/copies', title: '文案', icon: 'Document' })
  }
  if (can('posters.use')) {
    items.push({ index: '/posters', title: '海报', icon: 'PictureFilled' })
  }
  if (can('ai_image.use')) {
    items.push({ index: '/ai-image', title: 'GPT 生图', icon: 'MagicStick' })
  }

  if (can('leads.read')) {
    items.push({
      type: 'group',
      index: 'crm',
      title: '获客中心',
      icon: 'UserFilled',
      children: [{ index: '/leads', title: '线索跟进', icon: 'Phone' }],
    })
  }

  const academicChildren: MenuItem[] = []
  if (can('students.read')) {
    academicChildren.push({ index: '/students', title: '学员管理', icon: 'Avatar' })
  }
  if (can('academic.read')) {
    academicChildren.push(
      { index: '/academic/classes', title: '班级管理', icon: 'Collection' },
      { index: '/academic/schedule', title: '课表管理', icon: 'Calendar' },
      { index: '/academic/class-records', title: '上课记录', icon: 'Notebook' },
      { index: '/academic/courses', title: '课程管理', icon: 'Reading' },
      { index: '/academic/teachers', title: '老师管理', icon: 'User' },
    )
  }
  if (can('learning.write')) {
    academicChildren.push({ index: '/learning', title: '学情', icon: 'EditPen' })
  }
  if (academicChildren.length) {
    items.push({
      type: 'group',
      index: 'academic',
      title: '教务中心',
      icon: 'School',
      children: academicChildren,
    })
  }

  const financeChildren: MenuItem[] = []
  if (can('finance.read')) {
    financeChildren.push({ index: '/finance/orders', title: '订单管理', icon: 'Tickets' })
  }
  if (can('enrollments.manage')) {
    financeChildren.push({ index: '/enrollments', title: '报名/续费', icon: 'Ticket' })
  }
  if (can('finance.read')) {
    financeChildren.push(
      { index: '/finance/transactions', title: '收支明细', icon: 'List' },
      { index: '/finance/consumption', title: '课消记录', icon: 'DataLine' },
      { index: '/finance/recharge', title: '充值管理', icon: 'Coin' },
    )
  }
  if (can('finance.income_report')) {
    financeChildren.push({
      index: '/finance/income-report',
      title: '确认收入报表',
      icon: 'DataAnalysis',
    })
  }
  if (financeChildren.length) {
    items.push({
      type: 'group',
      index: 'finance',
      title: '财务中心',
      icon: 'Wallet',
      children: financeChildren,
    })
  }

  if (can('knowledge.read')) {
    items.push({
      type: 'group',
      index: 'growth',
      title: '成长中心',
      icon: 'Reading',
      children: [
        { index: '/knowledge/scripts', title: '沟通话术', icon: 'ChatDotRound' },
        { index: '/knowledge/objections', title: '异议处理', icon: 'Comment' },
        { index: '/knowledge/banned', title: '禁用词列表', icon: 'Warning' },
      ],
    })
  }
  if (can('templates.manage')) {
    items.push({ index: '/templates', title: '模板', icon: 'Files' })
  }
  if (can('office.use')) {
    items.push({ index: '/office', title: '综合办公表', icon: 'Grid' })
  }
  if (can('users.manage')) {
    items.push({ index: '/users', title: '用户管理', icon: 'User' })
  }
  return items
})

const brandTag = computed(() => (auth.isTeacher ? '老师端后台' : '管理后台'))

/** 老师在手机宽度下用底栏主导航（有额外授权时走完整侧栏） */
const showTeacherTabBar = computed(() => {
  if (!auth.isTeacher || !isMobile.value) return false
  const extra =
    auth.hasPermission('copies.use') ||
    auth.hasPermission('leads.read') ||
    auth.hasPermission('finance.read') ||
    auth.hasPermission('users.manage')
  return !extra
})

const teacherTabs: MenuItem[] = [
  { index: '/upload', title: '上传', icon: 'Upload' },
  { index: '/materials', title: '素材', icon: 'Picture' },
  { index: '/students', title: '学生', icon: 'User' },
  { index: '/academic/schedule', title: '课表', icon: 'Calendar' },
  { index: '/learning', title: '学情', icon: 'EditPen' },
]

/** 仅手动 push，不用 el-menu 的 router 属性，避免双跳 + EP 默认蓝底闪一下 */
function onSelect(index: string) {
  // 分组 index（crm / growth）不导航
  if (!index.startsWith('/')) return
  if (route.path !== index) void router.push(index)
  if (isMobile.value) drawer.value = false
  // 折叠态：选中子项后锁弹层，避免 pad/touch「关一下又弹回来」
  lockCollapsedPopper()
}

/** 锁定期内若 EP 又因 hover 打开分组，立刻关掉 */
function onSubMenuOpen(index: string) {
  if (!popperLock.value || !collapsed.value) return
  void nextTick(() => {
    try {
      menuRef.value?.close?.(index)
    } catch {
      /* ignore */
    }
  })
}

function logout() {
  auth.logout()
  router.replace('/login')
}

watch(isMobile, (v) => {
  if (!v) drawer.value = false
})

watch(
  () => route.path,
  () => {
    if (isMobile.value) drawer.value = false
    // .main 不随路由卸载，切换模块时先回顶；列表若需从详情恢复会在 load 后再滚回去
    requestAnimationFrame(() => {
      const main = document.querySelector('.layout .main') as HTMLElement | null
      if (main) main.scrollTop = 0
    })
  },
)
</script>

<template>
  <el-container class="layout">
    <el-aside
      v-if="!isMobile"
      :width="collapsed ? '64px' : '232px'"
      class="aside"
      :class="{ 'is-collapsed': collapsed, 'is-popper-lock': popperLock }"
    >
      <div class="brand" :class="{ 'is-collapsed': collapsed }">
        <img class="brand-logo" src="/brand-mark.png" alt="" width="36" height="36" />
        <div
          class="brand-meta"
          :class="{ 'is-hidden': !brandMetaVisible }"
          :aria-hidden="!brandMetaVisible"
        >
          <span class="brand-text">嘉壹启航</span>
          <span class="brand-tag">{{ brandTag }}</span>
        </div>
      </div>
      <!-- 仅菜单区滚动，brand 钉住；避免整栏 overflow 在 pad 上滑不动/乱滑 -->
      <div class="aside-scroll">
        <el-menu
          ref="menuRef"
          class="aside-menu"
          :default-active="active"
          :default-openeds="[]"
          :collapse="collapsed"
          :collapse-transition="false"
          :persistent="false"
          :show-timeout="0"
          :hide-timeout="150"
          background-color="transparent"
          text-color="#e7e5e4"
          active-text-color="#f5e6c8"
          @select="onSelect"
          @open="onSubMenuOpen"
        >
          <template v-for="m in menus" :key="m.index">
            <el-sub-menu v-if="m.type === 'group'" :index="m.index" popper-class="oc-aside-popper">
              <template #title>
                <el-icon><component :is="m.icon" /></el-icon>
                <span>{{ m.title }}</span>
              </template>
              <el-menu-item v-for="c in m.children" :key="c.index" :index="c.index">
                <el-icon><component :is="c.icon" /></el-icon>
                <span>{{ c.title }}</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item v-else :index="m.index">
              <el-icon><component :is="m.icon" /></el-icon>
              <span>{{ m.title }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </div>
    </el-aside>

    <el-drawer
      v-model="drawer"
      direction="ltr"
      size="240px"
      :with-header="false"
      :resizable="false"
      :show-close="false"
      modal-class="nav-drawer-modal"
      class="nav-drawer"
    >
      <div class="brand drawer-brand">
        <img class="brand-logo" src="/brand-mark.png" alt="" width="36" height="36" />
        <div class="brand-meta">
          <span class="brand-text">嘉壹启航</span>
          <span class="brand-tag">{{ brandTag }}</span>
        </div>
      </div>
      <el-menu
        class="aside-menu"
        :default-active="active"
        :default-openeds="[]"
        background-color="transparent"
        text-color="#e7e5e4"
        active-text-color="#f5e6c8"
        @select="onSelect"
      >
        <template v-for="m in menus" :key="m.index">
          <el-sub-menu v-if="m.type === 'group'" :index="m.index">
            <template #title>
              <el-icon><component :is="m.icon" /></el-icon>
              <span>{{ m.title }}</span>
            </template>
            <el-menu-item v-for="c in m.children" :key="c.index" :index="c.index">
              <el-icon><component :is="c.icon" /></el-icon>
              <span>{{ c.title }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="m.index">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ m.title }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-drawer>

    <el-container class="content-wrap" :class="{ 'has-teacher-tabs': showTeacherTabBar }">
      <el-header class="header">
        <el-button v-if="isMobile" text class="icon-btn" @click="drawer = true">
          <el-icon><Menu /></el-icon>
        </el-button>
        <el-button v-else text class="icon-btn" @click="toggleAside">
          <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </el-button>
        <button
          v-if="showTeacherTabBar"
          type="button"
          class="header-home"
          @click="onSelect('/')"
        >
          工作台
        </button>
        <div class="spacer" />
        <el-dropdown>
          <span class="user-trigger">
            <el-avatar :size="32" class="user-avatar">{{ displayName.slice(0, 1) }}</el-avatar>
            <span class="user-meta">
              <span class="user-name">{{ displayName }}</span>
              <span v-if="roleText" class="user-role">{{ roleText }}</span>
            </span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="changePwdVisible = true">修改密码</el-dropdown-item>
              <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <KeepAlive include="LeadListView" :max="1">
            <component :is="Component" />
          </KeepAlive>
        </router-view>
      </el-main>

      <!-- 老师 WAP：底栏（与侧栏能力对齐） -->
      <nav v-if="showTeacherTabBar" class="teacher-tabbar" aria-label="老师主导航">
        <button
          v-for="tab in teacherTabs"
          :key="tab.index"
          type="button"
          class="teacher-tab"
          :class="{ 'is-active': teacherTabActive === tab.index }"
          @click="onSelect(tab.index)"
        >
          <el-icon :size="20"><component :is="tab.icon" /></el-icon>
          <span>{{ tab.title }}</span>
        </button>
      </nav>
    </el-container>

    <ChangePasswordDialog v-model="changePwdVisible" />
  </el-container>
</template>

<style scoped>
.layout {
  width: 100%;
  max-width: 100%;
  /*
   * 壳层必须贴「动态可视高度」。
   * 纯 100vh 在 iPad / 平板浏览器里常大于可视区（地址栏、底栏），
   * 再叠加 overflow:hidden 就会底部被裁切，且整页无法下滚。
   */
  height: 100vh;
  height: 100dvh;
  max-height: 100vh;
  max-height: 100dvh;
  min-height: 0;
  overflow: hidden;
  background: transparent;
}

.aside {
  --oc-menu-active-bg: linear-gradient(
    90deg,
    rgba(161, 98, 7, 0.42) 0%,
    rgba(180, 140, 60, 0.22) 55%,
    rgba(180, 140, 60, 0.1) 100%
  );
  /* 彻底关掉 EP 默认蓝系 hover/active，避免点击时蓝直角闪一下 */
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #e7e5e4;
  --el-menu-hover-bg-color: rgba(245, 230, 200, 0.1);
  --el-menu-hover-text-color: #f5e6c8;
  --el-menu-active-color: #f5e6c8;
  --el-menu-border-color: transparent;
  --el-color-primary: #a16207;

  /* 列布局：brand 固定，.aside-scroll 独自滚动（盖掉 EP .el-aside{overflow:auto}） */
  position: relative;
  top: auto;
  align-self: stretch;
  display: flex !important;
  flex-direction: column;
  height: 100% !important;
  max-height: 100%;
  min-height: 0;
  overflow: hidden !important;
  flex-shrink: 0;
  z-index: 30;
  background: linear-gradient(90deg, #25211f 0%, #2c2825 100%);
  color: var(--oc-sidebar-text, #e7e5e4);
  transition: width 0.22s cubic-bezier(0.4, 0, 0.2, 1);
  border-right: 1px solid rgba(245, 230, 200, 0.14);
  box-shadow: inset -1px 0 0 rgba(161, 98, 7, 0.18);
}

/* 选中折叠子项后短暂锁交互，防止 touch 残留 hover 把弹层再打开 */
.aside.is-popper-lock :deep(.el-sub-menu),
.aside.is-popper-lock :deep(.el-menu-item) {
  pointer-events: none !important;
}

.aside-scroll {
  flex: 1 1 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
  overscroll-behavior: contain;
  /* pad 细滚动条，不占太多宽度 */
  scrollbar-width: thin;
  scrollbar-color: rgba(245, 230, 200, 0.28) transparent;
}

.aside-scroll::-webkit-scrollbar {
  width: 4px;
}

.aside-scroll::-webkit-scrollbar-thumb {
  background: rgba(245, 230, 200, 0.28);
  border-radius: 4px;
}

.aside-scroll::-webkit-scrollbar-track {
  background: transparent;
}

.aside-menu {
  border-right: none;
  width: 100%;
  min-height: 100%;
  box-sizing: border-box;
}

.aside :deep(.el-menu),
.nav-drawer :deep(.el-menu) {
  border-right: none;
  background: transparent !important;
  padding: 8px 0 14px;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(245, 230, 200, 0.1);
  --el-menu-active-color: #f5e6c8;
  --el-menu-text-color: #e7e5e4;
}

/*
 * 仅根 .aside-menu 不二次滚动（滚动在 .aside-scroll）。
 * 切勿对所有 .el-menu 设 overflow:visible !important —— 会盖住 EP 收起时的 overflow:hidden，
 * 导致「高度已折上、子项文字还挂在外面慢慢消失」。
 */
.aside :deep(.aside-menu.el-menu) {
  height: auto !important;
  overflow: visible !important;
}

/*
 * 分组子菜单收起/展开：高度与文字同步消失。
 * leave 略快并带 opacity，避免「壳先合上、字还在」。
 */
.aside :deep(.el-collapse-transition-enter-active),
.nav-drawer :deep(.el-collapse-transition-enter-active) {
  transition:
    max-height 0.2s cubic-bezier(0.22, 1, 0.36, 1),
    padding-top 0.2s cubic-bezier(0.22, 1, 0.36, 1),
    padding-bottom 0.2s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.16s ease !important;
  overflow: hidden !important;
}

.aside :deep(.el-collapse-transition-leave-active),
.nav-drawer :deep(.el-collapse-transition-leave-active) {
  transition:
    max-height 0.16s cubic-bezier(0.4, 0, 1, 1),
    padding-top 0.16s cubic-bezier(0.4, 0, 1, 1),
    padding-bottom 0.16s cubic-bezier(0.4, 0, 1, 1),
    opacity 0.1s linear !important;
  overflow: hidden !important;
}

.aside :deep(.el-collapse-transition-enter-from),
.nav-drawer :deep(.el-collapse-transition-enter-from) {
  opacity: 0;
}

.aside :deep(.el-collapse-transition-enter-to),
.nav-drawer :deep(.el-collapse-transition-enter-to) {
  opacity: 1;
}

.aside :deep(.el-collapse-transition-leave-from),
.nav-drawer :deep(.el-collapse-transition-leave-from) {
  opacity: 1;
}

.aside :deep(.el-collapse-transition-leave-to),
.nav-drawer :deep(.el-collapse-transition-leave-to) {
  opacity: 0;
}

.aside :deep(.el-menu-item),
.nav-drawer :deep(.el-menu-item) {
  position: relative;
  margin: 0 10px 4px;
  border-radius: 10px !important;
  height: 44px;
  line-height: 44px;
  box-sizing: border-box;
  font-weight: 500;
  letter-spacing: 0.02em;
  background-color: transparent !important;
  border: none !important;
  outline: none !important;
  transition: background 0.15s ease, color 0.15s ease;
}

.aside :deep(.el-menu-item:hover),
.aside :deep(.el-menu-item:focus),
.aside :deep(.el-menu-item:focus-visible),
.nav-drawer :deep(.el-menu-item:hover),
.nav-drawer :deep(.el-menu-item:focus) {
  background-color: rgba(245, 230, 200, 0.1) !important;
  background: rgba(245, 230, 200, 0.1) !important;
  color: #f5e6c8 !important;
  outline: none !important;
  box-shadow: none !important;
}

.aside :deep(.el-menu-item.is-active),
.nav-drawer :deep(.el-menu-item.is-active) {
  background: var(--oc-menu-active-bg) !important;
  background-color: transparent !important;
  color: #f5e6c8 !important;
  font-weight: 600;
  box-shadow: inset 0 0 0 1px rgba(245, 230, 200, 0.12);
  border-radius: 10px !important;
}

.aside :deep(.el-menu-item.is-active:hover),
.aside :deep(.el-menu-item.is-active:focus),
.nav-drawer :deep(.el-menu-item.is-active:hover) {
  background: var(--oc-menu-active-bg) !important;
  background-color: transparent !important;
  color: #f5e6c8 !important;
}

.aside :deep(.el-menu-item.is-active::before),
.nav-drawer :deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--oc-gold, #f5e6c8);
  z-index: 1;
}

.aside :deep(.el-menu-item .el-icon),
.nav-drawer :deep(.el-menu-item .el-icon),
.aside :deep(.el-sub-menu__title .el-icon),
.nav-drawer :deep(.el-sub-menu__title .el-icon) {
  color: rgba(245, 230, 200, 0.72);
  font-size: 18px;
  width: 1.2em;
  flex-shrink: 0;
}

.aside :deep(.el-menu-item.is-active .el-icon),
.nav-drawer :deep(.el-menu-item.is-active .el-icon) {
  color: var(--oc-gold, #f5e6c8);
}

/* ── 收起：EP 标准 64px 轨，图标居中，强制藏箭头 ── */
.aside :deep(.el-menu--collapse) {
  width: 100% !important;
  padding: 8px 0 12px !important;
}

.aside :deep(.el-menu--collapse .el-menu-item),
.aside :deep(.el-menu--collapse .el-sub-menu__title) {
  margin: 0 8px 4px !important;
  padding: 0 !important;
  /* 与展开态同为 44px，避免折叠「变大」、展开「变小」 */
  height: 44px !important;
  line-height: 44px !important;
  border-radius: 10px !important;
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  background-color: transparent !important;
}

.aside :deep(.el-menu--collapse .el-sub-menu) {
  margin: 0 !important;
}

.aside :deep(.el-menu--collapse .el-tooltip__trigger),
.aside :deep(.el-menu--collapse .el-menu-tooltip__trigger) {
  display: flex !important;
  justify-content: center !important;
  align-items: center !important;
  width: 100% !important;
  height: 44px !important;
  padding: 0 !important;
  margin: 0 !important;
}

.aside :deep(.el-menu--collapse .el-menu-item .el-icon),
.aside :deep(.el-menu--collapse .el-sub-menu__title .el-icon) {
  margin: 0 !important;
  width: 20px !important;
  height: 20px !important;
  font-size: 18px !important;
}

/* 收起：文字、箭头全部藏死（含伪元素箭头） */
.aside :deep(.el-menu--collapse .el-menu-item > span),
.aside :deep(.el-menu--collapse .el-sub-menu__title > span),
.aside :deep(.el-menu--collapse .el-sub-menu__title span) {
  height: 0 !important;
  width: 0 !important;
  overflow: hidden !important;
  visibility: hidden !important;
  display: inline-block !important;
  margin: 0 !important;
  padding: 0 !important;
}

.aside :deep(.el-menu--collapse .el-sub-menu__icon-arrow),
.aside :deep(.el-menu--collapse .el-icon.el-sub-menu__icon-arrow),
.aside :deep(.el-menu--collapse .el-sub-menu__title .el-sub-menu__icon-arrow) {
  display: none !important;
  visibility: hidden !important;
  width: 0 !important;
  height: 0 !important;
  opacity: 0 !important;
  font-size: 0 !important;
  margin: 0 !important;
  padding: 0 !important;
  right: -999px !important;
}

.aside :deep(.el-menu--collapse .el-menu-item.is-active),
.aside :deep(.el-menu--collapse .el-menu-item.is-active:hover),
.aside :deep(.el-menu--collapse .el-menu-item.is-active:focus) {
  background: var(--oc-menu-active-bg) !important;
  background-color: transparent !important;
  border-radius: 10px !important;
  box-shadow: inset 0 0 0 1px rgba(245, 230, 200, 0.12);
}

.aside :deep(.el-menu--collapse .el-menu-item.is-active::before) {
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  height: auto;
  border-radius: 0 3px 3px 0;
  transform: none;
  background: var(--oc-gold, #f5e6c8);
}

.aside :deep(.el-menu--collapse .el-sub-menu.is-active > .el-sub-menu__title) {
  background: var(--oc-menu-active-bg) !important;
  border-radius: 10px !important;
}

/* ── 子菜单标题（展开态） ── */
.aside :deep(.el-sub-menu__title),
.nav-drawer :deep(.el-sub-menu__title) {
  position: relative;
  display: flex;
  align-items: center;
  margin: 0 10px 4px;
  border-radius: 10px !important;
  height: 44px;
  line-height: 1;
  box-sizing: border-box;
  padding-right: 36px !important;
  font-weight: 500;
  color: #e7e5e4 !important;
  background-color: transparent !important;
  outline: none !important;
}

.aside :deep(.el-sub-menu__title:hover),
.aside :deep(.el-sub-menu__title:focus),
.nav-drawer :deep(.el-sub-menu__title:hover) {
  background: rgba(245, 230, 200, 0.1) !important;
  background-color: rgba(245, 230, 200, 0.1) !important;
  color: #f5e6c8 !important;
}

.aside :deep(.el-sub-menu__title .el-icon),
.nav-drawer :deep(.el-sub-menu__title .el-icon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.aside :deep(.el-sub-menu .el-menu--inline),
.nav-drawer :deep(.el-sub-menu .el-menu--inline) {
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  /* 收起动画依赖 overflow:hidden 裁切文字，必须 !important 压过其它规则 */
  overflow: hidden !important;
}

.aside :deep(.el-sub-menu .el-menu--inline .el-menu-item),
.nav-drawer :deep(.el-sub-menu .el-menu--inline .el-menu-item) {
  min-width: auto;
  height: 40px;
  line-height: 40px;
  margin: 0 10px 2px !important;
  padding-left: 48px !important;
  font-size: 13px;
  border-radius: 10px !important;
}

.aside :deep(.el-sub-menu__icon-arrow),
.nav-drawer :deep(.el-sub-menu__icon-arrow) {
  position: absolute !important;
  top: 0 !important;
  bottom: 0 !important;
  right: 12px !important;
  left: auto !important;
  width: 12px !important;
  height: 12px !important;
  margin: auto 0 !important;
  transform: none !important;
  transition: transform 0.2s ease;
  color: rgba(245, 230, 200, 0.55) !important;
}

.aside :deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-sub-menu__icon-arrow),
.nav-drawer :deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-sub-menu__icon-arrow) {
  transform: rotate(180deg) !important;
}

/* ── Brand ── */
.brand {
  --oc-topbar-h: 58px;
  --oc-brand-pad-x: 14px;
  height: var(--oc-topbar-h);
  min-height: var(--oc-topbar-h);
  max-height: var(--oc-topbar-h);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  padding: 0 var(--oc-brand-pad-x);
  color: var(--oc-gold, #f5e6c8);
  border-bottom: 1px solid rgba(245, 230, 200, 0.12);
  box-sizing: border-box;
  background: transparent;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}

.brand.is-collapsed {
  /* 64px 轨：pad 14 + logo 36 + 14，与展开同左缘，不横跳 */
  justify-content: flex-start;
  padding: 0 var(--oc-brand-pad-x);
  gap: 0;
}

.brand-logo {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: cover;
  background: #fff;
  transition: none;
  box-shadow:
    0 0 0 2px rgba(245, 230, 200, 0.28),
    0 4px 12px rgba(0, 0, 0, 0.25);
}

.brand-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  transition: none;
}

.brand-meta.is-hidden {
  position: absolute;
  width: 0;
  height: 0;
  margin: 0;
  padding: 0;
  opacity: 0;
  visibility: hidden;
  overflow: hidden;
  pointer-events: none;
  flex: none;
}

.brand-text {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-weight: 700;
  letter-spacing: 0.06em;
  font-size: 15px;
  line-height: 1.2;
}

.brand-tag {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: rgba(245, 230, 200, 0.55);
}

.drawer-brand {
  height: 58px;
  min-height: 58px;
  max-height: 58px;
  padding: 0 16px;
  box-sizing: border-box;
  background: #2c2825;
  color: var(--oc-gold, #f5e6c8);
  border-bottom: 1px solid rgba(245, 230, 200, 0.12);
}

.content-wrap {
  position: relative;
  min-width: 0;
  width: 100%;
  flex: 1;
  /* 吃满 .layout，勿再写死 100vh（Pad 上会比可视区更高） */
  height: 100%;
  max-height: 100%;
  min-height: 0;
  overflow: hidden;
  background: transparent;
  display: flex;
  flex-direction: column;
}

.header {
  --oc-topbar-h: 58px;
  --el-header-height: 58px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.92) 0%, rgba(250, 246, 238, 0.88) 100%);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(232, 224, 208, 0.85);
  height: var(--oc-topbar-h) !important;
  min-height: var(--oc-topbar-h);
  max-height: var(--oc-topbar-h);
  padding: 0 16px;
  box-sizing: border-box;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.6) inset;
  position: sticky;
  top: 0;
  z-index: 50;
}

.icon-btn {
  color: var(--oc-ink, #44403c);
  border-radius: 10px;
}

.icon-btn:hover {
  background: rgba(161, 98, 7, 0.08) !important;
  color: var(--oc-primary, #a16207);
}

.spacer {
  flex: 1;
}

.header-home {
  margin-left: 4px;
  border: none;
  background: transparent;
  color: var(--oc-primary, #a16207);
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 8px;
}

.header-home:hover {
  background: rgba(161, 98, 7, 0.08);
}

.content-wrap.has-teacher-tabs .main {
  padding-bottom: 72px;
}

.teacher-tabbar {
  position: sticky;
  bottom: 0;
  z-index: 40;
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  min-height: 56px;
  padding: 4px 0 calc(4px + env(safe-area-inset-bottom, 0px));
  background: var(--oc-card, #fffdf8);
  border-top: 1px solid var(--oc-border, #e8e0d0);
  flex-shrink: 0;
}

.teacher-tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: none;
  background: transparent;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
  cursor: pointer;
  padding: 6px 0;
  min-height: 52px;
}

.teacher-tab.is-active {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  color: var(--oc-ink, #44403c);
  padding: 6px 12px 6px 6px;
  border-radius: 999px;
  border: 1px solid rgba(232, 224, 208, 0.95);
  background: rgba(255, 253, 248, 0.9);
  box-shadow: 0 2px 8px rgba(41, 37, 36, 0.04);
  transition:
    border-color 0.15s,
    box-shadow 0.15s;
  outline: none;
}

.user-trigger:hover {
  border-color: #dbbf94;
  box-shadow: 0 4px 12px rgba(161, 98, 7, 0.08);
}

.user-avatar {
  background: linear-gradient(145deg, #c9a066, #a16207);
  color: #fffdf8;
  font-size: 13px;
  font-weight: 700;
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.25);
}

.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.2;
  padding-right: 2px;
}

.user-name {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.user-role {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
  margin-top: 2px;
}

.main {
  /* flex-basis:0 才能在列 flex 里真正收缩，否则内容把壳撑破后 overflow 形同虚设 */
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
  height: auto;
  width: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  touch-action: pan-y;
  padding: 18px 20px;
  overscroll-behavior: contain;
  background: transparent;
  box-sizing: border-box;
  /* 桌面：主区自管滚动时预留槽，避免出现滚动条时内容右跳 */
  scrollbar-gutter: stable;
}

@media (max-width: 991px) {
  .main {
    /*
     * Windows / DevTools 经典滚动条只吃右侧宽度，会显得「右边距更大」。
     * both-edges：左右各留同等槽位，内容视觉居中对称。
     * pad（768–991）与手机一样走主区滚动，勿依赖 body 滚动。
     */
    padding: 14px 12px;
    overflow-x: hidden;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    touch-action: pan-y;
    scrollbar-gutter: stable both-edges;
    scrollbar-width: thin;
  }

  .main::-webkit-scrollbar {
    width: 4px;
  }

  .main::-webkit-scrollbar-thumb {
    background: rgba(120, 113, 108, 0.35);
    border-radius: 4px;
  }

  .main::-webkit-scrollbar-track {
    background: transparent;
  }
}

@media (max-width: 767px) {
  .user-meta {
    display: none;
  }

  .user-trigger {
    padding: 4px;
  }

  .main {
    padding: 10px;
    overflow-x: hidden;
    overflow-y: auto;
    flex: 1 1 0;
    min-height: 0;
    -webkit-overflow-scrolling: touch;
    touch-action: pan-y;
    scrollbar-gutter: stable both-edges;
    scrollbar-width: thin;
  }

  .header {
    padding: 0 8px;
    position: relative;
    top: auto;
  }
}
</style>

<style>
/* drawer / 折叠子弹层 teleports 到 body，必须非 scoped */
.nav-drawer {
  --oc-menu-active-bg: linear-gradient(
    90deg,
    rgba(161, 98, 7, 0.42) 0%,
    rgba(180, 140, 60, 0.22) 55%,
    rgba(180, 140, 60, 0.1) 100%
  );
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(245, 230, 200, 0.1);
  --el-menu-active-color: #f5e6c8;
  --el-color-primary: #a16207;
  /* 盖掉 EP 默认浅色底，否则右侧会透出一条「白边」 */
  --el-drawer-bg-color: #2c2825;
  --el-bg-color: #2c2825;
}

/*
 * 移动端抽屉右侧白边根因：
 * 1) EP 默认 --el-drawer-bg-color / box-shadow-dark 偏浅，与遮罩交界发白
 * 2) 深色面板与半透明 mask 抗锯齿会在右缘留 1px 亮线
 * 处理：同色铺满 + 去掉浅阴影 + 右缘深色封边条盖住缝
 */
.el-overlay.is-drawer.nav-drawer-modal,
.el-overlay.el-modal-drawer.nav-drawer-modal {
  background-color: rgba(41, 37, 36, 0.55) !important;
}

.el-overlay.is-drawer .el-drawer.nav-drawer,
.el-overlay .el-drawer.nav-drawer,
.el-drawer.nav-drawer.ltr,
.el-drawer.nav-drawer.open,
.nav-drawer.el-drawer {
  background: #2c2825 !important;
  background-color: #2c2825 !important;
  border: none !important;
  border-right: none !important;
  outline: none !important;
  /* 禁止 EP 默认 el-box-shadow-dark（多层浅阴影在深色边缘会发白） */
  box-shadow: none !important;
  /* 单独用深色投影，不发白 */
  filter: drop-shadow(6px 0 16px rgba(0, 0, 0, 0.4));
  overflow: visible !important;
}

/* 右缘封边：盖住抗锯齿亮线（比面板略探出 2px） */
.el-drawer.nav-drawer.ltr::after,
.nav-drawer.el-drawer.ltr::after {
  content: '';
  position: absolute;
  top: 0;
  right: -2px;
  bottom: 0;
  width: 4px;
  background: #2c2825;
  pointer-events: none;
  z-index: 5;
}

.nav-drawer .el-drawer__body,
.el-drawer.nav-drawer .el-drawer__body {
  padding: 0 !important;
  background: #2c2825 !important;
  background-color: #2c2825 !important;
  border: none !important;
  box-shadow: none !important;
  overflow-x: hidden !important;
  overflow-y: auto !important;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.nav-drawer .aside-menu {
  flex: 1 1 auto;
  min-height: 0;
}

.nav-drawer .el-drawer__header {
  display: none !important;
  margin: 0 !important;
  padding: 0 !important;
  border: none !important;
}

.nav-drawer .el-drawer__dragger {
  display: none !important;
}

/*
 * 收起侧栏 · 子菜单弹出层（图3 白底灰字问题）
 * popper-class="oc-aside-popper"
 */
.oc-aside-popper.el-popper,
.oc-aside-popper {
  background: #2c2825 !important;
  border: 1px solid rgba(245, 230, 200, 0.18) !important;
  border-radius: 12px !important;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35) !important;
  padding: 6px !important;
  min-width: 160px !important;
  overflow: hidden;
}

.oc-aside-popper .el-menu,
.oc-aside-popper .el-menu--popup {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
  min-width: 148px !important;
  box-shadow: none !important;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #e7e5e4;
  --el-menu-hover-bg-color: rgba(245, 230, 200, 0.12);
  --el-menu-hover-text-color: #f5e6c8;
  --el-menu-active-color: #f5e6c8;
  --el-color-primary: #a16207;
}

.oc-aside-popper .el-menu-item {
  height: 40px !important;
  line-height: 40px !important;
  margin: 2px 0 !important;
  padding: 0 14px !important;
  border-radius: 8px !important;
  color: #e7e5e4 !important;
  background: transparent !important;
  background-color: transparent !important;
}

.oc-aside-popper .el-menu-item:hover,
.oc-aside-popper .el-menu-item:focus {
  background: rgba(245, 230, 200, 0.12) !important;
  background-color: rgba(245, 230, 200, 0.12) !important;
  color: #f5e6c8 !important;
}

.oc-aside-popper .el-menu-item.is-active {
  background: linear-gradient(
    90deg,
    rgba(161, 98, 7, 0.42) 0%,
    rgba(180, 140, 60, 0.18) 100%
  ) !important;
  color: #f5e6c8 !important;
  font-weight: 600;
}

.oc-aside-popper .el-menu-item .el-icon {
  color: rgba(245, 230, 200, 0.7) !important;
  margin-right: 8px;
}

.oc-aside-popper .el-menu-item.is-active .el-icon {
  color: #f5e6c8 !important;
}

/* 箭头小三角 */
.oc-aside-popper .el-popper__arrow::before {
  background: #2c2825 !important;
  border: 1px solid rgba(245, 230, 200, 0.18) !important;
}

.content-wrap::before {
  content: '';
  position: absolute;
  pointer-events: none;
  z-index: 0;
  width: min(48vw, 420px);
  height: min(48vw, 420px);
  right: -10%;
  bottom: -18%;
  left: auto;
  border-radius: 50%;
  border: 1.5px solid rgba(161, 98, 7, 0.12);
  background: radial-gradient(circle, rgba(245, 230, 200, 0.35) 0%, transparent 65%);
  box-shadow: inset 0 0 0 28px rgba(255, 253, 248, 0.12);
}

.content-wrap::after {
  content: '';
  position: absolute;
  pointer-events: none;
  z-index: 0;
  width: min(34vw, 300px);
  height: min(34vw, 300px);
  right: -2%;
  bottom: -8%;
  left: auto;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.1);
  background: transparent;
}

.content-wrap > .header,
.content-wrap > .main,
.content-wrap > .teacher-tabbar {
  position: relative;
  z-index: 1;
}

.content-wrap > .teacher-tabbar {
  z-index: 40;
}
</style>
