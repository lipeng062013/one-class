<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  getIncomeReportApi,
  getPendingHoursReportApi,
  type IncomeReport,
  type PendingHoursReport,
} from '../../api/finance'
import { useBreakpoint } from '../../composables/useBreakpoint'

type QuickRange = 'month' | 'week' | 'lastWeek' | 'custom'

const loading = ref(false)
const { isCompact } = useBreakpoint()
const activeReport = ref('income')
const quickRange = ref<QuickRange>('month')
const customRange = ref<[string, string] | null>(null)
const report = ref<IncomeReport | null>(null)
const pendingReport = ref<PendingHoursReport | null>(null)

const filters = reactive({
  start_date: '',
  end_date: '',
})

const pendingFilters = reactive({
  keyword: '',
  course_id: undefined as number | undefined,
  risk_status: '',
})

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const incomeChartRows = computed(() => report.value?.income_chart || [])
const consumptionChartRows = computed(() => report.value?.course_consumption?.chart || [])

const maxIncomeValue = computed(() => Math.max(...incomeChartRows.value.map((item) => item.total), 1))
const maxConsumptionValue = computed(() => Math.max(...consumptionChartRows.value.map((item) => item.amount), 1))

const confirmedRate = computed(() => {
  const total = report.value?.total_income || 0
  if (!total) return 0
  return Math.round(((report.value?.confirmed_income || 0) / total) * 100)
})

const pendingDetailRows = computed(() => {
  const keyword = pendingFilters.keyword.trim().toLowerCase()
  return (pendingReport.value?.items || []).filter((item) => {
    if (pendingFilters.course_id && item.course_id !== pendingFilters.course_id) return false
    if (pendingFilters.risk_status && item.risk_status !== pendingFilters.risk_status) return false
    if (!keyword) return true
    return [item.student_name, item.student_phone, item.course_name, item.student_grade]
      .some((value) => String(value || '').toLowerCase().includes(keyword))
  })
})

function formatDate(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function formatShortDate(v: string) {
  const [, month, day] = v.split('-')
  return month && day ? `${month}/${day}` : v
}

function formatMoney(n: number) {
  return `¥ ${Number(n || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function formatAmount(n: number) {
  return Number(n || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function formatHours(n: number) {
  return Number(n || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function formatRate(n: number) {
  return `${Number(n || 0).toLocaleString('zh-CN', { maximumFractionDigits: 1 })}%`
}

function riskLabel(status: string) {
  if (status === 'expired') return '存在已过期'
  if (status === 'expiring') return '30天内到期'
  if (status === 'consumed') return '已消完'
  return '正常'
}

function riskTagType(status: string): 'danger' | 'warning' | 'info' | 'success' {
  if (status === 'expired') return 'danger'
  if (status === 'expiring') return 'warning'
  if (status === 'consumed') return 'info'
  return 'success'
}

function pendingRowKey(row: { student_id: number; course_id: number }) {
  return `${row.student_id}-${row.course_id}`
}

function weekStart(d: Date) {
  const day = d.getDay() || 7
  const start = new Date(d)
  start.setDate(d.getDate() - day + 1)
  return start
}

function applyQuickRange() {
  const today = new Date()
  let start = new Date(today)
  let end = new Date(today)

  if (quickRange.value === 'month') {
    start = new Date(today.getFullYear(), today.getMonth(), 1)
  } else if (quickRange.value === 'week') {
    start = weekStart(today)
  } else if (quickRange.value === 'lastWeek') {
    end = weekStart(today)
    end.setDate(end.getDate() - 1)
    start = new Date(end)
    start.setDate(end.getDate() - 6)
  } else if (customRange.value?.length === 2) {
    filters.start_date = customRange.value[0]
    filters.end_date = customRange.value[1]
    return
  }

  filters.start_date = formatDate(start)
  filters.end_date = formatDate(end)
}

async function load() {
  loading.value = true
  try {
    const [income, pending] = await Promise.all([
      getIncomeReportApi({
        start_date: filters.start_date || undefined,
        end_date: filters.end_date || undefined,
      }),
      getPendingHoursReportApi(),
    ])
    report.value = income
    pendingReport.value = pending
  } catch {
    report.value = null
    pendingReport.value = null
  } finally {
    loading.value = false
  }
}

function runQuery() {
  applyQuickRange()
  void load()
}

function onCustomRangeChange() {
  quickRange.value = 'custom'
  runQuery()
}

onMounted(() => {
  applyQuickRange()
  void load()
})
</script>

<template>
  <div class="report-page" v-loading="loading">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="确认收入报表" />
      <el-button class="tb-btn" plain @click="load">刷新</el-button>
    </div>

    <div class="report-shell">
      <div v-if="activeReport !== 'pending'" class="report-filter">
        <el-segmented
          v-model="quickRange"
          :options="[
            { label: '本月', value: 'month' },
            { label: '本周', value: 'week' },
            { label: '上周', value: 'lastWeek' },
          ]"
          @change="runQuery"
        />
        <el-date-picker
          v-model="customRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          class="date-range"
          @change="onCustomRangeChange"
        />
        <span class="range-text">{{ filters.start_date }} 至 {{ filters.end_date }}</span>
      </div>

      <el-tabs v-model="activeReport" class="report-tabs">
        <el-tab-pane label="确认收入报表" name="income" />
        <el-tab-pane label="课时课消报表" name="consumption" />
        <el-tab-pane label="课时待消报表" name="pending" />
      </el-tabs>

      <template v-if="activeReport === 'income'">
        <section class="income-overview">
          <div class="overview-main">
            <span class="eyebrow">收入合计（元）</span>
            <strong>{{ formatMoney(report?.total_income ?? 0) }}</strong>
            <span class="overview-range">{{ filters.start_date }} 至 {{ filters.end_date }}</span>
          </div>
          <div class="overview-side">
            <div class="rate-row">
              <span>确认率</span>
              <strong>{{ confirmedRate }}%</strong>
            </div>
            <div class="rate-track">
              <span :style="{ width: `${confirmedRate}%` }" />
            </div>
            <div class="mini-split">
              <span>已确认 {{ formatMoney(report?.confirmed_income ?? 0) }}</span>
              <span>待确认 {{ formatMoney(report?.pending_income ?? 0) }}</span>
            </div>
          </div>
        </section>

        <div class="stat-cards">
          <div class="stat-card tone-warn">
            <div class="stat-label">待确认收入</div>
            <div class="stat-value">{{ formatMoney(report?.pending_income ?? 0) }}</div>
          </div>
          <div class="stat-card tone-ok">
            <div class="stat-label">已确认收入</div>
            <div class="stat-value">{{ formatMoney(report?.confirmed_income ?? 0) }}</div>
          </div>
          <div class="stat-card tone-neutral">
            <div class="stat-label">支付方式</div>
            <div class="stat-value">{{ report?.by_pay_method?.length ?? 0 }}</div>
          </div>
        </div>

        <el-card class="module-card chart-card income-chart-card" shadow="never">
          <div class="card-head">
            <div>
              <div class="card-title">收入情况</div>
              <div class="card-subtitle">按收款日期汇总，单位：元</div>
            </div>
            <div class="legend">
              <span class="legend-dot" />
              <span>收入</span>
            </div>
          </div>
          <div v-if="incomeChartRows.length" class="chart-frame">
            <div class="chart-scale">
              <span>{{ formatAmount(maxIncomeValue) }}</span>
              <span>{{ formatAmount(maxIncomeValue / 2) }}</span>
              <span>0</span>
            </div>
            <div class="bar-chart">
            <div v-for="item in incomeChartRows" :key="item.date" class="bar-item">
              <div class="bar-value">{{ formatAmount(item.total) }}</div>
              <div class="bar-track income-track">
                <div class="bar-fill income-fill" :style="{ height: `${Math.max((item.total / maxIncomeValue) * 100, 4)}%` }" />
              </div>
              <div class="bar-label">{{ formatShortDate(item.date) }}</div>
            </div>
            </div>
          </div>
          <el-empty v-else description="暂无收入数据" />
        </el-card>

        <el-card class="module-card pc-table-card" shadow="never">
          <div class="card-head compact">
            <div class="card-title">按支付方式汇总</div>
          </div>
          <el-table v-if="!isCompact" :data="report?.by_pay_method || []" row-key="method" stripe border :header-cell-style="pcHeaderStyle">
            <el-table-column prop="method" label="支付方式" min-width="140" />
            <el-table-column prop="count" label="笔数" width="100" align="center" />
            <el-table-column label="金额（元）" min-width="140" align="right">
              <template #default="{ row }">
                <span class="pc-mono">{{ formatMoney(row.amount) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="占比" width="120" align="center">
              <template #default="{ row }">
                {{ report?.total_income ? ((row.amount / report.total_income) * 100).toFixed(1) : 0 }}%
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="report-card-list">
            <article v-for="row in report?.by_pay_method || []" :key="row.method" class="report-row-card">
              <div class="report-row-head"><strong>{{ row.method }}</strong><span>{{ row.count }} 笔</span></div>
              <div class="report-row-value">{{ formatMoney(row.amount) }}</div>
              <div class="report-row-meta">收入占比 {{ report?.total_income ? ((row.amount / report.total_income) * 100).toFixed(1) : 0 }}%</div>
            </article>
            <el-empty v-if="!report?.by_pay_method?.length" description="暂无支付数据" :image-size="52" />
          </div>
        </el-card>
      </template>

      <template v-else-if="activeReport === 'consumption'">
        <div class="stat-cards">
          <div class="stat-card tone-neutral">
            <div class="stat-label">课消次数</div>
            <div class="stat-value">{{ report?.course_consumption?.total_count ?? 0 }}</div>
          </div>
          <div class="stat-card tone-warn">
            <div class="stat-label">课消课时</div>
            <div class="stat-value">{{ formatHours(report?.course_consumption?.total_hours ?? 0) }}</div>
          </div>
          <div class="stat-card tone-ok">
            <div class="stat-label">课消金额（元）</div>
            <div class="stat-value">{{ formatMoney(report?.course_consumption?.total_amount ?? 0) }}</div>
          </div>
        </div>

        <el-card class="module-card chart-card" shadow="never">
          <div class="card-head">
            <div>
              <div class="card-title">课时课消情况</div>
              <div class="card-subtitle">按课程汇总课消金额，单位：元</div>
            </div>
            <div class="legend">
              <span class="legend-dot consumption-dot" />
              <span>课消金额</span>
            </div>
          </div>
          <div v-if="consumptionChartRows.length" class="chart-frame">
            <div class="chart-scale">
              <span>{{ formatAmount(maxConsumptionValue) }}</span>
              <span>{{ formatAmount(maxConsumptionValue / 2) }}</span>
              <span>0</span>
            </div>
            <div class="bar-chart">
            <div v-for="item in consumptionChartRows" :key="item.date" class="bar-item">
              <div class="bar-value">{{ formatAmount(item.amount) }}</div>
              <div class="bar-track consumption-track">
                <div
                  class="bar-fill consumption-fill"
                  :style="{ height: `${Math.max((item.amount / maxConsumptionValue) * 100, 4)}%` }"
                />
              </div>
              <div class="bar-label">{{ formatShortDate(item.date) }}</div>
            </div>
            </div>
          </div>
          <el-empty v-else description="暂无课消数据" />
        </el-card>

        <el-card class="module-card pc-table-card" shadow="never">
          <div class="card-head compact">
            <div class="card-title">按课程汇总课消</div>
          </div>
          <el-table
            v-if="!isCompact"
            :data="report?.course_consumption?.by_course || []"
            row-key="course_name"
            stripe
            border
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="course_name" label="课程" min-width="180" />
            <el-table-column label="课程类型" width="110" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.course_type_label" size="small" effect="plain">
                  {{ row.course_type_label }}
                </el-tag>
                <span v-else class="muted">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="count" label="课消次数" width="110" align="center" />
            <el-table-column label="课消课时" width="120" align="center">
              <template #default="{ row }">{{ formatHours(row.hours) }}</template>
            </el-table-column>
            <el-table-column label="课消金额（元）" min-width="150" align="right">
              <template #default="{ row }">
                <span class="pc-mono">{{ formatMoney(row.amount) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="report-card-list">
            <article v-for="row in report?.course_consumption?.by_course || []" :key="row.course_name" class="report-row-card">
              <div class="report-row-head">
                <strong>{{ row.course_name }}</strong>
                <el-tag v-if="row.course_type_label" size="small" effect="plain">{{ row.course_type_label }}</el-tag>
              </div>
              <div class="report-row-value">{{ formatMoney(row.amount) }}</div>
              <div class="report-row-meta"><span>{{ row.count }} 次课消</span><span>{{ formatHours(row.hours) }} 课时</span></div>
            </article>
            <el-empty v-if="!report?.course_consumption?.by_course?.length" description="暂无课程课消" :image-size="52" />
          </div>
        </el-card>
      </template>

      <template v-else>
        <section class="income-overview pending-overview">
          <div class="overview-main">
            <span class="eyebrow">机构待消课时</span>
            <strong>{{ formatHours(pendingReport?.summary.pending_hours ?? 0) }} 课时</strong>
            <span class="overview-range">截至 {{ pendingReport?.as_of || '-' }}，按当前有效业务课包快照统计</span>
          </div>
          <div class="overview-side">
            <div class="rate-row">
              <span>机构消课比例</span>
              <strong>{{ formatRate(pendingReport?.summary.consumption_rate ?? 0) }}</strong>
            </div>
            <div class="rate-track pending-rate-track">
              <span :style="{ width: `${Math.min(pendingReport?.summary.consumption_rate ?? 0, 100)}%` }" />
            </div>
            <div class="mini-split">
              <span>已消 {{ formatHours(pendingReport?.summary.consumed_hours ?? 0) }} 课时</span>
              <span>总课时 {{ formatHours(pendingReport?.summary.total_hours ?? 0) }} 课时</span>
            </div>
          </div>
        </section>

        <div class="stat-cards pending-stat-cards">
          <div class="stat-card tone-neutral">
            <div class="stat-label">有待消课时学员</div>
            <div class="stat-value">{{ pendingReport?.summary.pending_student_count ?? 0 }} 人</div>
          </div>
          <div class="stat-card tone-ok">
            <div class="stat-label">待消课时估值</div>
            <div class="stat-value">{{ formatMoney(pendingReport?.summary.pending_value ?? 0) }}</div>
          </div>
          <div class="stat-card tone-danger">
            <div class="stat-label">已过期仍待消</div>
            <div class="stat-value">{{ formatHours(pendingReport?.summary.expired_hours ?? 0) }} 课时</div>
          </div>
          <div class="stat-card tone-warn">
            <div class="stat-label">30天内到期待消</div>
            <div class="stat-value">{{ formatHours(pendingReport?.summary.expiring_soon_hours ?? 0) }} 课时</div>
          </div>
        </div>

        <el-card class="module-card pc-table-card" shadow="never">
          <div class="card-head compact">
            <div>
              <div class="card-title">按课程汇总待消</div>
              <div class="card-subtitle">赠送课时计入总课时与待消课时</div>
            </div>
          </div>
          <el-table
            v-if="!isCompact"
            :data="pendingReport?.by_course || []"
            row-key="course_id"
            stripe
            border
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="course_name" label="课程" min-width="180" fixed="left" />
            <el-table-column prop="student_count" label="学员" width="82" align="center" />
            <el-table-column label="总课时" width="105" align="right">
              <template #default="{ row }">{{ formatHours(row.total_hours) }}</template>
            </el-table-column>
            <el-table-column label="已消课时" width="105" align="right">
              <template #default="{ row }">{{ formatHours(row.consumed_hours) }}</template>
            </el-table-column>
            <el-table-column label="待消课时" width="105" align="right">
              <template #default="{ row }"><strong>{{ formatHours(row.pending_hours) }}</strong></template>
            </el-table-column>
            <el-table-column label="消课比例" width="105" align="right">
              <template #default="{ row }">{{ formatRate(row.consumption_rate) }}</template>
            </el-table-column>
            <el-table-column label="待消估值" min-width="130" align="right">
              <template #default="{ row }">{{ formatMoney(row.pending_value) }}</template>
            </el-table-column>
            <el-table-column label="课时风险" width="125" align="center">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="riskTagType(row.risk_status)">
                  {{ riskLabel(row.risk_status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="report-card-list">
            <article v-for="row in pendingReport?.by_course || []" :key="row.course_id" class="report-row-card">
              <div class="report-row-head">
                <strong>{{ row.course_name }}</strong>
                <el-tag size="small" effect="plain" :type="riskTagType(row.risk_status)">{{ riskLabel(row.risk_status) }}</el-tag>
              </div>
              <div class="report-row-value">待消 {{ formatHours(row.pending_hours) }} 课时</div>
              <div class="report-row-meta">
                <span>{{ row.student_count }} 名学员</span>
                <span>已消 {{ formatHours(row.consumed_hours) }} / 总计 {{ formatHours(row.total_hours) }}</span>
                <span>比例 {{ formatRate(row.consumption_rate) }}</span>
                <span>估值 {{ formatMoney(row.pending_value) }}</span>
              </div>
            </article>
            <el-empty v-if="!pendingReport?.by_course?.length" description="暂无课程待消" :image-size="52" />
          </div>
        </el-card>

        <div class="pending-detail-filter">
          <el-input
            v-model="pendingFilters.keyword"
            clearable
            prefix-icon="Search"
            placeholder="搜索学员、手机号、课程或年级"
            class="pending-search"
          />
          <el-select v-model="pendingFilters.course_id" clearable filterable placeholder="全部课程" class="pending-select">
            <el-option
              v-for="course in pendingReport?.by_course || []"
              :key="course.course_id"
              :label="course.course_name"
              :value="course.course_id"
            />
          </el-select>
          <el-select v-model="pendingFilters.risk_status" clearable placeholder="全部风险" class="pending-select">
            <el-option label="存在已过期" value="expired" />
            <el-option label="30天内到期" value="expiring" />
            <el-option label="正常" value="normal" />
            <el-option label="已消完" value="consumed" />
          </el-select>
          <span class="range-text">共 {{ pendingDetailRows.length }} 条</span>
        </div>

        <el-card class="module-card pc-table-card" shadow="never">
          <div class="card-head compact">
            <div class="card-title">学员待消明细</div>
          </div>
          <el-table
            v-if="!isCompact"
            :data="pendingDetailRows"
            :row-key="pendingRowKey"
            stripe
            border
            max-height="560"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="student_name" label="学员" min-width="110" fixed="left" />
            <el-table-column prop="student_phone" label="手机号" min-width="125" />
            <el-table-column prop="student_grade" label="年级" width="90" />
            <el-table-column prop="course_name" label="课程" min-width="170" />
            <el-table-column label="总课时" width="95" align="right">
              <template #default="{ row }">{{ formatHours(row.total_hours) }}</template>
            </el-table-column>
            <el-table-column label="已消" width="90" align="right">
              <template #default="{ row }">{{ formatHours(row.consumed_hours) }}</template>
            </el-table-column>
            <el-table-column label="待消" width="90" align="right">
              <template #default="{ row }"><strong>{{ formatHours(row.pending_hours) }}</strong></template>
            </el-table-column>
            <el-table-column label="消课比例" width="100" align="right">
              <template #default="{ row }">{{ formatRate(row.consumption_rate) }}</template>
            </el-table-column>
            <el-table-column prop="valid_until" label="最近到期日" width="120">
              <template #default="{ row }">{{ row.valid_until || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="125" align="center" fixed="right">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="riskTagType(row.risk_status)">
                  {{ riskLabel(row.risk_status) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="report-card-list">
            <article v-for="row in pendingDetailRows" :key="pendingRowKey(row)" class="report-row-card">
              <div class="report-row-head">
                <div><strong>{{ row.student_name }}</strong><div class="report-row-sub">{{ row.student_phone || '-' }} · {{ row.student_grade || '未填年级' }}</div></div>
                <el-tag size="small" effect="plain" :type="riskTagType(row.risk_status)">{{ riskLabel(row.risk_status) }}</el-tag>
              </div>
              <div class="report-row-course">{{ row.course_name }}</div>
              <div class="report-row-value">待消 {{ formatHours(row.pending_hours) }} 课时</div>
              <div class="report-row-meta">
                <span>已消 {{ formatHours(row.consumed_hours) }} / 总计 {{ formatHours(row.total_hours) }}</span>
                <span>比例 {{ formatRate(row.consumption_rate) }}</span>
                <span>到期 {{ row.valid_until || '-' }}</span>
              </div>
            </article>
            <el-empty v-if="!pendingDetailRows.length" description="暂无学员待消明细" :image-size="52" />
          </div>
        </el-card>
      </template>
    </div>
  </div>
</template>

<style scoped>
.report-page {
  width: 100%;
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.report-shell {
  margin-top: 14px;
}

.report-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: rgba(255, 253, 248, 0.78);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
}

.date-range {
  width: 280px;
}

.range-text {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.report-tabs {
  margin-top: 10px;
}

.report-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.income-overview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
  gap: 16px;
  align-items: center;
  padding: 20px;
  background: #fffdf8;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  box-shadow: 0 8px 22px rgba(68, 64, 60, 0.05);
}

.overview-main {
  display: grid;
  gap: 6px;
}

.eyebrow,
.overview-range,
.card-subtitle {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.overview-main strong {
  color: #342d26;
  font-size: 32px;
  line-height: 1.12;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.overview-side {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  background: #faf6ee;
  border: 1px solid #efe4d3;
  border-radius: 8px;
}

.rate-row,
.mini-split {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
}

.rate-row strong {
  color: var(--oc-ink, #44403c);
  font-size: 18px;
  font-variant-numeric: tabular-nums;
}

.rate-track {
  height: 8px;
  background: #eadcc6;
  border-radius: 999px;
  overflow: hidden;
}

.rate-track span {
  display: block;
  height: 100%;
  max-width: 100%;
  border-radius: inherit;
  background: #3a6351;
}

.mini-split {
  flex-wrap: wrap;
}

.stat-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
  margin: 12px 0;
}

.stat-card {
  position: relative;
  overflow: hidden;
  background: rgba(255, 253, 248, 0.92);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  padding: 16px 18px;
  box-shadow: 0 4px 14px rgba(68, 64, 60, 0.035);
}

.stat-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #a16207;
}

.stat-card.tone-ok::before {
  background: #3a6351;
}

.stat-card.tone-neutral::before {
  background: #7c6f64;
}

.stat-card.tone-danger::before {
  background: #b42318;
}

.stat-label {
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 21px;
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  font-variant-numeric: tabular-nums;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 16px 0;
}

.card-head.compact {
  padding-bottom: 12px;
}

.card-title {
  font-weight: 700;
  color: var(--oc-ink, #44403c);
}

.legend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  white-space: nowrap;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #a16207;
}

.consumption-dot {
  background: #3a6351;
}

.chart-card {
  margin-bottom: 12px;
  overflow: hidden;
  background: #fffdf8;
}

.income-chart-card {
  background: #fffdf8;
}

.chart-frame {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 10px;
  margin: 10px 16px 18px;
  padding-top: 8px;
  border-top: 1px solid #f0e7d8;
}

.chart-scale {
  height: 244px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
  padding: 4px 0 28px;
  color: #9a8f83;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.bar-chart {
  position: relative;
  display: flex;
  align-items: end;
  gap: 12px;
  height: 244px;
  padding: 4px 8px 0;
  overflow-x: auto;
  background:
    linear-gradient(#f3eadb 1px, transparent 1px) 0 0 / 100% 50%,
    linear-gradient(to right, transparent 0, transparent 100%);
  border-bottom: 1px solid #d9cbb7;
}

.bar-item {
  min-width: 56px;
  height: 100%;
  display: grid;
  grid-template-rows: 24px 1fr 24px;
  justify-items: center;
  align-items: end;
}

.bar-value,
.bar-label {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.bar-track {
  width: 32px;
  height: 100%;
  border-radius: 5px 5px 0 0;
  display: flex;
  align-items: end;
  overflow: hidden;
}

.income-track {
  background: #f1e3cb;
}

.consumption-track {
  background: #dfe9e3;
}

.bar-fill {
  width: 100%;
  min-height: 4px;
  border-radius: 5px 5px 0 0;
  transition: height 0.2s ease;
}

.income-fill {
  background: #b7791f;
}

.consumption-fill {
  background: #3a6351;
}

.pc-table-card {
  overflow: hidden;
}

.report-card-list {
  display: grid;
  gap: 10px;
}

.report-row-card {
  display: grid;
  gap: 8px;
  padding: 13px 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fff;
}

.report-row-head,
.report-row-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px 12px;
}

.report-row-head strong {
  color: var(--oc-ink, #44403c);
}

.report-row-value {
  color: var(--oc-primary, #a16207);
  font-size: 18px;
  font-weight: 700;
}

.report-row-meta,
.report-row-sub {
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.report-row-course {
  color: var(--oc-ink, #44403c);
  font-size: 13px;
}

.pc-mono {
  font-variant-numeric: tabular-nums;
}

.muted {
  color: var(--oc-muted, #78716c);
}

.pending-overview {
  margin-bottom: 12px;
}

.pending-rate-track span {
  background: #2f6f62;
}

.pending-stat-cards {
  grid-template-columns: repeat(4, minmax(180px, 1fr));
}

.pending-detail-filter {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 12px 0;
  padding: 12px 14px;
  background: rgba(255, 253, 248, 0.78);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
}

.pending-search {
  width: min(320px, 100%);
}

.pending-select {
  width: 180px;
}

@media (max-width: 720px) {
  .report-filter,
  .income-overview {
    grid-template-columns: 1fr;
  }

  .date-range {
    width: 100%;
  }

  .pending-stat-cards {
    grid-template-columns: 1fr;
  }

  .pending-search,
  .pending-select {
    width: 100%;
  }

  .overview-main strong {
    font-size: 28px;
  }

  .chart-frame {
    grid-template-columns: 1fr;
  }

  .chart-scale {
    display: none;
  }

  .bar-chart {
    padding-left: 4px;
    padding-right: 4px;
  }
}
</style>
