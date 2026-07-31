<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createUserApi,
  deleteUserApi,
  listUsersApi,
  patchUserApi,
  resetPasswordApi,
  type UserRow,
} from '../../api/users'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useInfiniteScroll } from '../../composables/useInfiniteScroll'
import { useListScrollRestore } from '../../composables/useListScrollRestore'

const LIST_STATE_KEY = 'oc-user-list-state'
const PAGE_SIZES = [10, 20, 50, 100]
const SCROLL_CHUNK = 10

const route = useRoute()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const loading = ref(false)
const rows = ref<UserRow[]>([])
const page = ref(1)
const pageSize = ref(20)
const filterExpanded = ref(false)

const filters = reactive({
  role: '',
  is_active: '' as '' | 'true' | 'false',
  username: '',
  display_name: '',
})

const createVisible = ref(false)
const resetVisible = ref(false)
const revealVisible = ref(false)
const revealTitle = ref('')
const revealUsername = ref('')
const revealPassword = ref('')

const createFormRef = ref<FormInstance>()
const resetFormRef = ref<FormInstance>()
const createLoading = ref(false)
const resetLoading = ref(false)
const resetTarget = ref<UserRow | null>(null)

const createForm = reactive({
  username: '',
  display_name: '',
  role: 'operator',
  password: '',
})

const resetForm = reactive({
  new_password: '',
})

const createRules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  password: [
    { required: true, message: '请设置初始密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
}

const resetRules: FormRules = {
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
}

const roleLabel: Record<string, string> = {
  admin: '负责人',
  operator: '运营',
  teacher: '老师',
}

function roleTagType(role: string): 'danger' | 'warning' | 'info' | 'success' {
  if (role === 'admin') return 'danger'
  if (role === 'operator') return 'warning'
  if (role === 'teacher') return 'success'
  return 'info'
}

const activeFilterCount = computed(() => {
  let n = 0
  if (filters.role) n += 1
  if (filters.is_active) n += 1
  if (filters.username.trim()) n += 1
  if (filters.display_name.trim()) n += 1
  return n
})

const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize.value) || 1))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

const sentinelRef = ref<HTMLElement | null>(null)
const {
  displayRows: infiniteRows,
  hasMore: hasMoreInfinite,
  loadingMore,
  visibleCount,
  resetVisible: resetInfinite,
  ensureVisible,
} = useInfiniteScroll(rows, {
  chunk: SCROLL_CHUNK,
  enabled: isCompact,
  sentinelRef,
})

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('users', {
  visibleCount,
  enabled: isCompact,
})

function clampPage() {
  if (page.value > totalPages.value) page.value = totalPages.value
  if (page.value < 1) page.value = 1
}

function goFirstPage() {
  page.value = 1
  saveListState()
}

function goLastPage() {
  page.value = totalPages.value
  saveListState()
}

function onPageChange() {
  saveListState()
}

function onPageSizeChange() {
  page.value = 1
  saveListState()
}

function restoreListState() {
  try {
    const raw = sessionStorage.getItem(LIST_STATE_KEY)
    if (!raw) return
    const s = JSON.parse(raw) as {
      filters?: Partial<typeof filters>
      page?: number
      pageSize?: number
    }
    if (s.filters) {
      filters.role = s.filters.role ?? ''
      filters.is_active = s.filters.is_active ?? ''
      filters.username = s.filters.username ?? ''
      filters.display_name = s.filters.display_name ?? ''
    }
    if (typeof s.page === 'number' && s.page > 0) page.value = s.page
    if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
      pageSize.value = s.pageSize
    }
  } catch {
    /* ignore */
  }
}

function saveListState() {
  try {
    sessionStorage.setItem(
      LIST_STATE_KEY,
      JSON.stringify({
        filters: { ...filters },
        page: page.value,
        pageSize: pageSize.value,
      }),
    )
  } catch {
    /* ignore */
  }
}

async function load(opts?: { resetPage?: boolean }) {
  const snap = opts?.resetPage ? null : takeSnapshotForLoad(route.path)
  if (opts?.resetPage) clearSnapshot()

  loading.value = true
  if (opts?.resetPage) page.value = 1
  try {
    const params: {
      role?: string
      is_active?: boolean
      username?: string
      display_name?: string
    } = {}
    if (filters.role) params.role = filters.role
    if (filters.is_active === 'true') params.is_active = true
    if (filters.is_active === 'false') params.is_active = false
    if (filters.username.trim()) params.username = filters.username.trim()
    if (filters.display_name.trim()) params.display_name = filters.display_name.trim()
    rows.value = await listUsersApi(params)
    if (opts?.resetPage) {
      resetInfinite()
    } else if (snap?.visibleCount != null && isCompact.value) {
      ensureVisible(snap.visibleCount)
    } else if (isCompact.value) {
      resetInfinite()
    }
    clampPage()
    saveListState()
  } finally {
    loading.value = false
  }
  void finishListEnter({ snap, forceTop: !!opts?.resetPage })
}

function runQuery() {
  filterExpanded.value = false
  load({ resetPage: true })
}

function resetFilters() {
  filters.role = ''
  filters.is_active = ''
  filters.username = ''
  filters.display_name = ''
  filterExpanded.value = false
  load({ resetPage: true })
}

function toggleFilterExpand() {
  filterExpanded.value = !filterExpanded.value
}

function nameInitial(row: UserRow) {
  const t = (row.display_name || row.username || '').trim()
  return t ? t.slice(0, 1) : '?'
}

function randomPassword(len = 10) {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789'
  let s = ''
  for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * chars.length)]
  return s
}

function openCreate() {
  createForm.username = ''
  createForm.display_name = ''
  createForm.role = 'operator'
  createForm.password = ''
  createVisible.value = true
}

function openReset(row: UserRow) {
  resetTarget.value = row
  resetForm.new_password = ''
  resetVisible.value = true
}

async function submitCreate() {
  const ok = await createFormRef.value?.validate().catch(() => false)
  if (!ok) return
  createLoading.value = true
  try {
    const plain = createForm.password
    const user = await createUserApi({ ...createForm })
    createVisible.value = false
    revealTitle.value = '账号已创建（密码仅展示一次）'
    revealUsername.value = user.username
    revealPassword.value = plain
    revealVisible.value = true
    await load()
  } catch {
    /* interceptor */
  } finally {
    createLoading.value = false
  }
}

async function submitReset() {
  const ok = await resetFormRef.value?.validate().catch(() => false)
  if (!ok || !resetTarget.value) return
  resetLoading.value = true
  try {
    const plain = resetForm.new_password
    await resetPasswordApi(resetTarget.value.id, plain)
    resetVisible.value = false
    revealTitle.value = '密码已重置（仅展示一次）'
    revealUsername.value = resetTarget.value.username
    revealPassword.value = plain
    revealVisible.value = true
  } catch {
    /* interceptor */
  } finally {
    resetLoading.value = false
  }
}

async function toggleActive(row: UserRow) {
  await patchUserApi(row.id, { is_active: !row.is_active })
  ElMessage.success(row.is_active ? '已停用' : '已启用')
  await load()
}

async function onDelete(row: UserRow) {
  if (auth.user?.id === row.id) {
    ElMessage.warning('不能删除当前登录账号')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定删除用户「${row.display_name || row.username}」？\n关联素材/学情会改挂到当前管理员，待办会一并删除，且不可恢复。`,
      '删除用户',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteUserApi(row.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel or interceptor */
  }
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

watch(pageSize, () => clampPage())

onMounted(() => {
  restoreListState()
  load()
})
</script>

<template>
  <div class="user-page">
    <div class="page-toolbar user-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header content="用户管理" />
      <el-button class="create-btn tb-btn tb-btn--primary" type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新建用户
      </el-button>
    </div>

    <!-- PC 筛选 -->
    <div class="user-pc">
      <el-card class="filters pc-filters" shadow="never">
        <div class="pc-filters-head">
          <div class="pc-filters-head-main">
            <span class="pc-filters-title">筛选条件</span>
            <span v-if="activeFilterCount" class="pc-filters-badge">{{ activeFilterCount }} 项生效</span>
          </div>
          <div class="pc-list-summary">
            <span class="pc-list-summary__label">系统账号</span>
            <span class="pc-list-summary__count">
              共 <strong>{{ rows.length }}</strong> 人
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="角色">
            <el-select v-model="filters.role" clearable placeholder="全部" style="width: 120px">
              <el-option label="负责人" value="admin" />
              <el-option label="运营" value="operator" />
              <el-option label="老师" value="teacher" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="filters.is_active" clearable placeholder="全部" style="width: 110px">
              <el-option label="启用" value="true" />
              <el-option label="停用" value="false" />
            </el-select>
          </el-form-item>
          <el-form-item label="用户名">
            <el-input
              v-model="filters.username"
              clearable
              placeholder="搜索"
              style="width: 130px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item label="显示名">
            <el-input
              v-model="filters.display_name"
              clearable
              placeholder="搜索"
              style="width: 130px"
              @keyup.enter="runQuery"
            />
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" @click="runQuery">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>

    <!-- wap/pad 筛选 -->
    <div class="user-m m-filter">
      <div class="m-filter-search">
        <el-icon class="m-filter-search__icon"><Search /></el-icon>
        <input
          v-model="filters.display_name"
          class="m-filter-search__input"
          type="search"
          enterkeyhint="search"
          placeholder="搜索显示名"
          @keyup.enter="runQuery"
        />
        <button type="button" class="m-filter-search__btn" @click="runQuery">查询</button>
      </div>
      <div class="m-filter-row">
        <el-select
          v-model="filters.role"
          class="m-filter-select"
          clearable
          placeholder="角色"
          teleported
          placement="bottom-start"
          :fit-input-width="true"
          :popper-options="{ strategy: 'fixed' }"
          popper-class="user-m-select-popper"
        >
          <el-option label="负责人" value="admin" />
          <el-option label="运营" value="operator" />
          <el-option label="老师" value="teacher" />
        </el-select>
        <el-select
          v-model="filters.is_active"
          class="m-filter-select"
          clearable
          placeholder="状态"
          teleported
          placement="bottom-start"
          :fit-input-width="true"
          :popper-options="{ strategy: 'fixed' }"
          popper-class="user-m-select-popper"
        >
          <el-option label="启用" value="true" />
          <el-option label="停用" value="false" />
        </el-select>
        <button
          type="button"
          class="m-filter-more"
          :class="{ 'is-active': filterExpanded || activeFilterCount > 0 }"
          @click="toggleFilterExpand"
        >
          更多{{ activeFilterCount ? ` · ${activeFilterCount}` : '' }}
          <el-icon :class="{ 'is-open': filterExpanded }"><ArrowDown /></el-icon>
        </button>
      </div>
      <div v-show="filterExpanded" class="m-filter-panel">
        <el-input v-model="filters.username" clearable placeholder="用户名" />
        <div class="m-filter-panel__actions">
          <button type="button" class="m-filter-link" @click="resetFilters">重置</button>
          <button type="button" class="m-filter-apply" @click="runQuery">完成</button>
        </div>
      </div>
    </div>

    <!-- 移动卡片 -->
    <div v-loading="loading" class="user-m user-card-list">
      <div v-if="!rows.length && !loading" class="user-card user-card--empty">暂无用户</div>
      <div v-for="row in infiniteRows" :key="row.id" class="user-card">
        <div class="user-card__top">
          <div class="user-card__avatar">{{ nameInitial(row) }}</div>
          <div class="user-card__who">
            <div class="user-card__name">{{ row.display_name || row.username }}</div>
            <div class="user-card__sub">
              <span class="user-card__uname">@{{ row.username }}</span>
            </div>
          </div>
          <div class="user-card__badges">
            <el-tag :type="roleTagType(row.role)" size="small" effect="plain" round>
              {{ roleLabel[row.role] || row.role }}
            </el-tag>
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain" round>
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </div>
        </div>

        <div class="user-card__actions">
          <el-button size="small" type="primary" @click="openReset(row)">重置密码</el-button>
          <el-button size="small" type="warning" plain @click="toggleActive(row)">
            {{ row.is_active ? '停用' : '启用' }}
          </el-button>
          <el-button
            size="small"
            type="danger"
            plain
            :disabled="auth.user?.id === row.id"
            @click="onDelete(row)"
          >
            删除
          </el-button>
        </div>
      </div>
      <div v-if="rows.length" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ rows.length }} 人</span>
      </div>
    </div>

    <!-- PC 表格 -->
    <div class="user-pc">
      <el-card class="pc-table-card" v-loading="loading" shadow="never">
        <div class="table-scroll">
          <el-table
            :data="pagedRows"
            stripe
            class="pc-user-table"
            style="width: 100%"
            empty-text="暂无用户"
            :header-cell-style="pcHeaderStyle"
          >
            <el-table-column prop="display_name" label="显示名" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <div class="pc-name-cell">
                  <span class="pc-avatar">{{ nameInitial(row) }}</span>
                  <span class="pc-name-text">{{ row.display_name || row.username }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="username" label="用户名" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="pc-mono">{{ row.username }}</span>
              </template>
            </el-table-column>
            <el-table-column label="角色" width="108">
              <template #default="{ row }">
                <el-tag :type="roleTagType(row.role)" size="small" effect="plain" round>
                  {{ roleLabel[row.role] || row.role }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="88" align="center">
              <template #default="{ row }">
                <el-tag
                  :type="row.is_active ? 'success' : 'info'"
                  size="small"
                  effect="plain"
                  round
                >
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
                  <el-button link type="warning" @click="toggleActive(row)">
                    {{ row.is_active ? '停用' : '启用' }}
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    :disabled="auth.user?.id === row.id"
                    @click="onDelete(row)"
                  >
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <div v-if="rows.length" class="pager-bar pc-pager">
        <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="PAGE_SIZES"
          :total="rows.length"
          :pager-count="5"
          background
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="onPageChange"
          @size-change="onPageSizeChange"
        />
        <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
      </div>
    </div>

    <el-dialog
      v-model="createVisible"
      title="新建用户"
      width="90%"
      style="max-width: 480px"
      destroy-on-close
      class="user-dialog"
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="登录账号" />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="createForm.display_name" placeholder="界面展示名称" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="负责人" value="admin" />
            <el-option label="运营" value="operator" />
            <el-option label="老师" value="teacher" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <div class="pwd-row">
            <el-input v-model="createForm.password" type="password" show-password />
            <el-button @click="createForm.password = randomPassword()">生成</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="resetVisible"
      title="重置密码"
      width="90%"
      style="max-width: 420px"
      destroy-on-close
      class="user-dialog"
    >
      <p v-if="resetTarget" class="reset-hint">
        为用户 <strong>{{ resetTarget.username }}</strong> 设置新密码：
      </p>
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="新密码" prop="new_password">
          <div class="pwd-row">
            <el-input v-model="resetForm.new_password" type="password" show-password />
            <el-button @click="resetForm.new_password = randomPassword()">生成</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="resetLoading" @click="submitReset">确认重置</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="revealVisible" :title="revealTitle" width="90%" style="max-width: 420px">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="关闭后将无法再次查看明文密码，请立即复制并告知对方。"
      />
      <el-descriptions :column="1" border style="margin-top: 12px">
        <el-descriptions-item label="用户名">{{ revealUsername }}</el-descriptions-item>
        <el-descriptions-item label="密码">{{ revealPassword }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="copyText(`${revealUsername} / ${revealPassword}`)">复制账号密码</el-button>
        <el-button type="primary" @click="revealVisible = false">已保存，关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.user-page {
  min-width: 0;
}

.user-pc {
  display: none;
}

.user-m {
  display: block;
}

@media (min-width: 992px) {
  .user-pc {
    display: block;
  }

  .user-m {
    display: none !important;
  }
}

.user-toolbar.is-compact {
  gap: 10px;
}

.create-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.tb-btn--primary {
  height: 36px;
  border-radius: 9px;
  font-weight: 500;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.22);
}

/* ── PC 筛选卡 ── */
.pc-filters {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: linear-gradient(180deg, #fffdfb 0%, #faf6ee 100%);
}

.pc-filters :deep(.el-card__body) {
  padding: 14px 16px 8px;
}

.pc-filters-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  margin-bottom: 10px;
}

.pc-filters-head-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pc-filters-title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.pc-filters-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(161, 98, 7, 0.1);
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.pc-list-summary {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 253, 248, 0.9);
  border: 1px solid var(--oc-border, #e8e0d0);
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.pc-list-summary__label {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.pc-list-summary strong {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
}

.pc-filter-form :deep(.el-form-item) {
  margin-bottom: 10px;
  margin-right: 14px;
}

.pc-filter-form :deep(.el-form-item__label) {
  color: var(--oc-muted, #78716c);
  font-weight: 500;
}

/* ── wap 筛选 ── */
.m-filter {
  position: relative;
  z-index: 20;
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--oc-card, #fffdf8);
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  overflow: visible;
}

.m-filter-search {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 4px 0 12px;
  background: #f5f0e6;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
}

.m-filter-search__icon {
  color: #a8a29e;
  font-size: 16px;
  flex-shrink: 0;
}

.m-filter-search__input {
  flex: 1;
  min-width: 0;
  height: 100%;
  margin: 0 8px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
  appearance: none;
}

.m-filter-search__input::-webkit-search-cancel-button {
  -webkit-appearance: none;
}

.m-filter-search__input::placeholder {
  color: #a8a29e;
}

.m-filter-search__btn {
  flex-shrink: 0;
  height: 32px;
  padding: 0 14px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.m-filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  overflow: visible;
}

.m-filter-select {
  flex: 1 1 0;
  min-width: 0;
}

.m-filter-select :deep(.el-select__wrapper) {
  min-height: 34px;
  border-radius: 8px;
  background: #faf6ef !important;
  box-shadow: 0 0 0 1px var(--oc-border, #e8e0d0) inset !important;
}

.m-filter-more {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 8px;
  background: #fffdf8;
  color: var(--oc-ink, #44403c);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.m-filter-more.is-active {
  border-color: #d4b483;
  color: var(--oc-primary, #a16207);
  background: #faf3e6;
}

.m-filter-more .el-icon {
  transition: transform 0.15s ease;
}

.m-filter-more .el-icon.is-open {
  transform: rotate(180deg);
}

.m-filter-panel {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--oc-border, #e8e0d0);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.m-filter-panel__actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}

.m-filter-link {
  border: none;
  background: transparent;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  cursor: pointer;
}

.m-filter-apply {
  height: 32px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: var(--oc-primary, #a16207);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

/* ── 移动卡片 ── */
.user-card-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 80px;
}

.user-card {
  padding: 14px;
  border-radius: 14px;
  border: 2px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.user-card--empty {
  text-align: center;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  padding: 28px 14px;
  border-style: dashed;
}

.user-card__top {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.user-card__avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #c9a227 0%, #a16207 100%);
  box-shadow: 0 2px 6px rgba(161, 98, 7, 0.25);
}

.user-card__who {
  flex: 1;
  min-width: 0;
}

.user-card__name {
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
  word-break: break-word;
}

.user-card__sub {
  margin-top: 4px;
}

.user-card__uname {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.user-card__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.user-card__actions {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.user-card__actions .el-button {
  margin: 0;
  width: 100%;
}

.scroll-sentinel {
  padding: 12px 0 4px;
  text-align: center;
}

.scroll-hint {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

/* ── PC 表格 ── */
.pc-table-card {
  margin-top: 12px;
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  min-height: 200px;
}

.pc-table-card :deep(.el-card__body) {
  padding: 0;
}

.table-scroll {
  width: 100%;
  overflow-x: auto;
}

.pc-user-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #faf6ee !important;
}

.pc-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.pc-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #c9a227 0%, #a16207 100%);
}

.pc-name-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 550;
  color: var(--oc-ink, #44403c);
}

.pc-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.pc-ops {
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  padding-right: 4px;
}

/* 分页见全局 style.css · .pager-bar.pc-pager */

.pwd-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.pwd-row .el-input {
  flex: 1;
}

.reset-hint {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--oc-ink, #44403c);
}

@media (max-width: 991px) {
  .user-toolbar {
    flex-wrap: wrap;
    gap: 10px;
  }

  .create-btn {
    width: 100%;
    height: 40px;
    border-radius: 10px;
    font-weight: 600;
  }
}
</style>

<style>
.user-m-select-popper {
  z-index: 5000 !important;
}
</style>
