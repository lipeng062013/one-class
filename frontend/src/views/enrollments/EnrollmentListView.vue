<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  listEnrollmentsApi,
  type EnrollmentKind,
  type EnrollmentRecord,
} from '../../api/enrollments'
import PcPagerBar from '../../components/PcPagerBar.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'

const router = useRouter()
const { isCompact } = useBreakpoint()
const loading = ref(false)
const rows = ref<EnrollmentRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const kind = ref<'' | EnrollmentKind>('')

const kindLabels: Record<string, string> = {
  enroll: '报名',
  renew: '续费',
}

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

function formatMoney(value?: number | null) {
  return `¥${Number(value || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function formatTime(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function courseSummary(row: EnrollmentRecord) {
  return (row.courses || [])
    .map((course) => {
      const details = [course.name]
      if (course.hours != null) details.push(`购买${Number(course.hours)}课时`)
      if (Number(course.gift_hours || 0) > 0) {
        details.push(`赠送${Number(course.gift_hours)}课时`)
      }
      return details.join(' · ')
    })
    .join('；')
}

function paymentSummary(row: EnrollmentRecord) {
  const methods = row.pay_methods || []
  if (!methods.length) return ''
  return methods.join('、') + (row.pay_other ? `（${row.pay_other}）` : '')
}

function attributionSummary(row: EnrollmentRecord) {
  return (row.attributions || [])
    .map((item) => `${item.display_name || `用户#${item.user_id}`} ${formatMoney(item.amount)}`)
    .join('、')
}

async function load() {
  loading.value = true
  try {
    const result = await listEnrollmentsApi({
      kind: kind.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    rows.value = result.items
    total.value = result.total
  } catch {
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function runQuery() {
  page.value = 1
  void load()
}

function goBack() {
  void router.push('/enrollments')
}

function goOrder(row: EnrollmentRecord) {
  if (!row.order_id) return
  void router.push(`/finance/orders/${row.order_id}`)
}

function recordRowClass({ row }: { row: EnrollmentRecord }) {
  return row.order_id ? 'is-linked-order' : ''
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="enrollment-records-page">
    <div class="page-toolbar">
      <el-page-header content="最近登记" @back="goBack" />
    </div>

    <el-card class="module-card" shadow="never" v-loading="loading">
      <div class="records-toolbar">
        <el-radio-group v-model="kind" @change="runQuery">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="enroll">报名</el-radio-button>
          <el-radio-button value="renew">续费</el-radio-button>
        </el-radio-group>
        <span class="record-count">共 {{ total }} 条</span>
      </div>

      <template v-if="isCompact">
        <el-empty v-if="!rows.length && !loading" description="暂无报名/续费记录" />
        <div v-else class="mobile-record-list">
          <button
            v-for="row in rows"
            :key="row.id"
            type="button"
            class="mobile-record-row"
            :class="{ 'is-unlinked': !row.order_id }"
            :disabled="!row.order_id"
            @click="goOrder(row)"
          >
            <div class="mobile-record-head">
              <span class="student-name">{{ row.student_name || `学员#${row.student_id}` }}</span>
              <el-tag
                size="small"
                effect="plain"
                :type="row.kind === 'enroll' ? 'success' : 'warning'"
              >
                {{ kindLabels[row.kind] || row.kind }}
              </el-tag>
            </div>
            <div class="mobile-record-meta">
              <span v-if="row.order_no">订单 {{ row.order_no }}</span>
              <span>{{ formatMoney(row.amount) }}</span>
              <span v-if="row.handled_at">{{ formatTime(row.handled_at) }}</span>
            </div>
            <div v-if="courseSummary(row)" class="mobile-record-course">
              {{ courseSummary(row) }}
            </div>
            <el-icon v-if="row.order_id" class="row-arrow"><ArrowRight /></el-icon>
          </button>
        </div>
      </template>

      <div v-else class="records-table-wrap">
        <el-table
          :data="rows"
          row-key="id"
          stripe
          border
          class="records-table"
          :header-cell-style="pcHeaderStyle"
          :row-class-name="recordRowClass"
          empty-text="暂无报名/续费记录"
          @row-click="goOrder"
        >
          <el-table-column prop="order_no" label="订单号" min-width="180" fixed>
            <template #default="{ row }">
              <button
                v-if="row.order_id && row.order_no"
                type="button"
                class="order-link link-btn"
                @click.stop="goOrder(row)"
              >
                {{ row.order_no }}
              </button>
              <span v-else class="order-link">{{ row.order_no }}</span>
            </template>
          </el-table-column>
          <el-table-column label="学员" min-width="145">
            <template #default="{ row }">
              <div class="student-name">{{ row.student_name || `学员#${row.student_id}` }}</div>
              <div v-if="row.student_phone" class="cell-muted">{{ row.student_phone }}</div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="86" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                effect="plain"
                :type="row.kind === 'enroll' ? 'success' : 'warning'"
              >
                {{ kindLabels[row.kind] || row.kind }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="购买内容" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">{{ courseSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="应收金额" width="120" align="right">
            <template #default="{ row }">
              <strong class="amount">{{ formatMoney(row.amount) }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="支付方式" min-width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ paymentSummary(row) }}</template>
          </el-table-column>
          <el-table-column label="业绩归属" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">{{ attributionSummary(row) }}</template>
          </el-table-column>
          <el-table-column prop="created_by_name" label="经办人" min-width="100" />
          <el-table-column label="登记时间" width="170">
            <template #default="{ row }">{{ formatTime(row.handled_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="76" fixed="right" align="center">
            <template #default="{ row }">
              <el-tooltip v-if="row.order_id" content="查看订单详情" placement="top">
                <el-button link type="primary" aria-label="查看订单详情" @click.stop="goOrder(row)">
                  <el-icon><View /></el-icon>
                </el-button>
              </el-tooltip>
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
  </div>
</template>

<style scoped>
.enrollment-records-page {
  width: 100%;
}

.module-card {
  border-radius: 8px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.module-card :deep(.el-card__body) {
  padding: 14px 16px 10px;
}

.records-toolbar {
  min-height: 40px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.record-count,
.cell-muted {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.records-table-wrap {
  overflow-x: auto;
}

.records-table {
  min-width: 1220px;
}

.records-table :deep(.el-table__row.is-linked-order) {
  cursor: pointer;
}

.student-name {
  color: var(--oc-ink, #44403c);
  font-weight: 600;
}

.order-link,
.amount {
  color: var(--oc-primary, #a16207);
  font-variant-numeric: tabular-nums;
}

.link-btn {
  appearance: none;
  border: 0;
  padding: 0;
  background: transparent;
  font: inherit;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
}

.mobile-record-list {
  border-top: 1px solid var(--oc-border, #e8e0d0);
}

.mobile-record-row {
  position: relative;
  width: 100%;
  min-height: 112px;
  padding: 14px 32px 14px 2px;
  border: 0;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.mobile-record-row.is-unlinked {
  cursor: default;
}

.mobile-record-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-record-meta {
  margin-top: 7px;
  display: flex;
  flex-wrap: wrap;
  gap: 5px 12px;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.mobile-record-course {
  margin-top: 7px;
  overflow: hidden;
  color: var(--oc-primary, #a16207);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-arrow {
  position: absolute;
  top: 50%;
  right: 4px;
  transform: translateY(-50%);
  color: var(--oc-muted, #78716c);
}

@media (max-width: 640px) {
  .module-card :deep(.el-card__body) {
    padding: 12px;
  }

  .records-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
