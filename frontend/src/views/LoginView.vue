<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const forgotVisible = ref(false)
const showDemoAccounts = import.meta.env.DEV
const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

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
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading" class="submit-btn">
            登录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="login-links">
        <el-button link type="primary" @click="forgotVisible = true">忘记密码？</el-button>
      </div>

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

    <el-dialog v-model="forgotVisible" title="忘记密码" width="90%" style="max-width: 420px">
      <p>
        本系统为机构内部工具，暂不支持短信/邮箱自助找回。请联系
        <strong>负责人</strong>，在「用户管理」中为您
        <strong>重置密码</strong>。重置后负责人会把新密码告知您。
      </p>
      <template #footer>
        <el-button type="primary" @click="forgotVisible = false">我知道了</el-button>
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
  text-align: right;
  margin-top: -8px;
  margin-bottom: 8px;
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
</style>
