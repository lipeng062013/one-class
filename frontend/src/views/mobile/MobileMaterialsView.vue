<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listMaterialsApi, type Material } from '../../api/materials'

const loading = ref(false)
const rows = ref<Material[]>([])

const statusLabel: Record<string, string> = {
  new: '新建',
  usable: '可用',
  used: '已用',
  archived: '归档',
}
const authLabel: Record<string, string> = {
  pending: '待授权',
  authorized: '已授权',
  denied: '拒绝',
  anonymized: '已脱敏',
}

async function load() {
  loading.value = true
  try {
    rows.value = await listMaterialsApi()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="head">
      <h2>我的素材</h2>
      <el-button @click="load">刷新</el-button>
    </div>
    <div v-loading="loading">
      <el-empty v-if="!rows.length" description="还没有提交素材" />
      <el-card v-for="row in rows" :key="row.id" class="card" shadow="hover">
        <div class="title">{{ row.title }}</div>
        <div class="meta">{{ row.grade || '—' }} · {{ row.subject || '—' }}</div>
        <el-space wrap style="margin-top: 8px">
          <el-tag size="small">{{ authLabel[row.auth_status] || row.auth_status }}</el-tag>
          <el-tag size="small" type="success">{{ statusLabel[row.status] || row.status }}</el-tag>
          <el-tag size="small" type="info">{{ row.files?.length || 0 }} 张图</el-tag>
        </el-space>
        <p v-if="row.pain_point" class="desc">痛点：{{ row.pain_point }}</p>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 16px 16px 80px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

h2 {
  margin: 0;
  font-size: 1.25rem;
}

.card {
  margin-bottom: 12px;
}

.title {
  font-weight: 600;
  font-size: 1.05rem;
}

.meta {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}

.desc {
  margin: 8px 0 0;
  color: #606266;
  font-size: 13px;
}
</style>
