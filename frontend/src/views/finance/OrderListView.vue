<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createOrderApi, listOrdersApi, type FinanceOrder } from '../../api/finance'
import { listStudentsApi, type Student } from '../../api/students'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useListScrollRestore } from '../../composables/useListScrollRestore'

const LIST_STATE_KEY = 'oc-order-list-state'
const PAGE_SIZES = [10, 20, 50, 100]

const route = useRoute()
const router = useRouter()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const tab = ref('list')
const keywordOrder = ref('')
const keywordStudent = ref('')
const orderType = ref('')
const rows = ref<FinanceOrder[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedOrderId = ref<number | null>(null)
const visibleCount = computed(() => rows.value.length)

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('orders', {
  visibleCount,
})

const formVisible = ref(false)
const saving = ref(false)
const studentOptions = ref<Student[]>([])
const form = reactive({
  student_id: undefined as number | undefined,
  order_type: 'transfer',
  item_summary: '',
  receivable: 0,
  received: 0,
  pay_method: '微信',
})

const quickActions = [
  { key: 'enroll', label: '报名/续费', icon: 'Ticket', path: '/enrollments' },
  { key: 'recharge', label: '账户充值', icon: 'Wallet', path: '/finance/recharge' },
  { key: 'transfer', label: '转课', icon: 'Switch', orderType: 'transfer' },
  { key: 'drop', label: '退课', icon: 'Remove', orderType: 'drop' },
  { key: 'refund', label: '账户退款', icon: 'RefreshLeft', orderType: 'refund' },
  { key: 'other', label: '其他建单', icon: 'Document', orderType: 'other' },
]

const typeLabels: Record<string, string> = {
  transfer: '转课',
  drop: '退课',
  refund: '账户退款',
  other: '其他',
}

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
    return v
  }
}

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY)
    if (!raw) return
    const state = JSON.parse(raw) as {
      tab?: string
      keywordOrder?: string
      keywordStudent?: string
      orderType?: string
      page?: number
      pageSize?: number
      selectedOrderId?: number | null
    }
    if (state.tab === 'list') tab.value = state.tab
    keywordOrder.value = state.keywordOrder ?? ''
    keywordStudent.value = state.keywordStudent ?? ''
    orderType.value = state.orderType ?? ''
    if (typeof state.page === 'number' && state.page > 0) page.value = state.page
    if (typeof state.pageSize === 'number' && PAGE_SIZES.includes(state.pageSize)) {
      pageSize.value = state.pageSize
    }
    selectedOrderId.value =
      typeof state.selectedOrderId === 'number' ? state.selectedOrderId : null
  } catch {
    /* ignore corrupt state */
  }
}

function saveListState() {
  try {
    sessionStorage.setItem(
      LIST_STATE_KEY,
      JSON.stringify({
        tab: tab.value,
        keywordOrder: keywordOrder.value,
        keywordStudent: keywordStudent.value,
        orderType: orderType.value,
        page: page.value,
        pageSize: pageSize.value,
        selectedOrderId: selectedOrderId.value,
      }),
    )
  } catch {
    /* quota / private mode */
  }
}

async function load(options?: { forceTop?: boolean }) {
  const snap = options?.forceTop ? null : takeSnapshotForLoad(route.path)
  if (options?.forceTop) clearSnapshot()
  loading.value = true
  try {
    const res = await listOrdersApi({
      order_no: keywordOrder.value.trim() || undefined,
      student_q: keywordStudent.value.trim() || undefined,
      order_type: orderType.value || undefined,
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
  saveListState()
  void finishListEnter({ snap, forceTop: !!options?.forceTop })
}

function runQuery() {
  page.value = 1
  selectedOrderId.value = null
  void load({ forceTop: true })
}

function onPagerChange() {
  selectedOrderId.value = null
  void load({ forceTop: true })
}

function onQuick(a: (typeof quickActions)[0]) {
  if (a.path) {
    void router.push(a.path)
    return
  }
  if (a.orderType) openManual(a.orderType)
}

function openManual(type: string) {
  form.student_id = undefined
  form.order_type = type
  form.item_summary = typeLabels[type] || '其他'
  form.receivable = 0
  form.received = 0
  form.pay_method = '微信'
  studentOptions.value = []
  formVisible.value = true
}

async function searchStudents(q: string) {
  if (!q.trim()) return
  const res = await listStudentsApi({ q: q.trim(), page: 1, page_size: 20 }).catch(() => ({
    items: [] as Student[],
  }))
  studentOptions.value = res.items
}

async function saveManual() {
  if (!form.student_id) {
    ElMessage.warning('请选择学员')
    return
  }
  if (!form.item_summary.trim()) {
    ElMessage.warning('请填写购买项目/摘要')
    return
  }
  saving.value = true
  try {
    const order = await createOrderApi({
      student_id: form.student_id,
      order_type: form.order_type,
      item_summary: form.item_summary.trim(),
      receivable: form.receivable,
      received: form.received,
      pay_method: form.pay_method,
    })
    ElMessage.success('订单已创建')
    formVisible.value = false
    await load()
    selectedOrderId.value = order.id
    saveListState()
    void router.push(`/finance/orders/${order.id}`)
  } catch {
    /* */
  } finally {
    saving.value = false
  }
}

function goDetail(row: FinanceOrder) {
  selectedOrderId.value = row.id
  saveListState()
  void router.push(`/finance/orders/${row.id}`)
}

onMounted(() => {
  restoreListState()
  void load()
})
</script>

<template>
  <div class="order-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="订单管理" />
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <div class="quick-actions">
        <button
          v-for="a in quickActions"
          :key="a.key"
          type="button"
          class="quick-item"
          @click="onQuick(a)"
        >
          <el-icon :size="22"><component :is="a.icon" /></el-icon>
          <span>{{ a.label }}</span>
        </button>
      </div>

      <el-tabs v-model="tab" class="mode-tabs">
        <el-tab-pane label="订单列表" name="list" />
      </el-tabs>

      <div class="filter-row">
        <el-input v-model="keywordOrder" clearable placeholder="订单号" class="filter-search" @keyup.enter="runQuery">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input
          v-model="keywordStudent"
          clearable
          placeholder="学员姓名/手机号"
          class="filter-search"
          @keyup.enter="runQuery"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="orderType" clearable placeholder="订单类型" class="filter-type" @change="runQuery">
          <el-option label="报名" value="enroll" />
          <el-option label="续费" value="renew" />
          <el-option label="充值" value="recharge" />
          <el-option label="转课" value="transfer" />
          <el-option label="退课" value="drop" />
          <el-option label="退款" value="refund" />
          <el-option label="其他" value="other" />
        </el-select>
        <el-button type="primary" @click="runQuery">查询</el-button>
      </div>

      <div v-if="isCompact" class="m-card-list">
        <div v-if="!rows.length && !loading" class="m-card m-card-empty">暂无订单</div>
        <div
          v-for="row in rows"
          :key="row.id"
          class="m-card order-m-card"
          :class="{ 'is-selected': selectedOrderId === row.id }"
          @click="goDetail(row)"
        >
          <div class="m-card-head">
            <div>
              <div class="link-name">{{ row.order_no }}</div>
              <div class="pc-muted">{{ row.student }} · {{ row.phone || '—' }}</div>
            </div>
            <el-tag
              :type="row.status === 'void' ? 'info' : 'success'"
              size="small"
              effect="plain"
              round
            >
              {{ row.status_label }}
            </el-tag>
          </div>
          <div class="m-card-meta">
            <span><span class="k">类型</span>{{ row.order_type_label }}</span>
            <span><span class="k">项目</span>{{ row.item || '—' }}</span>
            <span><span class="k">应收</span>{{ formatMoney(row.receivable) }}</span>
            <span><span class="k">实收</span>{{ formatMoney(row.received) }}</span>
            <span><span class="k">时间</span>{{ formatTime(row.created_at) }}</span>
          </div>
        </div>
      </div>

      <div v-else class="oc-compact-table-wrap">
        <el-table
          :data="rows"
          row-key="id"
          stripe
          border
          highlight-current-row
          :current-row-key="selectedOrderId ?? undefined"
          :header-cell-style="pcHeaderStyle"
          @row-click="goDetail"
        >
          <el-table-column prop="order_no" label="订单号" min-width="170" fixed>
            <template #default="{ row }">
              <span class="link-name" @click.stop="goDetail(row)">{{ row.order_no }}</span>
            </template>
          </el-table-column>
          <el-table-column label="学员/手机号" min-width="130">
            <template #default="{ row }">
              <div>{{ row.student }}</div>
              <div class="pc-muted">{{ row.phone || '—' }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="order_type_label" label="订单类型" width="90" align="center" />
          <el-table-column prop="item" label="购买项目" min-width="180" show-overflow-tooltip />
          <el-table-column label="应收" width="110" align="right">
            <template #default="{ row }">
              <span class="money-in">{{ formatMoney(row.receivable) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="实收" width="110" align="right">
            <template #default="{ row }">
              <span class="money-in">{{ formatMoney(row.received) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="source" label="订单来源" width="100" />
          <el-table-column prop="performance_owner" label="业绩归属人" min-width="120" show-overflow-tooltip />
          <el-table-column prop="handler" label="经办人" min-width="100" show-overflow-tooltip />
          <el-table-column label="创建时间" width="150">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="status_label" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.status === 'void' ? 'info' : 'success'"
                size="small"
                effect="plain"
                round
              >
                {{ row.status_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="pay_method" label="支付方式" width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </el-card>

    <PcPagerBar
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="onPagerChange"
    />

    <el-dialog
      v-model="formVisible"
      :title="`手工建单 · ${typeLabels[form.order_type] || '其他'}`"
      width="460px"
      destroy-on-close
      align-center
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="manual-tip"
        title="转课/退课等为财务记账入口；复杂调课仍请在教务侧调整班级与课包。"
      />
      <el-form label-width="100px" style="margin-top: 12px">
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
        <el-form-item label="订单类型">
          <el-select v-model="form.order_type" style="width: 100%">
            <el-option label="转课" value="transfer" />
            <el-option label="退课" value="drop" />
            <el-option label="账户退款" value="refund" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目摘要" required>
          <el-input v-model="form.item_summary" placeholder="如：转至高一物理 / 退剩余课时" />
        </el-form-item>
        <el-form-item label="应收(元)">
          <el-input-number v-model="form.receivable" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="实收(元)">
          <el-input-number v-model="form.received" :min="0" :precision="2" style="width: 100%" />
          <p class="form-hint">退课/退款可填实退金额；将生成待确认收支。</p>
        </el-form-item>
        <el-form-item label="支付方式">
          <el-select v-model="form.pay_method" style="width: 100%">
            <el-option label="微信" value="微信" />
            <el-option label="支付宝" value="支付宝" />
            <el-option label="POS机刷卡" value="POS机刷卡" />
            <el-option label="现金" value="现金" />
            <el-option label="账户余额" value="账户余额" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveManual">创建并查看</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.order-page {
  width: 100%;
}

.module-card {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.module-card :deep(.el-card__body) {
  padding: 16px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 4px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  margin-bottom: 8px;
}

.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 72px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  color: var(--oc-ink, #44403c);
  font-size: 12px;
}

.quick-item:hover {
  background: rgba(161, 98, 7, 0.08);
  color: var(--oc-primary, #a16207);
}

.quick-item .el-icon {
  color: var(--oc-primary, #a16207);
}

.mode-tabs :deep(.el-tabs__item.is-active) {
  color: var(--oc-primary, #a16207);
  font-weight: 650;
}

.order-m-card {
  cursor: pointer;
}

.order-m-card.is-selected {
  border-color: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.16);
}

.filter-type {
  width: 140px;
}

@media (max-width: 991px) {
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-search,
  .filter-type {
    width: 100% !important;
  }

  .quick-actions {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .quick-item {
    min-width: 0;
    padding: 10px 6px;
  }
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
}

.filter-search {
  width: min(240px, 100%);
}

.link-name {
  color: var(--oc-primary, #a16207);
  font-weight: 600;
  cursor: pointer;
}

.money-in {
  color: #67c23a;
  font-variant-numeric: tabular-nums;
  font-weight: 600;
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */

.manual-tip {
  margin-bottom: 4px;
}

.form-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

:deep(.el-table__row) {
  cursor: pointer;
}
</style>
