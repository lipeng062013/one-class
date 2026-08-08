<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  confirmTransactionsApi,
  listTransactionsApi,
  voidTransactionApi,
  type FinanceTransaction,
} from '../../api/finance'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'

const auth = useAuthStore()
const router = useRouter()
const { isApp } = useBreakpoint()
const tab = ref('list')
const loading = ref(false)
const loadingMore = ref(false)
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
const hasMore = computed(() => rows.value.length < total.value)
const sentinelRef = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null

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

async function load(options?: { append?: boolean }) {
  const append = Boolean(options?.append && isApp.value)
  if (isApp.value && !append) page.value = 1
  if (append) loadingMore.value = true
  else loading.value = true
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
      page_size: isApp.value ? 10 : pageSize.value,
    })
    rows.value = append ? [...rows.value, ...res.items] : res.items
    total.value = res.total
    if (res.summary) {
      summary.income = res.summary.income
      summary.pending_income = res.summary.pending_income
      summary.expense = res.summary.expense
      summary.pending_expense = res.summary.pending_expense
    }
  } catch {
    if (append) page.value = Math.max(1, page.value - 1)
    else {
      rows.value = []
      total.value = 0
    }
  } finally {
    if (append) loadingMore.value = false
    else loading.value = false
  }
}

function loadMore() {
  if (!isApp.value || loading.value || loadingMore.value || !hasMore.value) return
  page.value += 1
  void load({ append: true })
}

function setupScrollObserver() {
  teardownScrollObserver()
  if (!isApp.value) return
  const el = sentinelRef.value
  if (!el) return
  scrollObserver = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore()
    },
    { root: null, rootMargin: '160px 0px', threshold: 0 },
  )
  scrollObserver.observe(el)
}

function teardownScrollObserver() {
  scrollObserver?.disconnect()
  scrollObserver = null
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
    ElMessage.success(`已确认${r.confirmed} 笔`)
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

watch(sentinelRef, async () => {
  await nextTick()
  if (isApp.value) setupScrollObserver()
})

onMounted(async () => {
  await load()
  await nextTick()
  if (isApp.value) setupScrollObserver()
})

onUnmounted(() => teardownScrollObserver())

watch(isApp, async () => {
  selectedIds.value = []
  page.value = 1
  await load()
  await nextTick()
  if (isApp.value) setupScrollObserver()
  else teardownScrollObserver()
})
</script>

<template>
  <div class="tx-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="收支明细" />
      <el-button
        v-if="auth.isAdmin && !isApp"
        type="primary"
        class="tb-btn tb-btn--primary"
        :disabled="!selectedIds.length"
        @click="onConfirm"
      >
        确认收入{{ selectedIds.length ? ` ${selectedIds.length}` : '' }}
      </el-button>
    </div>

    <section class="module-card" v-loading="loading">
      <el-tabs
        v-model="tab"
        class="mode-tabs"
        :class="{ 'oc-segment-tabs': isApp }"
        @tab-change="runQuery"
      >
        <el-tab-pane label="收支明细" name="list" />
        <el-tab-pane label="已作废明细" name="void" />
      </el-tabs>

      <div v-if="!isApp" class="filter-row">
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

      <CompactFilterBar
        v-else
        :active-count="activeFilterCount"
        :total="total"
        label="笔收支"
        @open="filterVisible = true"
      />

      <div class="summary-bar" aria-label="收支汇总">
        <div class="summary-item">
          <span>合计收入</span>
          <strong class="income">{{ summary.income.toFixed(2) }}</strong>
        </div>
        <div class="summary-item">
          <span>待确认收入</span>
          <strong class="warn">{{ summary.pending_income.toFixed(2) }}</strong>
        </div>
        <div class="summary-item">
          <span>合计支出</span>
          <strong>{{ summary.expense.toFixed(2) }}</strong>
        </div>
        <div class="summary-item">
          <span>待确认支出</span>
          <strong>{{ summary.pending_expense.toFixed(2) }}</strong>
        </div>
      </div>

      <div v-if="isApp" class="m-card-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty oc-app-empty">
          <span class="tx-empty-ico" aria-hidden="true">💰</span>
          <strong>{{ tab === 'void' ? '暂无作废明细' : '暂无收支记录' }}</strong>
          <em>{{ activeFilterCount ? '当前筛选没有匹配记录，可清空条件后重试' : '订单收款或确认后会出现在这里' }}</em>
        </div>
        <article v-for="row in rows" :key="row.id" class="m-card tx-m-card">
          <div class="m-card-head">
            <div class="tx-card-main">
              <div class="m-card-title">{{ row.item || '收支' }}</div>
              <div class="tx-card-sub">
                <span>{{ formatTime(row.handled_at) }}</span>
                <el-tag
                  size="small"
                  effect="plain"
                  round
                  :type="row.status_code === 'pending' ? 'warning' : row.status_code === 'void' ? 'info' : 'success'"
                >
                  {{ row.status }}
                </el-tag>
              </div>
            </div>
            <strong
              class="tx-card-amount"
              :class="row.tx_type === 'income' ? 'amt-in' : 'amt-out'"
            >
              {{ row.tx_type === 'income' ? '+' : '-' }}{{ Number(row.amount || 0).toFixed(2) }}
            </strong>
          </div>
          <div class="oc-meta-chips tx-m-chips">
            <span class="oc-meta-chip" :class="row.tx_type === 'income' ? 'is-ok' : 'is-danger'">
              {{ row.type || (row.tx_type === 'income' ? '收入' : '支出') }}
            </span>
            <span v-if="row.payer" class="oc-meta-chip">{{ row.payer }}</span>
            <span v-if="row.handler" class="oc-meta-chip">经办 {{ row.handler }}</span>
            <span v-if="row.pay_method" class="oc-meta-chip">{{ row.pay_method }}</span>
            <button
              v-if="row.order_id && row.order_no"
              type="button"
              class="oc-meta-chip is-gold link-chip"
              @click.stop="goOrder(row.order_id)"
            >
              {{ row.order_no }}
            </button>
            <span v-else-if="row.order_no" class="oc-meta-chip">{{ row.order_no }}</span>
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
        </article>
        <div ref="sentinelRef" class="list-load-sentinel"><ListLoadStatus :has-more="hasMore"
          :loading="loadingMore"
          :loaded="rows.length"
          :total="total"
          @more="loadMore"
          @retry="loadMore"
        /></div>
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
            <span v-if="row.status_code === 'pending'" class="status-dot">◍</span>
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
    </section>

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
      v-if="!isApp"
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
  padding: 12px 16px 8px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: var(--oc-card, #fffdf8);
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

.tx-card-main {
  min-width: 0;
}

.tx-card-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 5px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.tx-card-amount {
  flex: 0 0 auto;
  font-size: 18px;
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
}

.tx-m-chips {
  margin-top: 10px;
}

.tx-empty-ico {
  font-size: 28px;
  line-height: 1;
}

.link-chip {
  appearance: none;
  cursor: pointer;
  font: inherit;
}

@media (max-width: 1199px) {
  .module-card {
    margin-top: 0;
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
  }

  .filter-row {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: stretch;
  }

  .filter-ctl,
  .filter-ctl--sm {
    width: 100%;
  }

  .page-toolbar {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }

  .page-toolbar .el-button {
    width: 100%;
  }

  .summary-bar {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0;
    padding: 0;
    line-height: 1.4;
    border-radius: 16px;
    overflow: hidden;
  }

  .summary-item {
    padding: 12px;
  }

  .summary-item:nth-child(odd) {
    border-right: 1px solid var(--oc-border, #e8e0d0);
  }

  .summary-item:nth-child(-n + 2) {
    border-bottom: 1px solid var(--oc-border, #e8e0d0);
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
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.summary-item span {
  font-size: 12px;
}

.summary-item strong {
  color: var(--oc-ink, #44403c);
  font-weight: 700;
  font-size: 16px;
}

.summary-item strong::before {
  content: '¥';
  margin-right: 2px;
  color: var(--oc-muted, #78716c);
  font-size: 11px;
  font-weight: 500;
}

.summary-item strong.warn {
  color: var(--oc-primary, #a16207);
}

.summary-item strong.income {
  color: #438a37;
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

@media (max-width: 1199px) {
  .summary-bar {
    gap: 0;
    padding: 0;
    line-height: 1.4;
  }
}

@media (min-width: 768px) and (max-width: 1199px) {
  .summary-bar {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .summary-item {
    border-right: 1px solid var(--oc-border, #e8e0d0);
    border-bottom: 0 !important;
  }

  .summary-item:last-child {
    border-right: 0;
  }
}

@media (max-width: 767px) {
  .summary-bar {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */
</style>
