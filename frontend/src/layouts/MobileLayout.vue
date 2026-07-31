<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const active = computed(() => {
  if (route.path.startsWith('/m/materials')) return '/m/materials'
  if (route.path.startsWith('/m/students')) return '/m/students'
  if (route.path.startsWith('/m/learning')) return '/m/learning'
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
      <div class="brand">
        <img class="brand-logo" src="/brand-mark.png" alt="" width="28" height="28" />
        <span class="brand-text">嘉壹启航 · 老师端</span>
      </div>
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
          <span>素材</span>
        </el-menu-item>
        <el-menu-item index="/m/students">
          <el-icon><User /></el-icon>
          <span>学生</span>
        </el-menu-item>
        <el-menu-item index="/m/learning">
          <el-icon><EditPen /></el-icon>
          <span>学情</span>
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
  position: sticky;
  top: 0;
  z-index: 50;
  flex-shrink: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.brand-logo {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: #fff;
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.15);
}

.brand-text {
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
  font-size: 14px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.logout {
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.body {
  flex: 1;
  padding: 12px;
  padding-bottom: 8px;
  min-height: 0;
}

.bottom {
  position: sticky;
  bottom: 0;
  background: var(--oc-card, #fffdf8);
  border-top: 1px solid var(--oc-border, #e8e0d0);
  z-index: 10;
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
  flex-direction: column;
  height: 56px;
  line-height: 1.2;
  padding: 6px 0 !important;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
  gap: 2px;
}

.bottom :deep(.el-menu-item .el-icon) {
  margin-right: 0;
  font-size: 18px;
}

.bottom :deep(.el-menu-item.is-active) {
  color: var(--oc-primary, #a16207) !important;
  font-weight: 600;
  border-bottom-color: transparent !important;
}
</style>
