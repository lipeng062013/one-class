<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const active = computed(() => {
  if (route.path.startsWith('/m/materials')) return '/m/materials'
  return '/m/upload'
})

function onSelect(index: string) {
  router.push(index)
}

function logout() {
  auth.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="mobile-shell">
    <header class="top">
      <span class="brand">壹号教室 · 老师端</span>
      <el-button link class="logout" @click="logout">退出</el-button>
    </header>
    <main class="body">
      <router-view />
    </main>
    <nav class="bottom">
      <el-menu mode="horizontal" :ellipsis="false" :default-active="active" @select="onSelect">
        <el-menu-item index="/m/upload">
          <el-icon><Upload /></el-icon>
          <span>上传</span>
        </el-menu-item>
        <el-menu-item index="/m/materials">
          <el-icon><Folder /></el-icon>
          <span>我的素材</span>
        </el-menu-item>
      </el-menu>
    </nav>
  </div>
</template>

<style scoped>
.mobile-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--oc-page, #faf8f3);
}

.top {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  background: var(--oc-card, #fffdf8);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.brand {
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
}

.logout {
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.body {
  flex: 1;
  padding: 12px;
}

.bottom {
  position: sticky;
  bottom: 0;
  background: var(--oc-card, #fffdf8);
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.bottom :deep(.el-menu) {
  width: 100%;
  justify-content: space-around;
  border-bottom: none;
  background: transparent;
}

.bottom :deep(.el-menu-item) {
  flex: 1;
  justify-content: center;
  color: var(--oc-muted, #78716c);
}

.bottom :deep(.el-menu-item.is-active) {
  color: var(--oc-primary, #a16207) !important;
  font-weight: 600;
  border-bottom-color: var(--oc-primary, #a16207) !important;
}
</style>
