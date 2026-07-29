<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSummary, type DashboardSummary } from '../api/dashboard'
import { listMaterialsApi, type Material } from '../api/materials'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const summary = ref<DashboardSummary | null>(null)
const pending = ref<Material[]>([])
const loading = ref(false)

async function load() {
  if (auth.isTeacher) return
  loading.value = true
  try {
    const [s, all] = await Promise.all([getSummary(), listMaterialsApi()])
    summary.value = s
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
    <el-row :gutter="16" style="margin-top: 16px" v-loading="loading">
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover">
          <el-statistic title="待处理素材" :value="summary?.materials_new ?? 0" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover">
          <el-statistic title="今日待跟进线索" :value="summary?.leads_follow_today ?? 0" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card shadow="hover">
          <el-statistic title="已生成文案" :value="summary?.recent_copies ?? 0" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-head">
              <span>快捷入口</span>
              <el-tag size="small">{{ auth.user?.display_name }} · {{ auth.user?.role }}</el-tag>
            </div>
          </template>
          <el-space wrap>
            <el-button type="primary" @click="router.push('/materials')">素材</el-button>
            <el-button @click="router.push('/copies/generate')">生成文案</el-button>
            <el-button @click="router.push('/posters/generate')">生成海报</el-button>
            <el-button @click="router.push('/leads')">线索</el-button>
            <el-button @click="router.push('/knowledge')">知识库</el-button>
            <el-button v-if="auth.isAdmin" @click="router.push('/users')">用户</el-button>
          </el-space>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>待处理素材（new）</template>
          <el-empty v-if="!pending.length" description="暂无待处理素材" />
          <el-table
            v-else
            :data="pending"
            size="small"
            @row-click="(row: Material) => router.push(`/materials/${row.id}`)"
          >
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
