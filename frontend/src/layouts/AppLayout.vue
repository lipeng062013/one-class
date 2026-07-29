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

const active = computed(() => route.path)

const menus = computed(() => {
  const items = [
    { index: '/', title: '工作台', icon: 'Odometer' },
    { index: '/materials', title: '素材', icon: 'Picture' },
    { index: '/copies', title: '文案', icon: 'Document' },
    { index: '/posters', title: '海报', icon: 'PictureFilled' },
    { index: '/leads', title: '线索', icon: 'Phone' },
    { index: '/knowledge', title: '知识库', icon: 'Collection' },
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
      <el-menu :default-active="active" :collapse="collapsed" router @select="onSelect">
        <el-menu-item v-for="m in menus" :key="m.index" :index="m.index">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-drawer v-model="drawer" direction="ltr" size="220px" :with-header="false" class="nav-drawer">
      <div class="brand drawer-brand">壹号教室</div>
      <el-menu :default-active="active" router @select="onSelect">
        <el-menu-item v-for="m in menus" :key="m.index" :index="m.index">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <el-container>
      <el-header class="header">
        <el-button v-if="isMobile" text @click="drawer = true">
          <el-icon><Menu /></el-icon>
        </el-button>
        <el-button v-else text @click="collapsed = !collapsed">
          <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
        </el-button>
        <div class="spacer" />
        <el-dropdown>
          <span class="user-trigger">
            <el-avatar :size="28">{{ auth.user?.display_name?.[0] || 'U' }}</el-avatar>
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
}

.aside {
  background: #001529;
  color: #fff;
  transition: width 0.2s;
}

.aside :deep(.el-menu),
.nav-drawer :deep(.el-menu) {
  border-right: none;
  background: transparent;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.drawer-brand {
  color: #303133;
  border-bottom: 1px solid #ebeef5;
}

.header {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  height: 56px;
}

.spacer {
  flex: 1;
}

.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.user-name {
  font-size: 14px;
}

.main {
  padding: 16px;
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
