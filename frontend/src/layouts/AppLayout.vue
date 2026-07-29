<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const drawer = ref(false)
const isMobile = ref(false)
const changePwdVisible = ref(false)

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
  ]
  if (auth.isAdmin) {
    items.push({ index: '/users', title: '用户管理', icon: 'User' })
  }
  return items
})

function checkMobile() {
  isMobile.value = window.innerWidth < 768
  if (!isMobile.value) drawer.value = false
}

function onSelect(index: string) {
  router.push(index)
  if (isMobile.value) drawer.value = false
}

function logout() {
  auth.logout()
  router.replace('/login')
}

watch(
  () => route.path,
  () => {
    if (isMobile.value) drawer.value = false
  },
)

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})
onUnmounted(() => window.removeEventListener('resize', checkMobile))
</script>

<template>
  <el-container class="layout">
    <el-aside v-if="!isMobile" :width="collapsed ? '64px' : '220px'" class="aside">
      <div class="brand">
        <span v-if="!collapsed">壹号教室</span>
        <span v-else>壹</span>
      </div>
      <el-menu
        :default-active="active"
        :default-openeds="['crm', 'growth']"
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
      <div class="brand drawer-brand">壹号教室</div>
      <el-menu
        :default-active="active"
        :default-openeds="['crm', 'growth']"
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
  min-height: 100vh;
  background: var(--oc-page, #faf8f3);
}

.aside {
  background: var(--oc-sidebar, #292524);
  color: var(--oc-sidebar-text, #e7e5e4);
  transition: width 0.2s;
  border-right: 1px solid rgba(245, 230, 200, 0.08);
}

.aside :deep(.el-menu),
.nav-drawer :deep(.el-menu) {
  border-right: none;
  background: transparent;
}

.aside :deep(.el-menu-item),
.nav-drawer :deep(.el-menu-item) {
  margin: 4px 8px;
  border-radius: 8px;
  height: 44px;
  line-height: 44px;
}

.aside :deep(.el-menu-item:hover),
.nav-drawer :deep(.el-menu-item:hover) {
  background: rgba(180, 140, 60, 0.18) !important;
}

.aside :deep(.el-menu-item.is-active),
.nav-drawer :deep(.el-menu-item.is-active) {
  background: rgba(180, 140, 60, 0.28) !important;
  color: var(--oc-gold, #f5e6c8) !important;
  font-weight: 600;
}

.aside :deep(.el-sub-menu__title),
.nav-drawer :deep(.el-sub-menu__title) {
  margin: 4px 8px;
  border-radius: 8px;
  height: 44px;
  line-height: 44px;
  color: #e7e5e4 !important;
}

.aside :deep(.el-sub-menu__title:hover),
.nav-drawer :deep(.el-sub-menu__title:hover) {
  background: rgba(180, 140, 60, 0.18) !important;
}

.aside :deep(.el-sub-menu .el-menu-item),
.nav-drawer :deep(.el-sub-menu .el-menu-item) {
  min-width: auto;
  padding-left: 48px !important;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--oc-gold, #f5e6c8);
  border-bottom: 1px solid rgba(245, 230, 200, 0.12);
}

.drawer-brand {
  background: var(--oc-sidebar, #292524);
  color: var(--oc-gold, #f5e6c8);
  border-bottom: 1px solid rgba(245, 230, 200, 0.12);
}

.content-wrap {
  min-width: 0;
  background: var(--oc-page, #faf8f3);
}

.header {
  display: flex;
  align-items: center;
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
  padding: 18px 20px;
}

@media (max-width: 768px) {
  .user-name {
    display: none;
  }

  .main {
    padding: 12px;
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
