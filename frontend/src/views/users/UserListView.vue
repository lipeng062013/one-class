<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createUserApi, listUsersApi, patchUserApi, resetPasswordApi, type UserRow } from '../../api/users'

const loading = ref(false)
const rows = ref<UserRow[]>([])
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

async function load() {
  loading.value = true
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
    if (filters.username) params.username = filters.username
    if (filters.display_name) params.display_name = filters.display_name
    rows.value = await listUsersApi(params)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.role = ''
  filters.is_active = ''
  filters.username = ''
  filters.display_name = ''
  load()
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

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <el-page-header content="用户管理" />
      <el-button type="primary" @click="openCreate">新建用户</el-button>
    </div>

    <el-card class="filters" shadow="never" style="margin-top: 12px">
      <el-form :inline="true" @submit.prevent="load">
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
          <el-input v-model="filters.username" clearable placeholder="搜索" style="width: 120px" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="filters.display_name" clearable placeholder="搜索" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card style="margin-top: 12px">
      <el-table v-loading="loading" :data="rows" stripe style="width: 100%">
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="display_name" label="显示名" min-width="120" />
        <el-table-column label="角色" min-width="100">
          <template #default="{ row }">{{ roleLabel[row.role] || row.role }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openReset(row)">重置密码</el-button>
            <el-button link type="warning" @click="toggleActive(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建用户" width="90%" style="max-width: 480px" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" />
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="createForm.display_name" />
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

    <el-dialog v-model="resetVisible" title="重置密码" width="90%" style="max-width: 420px" destroy-on-close>
      <p v-if="resetTarget">
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
      <el-alert type="warning" :closable="false" show-icon title="关闭后将无法再次查看明文密码，请立即复制并告知对方。" />
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
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.filters {
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.pwd-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.pwd-row .el-input {
  flex: 1;
}
</style>
