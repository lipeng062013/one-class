<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  downloadGrowthReportApi,
  getStudentApi,
  learningFileObjectUrl,
  listLearningApi,
  type LearningRecord,
  type Student,
} from '../../api/students'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const student = ref<Student | null>(null)
const records = ref<LearningRecord[]>([])
const imageUrls = ref<Record<number, string>>({})

const studentId = computed(() => Number(route.params.id))

const classLabels: Record<string, string> = {
  attended: '已上课',
  absent: '缺勤',
  late: '迟到',
  leave: '请假',
  makeup: '补课',
}

async function loadImages(list: LearningRecord[]) {
  for (const url of Object.values(imageUrls.value)) URL.revokeObjectURL(url)
  imageUrls.value = {}
  for (const rec of list) {
    for (const f of rec.files || []) {
      try {
        imageUrls.value[f.id] = await learningFileObjectUrl(f.id)
      } catch {
        /* ignore */
      }
    }
  }
}

async function load() {
  loading.value = true
  try {
    student.value = await getStudentApi(studentId.value)
    records.value = await listLearningApi({ student_id: studentId.value })
    await loadImages(records.value)
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

const reportLoading = ref(false)

function writeLearning() {
  router.push({ path: '/m/learning/new', query: { student_id: String(studentId.value) } })
}

async function downloadReport() {
  if (!student.value) return
  reportLoading.value = true
  try {
    await downloadGrowthReportApi(student.value.id, student.value.name)
    ElMessage.success('成长档案已开始下载')
  } catch {
    /* interceptor */
  } finally {
    reportLoading.value = false
  }
}

watch(studentId, load)
onMounted(load)
onUnmounted(() => {
  for (const url of Object.values(imageUrls.value)) URL.revokeObjectURL(url)
})
</script>

<template>
  <div v-loading="loading" class="page">
    <el-page-header @back="router.push('/m/students')">
      <template #content>
        <span>{{ student?.name || '学生详情' }}</span>
      </template>
    </el-page-header>

    <el-card v-if="student" class="profile" shadow="never">
      <p><b>年级</b> {{ student.grade }}</p>
      <p><b>学校</b> {{ student.school || '—' }}</p>
      <p><b>学管师</b> {{ student.academic_manager_name || '—' }}</p>
      <p><b>电话</b> {{ student.phone || '—' }}</p>
      <p v-if="student.parent_name"><b>家长</b> {{ student.parent_name }}</p>
      <p v-if="student.notes"><b>备注</b> {{ student.notes }}</p>
    </el-card>

    <el-button type="primary" size="large" class="write-btn" @click="writeLearning">
      写学情
    </el-button>

    <div class="section-row">
      <h3 class="section-title">学情记录</h3>
      <el-button
        type="primary"
        plain
        size="small"
        class="report-btn"
        :loading="reportLoading"
        @click="downloadReport"
      >
        生成学情报告
      </el-button>
    </div>
    <el-empty v-if="!records.length" description="暂无学情" />
    <el-card v-for="r in records" :key="r.id" class="rec" shadow="hover">
      <div class="rec-head">
        <el-tag size="small">{{ classLabels[r.class_status] || r.class_status }}</el-tag>
        <span class="time">{{ formatTime(r.class_date) }}</span>
      </div>
      <p class="summary">{{ r.learning_summary }}</p>
      <p v-if="r.notes" class="sub">备注：{{ r.notes }}</p>
      <div v-if="r.files?.length" class="imgs">
        <el-image
          v-for="f in r.files"
          :key="f.id"
          :src="imageUrls[f.id]"
          fit="cover"
          class="thumb"
          :preview-src-list="r.files.map((x) => imageUrls[x.id]).filter(Boolean)"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 80px;
}

.profile {
  margin: 12px 0;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.profile p {
  margin: 4px 0;
  font-size: 14px;
}

.write-btn {
  display: block;
  width: 100%;
  margin: 0 0 14px !important; /* 覆盖 .el-button + .el-button 的 margin-left */
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 0 0 10px;
}

.section-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  min-width: 0;
}

.report-btn {
  flex-shrink: 0;
  margin: 0 !important;
}

.rec {
  margin-bottom: 10px;
}

.rec-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.time {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.summary {
  margin: 0;
  white-space: pre-wrap;
}

.sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.imgs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.thumb {
  width: 64px;
  height: 64px;
  border-radius: 8px;
}
</style>
