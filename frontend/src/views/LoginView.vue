<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  forgotPasswordApi,
  passwordHelpApi,
  type PasswordHelpInfo,
} from '../api/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const forgotFormRef = ref<FormInstance>()
const loading = ref(false)
const forgotVisible = ref(false)
const forgotLoading = ref(false)
const forgotSubmitting = ref(false)
const forgotSubmitted = ref(false)
const help = ref<PasswordHelpInfo | null>(null)
const showDemoAccounts = import.meta.env.DEV
const form = reactive({
  username: '',
  password: '',
})
const forgotForm = reactive({
  username: '',
  note: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const forgotRules: FormRules = {
  username: [{ required: true, message: '请填写登录用户名', trigger: 'blur' }],
}

const adminNames = computed(() => {
  const names = (help.value?.admins || [])
    .map((a) => (a.display_name || '').trim())
    .filter(Boolean)
  return names
})

const adminLabel = computed(() => {
  if (!adminNames.value.length) return '机构负责人'
  return adminNames.value.join('、')
})

const helpMessage = computed(() => {
  const u = forgotForm.username.trim() || '（请填写用户名）'
  return [
    '您好，我忘记了管理后台登录密码，麻烦帮忙重置。',
    `登录用户名：${u}`,
    forgotForm.note.trim() ? `补充说明：${forgotForm.note.trim()}` : '',
    '重置后请把新密码发给我，谢谢。',
  ]
    .filter(Boolean)
    .join('\n')
})

async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    ElMessage.success('登录成功')
    const raw = (route.query.redirect as string) || ''
    // 旧 /m/* 书签映射到正式路径
    let redirect = raw
    if (redirect.startsWith('/m/') || redirect === '/m') {
      const map: Record<string, string> = {
        '/m': '/',
        '/m/upload': '/upload',
        '/m/materials': '/materials',
        '/m/students': '/students',
        '/m/learning': '/learning',
        '/m/learning/new': '/learning/new',
      }
      if (map[redirect]) {
        redirect = map[redirect]
      } else if (redirect.startsWith('/m/students/')) {
        redirect = redirect.replace(/^\/m/, '')
      } else {
        redirect = redirect.replace(/^\/m/, '') || '/'
      }
    }
    if (redirect && redirect !== '/login') {
      await router.replace(redirect)
    } else {
      await router.replace('/')
    }
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '登录失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function fillDemo(username: string, password: string) {
  form.username = username
  form.password = password
}

async function openForgot() {
  forgotForm.username = form.username.trim()
  forgotForm.note = ''
  forgotSubmitted.value = false
  forgotVisible.value = true
  if (!help.value) {
    forgotLoading.value = true
    try {
      help.value = await passwordHelpApi()
    } catch {
      help.value = {
        supports_self_reset: false,
        method: 'admin_reset',
        title: '如何找回密码',
        summary:
          '本系统为机构内部工具，暂不支持短信/邮箱自助找回。请联系负责人在「用户管理」中重置密码。',
        steps: [
          '确认并记下您的登录用户名',
          '联系负责人，说明需要重置密码',
          '负责人在「用户管理」中为您设置新密码并告知您',
          '用新密码登录后，建议立即在右上角「修改密码」改成自己记得的密码',
        ],
        admins: [],
      }
    } finally {
      forgotLoading.value = false
    }
  }
}

watch(forgotVisible, (v) => {
  if (!v) {
    forgotFormRef.value?.clearValidate()
  }
})

async function copyHelpMessage() {
  try {
    await navigator.clipboard.writeText(helpMessage.value)
    ElMessage.success('已复制求助信息，可发给负责人')
  } catch {
    ElMessage.warning('复制失败，请手动选择下方文字')
  }
}

async function submitForgot() {
  const ok = await forgotFormRef.value?.validate().catch(() => false)
  if (!ok) return
  forgotSubmitting.value = true
  try {
    const result = await forgotPasswordApi(forgotForm.username.trim(), forgotForm.note.trim())
    forgotSubmitted.value = true
    ElMessage.success(result.message || '已提交申请')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '提交失败'
    ElMessage.error(msg)
  } finally {
    forgotSubmitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-ornament" aria-hidden="true" />
    <el-card class="login-card" shadow="never">
      <template #header>
        <div class="card-header">
          <img class="logo-mark" src="/brand-mark.png" alt="嘉壹启航" width="56" height="56" />
          <h2>嘉壹启航管理后台</h2>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" clearable autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            autocomplete="current-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <div class="login-links">
          <el-button link type="primary" @click="openForgot">忘记密码？</el-button>
        </div>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="submit-btn">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <el-collapse v-if="showDemoAccounts" class="demo-accounts">
        <el-collapse-item title="演示账号（仅开发环境）" name="demo">
          <el-space wrap>
            <el-tag class="demo-tag" @click="fillDemo('admin', 'admin123')">admin / admin123</el-tag>
            <el-tag type="success" class="demo-tag" @click="fillDemo('ops', 'ops123')">ops / ops123</el-tag>
            <el-tag type="warning" class="demo-tag" @click="fillDemo('teacher1', 't123')">
              teacher1 / t123
            </el-tag>
          </el-space>
          <p class="hint">点击标签可填入表单。生产环境请修改默认密码。</p>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <el-dialog
      v-model="forgotVisible"
      title="忘记密码"
      width="90%"
      style="max-width: 440px"
      align-center
      destroy-on-close
      class="forgot-dialog"
    >
      <div v-loading="forgotLoading" class="forgot-body">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          :title="help?.summary || '请联系负责人重置密码'"
        />

        <ol class="forgot-steps">
          <li v-for="(step, i) in help?.steps || []" :key="i">{{ step }}</li>
        </ol>

        <div class="forgot-admins">
          <span class="forgot-admins__label">当前负责人</span>
          <div class="forgot-admins__list">
            <template v-if="adminNames.length">
              <el-tag
                v-for="name in adminNames"
                :key="name"
                type="warning"
                effect="plain"
                round
              >
                {{ name }}
              </el-tag>
            </template>
            <span v-else class="forgot-admins__empty">请联系机构负责人</span>
          </div>
        </div>

        <el-form
          ref="forgotFormRef"
          class="forgot-form"
          :model="forgotForm"
          :rules="forgotRules"
          label-position="top"
          @submit.prevent="submitForgot"
        >
          <el-form-item label="您的登录用户名" prop="username">
            <el-input
              v-model="forgotForm.username"
              placeholder="与登录页相同的用户名"
              clearable
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item label="补充说明（可选）">
            <el-input
              v-model="forgotForm.note"
              type="textarea"
              :rows="2"
              maxlength="200"
              show-word-limit
              placeholder="例如：微信昵称、所在校区，方便负责人确认身份"
            />
          </el-form-item>
        </el-form>

        <div class="forgot-copy-box">
          <div class="forgot-copy-box__head">
            <span>可复制发给负责人</span>
            <el-button link type="primary" @click="copyHelpMessage">复制</el-button>
          </div>
          <pre class="forgot-copy-box__text">{{ helpMessage }}</pre>
        </div>

        <el-alert
          v-if="forgotSubmitted"
          class="forgot-done"
          type="success"
          :closable="false"
          show-icon
          title="申请已提交"
          :description="`若账号存在，${adminLabel} 的待办中会出现重置提醒。也可直接把上方求助信息发给对方。`"
        />
      </div>

      <template #footer>
        <el-button @click="forgotVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :loading="forgotSubmitting"
          :disabled="forgotSubmitted"
          @click="submitForgot"
        >
          {{ forgotSubmitted ? '已提交申请' : '通知负责人重置' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-page {
  box-sizing: border-box;
  min-height: 100vh;
  min-height: 100dvh;
  /* pad 上 html/body 锁高时，登录页自己可滚，避免小屏键盘顶起后裁切 */
  height: 100%;
  max-height: 100vh;
  max-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  position: relative;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  background:
    radial-gradient(ellipse 80% 60% at 10% 20%, rgba(245, 230, 200, 0.55), transparent 55%),
    radial-gradient(ellipse 70% 50% at 90% 80%, rgba(161, 98, 7, 0.12), transparent 50%),
    linear-gradient(160deg, #faf8f3 0%, #f3eee4 48%, #ebe4d6 100%);
}

.login-ornament {
  position: absolute;
  width: 420px;
  height: 420px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.12);
  top: -120px;
  right: -80px;
  pointer-events: none;
}

.login-card {
  width: 100%;
  max-width: 420px;
  position: relative;
  z-index: 1;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 16px 40px rgba(41, 37, 36, 0.08);
}

.card-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  padding: 8px 0 4px;
}

.logo-mark {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  flex-shrink: 0;
  background: #fff;
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.18), 0 4px 12px rgba(41, 37, 36, 0.08);
}

.card-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--oc-ink, #44403c);
  font-weight: 700;
  letter-spacing: 0.04em;
}

.submit-btn {
  width: 100%;
  height: 40px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.login-links {
  display: flex;
  justify-content: flex-end;
  margin: -4px 0 8px;
}

.demo-accounts {
  margin-top: 12px;
  border: none;
}

.demo-tag {
  cursor: pointer;
}

.hint {
  margin: 8px 0 0;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
}

.forgot-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 120px;
}

.forgot-steps {
  margin: 0;
  padding: 0 0 0 1.25rem;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
  line-height: 1.65;
}

.forgot-steps li + li {
  margin-top: 4px;
}

.forgot-admins {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 10px;
  background: #faf6ee;
}

.forgot-admins__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-muted, #78716c);
}

.forgot-admins__list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.forgot-admins__empty {
  font-size: 13px;
  color: var(--oc-ink, #44403c);
}

.forgot-form {
  margin: 0;
}

.forgot-copy-box {
  border: 1px dashed rgba(161, 98, 7, 0.35);
  border-radius: 10px;
  background: #fffdf8;
  overflow: hidden;
}

.forgot-copy-box__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-muted, #78716c);
  background: rgba(245, 230, 200, 0.35);
}

.forgot-copy-box__text {
  margin: 0;
  padding: 10px 12px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.55;
  color: var(--oc-ink, #44403c);
}

.forgot-done {
  margin-top: 2px;
}
</style>
