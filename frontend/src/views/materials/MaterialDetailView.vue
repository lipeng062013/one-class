<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  deleteMaterialApi,
  getMaterialApi,
  materialFileObjectUrl,
  patchMaterialApi,
  type Material,
} from '../../api/materials'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const item = ref<Material | null>(null)
const previewUrls = ref<Record<number, string>>({})

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

function revokePreviews() {
  Object.values(previewUrls.value).forEach((u) => URL.revokeObjectURL(u))
  previewUrls.value = {}
}

async function loadPreviews(material: Material) {
  revokePreviews()
  const map: Record<number, string> = {}
  for (const f of material.files || []) {
    try {
      map[f.id] = await materialFileObjectUrl(f.id)
    } catch {
      /* skip broken file */
    }
  }
  previewUrls.value = map
}

async function load() {
  loading.value = true
  try {
    item.value = await getMaterialApi(Number(route.params.id))
    if (item.value) await loadPreviews(item.value)
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

async function onDelete() {
  if (!item.value) return
  try {
    await ElMessageBox.confirm(`确定删除素材「${item.value.title}」？`, '删除确认', {
      type: 'warning',
    })
    await deleteMaterialApi(item.value.id)
    ElMessage.success('已删除')
    router.push('/materials')
  } catch {
    /* cancel */
  }
}

watch(
  () => route.params.id,
  () => load(),
)

onMounted(load)
onUnmounted(revokePreviews)
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
        <el-descriptions-item label="创建时间">{{ item.created_at || '—' }}</el-descriptions-item>
      </el-descriptions>

      <div class="actions">
        <el-space wrap>
          <template v-if="!auth.isTeacher">
            <el-button type="success" @click="setStatus('usable')">标为可用</el-button>
            <el-button @click="setStatus('used')">标为已用</el-button>
            <el-button @click="setStatus('archived')">归档</el-button>
            <el-button type="primary" plain @click="setAuth('authorized')">确认授权</el-button>
            <el-button plain @click="setAuth('anonymized')">已脱敏</el-button>
            <el-button type="primary" @click="router.push({ path: '/copies/generate', query: { material_id: String(item.id) } })">
              生成文案
            </el-button>
            <el-button @click="router.push({ path: '/posters/generate', query: { material_id: String(item.id) } })">
              生成海报
            </el-button>
          </template>
          <el-button type="danger" @click="onDelete">删除</el-button>
        </el-space>
      </div>

      <el-divider>图片预览</el-divider>
      <el-empty v-if="!item.files?.length" description="暂无图片" />
      <div v-else class="preview-grid">
        <el-image
          v-for="f in item.files"
          :key="f.id"
          :src="previewUrls[f.id]"
          :preview-src-list="Object.values(previewUrls)"
          fit="cover"
          class="thumb"
        >
          <template #error>
            <div class="thumb-error">无法预览<br />{{ f.file_path }}</div>
          </template>
        </el-image>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.actions {
  margin-top: 16px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.thumb {
  width: 100%;
  height: 140px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
  background: #f5f7fa;
}

.thumb-error {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 12px;
  color: #909399;
  text-align: center;
  padding: 8px;
}
</style>
