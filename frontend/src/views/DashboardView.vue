<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSummary, type DashboardSummary } from '../api/dashboard'
import { getIntegrationsStatus, type IntegrationsStatus } from '../api/system'
import { listMaterialsApi, type Material } from '../api/materials'
import { useAuthStore } from '../stores/auth'
import TodayTodos from '../components/TodayTodos.vue'

const auth = useAuthStore()
const router = useRouter()
const summary = ref<DashboardSummary | null>(null)
const integrations = ref<IntegrationsStatus | null>(null)
const pending = ref<Material[]>([])
const loading = ref(false)

async function load() {
  if (auth.isTeacher) return
  loading.value = true
  try {
    const [s, all, integ] = await Promise.all([
      getSummary(),
      listMaterialsApi(),
      getIntegrationsStatus().catch(() => null),
    ])
    summary.value = s
    integrations.value = integ
    pending.value = all.filter((m) => m.status === 'new').slice(0, 8)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="dashboard">
    <div class="page-head">
      <div>
        <h1 class="page-title">工作台</h1>
        <p class="page-sub">今日待办 · 运营概览 · 快捷入口</p>
      </div>
    </div>

    <TodayTodos class="todo-block" />

    <template v-if="!auth.isTeacher">
      <el-row :gutter="16" v-loading="loading" class="stats-row">
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="stat-card" @click="router.push('/materials')">
            <el-statistic title="待处理素材" :value="summary?.materials_new ?? 0" />
            <div class="stat-hint">点击进入素材</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="stat-card" @click="router.push('/leads')">
            <el-statistic title="今日待跟进线索" :value="summary?.leads_follow_today ?? 0" />
            <div class="stat-hint">点击进入线索</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-card shadow="hover" class="stat-card" @click="router.push('/copies')">
            <el-statistic title="已生成文案" :value="summary?.recent_copies ?? 0" />
            <div class="stat-hint">点击进入文案</div>
          </el-card>
        </el-col>
      </el-row>

      <el-alert
        v-if="integrations"
        class="ai-alert"
        :type="integrations.llm.configured || integrations.image.configured ? 'success' : 'info'"
        :closable="false"
        show-icon
      >
        <template #title>
          AI 接入状态：文案大模型
          {{ integrations.llm.configured ? `已配置（${integrations.llm.model}）` : '未配置（可用模板）' }}
          ；海报生图
          {{ integrations.image.configured ? `已配置（${integrations.image.model || '默认'}）` : '未配置（可用版式）' }}
        </template>
      </el-alert>

      <el-row :gutter="16" class="lower-row">
        <el-col :xs="24" :md="12">
          <el-card class="panel-card">
            <template #header>
              <div class="card-head">
                <span>快捷入口</span>
                <el-tag size="small" effect="plain" class="role-tag">
                  {{ auth.user?.display_name }} · {{ auth.user?.role }}
                </el-tag>
              </div>
            </template>
            <el-space wrap>
              <el-button type="primary" @click="router.push('/materials')">素材</el-button>
              <el-button @click="router.push('/copies/generate')">生成文案</el-button>
              <el-button @click="router.push('/posters/generate')">生成海报</el-button>
              <el-button @click="router.push('/leads')">线索</el-button>
              <el-button @click="router.push('/knowledge/scripts')">成长中心</el-button>
              <el-button @click="router.push('/office')">综合办公表</el-button>
              <el-button v-if="auth.isAdmin" @click="router.push('/users')">用户</el-button>
              <el-button v-if="auth.isAdmin" @click="router.push('/students')">学生</el-button>
            </el-space>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-card class="panel-card">
            <template #header>
              <div class="card-head">
                <span>待处理素材（new）</span>
                <el-button link type="primary" @click="router.push('/materials')">全部</el-button>
              </div>
            </template>
            <el-empty v-if="!pending.length" description="暂无待处理素材" />
            <div v-else class="pending-list">
              <div
                v-for="row in pending"
                :key="row.id"
                class="pending-item"
                @click="router.push(`/materials/${row.id}`)"
              >
                <div class="pending-title">{{ row.title }}</div>
                <div class="pending-meta">
                  <span>{{ row.grade || '—' }}</span>
                  <span>{{ row.auth_status }}</span>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<style scoped>
.page-head {
  margin-bottom: 16px;
}

.todo-block {
  margin-bottom: 16px;
}

.stats-row {
  margin-top: 4px;
}

.page-title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
}

.page-sub {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.stat-card {
  cursor: pointer;
  margin-bottom: 8px;
  border-color: var(--oc-border, #e8e0d0);
  transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s;
}

.stat-card:hover {
  border-color: var(--el-color-primary-light-5);
  transform: translateY(-1px);
  box-shadow: var(--oc-shadow, 0 8px 24px rgba(41, 37, 36, 0.06));
}

.stat-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.ai-alert {
  margin-top: 16px;
  border-radius: 10px;
}

.lower-row {
  margin-top: 16px;
}

.panel-card {
  margin-bottom: 12px;
}

.pending-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pending-item {
  padding: 10px 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.15s, background 0.15s;
}

.pending-item:hover {
  border-color: var(--el-color-primary-light-5);
  background: #faf6ee;
}

.pending-title {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
}

.pending-meta {
  margin-top: 4px;
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.role-tag {
  border-color: var(--oc-border, #e8e0d0);
  color: var(--oc-primary, #a16207);
  background: #f2e8d6;
}
</style>
