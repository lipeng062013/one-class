<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useBreakpoint } from '../composables/useBreakpoint'
import { useAppMenus } from '../composables/useAppMenus'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'
import AppRail from '../components/AppRail.vue'
import AppTabBar, { type AppNavItem } from '../components/AppTabBar.vue'
import { canHistoryBackToParent } from '../composables/usePageBack'

/** 与 .aside width transition 对齐 */
const ASIDE_MS = 220
/** 折叠弹层选中后锁住 pointer，挡住 touch 残留 mouseenter 再打开 */
const POPPER_LOCK_MS = 420

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const { isApp, isPadPortrait, isPadLandscape, isNarrowDesktop } = useBreakpoint()
const {
  menus,
  flatMenuItems,
  displayName,
  roleText,
  brandTag,
} = useAppMenus()
const collapsed = ref(isNarrowDesktop.value)
const collapseWasManuallySet = ref(false)
const brandMetaVisible = ref(true)
/** PC 窄屏仍可用；WAP/Pad「更多」改为独立页面 /more，不再用侧栏抽屉 */
const drawer = ref(false)
const changePwdVisible = ref(false)
/** 折叠态选中子项后短暂锁侧栏交互，避免弹层闪回 */
const popperLock = ref(false)

/** 侧栏菜单实例：用于强制关闭折叠弹层 */
const menuRef = ref<{ close: (index: string) => void } | null>(null)

const GROUP_MENU_INDEXES = ['ops', 'crm', 'academic', 'finance', 'growth'] as const

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
  collapseWasManuallySet.value = true
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

const active = computed(() => {
  if (route.path === '/more' || route.path.startsWith('/more/')) return '/more'
  if (route.path.startsWith('/students')) return '/students'
  if (route.path.startsWith('/enrollments')) return '/enrollments'
  if (route.path.startsWith('/learning')) return '/learning'
  // 上传页归属素材模块，侧栏高亮「素材」
  if (route.path.startsWith('/upload')) return '/materials'
  if (route.path.startsWith('/leads')) return '/leads' // 含 /leads/:id 详情
  if (route.path.startsWith('/knowledge')) return route.path
  if (route.path.startsWith('/copies')) return '/copies'
  if (route.path.startsWith('/posters')) return '/posters'
  if (route.path.startsWith('/ai-image')) return '/ai-image'
  if (route.path.startsWith('/materials')) return '/materials'
  if (route.path.startsWith('/templates')) return '/templates'
  // 教务 / 财务：新建/详情子页高亮父级列表
  if (route.path.startsWith('/academic/courses')) return '/academic/courses'
  if (route.path.startsWith('/academic/')) return route.path
  if (route.path.startsWith('/finance/orders')) return '/finance/orders'
  if (route.path.startsWith('/finance/')) return route.path
  return route.path
})

const moreActive = computed(() => route.path === '/more' || route.path.startsWith('/more/'))

/**
 * App 详情/新建流程使用顶栏返回，并隐藏底部主导航，避免误触跳出当前任务。
 * value 是没有可用浏览历史时的兜底列表页。
 */
const appBackFallbacks: Record<string, string> = {
  upload: '/materials',
  'material-detail': '/materials',
  'copies-generate': '/copies',
  'copy-detail': '/copies',
  'posters-generate': '/posters',
  'lead-detail': '/leads',
  'student-detail': '/students',
  'enrollment-records': '/enrollments',
  'learning-new': '/learning',
  'academic-class-detail': '/academic/classes',
  'academic-class-record-detail': '/academic/class-records',
  'academic-courses-new': '/academic/courses',
  'academic-courses-edit': '/academic/courses',
  'finance-order-detail': '/finance/orders',
  'copy-template-detail': '/templates',
  'poster-template-detail': '/templates',
}

const appRouteTitles: Record<string, string> = {
  'material-detail': '素材详情',
  'copies-generate': '生成文案',
  'copy-detail': '文案详情',
  'posters-generate': '生成海报',
  'lead-detail': '线索详情',
  'student-detail': '学生详情',
  'enrollment-records': '最近登记',
  'learning-new': '上传学情',
  'academic-class-detail': '班级详情',
  'academic-class-record-detail': '点名详情',
  'academic-courses-new': '新建课程',
  'academic-courses-edit': '编辑课程',
  'finance-order-detail': '订单详情',
  'copy-template-detail': '文案模板详情',
  'poster-template-detail': '海报模板详情',
}

const appBackTarget = computed(() => appBackFallbacks[String(route.name || '')] || '')

/**
 * 手机 / Pad 的主导航：最多 4 个高频入口，完整菜单通过“更多”面板访问。
 * 导航只改变展示层，不改变现有权限和路由。
 */
const appPrimaryTabs = computed<AppNavItem[]>(() => {
  const can = (code: string) => auth.hasPermission(code)
  const home: AppNavItem = { index: '/', title: '工作台', icon: 'Odometer' }
  const preferred: AppNavItem[] = [home]

  if (auth.isTeacher) {
    if (can('academic.read')) preferred.push({ index: '/academic/schedule', title: '课表', icon: 'Calendar' })
    if (can('students.read')) preferred.push({ index: '/students', title: '学员', icon: 'Avatar' })
    if (can('learning.write')) preferred.push({ index: '/learning', title: '学情', icon: 'EditPen' })
  } else if (auth.isCR) {
    if (can('leads.read')) preferred.push({ index: '/leads', title: '线索', icon: 'Phone' })
    if (can('students.read')) preferred.push({ index: '/students', title: '学员', icon: 'Avatar' })
    if (can('academic.read')) preferred.push({ index: '/academic/schedule', title: '课表', icon: 'Calendar' })
  } else {
    if (can('leads.read')) preferred.push({ index: '/leads', title: '线索', icon: 'Phone' })
    if (can('students.read')) preferred.push({ index: '/students', title: '学员', icon: 'Avatar' })
    if (can('finance.read')) preferred.push({ index: '/finance/orders', title: '财务', icon: 'Wallet' })
    if (can('academic.read')) preferred.push({ index: '/academic/schedule', title: '教务', icon: 'School' })
  }

  const seen = new Set<string>()
  const result: AppNavItem[] = []
  for (const item of [...preferred, ...flatMenuItems.value]) {
    if (seen.has(item.index)) continue
    seen.add(item.index)
    result.push(item)
    if (result.length >= 4) break
  }
  return result
})

/** 手机与 Pad 竖屏使用底部主导航，Pad 横屏使用左侧图标轨。 */
const showAppBottomNav = computed(
  () => isApp.value && !isPadLandscape.value && !appBackTarget.value,
)
const showPadRail = computed(() => isPadLandscape.value)

const appPageTitle = computed(() => {
  if (route.path === '/') return '工作台'
  if (moreActive.value) return '更多'
  const routeTitle = appRouteTitles[String(route.name || '')]
  if (routeTitle) return routeTitle
  // 页面标题优先完整菜单文案；底栏“财务/学员”等短文案仅作为导航标签。
  const items = [...flatMenuItems.value, ...appPrimaryTabs.value]
  const matched = items.find((item) => {
    if (item.index === '/') return route.path === '/'
    return route.path === item.index || route.path.startsWith(`${item.index}/`)
  })
  return matched?.title || '嘉壹启航'
})

const drawerSize = computed(() => (isPadPortrait.value ? '320px' : '292px'))

const layoutVars = computed(() => ({
  '--oc-app-content-left': showPadRail.value
    ? '76px'
    : isApp.value
      ? '0px'
      : collapsed.value
        ? '64px'
        : '232px',
  '--oc-app-bottom-inset': showAppBottomNav.value
    ? 'calc(64px + env(safe-area-inset-bottom, 0px))'
    : '0px',
}))

function openAppMore() {
  // WAP/Pad：进「更多」整页；不再弹出左侧抽屉
  if (route.path !== '/more') void router.push('/more')
}

/** 仅详情/新建页顶栏返回；「更多」只走底部 Tab，顶部不再放菜单入口 */
function onAppHeaderLeft() {
  if (!appBackTarget.value) return
  const historyBack = window.history.state?.back
  if (
    typeof historyBack === 'string' &&
    canHistoryBackToParent(historyBack, appBackTarget.value)
  ) {
    router.back()
    return
  }
  // 直接打开深链或从其它模块进入时，不把当前任务继续压进历史栈。
  void router.replace(appBackTarget.value)
}

/** 仅手动 push，不用 el-menu 的 router 属性，避免双跳 + EP 默认蓝底闪一下 */
function onSelect(index: string) {
  // 分组 index（crm / growth）不导航
  if (!index.startsWith('/')) return
  if (route.path !== index) void router.push(index)
  if (isApp.value) drawer.value = false
  // 折叠态：选中子项后锁弹层，避免 pad/touch「关一下又弹回来」
  lockCollapsedPopper()
}

function onAppSelect(index: string) {
  if (index === '__more__') {
    openAppMore()
    return
  }
  onSelect(index)
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

function openChangePassword() {
  drawer.value = false
  changePwdVisible.value = true
}

function logout() {
  auth.logout()
  router.replace('/login')
}

watch(isApp, (v) => {
  if (!v) drawer.value = false
})

watch(isNarrowDesktop, (v) => {
  if (collapseWasManuallySet.value) return
  collapsed.value = v
  brandMetaVisible.value = !v
})

watch(
  () => route.path,
  () => {
    if (isApp.value) drawer.value = false
    // .main 不随路由卸载，切换模块时先回顶；列表若需从详情恢复会在 load 后再滚回去
    requestAnimationFrame(() => {
      const main = document.querySelector('.layout .main') as HTMLElement | null
      if (main) main.scrollTop = 0
    })
  },
)
</script>

<template>
  <el-container class="layout" :style="layoutVars">
    <el-aside
      v-if="!isApp"
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

    <!-- 仅非 App 保留（兼容旧逻辑）；WAP/Pad 的「更多」走 /more 整页 -->
    <el-drawer
      v-if="!isApp"
      v-model="drawer"
      direction="ltr"
      :size="drawerSize"
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
        <button type="button" class="drawer-close" aria-label="关闭导航" @click="drawer = false">
          <el-icon><Close /></el-icon>
        </button>
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
      <!-- 账号区：所有角色可改自己的密码；退出登录 -->
      <div class="drawer-account">
        <div class="drawer-account__who">
          <span class="drawer-account__avatar">{{ displayName.slice(0, 1) }}</span>
          <div class="drawer-account__meta">
            <span class="drawer-account__name">{{ displayName }}</span>
            <span v-if="roleText" class="drawer-account__role">{{ roleText }}</span>
          </div>
        </div>
        <div class="drawer-account__actions">
          <button type="button" class="drawer-account__btn" @click="openChangePassword">
            <el-icon><Lock /></el-icon>
            <span>修改密码</span>
          </button>
          <button type="button" class="drawer-account__btn is-danger" @click="logout">
            <el-icon><SwitchButton /></el-icon>
            <span>退出登录</span>
          </button>
        </div>
      </div>
    </el-drawer>

    <AppRail
      v-if="showPadRail"
      :items="appPrimaryTabs"
      :active="active"
      :more-active="moreActive"
      @select="onAppSelect"
      @more="openAppMore"
    />

    <el-container
      class="content-wrap"
      :class="{ 'is-app-shell': isApp, 'has-app-tabs': showAppBottomNav, 'has-pad-rail': showPadRail }"
    >
      <el-header
        class="header"
        :class="{
          'is-app-header': isApp,
          'has-back': isApp && Boolean(appBackTarget),
        }"
      >
        <!-- PC：折叠侧栏 -->
        <el-button
          v-if="!isApp"
          text
          class="icon-btn"
          :aria-label="collapsed ? '展开侧栏' : '收起侧栏'"
          @click="toggleAside"
        >
          <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </el-button>

        <!-- App：仅详情/新建显示返回；列表页不再占左侧菜单位 -->
        <el-button
          v-if="isApp && appBackTarget"
          text
          class="icon-btn header-back"
          aria-label="返回上一页"
          @click="onAppHeaderLeft"
        >
          <el-icon><Back /></el-icon>
        </el-button>

        <div class="header-title-wrap">
          <button
            v-if="isApp && route.path === '/'"
            type="button"
            class="header-home"
            @click="onSelect('/')"
          >
            {{ appPageTitle }}
          </button>
          <h1 v-else-if="isApp" class="app-page-title">{{ appPageTitle }}</h1>
        </div>

        <div class="spacer" />

        <el-dropdown trigger="click" placement="bottom-end">
          <span class="user-trigger" role="button" tabindex="0" aria-label="账号菜单">
            <el-avatar :size="isApp ? 34 : 32" class="user-avatar">
              {{ displayName.slice(0, 1) }}
            </el-avatar>
            <span v-if="!isApp" class="user-meta">
              <span class="user-name">{{ displayName }}</span>
              <span v-if="roleText" class="user-role">{{ roleText }}</span>
            </span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="openChangePassword">修改密码</el-dropdown-item>
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

      <AppTabBar
        v-if="showAppBottomNav"
        :items="appPrimaryTabs"
        :active="active"
        :more-active="moreActive"
        @select="onAppSelect"
        @more="openAppMore"
      />
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
  background: linear-gradient(135deg, #fffdf8 0%, #faf6ee 55%, #f5e6c8 120%);
  color: #6b4f25;
  border-bottom: 1px solid #e8e0d0;
}

.drawer-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin-left: auto;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.drawer-close:hover,
.drawer-close:focus-visible {
  background: rgba(161, 98, 7, 0.08);
  color: #8b5406;
  outline: none;
}

.drawer-account {
  flex: 0 0 auto;
  margin-top: auto;
  padding: 12px 14px calc(14px + env(safe-area-inset-bottom, 0px));
  border-top: 1px solid #e8e0d0;
  background: linear-gradient(180deg, rgba(250, 246, 238, 0.55) 0%, #faf6ee 100%);
}

.drawer-account__who {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  min-width: 0;
}

.drawer-account__avatar {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #c9a066;
  color: #fffdf8;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 0 0 2px rgba(161, 98, 7, 0.14);
}

.drawer-account__meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 2px;
}

.drawer-account__name {
  font-size: 14px;
  font-weight: 650;
  color: #44403c;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drawer-account__role {
  font-size: 12px;
  color: #78716c;
}

.drawer-account__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.drawer-account__btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 40px;
  padding: 0 10px;
  border: 1px solid #e8e0d0;
  border-radius: 10px;
  background: #fffdf8;
  color: #57534e;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.drawer-account__btn:hover,
.drawer-account__btn:focus-visible {
  background: rgba(161, 98, 7, 0.08);
  border-color: rgba(161, 98, 7, 0.28);
  color: #8b5406;
  outline: none;
}

.drawer-account__btn.is-danger {
  color: #b45309;
}

.drawer-account__btn.is-danger:hover,
.drawer-account__btn.is-danger:focus-visible {
  background: rgba(180, 83, 9, 0.08);
  border-color: rgba(180, 83, 9, 0.28);
  color: #9a3412;
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

.header-title-wrap {
  min-width: 0;
  display: flex;
  align-items: center;
}

.header-home {
  margin: 0;
  border: none;
  background: transparent;
  color: var(--oc-primary, #a16207);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  padding: 4px 0;
  border-radius: 8px;
  line-height: 1.2;
}

.header-home:hover {
  color: var(--oc-primary-hover, #86530a);
}

.app-page-title {
  min-width: 0;
  margin: 0;
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 17px;
  font-weight: 740;
  line-height: 1.2;
  letter-spacing: 0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-back {
  flex: 0 0 auto;
  margin-right: 2px;
}

.content-wrap.has-app-tabs .main {
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

@media (max-width: 1199px) {
  .content-wrap.is-app-shell {
    background:
      radial-gradient(ellipse 80% 42% at 50% -12%, rgba(245, 230, 200, 0.55), transparent 58%),
      linear-gradient(180deg, #faf6ee 0%, #f5efe3 100%);
  }

  .is-app-shell .header,
  .header.is-app-header {
    --oc-topbar-h: 52px;
    --el-header-height: 52px;
    gap: 8px;
    padding: 0 14px 0 16px;
    border-bottom: 1px solid rgba(181, 145, 83, 0.2);
    background: linear-gradient(180deg, #fffefb 0%, #faf6ee 100%);
    box-shadow: 0 4px 14px rgba(88, 60, 24, 0.06);
  }

  /* 无返回时：标题贴左，不再空一块菜单位 */
  .header.is-app-header:not(.has-back) {
    padding-left: 16px;
  }

  .header.is-app-header.has-back {
    padding-left: 6px;
  }

  .is-app-shell .header .icon-btn,
  .header.is-app-header .header-back {
    width: 40px;
    height: 40px;
    margin: 0;
    border-radius: 12px;
    color: #57534e;
  }

  .is-app-shell .header .icon-btn:hover,
  .is-app-shell .header .icon-btn:active,
  .header.is-app-header .header-back:hover,
  .header.is-app-header .header-back:active {
    background: rgba(161, 98, 7, 0.08) !important;
    color: #8b5406;
  }

  .header.is-app-header .header-title-wrap {
    flex: 1 1 auto;
    min-width: 0;
  }

  .header.is-app-header .spacer {
    display: none;
  }

  .header.is-app-header .app-page-title,
  .header.is-app-header .header-home {
    max-width: 100%;
    color: #3f3a34;
    font-size: 17px;
    font-weight: 760;
  }

  .header.is-app-header .header-home {
    color: #8b5406;
  }

  .header.is-app-header .user-trigger {
    flex: 0 0 auto;
    padding: 2px;
    border: 1px solid rgba(181, 145, 83, 0.28);
    border-radius: 999px;
    background: linear-gradient(180deg, #fffefb, #f5e6c8);
    box-shadow: 0 2px 8px rgba(88, 60, 24, 0.06);
  }

  .header.is-app-header .user-avatar {
    background: linear-gradient(145deg, #d4b483, #a16207);
    color: #fffdf8;
    box-shadow: none;
  }

  .main {
    /*
     * Windows / DevTools 经典滚动条只吃右侧宽度，会显得「右边距更大」。
     * both-edges：左右各留同等槽位，内容视觉居中对称。
     * pad（768–991）与手机一样走主区滚动，勿依赖 body 滚动。
     */
    padding: 16px;
    overflow-x: hidden;
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    touch-action: pan-y;
    scrollbar-gutter: stable both-edges;
    scrollbar-width: thin;
    background: transparent;
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
    padding: 12px;
    overflow-x: hidden;
    overflow-y: auto;
    flex: 1 1 0;
    min-height: 0;
    -webkit-overflow-scrolling: touch;
    touch-action: pan-y;
    scrollbar-gutter: stable both-edges;
    scrollbar-width: thin;
  }

  .header:not(.is-app-header) {
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
    rgba(245, 230, 200, 0.9) 0%,
    rgba(250, 246, 238, 0.82) 100%
  );
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: rgba(161, 98, 7, 0.08);
  --el-menu-active-color: #8b5406;
  --el-color-primary: #a16207;
  --el-drawer-bg-color: #fffdf8;
  --el-bg-color: #fffdf8;
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
  background: linear-gradient(180deg, #fffdf9 0%, #faf6ee 100%) !important;
  background-color: #fffdf8 !important;
  border: none !important;
  border-right: none !important;
  outline: none !important;
  /* 禁止 EP 默认 el-box-shadow-dark（多层浅阴影在深色边缘会发白） */
  box-shadow: none !important;
  /* 单独用深色投影，不发白 */
  filter: drop-shadow(6px 0 16px rgba(88, 60, 24, 0.18));
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
  background: #e4d3b3;
  pointer-events: none;
  z-index: 5;
}

.nav-drawer .el-drawer__body,
.el-drawer.nav-drawer .el-drawer__body {
  padding: 0 !important;
  background: linear-gradient(180deg, #fffdf9 0%, #faf6ee 100%) !important;
  background-color: #fffdf8 !important;
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

.nav-drawer .drawer-account {
  flex: 0 0 auto;
  margin-top: auto;
}

.nav-drawer .el-menu {
  --el-menu-text-color: #57534e;
  --el-menu-hover-bg-color: rgba(161, 98, 7, 0.08);
  --el-menu-active-color: #8b5406;
}

.nav-drawer .el-menu-item,
.nav-drawer .el-sub-menu__title {
  color: #57534e !important;
}

.nav-drawer .el-menu-item:hover,
.nav-drawer .el-sub-menu__title:hover {
  background: rgba(161, 98, 7, 0.08) !important;
  color: #8b5406 !important;
}

.nav-drawer .el-menu-item.is-active {
  color: #8b5406 !important;
  box-shadow: inset 0 0 0 1px rgba(161, 98, 7, 0.14);
}

.nav-drawer .el-menu-item .el-icon,
.nav-drawer .el-sub-menu__title .el-icon {
  color: #9a7440 !important;
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
  background: #fffdf8 !important;
  border: 1px solid #e1cfad !important;
  border-radius: 8px !important;
  box-shadow: 0 12px 32px rgba(88, 60, 24, 0.16) !important;
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
  --el-menu-text-color: #57534e;
  --el-menu-hover-bg-color: rgba(161, 98, 7, 0.08);
  --el-menu-hover-text-color: #8b5406;
  --el-menu-active-color: #8b5406;
  --el-color-primary: #a16207;
}

.oc-aside-popper .el-menu-item {
  height: 40px !important;
  line-height: 40px !important;
  margin: 2px 0 !important;
  padding: 0 14px !important;
  border-radius: 8px !important;
  color: #57534e !important;
  background: transparent !important;
  background-color: transparent !important;
}

.oc-aside-popper .el-menu-item:hover,
.oc-aside-popper .el-menu-item:focus {
  background: rgba(161, 98, 7, 0.08) !important;
  background-color: rgba(161, 98, 7, 0.08) !important;
  color: #8b5406 !important;
}

.oc-aside-popper .el-menu-item.is-active {
  background: linear-gradient(
    90deg,
    rgba(245, 230, 200, 0.9) 0%,
    rgba(250, 246, 238, 0.8) 100%
  ) !important;
  color: #8b5406 !important;
  font-weight: 600;
}

.oc-aside-popper .el-menu-item .el-icon {
  color: #9a7440 !important;
  margin-right: 8px;
}

.oc-aside-popper .el-menu-item.is-active .el-icon {
  color: #8b5406 !important;
}

/* 箭头小三角 */
.oc-aside-popper .el-popper__arrow::before {
  background: #fffdf8 !important;
  border: 1px solid #e1cfad !important;
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

.content-wrap.is-app-shell::before,
.content-wrap.is-app-shell::after {
  display: none;
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
.content-wrap > .teacher-tabbar,
.content-wrap > .app-tabbar {
  position: relative;
  z-index: 1;
}

.content-wrap > .teacher-tabbar {
  z-index: 40;
}

.content-wrap > .app-tabbar {
  position: sticky;
  bottom: 0;
  z-index: 40;
  flex-shrink: 0;
}

/*
 * 部分业务弹窗没有 teleport 到 body，而是保留在 .main 内。
 * .main 默认层级为 1，移动端底部导航层级为 40，因而会盖住弹窗底部按钮。
 * 仅在主内容区存在可见 Element Plus 遮罩时提升层级，让弹窗完整覆盖应用导航；
 * 关闭弹窗后立即恢复原层级，不改变普通页面的导航与滚动行为。
 */
@media (max-width: 1199px) {
  .content-wrap.is-app-shell > .main:has(.el-overlay:not([style*='display: none'])) {
    z-index: 50;
  }
}

/* App 顶栏已经承担页面标题；内容区只保留副标题、筛选与业务操作。 */
.content-wrap.is-app-shell .main .page-toolbar > .el-page-header,
.content-wrap.is-app-shell .main .toolbar-title-block > .el-page-header.is-title-only {
  display: none;
}

.content-wrap.is-app-shell .main .page-toolbar:has(> .el-page-header.is-title-only) {
  justify-content: flex-end;
}

/* 生成/编辑类页面仍保留了 PC 专用 .page-head 容器。
 * App 顶栏已经提供返回与页面标题，移动端隐藏这行可避免重复占位，
 * 同时不影响 PC 端的原有页面头部。 */
.content-wrap.is-app-shell .main .page-head:has(> .el-page-header) {
  display: none;
}
</style>
