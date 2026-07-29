<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteCopy, listCopies, type GeneratedCopy } from '../../api/copies'

const router = useRouter()
const loading = ref(false)
const rows = ref<GeneratedCopy[]>([])

async function load() {
  loading.value = true
  try {
    rows.value = await listCopies()
  } finally {
    loading.value = false
  }
}

async function copyBody(row: GeneratedCopy) {
  try {
    await navigator.clipboard.writeText(`${row.title}\n\n${row.body}`)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

async function onDelete(row: GeneratedCopy) {
  try {
    await ElMessageBox.confirm(`删除文案「${row.title || row.id}」？`, '确认', { type: 'warning' })
    await deleteCopy(row.id)
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
      <el-page-header content="文案列表" />
      <el-button type="primary" @click="router.push('/copies/generate')">生成文案</el-button>
    </div>
    <el-card style="margin-top: 16px" v-loading="loading">
      <el-table :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column prop="mode" label="模式" width="130" />
        <el-table-column prop="platform" label="平台" width="90" />
        <el-table-column label="禁用词" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.banned_hits?.length" type="danger" size="small">
              {{ row.banned_hits.length }}
            </el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="copyBody(row)">复制</el-button>
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
