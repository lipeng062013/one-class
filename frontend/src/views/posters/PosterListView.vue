<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deletePoster, listPosters, openPosterDownload, type GeneratedPoster } from '../../api/posters'

const router = useRouter()
const loading = ref(false)
const rows = ref<GeneratedPoster[]>([])

async function load() {
  loading.value = true
  try {
    rows.value = await listPosters()
  } finally {
    loading.value = false
  }
}

async function download(row: GeneratedPoster) {
  try {
    await openPosterDownload(row.id, `${row.title || 'poster'}-${row.id}.png`)
    ElMessage.success('开始下载')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '下载失败')
  }
}

async function onDelete(row: GeneratedPoster) {
  try {
    await ElMessageBox.confirm(`删除海报「${row.title || row.id}」？`, '确认', { type: 'warning' })
    await deletePoster(row.id)
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
      <el-page-header content="海报列表" />
      <el-button type="primary" @click="router.push('/posters/generate')">生成海报</el-button>
    </div>
    <el-card style="margin-top: 16px" v-loading="loading">
      <el-table :data="rows" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="160" />
        <el-table-column prop="mode" label="模式" width="110" />
        <el-table-column prop="file_path" label="文件" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="download(row)">下载</el-button>
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
