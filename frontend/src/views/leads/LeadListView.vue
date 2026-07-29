<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  createLead,
  listLeads,
  patchLead,
  type Lead,
  type LeadSource,
  type LeadStatus,
} from '../../api/leads'

const loading = ref(false)
const rows = ref<Lead[]>([])
const createVisible = ref(false)
const formRef = ref<FormInstance>()
const saving = ref(false)

const filters = reactive({
  source: '',
  status: '',
  name: '',
  phone: '',
})

const form = reactive({
  student_or_parent_name: '',
  phone: '',
  source: 'referral' as LeadSource,
  referrer_name: '',
  need: '',
  notes: '',
  next_follow_at: null as Date | null,
})

const rules: FormRules = {
  student_or_parent_name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  source: [{ required: true, message: '请选择来源', trigger: 'change' }],
}

const sourceLabels: Record<string, string> = {
  referral: '老带新',
  dianping: '大众点评',
  wechat: '微信',
  walkin: '到店',
  other: '其他',
}
const statusLabels: Record<string, string> = {
  new: '新建',
  contacted: '已联系',
  visited: '已到访',
  enrolled: '已报名',
  lost: '已流失',
}
const statusOptions: LeadStatus[] = ['new', 'contacted', 'visited', 'enrolled', 'lost']

function isToday(value?: string | null) {
  if (!value) return false
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return false
  const now = new Date()
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  )
}

const sorted = computed(() =>
  [...rows.value].sort((a, b) => {
    const aToday = isToday(a.next_follow_at) || a.status === 'new' ? 1 : 0
    const bToday = isToday(b.next_follow_at) || b.status === 'new' ? 1 : 0
    if (aToday !== bToday) return bToday - aToday
    return (b.id || 0) - (a.id || 0)
  }),
)

async function load() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filters.source) params.source = filters.source
    if (filters.status) params.status = filters.status
    if (filters.name) params.name = filters.name
    if (filters.phone) params.phone = filters.phone
    rows.value = await listLeads(params)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.source = ''
  filters.status = ''
  filters.name = ''
  filters.phone = ''
  load()
}

function openCreate() {
  form.student_or_parent_name = ''
  form.phone = ''
  form.source = 'referral'
  form.referrer_name = ''
  form.need = ''
  form.notes = ''
  form.next_follow_at = null
  createVisible.value = true
}

function toIso(value: Date | string | null | undefined): string | null {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

async function submitCreate() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  saving.value = true
  try {
    await createLead({
      student_or_parent_name: form.student_or_parent_name,
      phone: form.phone || null,
      source: form.source,
      referrer_name: form.referrer_name || null,
      need: form.need,
      notes: form.notes,
      next_follow_at: toIso(form.next_follow_at),
    })
    ElMessage.success('线索已创建')
    createVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    saving.value = false
  }
}

async function changeStatus(row: Lead, status: LeadStatus) {
  await patchLead(row.id, { status })
  ElMessage.success('状态已更新')
  await load()
}

async function patchFollow(row: Lead, value: Date | null) {
  await patchLead(row.id, { next_follow_at: toIso(value) })
  ElMessage.success('跟进时间已更新')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <el-page-header content="线索管理" />
      <el-button type="primary" @click="openCreate">新建线索</el-button>
    </div>

    <el-card class="filters" shadow="never" style="margin-top: 12px">
      <el-form :inline="true" @submit.prevent="load">
        <el-form-item label="来源">
          <el-select v-model="filters.source" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
            <el-option v-for="(label, key) in statusLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="filters.name" clearable placeholder="搜索姓名" style="width: 130px" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="filters.phone" clearable placeholder="搜索电话" style="width: 130px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 12px" v-loading="loading">
      <el-table :data="sorted" stripe style="width: 100%">
        <el-table-column prop="student_or_parent_name" label="姓名" min-width="120" />
        <el-table-column prop="phone" label="电话" width="120" />
        <el-table-column label="来源" width="110">
          <template #default="{ row }">{{ sourceLabels[row.source] || row.source }}</template>
        </el-table-column>
        <el-table-column prop="need" label="需求" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-select
              :model-value="row.status"
              size="small"
              style="width: 110px"
              @change="(v: LeadStatus) => changeStatus(row, v)"
            >
              <el-option v-for="s in statusOptions" :key="s" :label="statusLabels[s]" :value="s" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="下次跟进" min-width="200">
          <template #default="{ row }">
            <div class="follow-cell">
              <el-tag v-if="isToday(row.next_follow_at)" type="danger" size="small">今日</el-tag>
              <el-date-picker
                :model-value="row.next_follow_at ? new Date(row.next_follow_at) : null"
                type="datetime"
                size="small"
                placeholder="设置跟进"
                style="width: 170px"
                @update:model-value="(v: Date | null) => patchFollow(row, v)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建线索" width="90%" style="max-width: 520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="学生/家长姓名" prop="student_or_parent_name">
          <el-input v-model="form.student_or_parent_name" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="来源" prop="source">
          <el-select v-model="form.source" style="width: 100%">
            <el-option v-for="(label, key) in sourceLabels" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="介绍人">
          <el-input v-model="form.referrer_name" />
        </el-form-item>
        <el-form-item label="需求">
          <el-input v-model="form.need" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="下次跟进时间">
          <el-date-picker
            v-model="form.next_follow_at"
            type="datetime"
            placeholder="选择日期时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>
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

.filters {
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.follow-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
</style>
