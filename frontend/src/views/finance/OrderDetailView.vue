<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  downloadOrderReceiptApi,
  getOrderDetailApi,
  listOrderLogsApi,
  voidOrderApi,
  type FinanceOrderDetail,
  type OrderOperationLog,
} from '../../api/finance'
import { usePageBack } from '../../composables/usePageBack'

const route = useRoute()
const { goBack } = usePageBack('/finance/orders')
const loading = ref(false)
const voiding = ref(false)
const printing = ref(false)
const detail = ref<FinanceOrderDetail | null>(null)

const logsVisible = ref(false)
const logsLoading = ref(false)
const logs = ref<OrderOperationLog[]>([])

const orderId = computed(() => Number(route.params.id))

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function formatMoney(n: number | undefined | null) {
  const v = Number(n || 0)
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return String(v)
  }
}

function formatDate(v?: string | null) {
  if (!v) return '—'
  try {
    const d = new Date(v)
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } catch {
    return String(v)
  }
}

const statusStamp = computed(() => {
  const s = detail.value?.status
  if (s === 'paid') return '已支付'
  if (s === 'partial') return '部分支付'
  if (s === 'unpaid') return '未支付'
  if (s === 'void') return '已作废'
  return detail.value?.status_label || ''
})

const stampClass = computed(() => {
  const s = detail.value?.status
  if (s === 'paid') return 'is-paid'
  if (s === 'void') return 'is-void'
  if (s === 'partial') return 'is-partial'
  return 'is-unpaid'
})

async function load() {
  if (!orderId.value || Number.isNaN(orderId.value)) {
    detail.value = null
    return
  }
  loading.value = true
  try {
    // 首次打开记入「查看订单」日志
    detail.value = await getOrderDetailApi(orderId.value, { logView: true })
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function onVoid() {
  if (!detail.value || detail.value.status === 'void') return
  try {
    await ElMessageBox.confirm(
      `确定作废订单「${detail.value.order_no}」？\n· 关联收支将一并作废\n· 报名/续费将收回剩余课包\n· 充值将回退账户余额`,
      '作废订单',
      { type: 'warning', confirmButtonText: '作废', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  voiding.value = true
  try {
    detail.value = await voidOrderApi(detail.value.id)
    ElMessage.success('订单已作废（关联收支/课包/充值余额已同步处理）')
  } catch {
    /* interceptor */
  } finally {
    voiding.value = false
  }
}

async function onPrint() {
  if (!detail.value) return
  printing.value = true
  try {
    await downloadOrderReceiptApi(detail.value.id, {
      orderNo: detail.value.order_no,
      studentName: detail.value.student,
    })
    ElMessage.success('收据 PDF 已开始下载')
  } catch {
    /* interceptor */
  } finally {
    printing.value = false
  }
}

async function onOpLog() {
  if (!detail.value) return
  logsVisible.value = true
  logsLoading.value = true
  try {
    const res = await listOrderLogsApi(detail.value.id)
    logs.value = res.items || []
  } catch {
    logs.value = []
  } finally {
    logsLoading.value = false
  }
}

watch(orderId, () => {
  void load()
})

onMounted(() => {
  void load()
})
</script>

<template>
  <div v-loading="loading" class="order-detail oc-page-shell">
    <div class="page-toolbar no-print">
      <el-page-header content="订单详情" @back="goBack" />
    </div>

    <el-empty v-if="!loading && !detail" description="订单不存在或已删除" />

    <template v-else-if="detail">
      <div class="action-bar no-print">
        <el-button class="tb-btn" plain type="primary" :loading="printing" @click="onPrint">
          打印收据
        </el-button>
        <el-button
          class="tb-btn"
          plain
          type="danger"
          :disabled="detail.status === 'void'"
          :loading="voiding"
          @click="onVoid"
        >
          作废订单
        </el-button>
        <el-button class="tb-btn" plain @click="onOpLog">操作日志</el-button>
      </div>

      <el-card class="detail-card" shadow="never">
        <div class="order-head">
          <div class="order-head-main">
            <div class="order-no-row">
              <span class="order-no-label">订单号：</span>
              <span class="order-no">{{ detail.order_no }}</span>
            </div>
            <div class="order-meta">
              <span>创建时间：{{ formatTime(detail.created_at) }}</span>
              <span>订单类型：{{ detail.order_type_label }}</span>
              <span>订单来源：{{ detail.source || '机构创建' }}</span>
            </div>
          </div>
          <div class="status-stamp" :class="stampClass" aria-hidden="true">
            {{ statusStamp }}
          </div>
        </div>

        <div class="info-grid">
          <div class="info-col">
            <div class="info-line">
              <span class="k">学员姓名：</span>
              <span class="v">{{ detail.student || '—' }}</span>
            </div>
            <div class="info-line">
              <span class="k">年级：</span>
              <span class="v">{{ detail.student_grade || '—' }}</span>
            </div>
            <div class="info-line">
              <span class="k">手机号：</span>
              <span class="v">{{ detail.phone || '—' }}</span>
            </div>
          </div>
          <div class="info-col">
            <div class="info-line">
              <span class="k">应收金额(元)：</span>
              <span class="v">{{ formatMoney(detail.receivable) }}</span>
            </div>
            <div class="info-line">
              <span class="k">实收金额(元)：</span>
              <span class="v">{{ formatMoney(detail.received) }}</span>
            </div>
            <div class="info-line">
              <span class="k">欠费金额(元)：</span>
              <span class="v">{{ formatMoney(detail.arrears) }}</span>
            </div>
            <div class="info-line">
              <span class="k">对内备注：</span>
              <span class="v note">{{ detail.internal_notes || '—' }}</span>
            </div>
          </div>
          <div class="info-col">
            <div class="info-line">
              <span class="k">经办日期：</span>
              <span class="v">{{ formatDate(detail.handled_at) }}</span>
            </div>
            <div class="info-line">
              <span class="k">经办人：</span>
              <span class="v">{{ detail.handler || '—' }}</span>
            </div>
            <div class="info-line">
              <span class="k">业绩归属人：</span>
              <span class="v">{{ detail.performance_owner || '—' }}</span>
            </div>
            <div class="info-line">
              <span class="k">对外备注：</span>
              <span class="v note">{{ detail.external_notes || '—' }}</span>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="detail-card section-card" shadow="never">
        <div class="section-title">购买内容</div>
        <el-table
          :data="detail.line_items || []"
          border
          stripe
          empty-text="暂无购买明细"
          :header-cell-style="pcHeaderStyle"
        >
          <el-table-column label="购买项目" min-width="180">
            <template #default="{ row }">
              <div class="item-name">
                <span>{{ row.name }}</span>
                <el-tag v-if="row.tag" size="small" type="warning" effect="plain" class="item-tag">
                  {{ row.tag }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="price_label" label="定价标准" min-width="130" />
          <el-table-column prop="quantity_label" label="购买数量" width="100" align="center" />
          <el-table-column label="总价(元)" width="110" align="right">
            <template #default="{ row }">{{ formatMoney(row.total) }}</template>
          </el-table-column>
          <el-table-column prop="gift_qty" label="赠送数量" width="90" align="center" />
          <el-table-column prop="leave_free" label="请假免扣次数" width="120" align="center" />
          <el-table-column label="直减/折扣" width="110" align="right">
            <template #default="{ row }">
              <template v-if="row.discount">直减 ¥ {{ formatMoney(row.discount) }}</template>
              <template v-else>—</template>
            </template>
          </el-table-column>
          <el-table-column label="小计(元)" width="110" align="right">
            <template #default="{ row }">
              <span class="subtotal">¥ {{ formatMoney(row.subtotal) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="coupon" label="优惠券" width="90" align="center" />
          <el-table-column label="应收" width="110" align="right">
            <template #default="{ row }">
              <span class="recv">¥ {{ formatMoney(row.receivable) }}</span>
            </template>
          </el-table-column>
        </el-table>

        <div
          v-for="(row, idx) in detail.line_items || []"
          :key="'cls-' + idx"
          class="class-row"
        >
          <span>班级：{{ row.class_name || '—' }}</span>
          <span class="class-valid">有效期至：{{ row.valid_until || '—' }}</span>
        </div>

        <div class="line-sum">
          应收金额(元)：
          <strong>{{ formatMoney(detail.line_receivable_sum || detail.receivable) }}</strong>
        </div>
      </el-card>

      <el-card class="detail-card section-card" shadow="never">
        <div class="section-title">支付记录</div>
        <el-table
          :data="detail.payments || []"
          border
          stripe
          empty-text="暂无支付记录"
          :header-cell-style="pcHeaderStyle"
        >
          <el-table-column label="支付时间" width="160">
            <template #default="{ row }">{{ formatTime(row.created_at || row.handled_at) }}</template>
          </el-table-column>
          <el-table-column prop="handler" label="经办人" min-width="120" />
          <el-table-column label="经办日期" width="120">
            <template #default="{ row }">{{ formatDate(row.handled_at) }}</template>
          </el-table-column>
          <el-table-column prop="item" label="项目" width="110" />
          <el-table-column prop="pay_method" label="支付方式" width="110" />
          <el-table-column label="支付金额(元)" width="120" align="right">
            <template #default="{ row }">{{ formatMoney(row.amount) }}</template>
          </el-table-column>
          <el-table-column prop="voucher" label="凭证" width="80" align="center" />
          <el-table-column prop="flow_no" label="支付流水号" min-width="120" align="center" />
          <el-table-column label="操作" width="80" align="center">
            <template #default>—</template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

    <el-dialog
      v-model="logsVisible"
      title="操作日志"
      width="90%"
      style="max-width: 720px"
      destroy-on-close
      class="no-print"
    >
      <div v-loading="logsLoading">
        <el-empty v-if="!logs.length && !logsLoading" description="暂无操作记录" />
        <el-timeline v-else class="log-timeline">
          <el-timeline-item
            v-for="log in logs"
            :key="log.id"
            :timestamp="formatTime(log.created_at)"
            placement="top"
          >
            <div class="log-card">
              <div class="log-head">
                <el-tag size="small" effect="plain" type="warning">{{ log.action_label }}</el-tag>
                <span class="log-op">{{ log.operator_name || '系统' }}</span>
              </div>
              <div v-if="log.detail" class="log-detail">{{ log.detail }}</div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>
      <template #footer>
        <el-button @click="logsVisible = false">关闭</el-button>
        <el-button type="primary" plain :loading="logsLoading" @click="onOpLog">刷新</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.order-detail {
  padding-bottom: 24px;
}

.page-toolbar {
  margin-bottom: 8px;
}

.action-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-card {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  margin-bottom: 14px;
  position: relative;
}

.detail-card :deep(.el-card__body) {
  padding: 16px 18px;
}

.order-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.order-no-row {
  font-size: 15px;
  color: var(--oc-ink, #44403c);
}

.order-no-label {
  font-weight: 500;
}

.order-no {
  font-weight: 700;
  letter-spacing: 0.02em;
}

.order-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.status-stamp {
  flex-shrink: 0;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 3px solid;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  transform: rotate(-18deg);
  opacity: 0.85;
  user-select: none;
}

.status-stamp.is-paid {
  color: #67c23a;
  border-color: #67c23a;
}

.status-stamp.is-void {
  color: #a8a29e;
  border-color: #a8a29e;
}

.status-stamp.is-partial {
  color: #e6a23c;
  border-color: #e6a23c;
}

.status-stamp.is-unpaid {
  color: #f56c6c;
  border-color: #f56c6c;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px 24px;
}

.info-line {
  font-size: 13px;
  line-height: 1.9;
  color: var(--oc-ink, #44403c);
}

.info-line .k {
  color: var(--oc-muted, #78716c);
}

.info-line .v.note {
  word-break: break-word;
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  margin-bottom: 12px;
}

.item-name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.item-tag {
  flex-shrink: 0;
}

.subtotal,
.recv {
  color: var(--oc-primary, #a16207);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.class-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  border-bottom: 1px dashed var(--oc-border, #e8e0d0);
  background: #faf8f3;
}

.class-valid {
  margin-left: auto;
}

.line-sum {
  margin-top: 12px;
  text-align: right;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
}

.line-sum strong {
  color: var(--oc-primary, #a16207);
  font-size: 18px;
  font-weight: 700;
  margin-left: 4px;
}

@media (max-width: 991px) {
  .info-grid {
    grid-template-columns: 1fr;
  }

  .status-stamp {
    width: 56px;
    height: 56px;
    font-size: 12px;
  }
}

.log-timeline {
  padding-left: 4px;
  max-height: 60vh;
  overflow-y: auto;
}

.log-card {
  padding: 4px 0;
}

.log-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.log-op {
  font-size: 13px;
  color: var(--oc-ink, #44403c);
  font-weight: 600;
}

.log-detail {
  margin-top: 4px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  line-height: 1.5;
}

@media print {
  .no-print {
    display: none !important;
  }

  .order-detail {
    background: #fff;
  }

  .detail-card {
    box-shadow: none;
    break-inside: avoid;
  }
}
</style>
