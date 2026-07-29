<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMaterialApi, patchMaterialApi, type Material } from '../../api/materials'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const item = ref<Material | null>(null)

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
    item.value = await getMaterialApi(Number(route.params.id))
  } catch {
    ElMessage.error('加载失败')
    router.back()
  } finally {
    loading.value = false
  }
}

async function setStatus(status: string) {
  if (!item.value) return
  item.value = await patchMaterialApi(item.value.id, { status })
  ElMessage.success('状态已更新')
}

async function setAuth(auth_status: string) {
  if (!item.value) return
  item.value = await patchMaterialApi(item.value.id, { auth_status })
  ElMessage.success('授权已更新')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-page-header @back="router.push('/materials')" content="素材详情" />
    <el-card v-if="item" style="margin-top: 16px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="标题">{{ item.title }}</el-descriptions-item>
        <el-descriptions-item label="年级">{{ item.grade || '—' }}</el-descriptions-item>
        <el-descriptions-item label="科目">{{ item.subject || '—' }}</el-descriptions-item>
        <el-descriptions-item label="家长痛点">{{ item.pain_point || '—' }}</el-descriptions-item>
        <el-descriptions-item label="老师处理">{{ item.teacher_action || '—' }}</el-descriptions-item>
        <el-descriptions-item label="下一步">{{ item.next_step || '—' }}</el-descriptions-item>
        <el-descriptions-item label="授权">
          {{ authLabel[item.auth_status] || item.auth_status }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          {{ statusLabel[item.status] || item.status }}
        </el-descriptions-item>
        <el-descriptions-item label="图片数">{{ item.files?.length || 0 }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ item.created_at || '—' }}</el-descriptions-item>
      </el-descriptions>

      <div v-if="!auth.isTeacher" class="actions">
        <el-space wrap>
          <el-button type="success" @click="setStatus('usable')">标为可用</el-button>
          <el-button @click="setStatus('used')">标为已用</el-button>
          <el-button @click="setStatus('archived')">归档</el-button>
          <el-button type="primary" plain @click="setAuth('authorized')">确认授权</el-button>
          <el-button plain @click="setAuth('anonymized')">已脱敏</el-button>
        </el-space>
      </div>

      <el-divider>附件路径</el-divider>
      <el-empty v-if="!item.files?.length" description="暂无图片" />
      <el-table v-else :data="item.files" size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="file_path" label="路径" min-width="200" />
        <el-table-column prop="file_type" label="类型" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.actions {
  margin-top: 16px;
}
</style>
