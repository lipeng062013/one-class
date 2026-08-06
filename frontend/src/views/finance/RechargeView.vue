<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createRechargeApi, listRechargesApi, type RechargeRecord } from '../../api/finance'
import { listStudentsApi, type Student } from '../../api/students'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'

const { isCompact } = useBreakpoint()
const loading = ref(false)
const keyword = ref('')
const rows = ref<RechargeRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const formVisible = ref(false)
const saving = ref(false)
const studentOptions = ref<Student[]>([])
const form = reactive({
  student_id: undefined as number | undefined,
  amount: 0,
  pay_method: '微信',
  remark: '',
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function formatMoney(n: number) {
  return `¥ ${Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return String(v)
  }
}

async function load() {
  loading.value = true
  try {
    const res = await listRechargesApi({
      student_q: keyword.value.trim() || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function searchStudents(q: string) {
  if (!q.trim()) {
    studentOptions.value = []
    return
  }
  const res = await listStudentsApi({ q: q.trim(), page: 1, page_size: 20 }).catch(() => ({
    items: [] as Student[],
  }))
  studentOptions.value = res.items
}

function openCreate() {
  form.student_id = undefined
  form.amount = 0
  form.pay_method = '微信'
  form.remark = ''
  studentOptions.value = []
  formVisible.value = true
}

async function save() {
  if (!form.student_id) {
    ElMessage.warning('请选择学员')
    return
  }
  if (!form.amount || form.amount <= 0) {
    ElMessage.warning('请填写充值金额')
    return
  }
  saving.value = true
  try {
    await createRechargeApi({
      student_id: form.student_id,
      amount: form.amount,
      pay_method: form.pay_method,
      remark: form.remark,
    })
    ElMessage.success('充值成功')
    formVisible.value = false
    await load()
  } catch {
    /* */
  } finally {
    saving.value = false
  }
}

function runQuery() {
  page.value = 1
  void load()
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="recharge-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="充值管理" />
      <el-button type="primary" class="tb-btn tb-btn--primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        账户充值
      </el-button>
    </div>

    <el-card class="pc-filters" shadow="never">
      <el-form :inline="true" class="pc-filter-form" @submit.prevent="runQuery">
        <el-form-item label="学员">
          <el-input
            v-model="keyword"
            clearable
            placeholder="姓名/手机号"
            :style="isCompact ? 'width: 100%' : 'width: 200px'"
          />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="runQuery">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div v-if="isCompact" v-loading="loading" class="m-card-list recharge-m">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无充值记录</div>
      <div v-for="row in rows" :key="row.id" class="m-card">
        <div class="m-card-head">
          <div class="pc-name-cell">
            <span class="pc-avatar">{{ (row.student || '?').slice(0, 1) }}</span>
            <div>
              <div class="pc-name-text">{{ row.student }}</div>
              <div class="pc-muted">{{ row.phone || '—' }}</div>
            </div>
          </div>
          <span class="amt">{{ formatMoney(row.amount) }}</span>
        </div>
        <div class="m-card-meta">
          <span><span class="k">余额</span>{{ formatMoney(row.balance) }}</span>
          <span><span class="k">支付</span>{{ row.pay_method || '—' }}</span>
          <span><span class="k">经办</span>{{ row.handler || '—' }}</span>
          <span><span class="k">时间</span>{{ formatTime(row.created_at) }}</span>
        </div>
      </div>
    </div>

    <el-card v-else class="pc-table-card" shadow="never" v-loading="loading">
      <div class="oc-compact-table-wrap">
        <el-table :data="rows" row-key="id" stripe border :header-cell-style="pcHeaderStyle">
          <el-table-column label="学员" min-width="140">
            <template #default="{ row }">
              <div class="pc-name-cell">
                <span class="pc-avatar">{{ (row.student || '?').slice(0, 1) }}</span>
                <div>
                  <div class="pc-name-text">{{ row.student }}</div>
                  <div class="pc-muted">{{ row.phone || '—' }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="充值金额" width="120" align="right">
            <template #default="{ row }">
              <span class="amt">{{ formatMoney(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="账户余额" width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.balance) }}</template>
          </el-table-column>
          <el-table-column prop="pay_method" label="支付方式" width="110" />
          <el-table-column prop="handler" label="经办人" width="100" />
          <el-table-column label="充值时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag type="success" size="small" effect="plain" round>{{ row.status }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <PcPagerBar
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="load"
    />

    <el-dialog v-model="formVisible" title="账户充值" width="420px" destroy-on-close align-center>
      <el-form :label-position="isCompact ? 'top' : 'right'" :label-width="isCompact ? undefined : '90px'">
        <el-form-item label="学员" required>
          <el-select
            v-model="form.student_id"
            filterable
            remote
            :remote-method="searchStudents"
            placeholder="搜索学员"
            style="width: 100%"
          >
            <el-option
              v-for="s in studentOptions"
              :key="s.id"
              :label="`${s.name}${s.phone ? ' · ' + s.phone : ''}`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="充值金额" required>
          <el-input-number v-model="form.amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="支付方式">
          <el-select v-model="form.pay_method" style="width: 100%">
            <el-option label="微信" value="微信" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="POS机刷卡" value="POS机刷卡" />
            <el-option label="现金" value="现金" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">确认充值</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.recharge-page {
  width: 100%;
}

.recharge-m {
  margin-top: 12px;
}

.pc-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.pc-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 14px;
  font-weight: 700;
}

.pc-name-text {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.pc-muted {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.amt {
  font-weight: 700;
  color: var(--oc-primary, #a16207);
}

@media (max-width: 991px) {
  .page-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .page-toolbar .el-button {
    width: 100%;
  }
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.amt {
  color: #67c23a;
  font-weight: 650;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */
</style>
