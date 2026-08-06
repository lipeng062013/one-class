<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  createUserApi,
  deleteUserApi,
  getUserPermissionsApi,
  listPermissionCatalogApi,
  listUsersApi,
  patchUserApi,
  putUserPermissionsApi,
  resetPasswordApi,
  type PermissionGroup,
  type UserRow,
} from '../../api/users'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useCardAccordion } from '../../composables/useCardAccordion'
import { useListScrollRestore } from '../../composables/useListScrollRestore'
import { useServerPagedList } from '../../composables/useServerPagedList'
import PcPagerBar from '../../components/PcPagerBar.vue'

const LIST_STATE_KEY = 'oc-user-list-state'

const route = useRoute()
const auth = useAuthStore()
const { isCompact } = useBreakpoint()
const { isExpanded, toggle: toggleCard, toggleForce, collapseAll } = useCardAccordion()

const pcHeaderStyle = {
  background: '#f5f0e6',
  color: '#44403c',
  fontWeight: '600',
  borderBottomColor: '#e8e0d0',
}

const filterExpanded = ref(false)

const filters = reactive({
  role: '',
  is_active: '' as '' | 'true' | 'false',
  username: '',
  display_name: '',
})

const {
  page,
  pageSize,
  total,
  rows,
  loading,
  loadingMore,
  hasMore: hasMoreInfinite,
  PAGE_SIZES,
  sentinelRef,
  load: loadPage,
  resetAndLoad,
  onPageChange,
  onPageSizeChange,
  setupScrollObserver,
} = useServerPagedList<UserRow>({
  isCompact,
  getId: (r) => r.id,
  fetchPage: (p, size) =>
    listUsersApi({
      role: filters.role || undefined,
      is_active:
        filters.is_active === 'true' ? true : filters.is_active === 'false' ? false : undefined,
      username: filters.username.trim() || undefined,
      display_name: filters.display_name.trim() || undefined,
      page: p,
      page_size: size,
    }),
})

/** PC / 移动端共用当前服务端页数据 */
const pagedRows = computed(() => rows.value)
const infiniteRows = computed(() => rows.value)
const visibleCount = computed(() => rows.value.length)

const createVisible = ref(false)
const resetVisible = ref(false)
const revealVisible = ref(false)
const revealTitle = ref('')
const revealUsername = ref('')
const revealPassword = ref('')
const permVisible = ref(false)
const permLoading = ref(false)
const permSaving = ref(false)
const permTarget = ref<UserRow | null>(null)
const permCatalog = ref<PermissionGroup[]>([])
const permRoleDefaults = ref<Set<string>>(new Set())
const permSelected = ref<string[]>([])
const permIsAdmin = ref(false)

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
  display_name: [
    { required: true, message: '请输入显示名', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        const name = (value || '').trim()
        if (!name) {
          callback()
          return
        }
        // 仅校验当前页；最终以后端唯一性校验为准
        const taken = rows.value.some((u) => (u.display_name || '').trim() === name)
        if (taken) {
          callback(new Error('显示名已存在，请更换'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
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
  cr: 'CR（班主任，学管师）',
  academic_manager: 'CR（班主任，学管师）',
}

function roleTagType(role: string): 'danger' | 'warning' | 'info' | 'success' {
  if (role === 'admin') return 'danger'
  if (role === 'operator') return 'warning'
  if (role === 'teacher' || role === 'cr' || role === 'academic_manager') return 'success'
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

const { takeSnapshotForLoad, finishListEnter, clearSnapshot } = useListScrollRestore('users', {
  visibleCount,
  enabled: isCompact,
  stateStorageKey: LIST_STATE_KEY,
})

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
    if (!isCompact.value) {
      if (typeof s.page === 'number' && s.page > 0) page.value = s.page
      if (typeof s.pageSize === 'number' && PAGE_SIZES.includes(s.pageSize)) {
        pageSize.value = s.pageSize
      }
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

async function load(opts?: { fromQuery?: boolean }) {
  const snap = opts?.fromQuery ? null : takeSnapshotForLoad(route.path)
  if (opts?.fromQuery) clearSnapshot()
  await (opts?.fromQuery ? resetAndLoad() : loadPage())
  saveListState()
  void finishListEnter({ snap, forceTop: !!opts?.fromQuery })
}

function runQuery() {
  clearSnapshot()
  collapseAll()
  filterExpanded.value = false
  saveListState()
  void load({ fromQuery: true })
}

function resetFilters() {
  clearSnapshot()
  collapseAll()
  filters.role = ''
  filters.is_active = ''
  filters.username = ''
  filters.display_name = ''
  filterExpanded.value = false
  saveListState()
  void load({ fromQuery: true })
}

function onPcPageChange() {
  onPageChange()
  saveListState()
}

function onPcPageSizeChange() {
  onPageSizeChange()
  saveListState()
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

async function ensurePermCatalog() {
  if (permCatalog.value.length) return
  permCatalog.value = await listPermissionCatalogApi()
}

async function openPermissions(row: UserRow) {
  permTarget.value = row
  permVisible.value = true
  permLoading.value = true
  permSelected.value = []
  permRoleDefaults.value = new Set()
  permIsAdmin.value = row.role === 'admin'
  try {
    await ensurePermCatalog()
    const detail = await getUserPermissionsApi(row.id)
    permIsAdmin.value = detail.role === 'admin'
    permRoleDefaults.value = new Set(detail.role_defaults)
    // UI shows role defaults + extras as checked; only extras are saved
    const selected = new Set<string>([...detail.role_defaults, ...detail.extra_permissions])
    permSelected.value = [...selected]
  } catch {
    permVisible.value = false
  } finally {
    permLoading.value = false
  }
}

function isRoleDefault(code: string) {
  return permRoleDefaults.value.has(code)
}

function permChecked(code: string) {
  return permSelected.value.includes(code)
}

function togglePerm(code: string, checked: boolean) {
  if (permIsAdmin.value || isRoleDefault(code)) return
  const set = new Set(permSelected.value)
  if (checked) set.add(code)
  else set.delete(code)
  permSelected.value = [...set]
}

function onPermItemClick(code: string) {
  if (permIsAdmin.value || isRoleDefault(code)) return
  togglePerm(code, !permChecked(code))
}

function groupCheckedCount(g: PermissionGroup) {
  return g.permissions.filter((p) => permChecked(p.code)).length
}

const permExtraSelectedCount = computed(
  () => permSelected.value.filter((c) => !permRoleDefaults.value.has(c)).length,
)

const permTargetRoleLabel = computed(() => {
  const role = permTarget.value?.role || ''
  return roleLabel[role] || role
})

async function submitPermissions() {
  if (!permTarget.value || permIsAdmin.value) {
    permVisible.value = false
    return
  }
  permSaving.value = true
  try {
    const extras = permSelected.value.filter((c) => !permRoleDefaults.value.has(c))
    await putUserPermissionsApi(permTarget.value.id, extras)
    ElMessage.success('权限已更新')
    permVisible.value = false
    await load()
  } catch {
    /* interceptor */
  } finally {
    permSaving.value = false
  }
}

const extraPermCount = (row: UserRow) => (row.extra_permissions || []).length

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
    ElMessage.warning(
      '不能删除当前登录账号。若要更换默认负责人：先新建另一负责人，用新账号登录后再删除此账号。',
    )
    return
  }
  try {
    const roleHint =
      row.role === 'admin'
        ? '\n（负责人账号可删除；删除后请确认仍有可用的负责人登录。）'
        : ''
    await ElMessageBox.confirm(
      `确定删除用户「${row.display_name || row.username}」？\n账号将无法登录并从列表移除；其上传的素材与填写的学情仍保留原作者署名。名下学管/线索归属会清空，个人待办会删除。${roleHint}`,
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

onMounted(async () => {
  restoreListState()
  await load()
  if (sentinelRef.value) setupScrollObserver()
})
</script>

<template>
  <div class="user-page">
    <div class="page-toolbar user-toolbar" :class="{ 'is-compact': isCompact }">
      <el-page-header class="is-title-only" content="用户管理" />
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
              共 <strong>{{ total }}</strong> 人
            </span>
          </div>
        </div>
        <el-form class="filter-form pc-filter-form" :inline="true" @submit.prevent="runQuery">
          <el-form-item label="角色">
            <el-select v-model="filters.role" clearable placeholder="全部" style="width: 120px">
              <el-option label="负责人" value="admin" />
              <el-option label="运营" value="operator" />
              <el-option label="老师" value="teacher" />
              <el-option label="CR（班主任，学管师）" value="cr" />
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
          <el-option label="CR（班主任，学管师）" value="cr" />
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

    <!-- 移动卡片（互斥折叠） -->
    <div v-loading="loading" class="user-m user-card-list">
      <div v-if="!rows.length && !loading" class="user-card user-card--empty">暂无用户</div>
      <div
        v-for="row in infiniteRows"
        :key="row.id"
        class="user-card"
        :class="{ 'is-expanded': isExpanded(row.id) }"
      >
        <div class="user-card__top" @click="toggleCard(row.id, $event)">
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
          <button
            type="button"
            class="m-card-acc-toggle"
            :aria-expanded="isExpanded(row.id)"
            @click.stop="toggleForce(row.id)"
          >
            <el-icon class="m-card-acc-chevron" :class="{ 'is-open': isExpanded(row.id) }">
              <ArrowDown />
            </el-icon>
          </button>
        </div>

        <div v-show="isExpanded(row.id)" class="m-card-acc-body">
          <div class="user-card__actions user-card__actions--4">
            <el-button size="small" type="primary" @click="openPermissions(row)">授权</el-button>
            <el-button size="small" type="primary" plain @click="openReset(row)">重置密码</el-button>
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
          <div v-if="extraPermCount(row)" class="user-card__perm-hint">
            额外授权 {{ extraPermCount(row) }} 项
          </div>
        </div>
      </div>
      <div v-if="rows.length || hasMoreInfinite" ref="sentinelRef" class="scroll-sentinel">
        <span v-if="hasMoreInfinite || loadingMore" class="scroll-hint">
          {{ loadingMore ? '加载中…' : '上拉加载更多' }}
        </span>
        <span v-else class="scroll-hint">已加载全部 {{ total }} 人</span>
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
            <el-table-column label="额外权限" width="100" align="center">
              <template #default="{ row }">
                <span v-if="row.role === 'admin'" class="pc-perm-all">全部</span>
                <el-tag
                  v-else-if="extraPermCount(row)"
                  type="warning"
                  size="small"
                  effect="plain"
                  round
                >
                  +{{ extraPermCount(row) }}
                </el-tag>
                <span v-else class="pc-perm-none">—</span>
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
            <el-table-column label="操作" width="300" fixed="right" align="right">
              <template #default="{ row }">
                <div class="pc-ops">
                  <el-button link type="primary" @click="openPermissions(row)">授权</el-button>
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

      <PcPagerBar
        v-model:page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="PAGE_SIZES"
        @change="onPcPageChange"
        @size-change="onPcPageSizeChange"
      />
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
            <el-option label="CR（班主任，学管师）" value="cr" />
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

    <el-dialog
      v-model="permVisible"
      width="92%"
      style="max-width: 720px"
      align-center
      destroy-on-close
      class="user-dialog perm-dialog"
    >
      <template #header>
        <div class="perm-head">
          <div class="perm-head__title">授权管理</div>
          <div v-if="permTarget" class="perm-head__sub">
            <span class="perm-head__name">{{ permTarget.display_name || permTarget.username }}</span>
            <el-tag
              :type="roleTagType(permTarget.role)"
              size="small"
              effect="plain"
              round
            >
              {{ permTargetRoleLabel }}
            </el-tag>
            <span class="perm-head__uname">@{{ permTarget.username }}</span>
          </div>
        </div>
      </template>

      <div v-loading="permLoading" class="perm-body">
        <el-alert
          v-if="permIsAdmin"
          type="info"
          :closable="false"
          show-icon
          title="负责人角色默认拥有全部权限，无需单独下发。"
        />
        <template v-else>
          <div class="perm-summary">
            <div class="perm-summary__item">
              <span class="perm-summary__label">角色自带</span>
              <b>{{ permRoleDefaults.size }}</b>
              <span class="perm-summary__unit">项</span>
            </div>
            <span class="perm-summary__sep" aria-hidden="true" />
            <div class="perm-summary__item">
              <span class="perm-summary__label">额外授权</span>
              <b>{{ permExtraSelectedCount }}</b>
              <span class="perm-summary__unit">项</span>
            </div>
            <p class="perm-summary__tip">
              勾选增加权限，取消收回额外授权。「角色自带」不可取消，需改角色。
            </p>
          </div>

          <div v-for="g in permCatalog" :key="g.group" class="perm-group">
            <div class="perm-group__head">
              <span class="perm-group__title">{{ g.group_label }}</span>
              <span class="perm-group__count">
                {{ groupCheckedCount(g) }}/{{ g.permissions.length }}
              </span>
            </div>
            <div class="perm-group__grid">
              <div
                v-for="p in g.permissions"
                :key="p.code"
                class="perm-item"
                :class="{
                  'is-default': isRoleDefault(p.code),
                  'is-checked': permChecked(p.code) && !isRoleDefault(p.code),
                  'is-disabled': isRoleDefault(p.code),
                }"
                role="button"
                :tabindex="isRoleDefault(p.code) ? -1 : 0"
                @click="onPermItemClick(p.code)"
                @keydown.enter.prevent="onPermItemClick(p.code)"
                @keydown.space.prevent="onPermItemClick(p.code)"
              >
                <el-checkbox
                  :model-value="permChecked(p.code)"
                  :disabled="isRoleDefault(p.code)"
                  @click.stop
                  @change="(v: boolean | string | number) => togglePerm(p.code, !!v)"
                />
                <div class="perm-item__main">
                  <div class="perm-item__label">{{ p.label }}</div>
                  <div v-if="p.description" class="perm-item__desc">{{ p.description }}</div>
                </div>
                <el-tag
                  v-if="isRoleDefault(p.code)"
                  size="small"
                  effect="plain"
                  type="info"
                  round
                  class="perm-item__badge"
                >
                  角色自带
                </el-tag>
              </div>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="permVisible = false">{{ permIsAdmin ? '关闭' : '取消' }}</el-button>
        <el-button
          v-if="!permIsAdmin"
          type="primary"
          :loading="permSaving"
          @click="submitPermissions"
        >
          保存授权
        </el-button>
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
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
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

.user-card__actions--4 {
  grid-template-columns: 1fr 1fr;
}

.user-card__actions .el-button {
  margin: 0;
  width: 100%;
}

.user-card__perm-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--oc-primary, #a16207);
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

.pc-perm-all {
  font-size: 12px;
  color: var(--oc-primary, #a16207);
  font-weight: 600;
}

.pc-perm-none {
  color: #a8a29e;
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

/* 授权弹窗：非 scoped，避免 teleport 后布局样式偶发失效 */
.perm-dialog .perm-head {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-right: 28px;
  min-width: 0;
}

.perm-dialog .perm-head__title {
  font-size: 16px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
}

.perm-dialog .perm-head__sub {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.perm-dialog .perm-head__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
}

.perm-dialog .perm-head__uname {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.perm-dialog .perm-body {
  min-height: 120px;
  max-height: min(64vh, 560px);
  overflow-x: hidden;
  overflow-y: auto;
  padding: 2px 2px 4px 0;
  -webkit-overflow-scrolling: touch;
}

.perm-dialog .perm-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  background: linear-gradient(180deg, #faf6ee 0%, #f5f0e6 100%);
  border: 1px solid var(--oc-border, #e8e0d0);
}

.perm-dialog .perm-summary__item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.perm-dialog .perm-summary__label {
  font-weight: 500;
}

.perm-dialog .perm-summary__item b {
  color: var(--oc-primary, #a16207);
  font-weight: 700;
  font-size: 15px;
}

.perm-dialog .perm-summary__unit {
  font-size: 12px;
}

.perm-dialog .perm-summary__sep {
  width: 1px;
  height: 14px;
  background: #e0d5c4;
  flex-shrink: 0;
}

.perm-dialog .perm-summary__tip {
  flex: 1 1 100%;
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.perm-dialog .perm-group {
  margin-bottom: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: var(--oc-card, #fffdf8);
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(41, 37, 36, 0.03);
}

.perm-dialog .perm-group:last-child {
  margin-bottom: 0;
}

.perm-dialog .perm-group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  background: linear-gradient(180deg, #faf6ee 0%, #f5efe3 100%);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.perm-dialog .perm-group__title {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
}

.perm-dialog .perm-group__count {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(161, 98, 7, 0.1);
}

.perm-dialog .perm-group__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
}

@media (min-width: 640px) {
  .perm-dialog .perm-group__grid {
    grid-template-columns: 1fr 1fr;
  }

  .perm-dialog .perm-group__grid .perm-item:nth-child(odd) {
    border-right: 1px solid #f0e9dc;
  }
}

.perm-dialog .perm-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid #f0e9dc;
  cursor: pointer;
  transition: background 0.12s ease;
  min-width: 0;
  box-sizing: border-box;
  -webkit-tap-highlight-color: transparent;
  user-select: none;
}

.perm-dialog .perm-item:last-child {
  border-bottom: none;
}

@media (min-width: 640px) {
  .perm-dialog .perm-group__grid .perm-item:nth-last-child(2):nth-child(odd) {
    border-bottom: none;
  }
}

.perm-dialog .perm-item:hover:not(.is-disabled) {
  background: rgba(161, 98, 7, 0.05);
}

.perm-dialog .perm-item.is-checked {
  background: rgba(161, 98, 7, 0.08);
}

.perm-dialog .perm-item.is-checked:hover:not(.is-disabled) {
  background: rgba(161, 98, 7, 0.11);
}

.perm-dialog .perm-item.is-default,
.perm-dialog .perm-item.is-disabled {
  background: #faf8f3;
  cursor: default;
  opacity: 0.9;
}

.perm-dialog .perm-item__main {
  flex: 1;
  min-width: 0;
}

.perm-dialog .perm-item__label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  line-height: 1.35;
  word-break: break-word;
}

.perm-dialog .perm-item__desc {
  display: block;
  margin-top: 3px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.45;
  word-break: break-word;
}

.perm-dialog .perm-item__badge {
  flex-shrink: 0;
  margin-top: 1px;
}

.perm-dialog .perm-item .el-checkbox {
  height: auto;
  margin-top: 1px;
  flex-shrink: 0;
}

.perm-dialog .el-dialog__header {
  padding-bottom: 12px;
  margin-right: 0;
}

.perm-dialog .el-dialog__body {
  padding-top: 8px;
}

.perm-dialog .el-dialog__footer {
  padding-top: 12px;
}
</style>
