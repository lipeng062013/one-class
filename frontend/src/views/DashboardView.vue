<script setup lang="ts">
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div>
    <el-page-header content="工作台" />
    <el-card style="margin-top: 16px">
      <p>
        你好，<strong>{{ auth.user?.display_name }}</strong>
        （{{ auth.user?.role }}）。登录与用户管理已可用。
      </p>
      <el-alert
        title="后续模块（素材、文案、海报、线索等）将继续用 Element Plus 接入。"
        type="info"
        :closable="false"
        show-icon
        style="margin-top: 12px"
      />
      <div style="margin-top: 16px">
        <el-button v-if="auth.isAdmin" type="primary" @click="$router.push('/users')">
          进入用户管理
        </el-button>
      </div>
    </el-card>
  </div>
</template>
