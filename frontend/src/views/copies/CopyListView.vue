<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteCopy, listCopies, type GeneratedCopy } from '../../api/copies'
import { useBreakpoint } from '../../composables/useBreakpoint'

const router = useRouter()
const { isCompact } = useBreakpoint()
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
    <div class="page-toolbar">
      <el-page-header content="文案列表" />
      <el-button type="primary" @click="router.push('/copies/generate')">生成文案</el-button>
    </div>

    <div v-if="isCompact" v-loading="loading" class="m-card-list" style="margin-top: 12px">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无文案</div>
      <div v-for="row in rows" :key="row.id" class="m-card">
        <div class="m-card-head">
          <div class="m-card-title">{{ row.title || `文案 #${row.id}` }}</div>
          <el-tag v-if="row.banned_hits?.length" type="danger" size="small">
            禁用词 {{ row.banned_hits.length }}
          </el-tag>
        </div>
        <div class="m-card-meta">
          <span><span class="k">模式</span> {{ row.mode }}</span>
          <span><span class="k">平台</span> {{ row.platform }}</span>
        </div>
        <div class="m-card-actions">
          <el-button type="primary" size="small" @click="copyBody(row)">复制</el-button>
          <el-button size="small" type="danger" plain @click="onDelete(row)">删除</el-button>
        </div>
      </div>
    </div>

    <el-card v-else style="margin-top: 16px" v-loading="loading">
      <div class="table-scroll">
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
      </div>
    </el-card>
  </div>
</template>

