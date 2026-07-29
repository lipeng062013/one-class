<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import ChangePasswordDialog from '../../components/ChangePasswordDialog.vue'
import { ref } from 'vue'

const auth = useAuthStore()
const router = useRouter()
const changePwdVisible = ref(false)

function logout() {
  auth.logout()
  router.replace('/login')
}
</script>

<template>
  <div class="mobile">
    <el-page-header content="老师端" />
    <el-card class="card">
      <p>你好，{{ auth.user?.display_name }}</p>
      <el-alert
        title="素材上传等业务页将在后续迭代接入。当前可登录、改密。"
        type="info"
        :closable="false"
        show-icon
      />
      <el-space direction="vertical" fill style="width: 100%; margin-top: 16px">
        <el-button type="primary" size="large" style="width: 100%" @click="changePwdVisible = true">
          修改密码
        </el-button>
        <el-button size="large" style="width: 100%" @click="logout">退出登录</el-button>
      </el-space>
    </el-card>
    <ChangePasswordDialog v-model="changePwdVisible" />
  </div>
</template>

<style scoped>
.mobile {
  min-height: 100vh;
  padding: 16px;
  background: #f5f7fa;
}

.card {
  margin-top: 16px;
}
</style>
