<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listMaterialsApi, type Material } from '../api/materials'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const pending = ref<Material[]>([])
const loading = ref(false)

async function load() {
  if (auth.isTeacher) return
  loading.value = true
  try {
    const all = await listMaterialsApi()
    pending.value = all.filter((m) => m.status === 'new').slice(0, 8)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <el-page-header content="工作台" />
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-head">
              <span>你好，{{ auth.user?.display_name }}</span>
              <el-tag size="small">{{ auth.user?.role }}</el-tag>
            </div>
          </template>
          <p>登录、用户、素材模块已可用。老师提交的素材会出现在「待处理」。</p>
          <el-space wrap style="margin-top: 12px">
            <el-button type="primary" @click="router.push('/materials')">素材列表</el-button>
            <el-button v-if="auth.isAdmin" @click="router.push('/users')">用户管理</el-button>
          </el-space>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card v-loading="loading">
          <template #header>待处理素材（new）</template>
          <el-empty v-if="!pending.length" description="暂无待处理素材" />
          <el-table v-else :data="pending" size="small" @row-click="(row: Material) => router.push(`/materials/${row.id}`)">
            <el-table-column prop="title" label="标题" />
            <el-table-column prop="grade" label="年级" width="90" />
            <el-table-column prop="auth_status" label="授权" width="100" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
</style>
