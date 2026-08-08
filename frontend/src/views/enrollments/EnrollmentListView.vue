<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  listEnrollmentsApi,
  type EnrollmentKind,
  type EnrollmentRecord,
} from '../../api/enrollments'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useServerPagedList } from '../../composables/useServerPagedList'

const router = useRouter()
const { isApp } = useBreakpoint()
const kind = ref<'' | EnrollmentKind>('')
const filterVisible = ref(false)

const kindLabels: Record<string, string> = {
  enroll: '报名',
  renew: '续费',
  transfer: '转课',
}

const kindTagType: Record<string, 'success' | 'warning' | 'primary' | 'info'> = {
  enroll: 'success',
  renew: 'warning',
  transfer: 'primary',
}

const activeFilterCount = computed(() => Number(Boolean(kind.value)))

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const {
  page,
  pageSize,
  total,
  rows,
  loading,
  loadingMore,
  hasMore,
  sentinelRef,
  load,
  loadMore,
  resetAndLoad,
  onPageChange,
  onPageSizeChange,
  setupScrollObserver,
} = useServerPagedList<EnrollmentRecord>({
  isCompact: isApp,
  getId: (r) => r.id,
  fetchPage: (p, size) =>
    listEnrollmentsApi({
      kind: kind.value || undefined,
      page: p,
      page_size: size,
    }),
})

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

function formatDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('zh-CN')
}

function nameInitial(name?: string | null) {
  return (name || '?').trim().slice(0, 1) || '?'
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
    .join('、')
}

function courseNames(row: EnrollmentRecord) {
  const names = (row.courses || []).map((c) => c.name).filter(Boolean)
  if (!names.length) return ''
  return names.length > 2 ? `${names.slice(0, 2).join('、')} 等${names.length}门` : names.join('、')
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

function goBack() {
  void router.push('/enrollments')
}

function goOrder(row: EnrollmentRecord) {
  if (!row.order_id) return
  void router.push(`/finance/orders/${row.order_id}`)
}

function goNewEnrollment() {
  void router.push('/enrollments')
}

function recordRowClass({ row }: { row: EnrollmentRecord }) {
  return row.order_id ? 'is-linked-order' : ''
}

function runQuery() {
  void resetAndLoad()
}

function resetFilters() {
  kind.value = ''
  void resetAndLoad()
}

watch(kind, () => {
  // PC radio group drives reload; app sheet applies via runQuery
  if (!isApp.value) void resetAndLoad()
})

onMounted(async () => {
  await load({ reset: true })
  await nextTick()
  if (sentinelRef.value) setupScrollObserver()
})
</script>

<template>
  <div class="enrollment-records-page">
    <div class="page-toolbar" :class="{ 'is-app': isApp }">
      <el-page-header v-if="!isApp" content="最近登记" @back="goBack" />
      <el-page-header v-else class="is-title-only" content="报名记录" />
      <el-button
        v-if="!isApp"
        type="primary"
        class="tb-btn tb-btn--primary"
        @click="goNewEnrollment"
      >
        <el-icon><Plus /></el-icon>
        去登记
      </el-button>
    </div>

    <button v-if="isApp" type="button" class="oc-app-cta enroll-cta" @click="goNewEnrollment">
      <span class="oc-app-cta__ico" aria-hidden="true">
        <el-icon><Ticket /></el-icon>
      </span>
      <span class="oc-app-cta__copy">
        <strong>报名 / 续费 / 转课</strong>
        <em>选学员 · 选课程 · 完成收款登记</em>
      </span>
      <span class="oc-app-cta__go">
        去办理
        <el-icon><ArrowRight /></el-icon>
      </span>
    </button>

    <el-card v-if="!isApp" class="module-card" shadow="never" v-loading="loading">
      <div class="records-toolbar">
        <el-radio-group v-model="kind">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="enroll">报名</el-radio-button>
          <el-radio-button value="renew">续费</el-radio-button>
          <el-radio-button value="transfer">转课</el-radio-button>
        </el-radio-group>
        <span class="record-count">共 {{ total }} 条</span>
      </div>

      <div class="records-table-wrap">
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
                :type="kindTagType[row.kind] || 'info'"
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

    <template v-else>
      <CompactFilterBar
        :active-count="activeFilterCount"
        :total="total"
        label="条登记"
        @open="filterVisible = true"
      />
      <MobileFilterSheet
        v-model="filterVisible"
        :active-count="activeFilterCount"
        @apply="runQuery"
        @reset="resetFilters"
      >
        <el-form label-position="top" @submit.prevent="runQuery">
          <el-form-item label="业务类型">
            <el-radio-group v-model="kind" class="kind-filter-group">
              <el-radio-button value="">全部</el-radio-button>
              <el-radio-button value="enroll">报名</el-radio-button>
              <el-radio-button value="renew">续费</el-radio-button>
              <el-radio-button value="transfer">转课</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </MobileFilterSheet>

      <div v-loading="loading" class="m-card-list enroll-m-list">
        <div v-if="!rows.length && !loading" class="oc-app-empty">
          <span class="enroll-empty-ico" aria-hidden="true">🎫</span>
          <strong>暂无报名记录</strong>
          <em>完成报名、续费或转课后，记录会出现在这里</em>
          <el-button type="primary" class="enroll-empty-cta" @click="goNewEnrollment">
            去登记
          </el-button>
        </div>

        <article
          v-for="row in rows"
          :key="row.id"
          class="m-card enroll-m-card"
          :class="{ 'is-unlinked': !row.order_id }"
          @click="goOrder(row)"
        >
          <div class="m-card-head">
            <div class="enroll-m-who">
              <span class="name-avatar" :class="`kind-${row.kind}`">
                {{ nameInitial(row.student_name) }}
              </span>
              <div class="enroll-m-text">
                <div class="m-card-title">
                  {{ row.student_name || `学员#${row.student_id}` }}
                  <el-tag
                    size="small"
                    effect="plain"
                    round
                    :type="kindTagType[row.kind] || 'info'"
                  >
                    {{ kindLabels[row.kind] || row.kind }}
                  </el-tag>
                </div>
                <div class="enroll-m-sub">
                  <template v-if="row.student_phone">{{ row.student_phone }} · </template>
                  {{ courseNames(row) || '未关联课程' }}
                </div>
              </div>
            </div>
            <div class="enroll-m-amount">
              <span class="enroll-m-amount-label">应收</span>
              <strong class="pc-mono">{{ formatMoney(row.amount) }}</strong>
            </div>
          </div>

          <div class="oc-meta-chips enroll-m-chips">
            <span v-if="row.handled_at" class="oc-meta-chip">
              <el-icon><Calendar /></el-icon>
              {{ formatDate(row.handled_at) }}
            </span>
            <span v-if="paymentSummary(row)" class="oc-meta-chip is-gold">
              <el-icon><Wallet /></el-icon>
              {{ paymentSummary(row) }}
            </span>
            <span v-if="row.order_no" class="oc-meta-chip">
              <el-icon><Ticket /></el-icon>
              {{ row.order_no }}
            </span>
            <span v-if="row.created_by_name" class="oc-meta-chip">
              <el-icon><User /></el-icon>
              {{ row.created_by_name }}
            </span>
            <span v-if="!row.order_id" class="oc-meta-chip is-warn">未关联订单</span>
          </div>

          <div class="m-card-actions" @click.stop>
            <el-button
              v-if="row.order_id"
              size="small"
              type="primary"
              plain
              @click="goOrder(row)"
            >
              查看订单
            </el-button>
            <el-button v-else size="small" disabled>无订单</el-button>
          </div>
        </article>

        <div ref="sentinelRef" class="list-load-sentinel">
          <ListLoadStatus
            :has-more="hasMore"
            :loading="loadingMore"
            :loaded="rows.length"
            :total="total"
            @more="loadMore"
            @retry="loadMore"
          />
        </div>
      </div>
    </template>

    <PcPagerBar
      v-if="!isApp"
      v-model:page="page"
      v-model:page-size="pageSize"
      :total="total"
      @change="onPageChange"
      @size-change="onPageSizeChange"
    />
  </div>
</template>

<style scoped>
.enrollment-records-page {
  width: 100%;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.page-toolbar.is-app {
  margin-bottom: 4px;
}

.enroll-cta {
  margin-bottom: 12px;
}

.module-card {
  border-radius: 8px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.records-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.record-count {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.enroll-m-list {
  margin-top: 4px;
}

.enroll-m-who {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.enroll-m-text {
  min-width: 0;
  flex: 1;
}

.enroll-m-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.enroll-m-amount {
  flex-shrink: 0;
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.enroll-m-amount-label {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
}

.enroll-m-amount strong {
  font-size: 15px;
  font-weight: 750;
  color: var(--oc-primary, #a16207);
}

.enroll-m-chips {
  margin-top: 10px;
}

.enroll-empty-ico {
  font-size: 28px;
  line-height: 1;
}

.enroll-empty-cta {
  margin-top: 8px;
  min-height: 40px;
  border-radius: 12px;
  font-weight: 650;
}

.kind-filter-group {
  display: flex;
  flex-wrap: wrap;
  width: 100%;
}

.kind-filter-group :deep(.el-radio-button) {
  flex: 1;
  min-width: 0;
}

.kind-filter-group :deep(.el-radio-button__inner) {
  width: 100%;
  padding: 8px 4px;
}

.records-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.order-link {
  color: var(--oc-primary, #a16207);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font: inherit;
}

.student-name {
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.cell-muted {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.amount {
  color: var(--oc-primary, #a16207);
}

:deep(.is-linked-order) {
  cursor: pointer;
}

@media (max-width: 1199px) {
  .enrollment-records-page {
    padding-bottom: 8px;
  }

  .enroll-m-list {
    gap: 12px;
  }

  .enroll-m-card {
    padding: 14px 14px 12px 16px;
    border-radius: 18px !important;
    border: 1px solid rgba(181, 145, 83, 0.3) !important;
    background:
      linear-gradient(155deg, rgba(255, 255, 255, 0.92), transparent 46%),
      #fffdf8 !important;
    box-shadow:
      0 12px 28px rgba(88, 60, 24, 0.09),
      0 2px 0 rgba(255, 255, 255, 0.9) inset !important;
  }

  .enroll-m-card.is-unlinked {
    border-style: dashed !important;
    opacity: 0.94;
  }

  .enroll-m-card .m-card-title {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    font-size: 15px;
    font-weight: 720;
  }

  .enroll-m-card .m-card-actions {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px dashed rgba(181, 145, 83, 0.22);
  }

  .enroll-m-card .m-card-actions .el-button {
    min-height: 36px;
    border-radius: 10px;
    font-weight: 650;
  }

  .name-avatar {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    font-size: 15px;
    font-weight: 750;
    color: #fffdf8;
    background: linear-gradient(145deg, #d97706, #a16207);
    box-shadow: 0 4px 10px rgba(161, 98, 7, 0.22);
  }

  .name-avatar.kind-renew {
    background: linear-gradient(145deg, #f59e0b, #b45309);
  }

  .name-avatar.kind-transfer {
    background: linear-gradient(145deg, #6366f1, #4338ca);
  }
}
</style>
