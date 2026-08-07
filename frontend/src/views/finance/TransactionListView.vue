<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmTransactionsApi,
  listTransactionsApi,
  voidTransactionApi,
  type FinanceTransaction,
} from '../../api/finance'
import PcPagerBar from '../../components/PcPagerBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'

const auth = useAuthStore()
const router = useRouter()
const { isCompact } = useBreakpoint()
const tab = ref('list')
const loading = ref(false)
const rows = ref<FinanceTransaction[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref<number[]>([])
const filterVisible = ref(false)
const summary = reactive({
  income: 0,
  pending_income: 0,
  expense: 0,
  pending_expense: 0,
})

const filters = reactive({
  item: '',
  typeIncome: false,
  typeExpense: false,
  status: '',
})

const activeFilterCount = computed(() => {
  let count = 0
  if (filters.item) count += 1
  if (filters.typeIncome || filters.typeExpense) count += 1
  if (filters.status) count += 1
  return count
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    const d = new Date(v)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return String(v)
  }
}

async function load() {
  loading.value = true
  try {
    let tx_type: string | undefined
    if (filters.typeIncome && !filters.typeExpense) tx_type = 'income'
    if (filters.typeExpense && !filters.typeIncome) tx_type = 'expense'
    const res = await listTransactionsApi({
      item: filters.item || undefined,
      tx_type,
      status: filters.status || undefined,
      include_void: tab.value === 'void',
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = res.items
    total.value = res.total
    if (res.summary) {
      summary.income = res.summary.income
      summary.pending_income = res.summary.pending_income
      summary.expense = res.summary.expense
      summary.pending_expense = res.summary.pending_expense
    }
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onSelectionChange(sel: FinanceTransaction[]) {
  selectedIds.value = sel.filter((r) => r.status_code === 'pending').map((r) => r.id)
}

async function onConfirm() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请勾选待确认记录')
    return
  }
  try {
    const r = await confirmTransactionsApi(selectedIds.value)
    ElMessage.success(`已确认 ${r.confirmed} 笔`)
    await load()
  } catch {
    /* */
  }
}

async function onVoid(row: FinanceTransaction) {
  try {
    await ElMessageBox.confirm('确定作废该笔收支？作废后不计入确认收入。', '作废确认', {
      type: 'warning',
    })
    await voidTransactionApi(row.id)
    ElMessage.success('已作废')
    await load()
  } catch {
    /* */
  }
}

function runQuery() {
  page.value = 1
  void load()
}

function resetFilters() {
  filters.item = ''
  filters.typeIncome = false
  filters.typeExpense = false
  filters.status = ''
}

function applyMobileFilters() {
  runQuery()
}

function goOrder(orderId?: number | null) {
  if (orderId) void router.push(`/finance/orders/${orderId}`)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="tx-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="收支明细" />
      <el-button
        v-if="auth.isAdmin"
        type="primary"
        class="tb-btn tb-btn--primary"
        :disabled="!selectedIds.length"
        @click="onConfirm"
      >
        确认收入{{ selectedIds.length ? ` ${selectedIds.length}` : '' }}
      </el-button>
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <el-tabs v-model="tab" class="mode-tabs" @tab-change="runQuery">
        <el-tab-pane label="收支明细" name="list" />
        <el-tab-pane label="已作废明细" name="void" />
      </el-tabs>

      <div v-if="!isCompact" class="filter-row">
        <el-select v-model="filters.item" clearable placeholder="项目" class="filter-ctl" @change="runQuery">
          <el-option label="报名/续费" value="报名/续费" />
          <el-option label="账户充值" value="账户充值" />
          <el-option label="退费" value="退费" />
        </el-select>
        <div class="check-group">
          <span class="check-label">收支类型</span>
          <el-checkbox v-model="filters.typeIncome" @change="runQuery">收入</el-checkbox>
          <el-checkbox v-model="filters.typeExpense" @change="runQuery">支出</el-checkbox>
        </div>
        <el-select v-model="filters.status" clearable placeholder="状态" class="filter-ctl filter-ctl--sm" @change="runQuery">
          <el-option label="待确认" value="pending" />
          <el-option label="已确认" value="confirmed" />
        </el-select>
        <el-button type="primary" @click="runQuery">查询</el-button>
      </div>

      <div v-else class="mobile-filter-trigger">
        <el-button class="mobile-filter-trigger__button" @click="filterVisible = true">
          筛选条件
          <span v-if="activeFilterCount" class="mobile-filter-trigger__count">{{ activeFilterCount }}</span>
        </el-button>
        <span class="mobile-filter-trigger__result">共 {{ total }} 条</span>
      </div>

      <div class="summary-bar">
        合计收入(元) <strong>{{ summary.income.toFixed(2) }}</strong>
        待确认收入(元) <strong class="warn">{{ summary.pending_income.toFixed(2) }}</strong>
        合计支出(元) <strong>{{ summary.expense.toFixed(2) }}</strong>
        待确认支出(元) <strong>{{ summary.pending_expense.toFixed(2) }}</strong>
      </div>

      <div v-if="isCompact" class="m-card-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无收支记录</div>
        <div v-for="row in rows" :key="row.id" class="m-card">
          <div class="m-card-head">
            <div class="m-card-title">{{ row.item || '收支' }}</div>
            <el-tag size="small" effect="plain" round>{{ row.status }}</el-tag>
          </div>
          <div class="m-card-meta">
            <span><span class="k">日期</span>{{ formatTime(row.handled_at) }}</span>
            <span><span class="k">类型</span>{{ row.type || row.tx_type }}</span>
            <span class="m-card-amount" :class="row.tx_type === 'income' ? 'amt-in' : 'amt-out'">
              <span class="k">金额</span>
              {{ row.tx_type === 'income' ? '+' : '-' }}{{ Number(row.amount || 0).toFixed(2) }}
            </span>
            <span v-if="row.payer"><span class="k">收付款人</span>{{ row.payer }}</span>
            <span v-if="row.order_no">
              <span class="k">订单</span>
              <button v-if="row.order_id" type="button" class="link-btn" @click.stop="goOrder(row.order_id)">
                {{ row.order_no }}
              </button>
              <span v-else>{{ row.order_no }}</span>
            </span>
          </div>
          <div
            v-if="auth.isAdmin && tab === 'list' && row.status_code !== 'void'"
            class="m-card-actions"
          >
            <el-button
              v-if="row.status_code === 'pending'"
              size="small"
              type="primary"
              plain
              @click="selectedIds = [row.id]; onConfirm()"
            >
              确认
            </el-button>
            <el-button size="small" type="danger" plain @click="onVoid(row)">作废</el-button>
          </div>
        </div>
      </div>

      <div v-else class="oc-compact-table-wrap">
      <el-table
        :data="rows"
        row-key="id"
        stripe
        border
        :header-cell-style="pcHeaderStyle"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="44" :selectable="(row: FinanceTransaction) => row.status_code === 'pending'" />
        <el-table-column label="经办日期" width="110">
          <template #default="{ row }">{{ formatTime(row.handled_at) }}</template>
        </el-table-column>
        <el-table-column prop="item" label="项目" width="110" />
        <el-table-column prop="type" label="收支类型" width="90" align="center" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.status_code === 'pending'" class="status-dot">●</span>
            {{ row.status }}
          </template>
        </el-table-column>
        <el-table-column label="收支金额(元)" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.tx_type === 'income' ? 'amt-in' : 'amt-out'">
              {{ row.tx_type === 'income' ? '+' : '-' }}{{ row.amount.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="pay_method" label="支付方式" width="110" />
        <el-table-column prop="handler" label="经办人" min-width="100" show-overflow-tooltip />
        <el-table-column prop="order_no" label="关联订单号" min-width="160">
          <template #default="{ row }">
            <button v-if="row.order_id && row.order_no" type="button" class="link-btn" @click.stop="goOrder(row.order_id)">
              {{ row.order_no }}
            </button>
            <span v-else>{{ row.order_no || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="payer" label="收付款人" min-width="110" show-overflow-tooltip />
        <el-table-column label="创建时间" width="150">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="auth.isAdmin && tab === 'list'" label="操作" width="90" fixed="right" align="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status_code !== 'void'"
              link
              type="primary"
              @click="onVoid(row)"
            >
              作废
            </el-button>
            <span v-else class="pc-muted">—</span>
          </template>
        </el-table-column>
      </el-table>
      </div>
    </el-card>

    <MobileFilterSheet
      v-model="filterVisible"
      :active-count="activeFilterCount"
      @reset="resetFilters"
      @apply="applyMobileFilters"
    >
      <label class="mobile-filter-field">
        <span>项目</span>
        <el-select v-model="filters.item" clearable placeholder="全部项目">
          <el-option label="报名/续费" value="报名/续费" />
          <el-option label="账户充值" value="账户充值" />
          <el-option label="退费" value="退费" />
        </el-select>
      </label>
      <div class="mobile-filter-field">
        <span>收支类型</span>
        <div class="mobile-type-options">
          <el-checkbox v-model="filters.typeIncome">收入</el-checkbox>
          <el-checkbox v-model="filters.typeExpense">支出</el-checkbox>
        </div>
      </div>
      <label class="mobile-filter-field">
        <span>状态</span>
        <el-select v-model="filters.status" clearable placeholder="全部状态">
          <el-option label="待确认" value="pending" />
          <el-option label="已确认" value="confirmed" />
        </el-select>
      </label>
    </MobileFilterSheet>

    <PcPagerBar
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="load"
    />
  </div>
</template>

<style scoped>
.tx-page {
  width: 100%;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.module-card {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.module-card :deep(.el-card__body) {
  padding: 12px 16px 8px;
}

.mode-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.filter-ctl {
  width: 160px;
}

.filter-ctl--sm {
  width: 120px;
}

.mobile-filter-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.mobile-filter-trigger__button {
  min-width: 116px;
}

.mobile-filter-trigger__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 10px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 12px;
}

.mobile-filter-trigger__result {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.mobile-filter-field {
  display: grid;
  gap: 8px;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  font-weight: 600;
}

.mobile-type-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mobile-type-options :deep(.el-checkbox) {
  margin: 0;
  padding: 0 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 6px;
}

.m-card-amount {
  font-size: 15px;
}

@media (max-width: 991px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-ctl,
  .filter-ctl--sm {
    width: 100%;
  }

  .page-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .page-toolbar .el-button {
    width: 100%;
  }

  .summary-bar {
    line-height: 1.8;
  }
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.check-group {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.check-label {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.summary-bar {
  background: #faf3e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  align-items: center;
}

.summary-bar strong {
  color: var(--oc-ink, #44403c);
  font-weight: 700;
  margin-right: 8px;
}

.summary-bar strong.warn {
  color: var(--oc-primary, #a16207);
}

.status-dot {
  color: #e6a23c;
  margin-right: 2px;
  font-size: 10px;
}

.amt-in {
  color: #67c23a;
  font-weight: 600;
}

.amt-out {
  color: #f56c6c;
  font-weight: 600;
}

.link-name {
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.link-btn {
  appearance: none;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--oc-primary, #a16207);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */
</style>
