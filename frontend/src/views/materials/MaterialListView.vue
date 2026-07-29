<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ElMessageBox } from 'element-plus'
import { deleteMaterialApi, listMaterialsApi, patchMaterialApi, type Material } from '../../api/materials'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const rows = ref<Material[]>([])
const statusFilter = ref('')

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

const filtered = computed(() => {
  if (!statusFilter.value) return rows.value
  return rows.value.filter((r) => r.status === statusFilter.value)
})

async function load() {
  loading.value = true
  try {
    rows.value = await listMaterialsApi()
  } finally {
    loading.value = false
  }
}

async function markUsable(row: Material) {
  await patchMaterialApi(row.id, { status: 'usable', auth_status: 'authorized' })
  ElMessage.success('已标为可用')
  await load()
}

async function onDelete(row: Material) {
  try {
    await ElMessageBox.confirm(`确定删除素材「${row.title}」？`, '删除确认', { type: 'warning' })
    await deleteMaterialApi(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <el-page-header content="素材管理" />
      <el-space wrap>
        <el-select v-model="statusFilter" clearable placeholder="状态筛选" style="width: 140px">
          <el-option v-for="(label, key) in statusLabel" :key="key" :label="label" :value="key" />
        </el-select>
        <el-button @click="load">刷新</el-button>
      </el-space>
    </div>

    <el-card style="margin-top: 16px">
      <el-table v-loading="loading" :data="filtered" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="grade" label="年级" width="100" />
        <el-table-column prop="subject" label="科目" width="100" />
        <el-table-column label="授权" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ authLabel[row.auth_status] || row.auth_status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" type="success">{{ statusLabel[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="图片" width="80">
          <template #default="{ row }">{{ row.files?.length || 0 }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="router.push(`/materials/${row.id}`)">详情</el-button>
            <el-button
              v-if="!auth.isTeacher && row.status === 'new'"
              link
              type="success"
              @click="markUsable(row)"
            >
              标为可用
            </el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
