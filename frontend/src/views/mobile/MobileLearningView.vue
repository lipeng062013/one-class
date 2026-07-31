<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listLearningApi, type LearningRecord } from '../../api/students'

const router = useRouter()
const loading = ref(false)
const rows = ref<LearningRecord[]>([])

const classLabels: Record<string, string> = {
  attended: '已上课',
  absent: '缺勤',
  late: '迟到',
  leave: '请假',
  makeup: '补课',
}

async function load() {
  loading.value = true
  try {
    rows.value = await listLearningApi({ mine: true })
  } finally {
    loading.value = false
  }
}

function formatTime(v?: string | null) {
  if (!v) return ''
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="head">
      <h2>我的学情</h2>
      <el-button type="primary" size="small" @click="router.push('/m/learning/new')">
        编写学情
      </el-button>
    </div>

    <div v-loading="loading">
      <el-empty v-if="!rows.length" description="还没有提交过学情" />
      <el-card v-for="r in rows" :key="r.id" class="card" shadow="hover">
        <div class="row1">
          <strong>{{ r.student_name || `学生#${r.student_id}` }}</strong>
          <el-tag size="small">{{ classLabels[r.class_status] || r.class_status }}</el-tag>
        </div>
        <div class="time">{{ formatTime(r.class_date) }}</div>
        <p class="summary">{{ r.learning_summary }}</p>
        <el-button
          link
          type="primary"
          @click="router.push(`/m/students/${r.student_id}`)"
        >
          看学生档案
        </el-button>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 72px;
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

h2 {
  margin: 0;
  font-size: 1.15rem;
}

.card {
  margin-bottom: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.row1 {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.time {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin: 4px 0;
}

.summary {
  margin: 6px 0;
  white-space: pre-wrap;
  font-size: 14px;
}
</style>
