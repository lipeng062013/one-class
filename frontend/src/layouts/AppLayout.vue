<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useBreakpoint } from '../composables/useBreakpoint'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const drawer = ref(false)
const changePwdVisible = ref(false)
const { isMobile } = useBreakpoint()

const active = computed(() => {
  if (route.path.startsWith('/students')) return '/students'
  if (route.path.startsWith('/leads')) return '/leads'
  if (route.path.startsWith('/knowledge')) return route.path
  return route.path
})

type MenuItem = { index: string; title: string; icon: string }
type MenuGroup = { type: 'group'; index: string; title: string; icon: string; children: MenuItem[] }
type MenuEntry = (MenuItem & { type?: 'item' }) | MenuGroup

const menus = computed((): MenuEntry[] => {
  const crmChildren: MenuItem[] = [{ index: '/leads', title: '线索跟进', icon: 'Phone' }]
  // 学生信息：运营不可见
  if (auth.isAdmin) {
    crmChildren.push({ index: '/students', title: '学生信息', icon: 'Avatar' })
  }

  const items: MenuEntry[] = [
    { index: '/', title: '工作台', icon: 'Odometer' },
    { index: '/materials', title: '素材', icon: 'Picture' },
    { index: '/copies', title: '文案', icon: 'Document' },
    { index: '/posters', title: '海报', icon: 'PictureFilled' },
    {
      type: 'group',
      index: 'crm',
      title: '获客与学员',
      icon: 'UserFilled',
      children: crmChildren,
    },
    {
      type: 'group',
      index: 'growth',
      title: '成长中心',
      icon: 'Reading',
      children: [
        { index: '/knowledge/scripts', title: '沟通话术', icon: 'ChatDotRound' },
        { index: '/knowledge/objections', title: '异议处理', icon: 'Comment' },
        { index: '/knowledge/banned', title: '禁用词列表', icon: 'Warning' },
      ],
    },
    { index: '/templates', title: '模板', icon: 'Files' },
    { index: '/office', title: '综合办公表', icon: 'Grid' },
  ]
  if (auth.isAdmin) {
    items.push({ index: '/users', title: '用户管理', icon: 'User' })
  }
  return items
})

function onSelect(index: string) {
  router.push(index)
  if (isMobile.value) drawer.value = false
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
  },
)
</script>

<template>
  <el-container class="layout">
    <el-aside v-if="!isMobile" :width="collapsed ? '64px' : '220px'" class="aside">
      <div class="brand" :class="{ 'is-collapsed': collapsed }">
        <img class="brand-logo" src="/brand-mark.png" alt="" width="32" height="32" />
        <span v-if="!collapsed" class="brand-text">嘉壹启航</span>
      </div>
      <el-menu
        :default-active="active"
        :default-openeds="[]"
        :collapse="collapsed"
        router
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
    </el-aside>

    <el-drawer v-model="drawer" direction="ltr" size="220px" :with-header="false" class="nav-drawer">
      <div class="brand drawer-brand">
        <img class="brand-logo" src="/brand-mark.png" alt="" width="32" height="32" />
        <span class="brand-text">嘉壹启航</span>
      </div>
      <el-menu
        :default-active="active"
        :default-openeds="[]"
        router
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

    <el-container class="content-wrap">
      <el-header class="header">
        <el-button v-if="isMobile" text class="icon-btn" @click="drawer = true">
          <el-icon><Menu /></el-icon>
        </el-button>
        <el-button v-else text class="icon-btn" @click="collapsed = !collapsed">
          <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </el-button>
        <div class="spacer" />
        <el-dropdown>
          <span class="user-trigger">
            <el-avatar :size="28" class="user-avatar">{{ auth.user?.display_name?.[0] || 'U' }}</el-avatar>
            <span class="user-name">{{ auth.user?.display_name }}（{{ auth.user?.role }}）</span>
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
        <router-view />
      </el-main>
    </el-container>

    <ChangePasswordDialog v-model="changePwdVisible" />
  </el-container>
</template>

<style scoped>
.layout {
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  background: var(--oc-page, #faf8f3);
}

/* 侧栏固定视口高度：主区滚动时侧栏始终可见（展开/折叠均适用） */
.aside {
  position: sticky;
  top: 0;
  align-self: stretch;
  height: 100vh !important;
  max-height: 100vh;
  overflow-x: hidden;
  overflow-y: auto;
  flex-shrink: 0;
  z-index: 30;
  background: var(--oc-sidebar, #292524);
  color: var(--oc-sidebar-text, #e7e5e4);
  transition: width 0.2s;
  border-right: 1px solid rgba(245, 230, 200, 0.08);
  overscroll-behavior: contain;
}

.aside :deep(.el-menu),
.nav-drawer :deep(.el-menu) {
  border-right: none;
  background: transparent;
  /* 用 padding 做整体间距，避免子项 margin 干扰展开高度计算 */
  padding: 6px 0 10px;
}

/*
 * 子菜单折叠：只动画 max-height，关掉 padding 过渡（EP 默认两者一起动，收尾易抖）。
 * 缓动偏软，展开稍长、收起稍短，避免「太硬」又尽量不弹。
 */
.aside :deep(.el-collapse-transition-enter-active),
.nav-drawer :deep(.el-collapse-transition-enter-active) {
  transition: max-height 0.28s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.aside :deep(.el-collapse-transition-leave-active),
.nav-drawer :deep(.el-collapse-transition-leave-active) {
  transition: max-height 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.aside :deep(.el-menu-item),
.nav-drawer :deep(.el-menu-item) {
  margin: 0 8px;
  border-radius: 8px;
  height: 44px;
  line-height: 44px;
  box-sizing: border-box;
  font-weight: 500;
}

/* 顶级项间距（不在折叠动画节点上） */
.aside :deep(.el-menu > .el-menu-item),
.nav-drawer :deep(.el-menu > .el-menu-item),
.aside :deep(.el-menu > .el-sub-menu),
.nav-drawer :deep(.el-menu > .el-sub-menu) {
  margin-bottom: 4px;
}

.aside :deep(.el-menu-item:hover),
.nav-drawer :deep(.el-menu-item:hover) {
  background: rgba(180, 140, 60, 0.18) !important;
}

.aside :deep(.el-menu-item.is-active),
.nav-drawer :deep(.el-menu-item.is-active) {
  background: rgba(180, 140, 60, 0.28) !important;
  color: var(--oc-gold, #f5e6c8) !important;
  font-weight: 500;
}

/*
 * 子菜单标题 + 箭头：
 * EP 默认 top:50% + margin-top 负值；展开时 transform:rotate 会盖掉 translateY，箭头整颗偏下。
 * 改用 top/bottom:0 + margin:auto 垂直居中，展开只 rotate，互不打架。
 */
.aside :deep(.el-sub-menu__title),
.nav-drawer :deep(.el-sub-menu__title) {
  position: relative;
  display: flex;
  align-items: center;
  margin: 0 8px;
  border-radius: 8px;
  height: 44px;
  line-height: 1;
  box-sizing: border-box;
  padding-right: 36px !important;
  font-weight: 500;
  color: #e7e5e4 !important;
}

.aside :deep(.el-sub-menu__title:hover),
.nav-drawer :deep(.el-sub-menu__title:hover) {
  background: rgba(180, 140, 60, 0.18) !important;
}

.aside :deep(.el-sub-menu__title .el-icon),
.nav-drawer :deep(.el-sub-menu__title .el-icon) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* 内联子菜单：零 padding，动画只改高度，高度计算更准 */
.aside :deep(.el-sub-menu .el-menu--inline),
.nav-drawer :deep(.el-sub-menu .el-menu--inline) {
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  overflow: hidden;
  will-change: max-height;
}

.aside :deep(.el-sub-menu .el-menu--inline .el-menu-item),
.nav-drawer :deep(.el-sub-menu .el-menu--inline .el-menu-item) {
  min-width: auto;
  height: 40px;
  line-height: 40px;
  margin: 0 8px !important;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
  padding-left: 48px !important;
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
}

.aside :deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-sub-menu__icon-arrow),
.nav-drawer :deep(.el-sub-menu.is-opened > .el-sub-menu__title .el-sub-menu__icon-arrow) {
  transform: rotate(180deg) !important;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 0 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--oc-gold, #f5e6c8);
  border-bottom: 1px solid rgba(245, 230, 200, 0.12);
  box-sizing: border-box;
}

.brand.is-collapsed {
  padding: 0;
  gap: 0;
}

.brand-logo {
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: cover;
  background: #fff;
  box-shadow: 0 0 0 1px rgba(245, 230, 200, 0.2);
}

.brand-text {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.drawer-brand {
  background: var(--oc-sidebar, #292524);
  color: var(--oc-gold, #f5e6c8);
  border-bottom: 1px solid rgba(245, 230, 200, 0.12);
}

.content-wrap {
  min-width: 0;
  flex: 1;
  height: 100vh;
  max-height: 100vh;
  overflow: hidden;
  background: var(--oc-page, #faf8f3);
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  background: var(--oc-card, #fffdf8);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  height: 56px;
  padding: 0 12px;
}

.icon-btn {
  color: var(--oc-ink, #44403c);
}

.spacer {
  flex: 1;
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--oc-ink, #44403c);
}

.user-avatar {
  background: var(--oc-primary, #a16207);
  color: #fffdf8;
  font-size: 13px;
  font-weight: 600;
}

.user-name {
  font-size: 14px;
}

.main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 18px 20px;
  overscroll-behavior: contain;
}

@media (max-width: 991px) {
  .main {
    padding: 14px 12px;
  }
}

@media (max-width: 767px) {
  .user-name {
    display: none;
  }

  .layout {
    height: auto;
    max-height: none;
    min-height: 100vh;
    overflow: visible;
  }

  .content-wrap {
    height: auto;
    max-height: none;
    min-height: 100vh;
    overflow: visible;
  }

  .main {
    padding: 10px;
    overflow: visible;
    flex: none;
  }

  .header {
    padding: 0 8px;
  }
}
</style>

<style>
/* drawer teleports outside component — need non-scoped */
.nav-drawer .el-drawer__body {
  padding: 0;
  background: #292524;
}
</style>
