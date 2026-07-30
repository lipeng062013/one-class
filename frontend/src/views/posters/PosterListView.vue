<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deletePoster, listPosters, openPosterDownload, type GeneratedPoster } from '../../api/posters'
import { useBreakpoint } from '../../composables/useBreakpoint'

const router = useRouter()
const { isCompact } = useBreakpoint()
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
    <div class="page-toolbar">
      <el-page-header content="海报列表" />
      <el-button type="primary" @click="router.push('/posters/generate')">生成海报</el-button>
    </div>

    <div v-if="isCompact" v-loading="loading" class="m-card-list" style="margin-top: 12px">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无海报</div>
      <div v-for="row in rows" :key="row.id" class="m-card">
        <div class="m-card-head">
          <div class="m-card-title">{{ row.title || `海报 #${row.id}` }}</div>
          <el-tag size="small">{{ row.mode }}</el-tag>
        </div>
        <div class="m-card-actions">
          <el-button type="primary" size="small" @click="download(row)">下载</el-button>
          <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
        </div>
      </div>
    </div>

    <el-card v-else style="margin-top: 16px" v-loading="loading">
      <div class="table-scroll">
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
      </div>
    </el-card>
  </div>
</template>

