<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createRechargeApi, listRechargesApi, type RechargeRecord } from '../../api/finance'
import { listStudentsApi, type Student } from '../../api/students'
import ListLoadStatus from '../../components/ListLoadStatus.vue'
import PcPagerBar from '../../components/PcPagerBar.vue'
import CompactFilterBar from '../../components/CompactFilterBar.vue'
import MobileFilterSheet from '../../components/MobileFilterSheet.vue'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useResponsiveSurface } from '../../composables/useResponsiveSurface'
import { SCROLL_CHUNK } from '../../composables/useServerPagedList'

const { isApp } = useBreakpoint()
const { surface: formSurface, surfaceProps: formSurfaceProps } = useResponsiveSurface({
  dialogWidth: '420px',
  dialogMaxWidth: '420px',
  compactSize: '78%',
  modalClass: 'recharge-form-sheet',
})
const loading = ref(false)
const loadingMore = ref(false)
const keyword = ref('')
const rows = ref<RechargeRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterVisible = ref(false)
const sentinelRef = ref<HTMLElement | null>(null)
let scrollObserver: IntersectionObserver | null = null
const activeFilterCount = computed(() => Number(Boolean(keyword.value.trim())))
const hasMore = computed(() => rows.value.length < total.value)

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

async function load(options?: { append?: boolean }) {
  const append = Boolean(options?.append && isApp.value)
  if (isApp.value && !append) page.value = 1
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const res = await listRechargesApi({
      student_q: keyword.value.trim() || undefined,
      page: page.value,
      page_size: isApp.value ? SCROLL_CHUNK : pageSize.value,
    })
    rows.value = append ? [...rows.value, ...res.items] : res.items
    total.value = res.total
  } catch {
    if (append) page.value = Math.max(1, page.value - 1)
    else {
      rows.value = []
      total.value = 0
    }
  } finally {
    loading.value = false
    loadingMore.value = false
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

function resetFilters() {
  keyword.value = ''
  runQuery()
}

watch(isApp, async () => {
  page.value = 1
  await load()
  await nextTick()
  if (isApp.value) setupScrollObserver()
  else teardownScrollObserver()
})

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
</script>

<template>
  <div class="recharge-page">
    <div class="page-toolbar">
      <el-page-header class="is-title-only" content="充值管理" />
      <el-button v-if="!isApp" type="primary" class="tb-btn tb-btn--primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        账户充值
      </el-button>
    </div>

    <button v-if="isApp" type="button" class="oc-app-cta recharge-cta" @click="openCreate">
      <span class="oc-app-cta__ico" aria-hidden="true">
        <el-icon><Plus /></el-icon>
      </span>
      <span class="oc-app-cta__copy">
        <strong>账户充值</strong>
        <em>为学员账户增加余额</em>
      </span>
      <span class="oc-app-cta__go">去充值</span>
    </button>

    <el-card v-if="!isApp" class="pc-filters" shadow="never">
      <el-form :inline="true" class="pc-filter-form" @submit.prevent="runQuery">
        <el-form-item label="学员">
          <el-input
            v-model="keyword"
            clearable
            placeholder="姓名/手机号"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button type="primary" @click="runQuery">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <CompactFilterBar v-if="isApp" :active-count="activeFilterCount" :total="total" label="笔充值" @open="filterVisible = true" />
    <MobileFilterSheet v-model="filterVisible" :active-count="activeFilterCount" @apply="runQuery" @reset="resetFilters">
      <el-form label-position="top" @submit.prevent="runQuery"><el-form-item label="学员"><el-input v-model="keyword" clearable placeholder="姓名 / 手机号" /></el-form-item></el-form>
    </MobileFilterSheet>

    <div v-if="isApp" v-loading="loading" class="m-card-list recharge-m">
      <div v-if="!rows.length && !loading" class="m-card m-card-empty oc-app-empty">
        <span class="recharge-empty-ico" aria-hidden="true">💳</span>
        <strong>暂无充值记录</strong>
        <em>{{ activeFilterCount ? '当前筛选没有匹配记录，可清空条件后重试' : '点击上方「账户充值」为学员加余额' }}</em>
        <el-button type="primary" class="tb-btn tb-btn--primary" @click="openCreate">账户充值</el-button>
      </div>
      <article v-for="row in rows" :key="row.id" class="m-card">
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
        <div class="oc-meta-chips recharge-chips">
          <span class="oc-meta-chip is-ok">余额 {{ formatMoney(row.balance) }}</span>
          <span v-if="row.pay_method" class="oc-meta-chip">{{ row.pay_method }}</span>
          <span v-if="row.handler" class="oc-meta-chip">经办 {{ row.handler }}</span>
          <span class="oc-meta-chip">{{ formatTime(row.created_at) }}</span>
          <span v-if="row.status" class="oc-meta-chip is-gold">{{ row.status }}</span>
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

    <component
      :is="formSurface"
      v-model="formVisible"
      v-bind="formSurfaceProps"
      title="账户充值"
    >
      <el-form :label-position="isApp ? 'top' : 'right'" :label-width="isApp ? undefined : '90px'">
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
    </component>
  </div>
</template>

<style scoped>
.recharge-page {
  width: 100%;
}

.recharge-m {
  margin-top: 12px;
}

.recharge-cta {
  width: 100%;
  margin: 4px 0 12px;
}

.recharge-chips {
  margin-top: 10px;
}

.recharge-empty-ico {
  font-size: 28px;
  line-height: 1;
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

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.amt {
  color: #67c23a;
  font-weight: 750;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1199px) {
  .page-toolbar {
    flex-direction: row;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
}

/* 分页样式见全局 style.css · .pager-bar.pc-pager */
</style>
