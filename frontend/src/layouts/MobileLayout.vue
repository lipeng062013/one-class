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
      <span>壹号教室 · 老师端</span>
      <el-button link type="danger" @click="logout">退出</el-button>
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
  background: #f5f7fa;
}

.top {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  font-weight: 600;
}

.body {
  flex: 1;
}

.bottom {
  position: sticky;
  bottom: 0;
  background: #fff;
  border-top: 1px solid #ebeef5;
}

.bottom :deep(.el-menu) {
  width: 100%;
  justify-content: space-around;
  border-bottom: none;
}

.bottom :deep(.el-menu-item) {
  flex: 1;
  justify-content: center;
}
</style>
