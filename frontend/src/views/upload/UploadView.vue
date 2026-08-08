<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadUserFile } from 'element-plus'
import { createMaterialApi, uploadMaterialFileApi } from '../../api/materials'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { usePageBack } from '../../composables/usePageBack'
import MobileActionBar from '../../components/MobileActionBar.vue'

const router = useRouter()
const { isApp } = useBreakpoint()
const { goBack } = usePageBack('/materials')
const formRef = ref<FormInstance>()
const loading = ref(false)
const fileList = ref<UploadUserFile[]>([])
const uploadStep = ref<'basic' | 'scene' | 'images'>('basic')
const uploadStepOptions = [
  { label: '基本信息', value: 'basic' },
  { label: '场景内容', value: 'scene' },
  { label: '图片', value: 'images' },
]

const form = reactive({
  title: '',
  grade: '',
  subject: '',
  pain_point: '',
  teacher_action: '',
  next_step: '',
  auth_status: 'authorized',
})

const authOptions = [
  { value: 'authorized', label: '已授权可发', desc: '可用于对外文案' },
  { value: 'pending', label: '待确认', desc: '暂缓对外使用' },
  { value: 'anonymized', label: '已脱敏', desc: '可发但需脱敏表述' },
  { value: 'denied', label: '不可用', desc: '仅内部留存' },
] as const

const rules: FormRules = {
  title: [{ required: true, message: '请填写场景标题', trigger: 'blur' }],
  auth_status: [{ required: true, message: '请选择授权状态', trigger: 'change' }],
}

const imageCount = computed(() => fileList.value.length)

const stepIndex = computed(() => {
  if (uploadStep.value === 'basic') return 0
  if (uploadStep.value === 'scene') return 1
  return 2
})

const stepHint = computed(() => {
  if (uploadStep.value === 'basic') return '先写标题与授权，年级科目可选'
  if (uploadStep.value === 'scene') return '痛点与处理会用于生成文案'
  return '可多选图片，也可稍后在详情补传'
})

function selectAuth(value: string) {
  form.auth_status = value
  void formRef.value?.validateField('auth_status')
}

function goStep(value: 'basic' | 'scene' | 'images') {
  uploadStep.value = value
}

function resetForm() {
  form.title = ''
  form.grade = ''
  form.subject = ''
  form.pain_point = ''
  form.teacher_action = ''
  form.next_step = ''
  form.auth_status = 'authorized'
  fileList.value = []
  formRef.value?.clearValidate()
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) {
    uploadStep.value = 'basic'
    return
  }
  loading.value = true
  try {
    const material = await createMaterialApi({ ...form })
    for (const item of fileList.value) {
      const raw = item.raw
      if (raw) {
        await uploadMaterialFileApi(material.id, raw as File)
      }
    }
    ElMessage.success('素材已提交')
    resetForm()
    // replace：详情页返回时不会再掉进空白上传表单
    await router.replace(`/materials/${material.id}`)
  } catch {
    /* interceptor */
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div
    class="upload-page oc-page-shell"
    :class="{ 'is-compact': isApp }"
  >
    <div class="page-toolbar">
      <el-page-header @back="goBack">
        <template #content>
          <span class="page-title">上传素材</span>
        </template>
      </el-page-header>
      <div class="toolbar-actions">
        <el-button plain @click="goBack()">
          <el-icon class="btn-ico"><FolderOpened /></el-icon>
          素材库
        </el-button>
      </div>
    </div>

    <section v-if="!isApp" class="hero">
      <div class="hero-ornament" aria-hidden="true" />
      <div class="hero-body">
        <div class="hero-main">
          <div class="hero-kicker">
            <el-icon><Upload /></el-icon>
            <span>课堂素材</span>
          </div>
          <h1 class="hero-title">记录场景，方便后续生成文案</h1>
          <p class="hero-desc">
            填写标题与场景要点，可附多张图片。提交后进入素材详情，可一键「生成文案」。
          </p>
          <div class="hero-steps" aria-hidden="true">
            <span class="step">1 基本信息</span>
            <span class="step-line" />
            <span class="step">2 场景内容</span>
            <span class="step-line" />
            <span class="step">3 图片与提交</span>
          </div>
        </div>
      </div>
    </section>

    <!-- WAP/Pad：步骤条 + 轻提示 -->
    <section v-if="isApp" class="compact-hero">
      <div class="compact-hero__top">
        <div class="compact-hero__kicker">
          <el-icon><Upload /></el-icon>
          <span>上传课堂素材</span>
        </div>
        <span class="compact-hero__progress">{{ stepIndex + 1 }} / 3</span>
      </div>
      <p class="compact-hero__hint">{{ stepHint }}</p>
      <div class="step-dots" role="tablist" aria-label="上传步骤">
        <button
          v-for="(opt, idx) in uploadStepOptions"
          :key="opt.value"
          type="button"
          class="step-dot"
          :class="{ active: uploadStep === opt.value, done: stepIndex > idx }"
          role="tab"
          :aria-selected="uploadStep === opt.value"
          @click="goStep(opt.value as 'basic' | 'scene' | 'images')"
        >
          <span class="step-dot__num">{{ idx + 1 }}</span>
          <span class="step-dot__label">{{ opt.label }}</span>
        </button>
      </div>
    </section>

    <el-form
      ref="formRef"
      v-loading="loading"
      class="upload-form"
      :model="form"
      :rules="rules"
      label-position="top"
      :size="isApp ? 'large' : 'default'"
      @submit.prevent
    >
      <div class="upload-layout" :class="{ 'is-compact': isApp }">
        <div class="main-col">
          <section v-show="!isApp || uploadStep === 'basic'" class="panel">
            <div class="panel-head">
              <div>
                <h2 class="panel-title">基本信息</h2>
                <p class="panel-sub">标题必填 · 年级 / 科目可选</p>
              </div>
            </div>

            <el-form-item label="场景标题" prop="title">
              <el-input
                v-model="form.title"
                maxlength="80"
                show-word-limit
                placeholder="例如：课堂进步 / 试听反馈"
              />
            </el-form-item>

            <div class="form-grid" :class="{ 'is-compact': isApp }">
              <el-form-item>
                <template #label>
                  <span class="label-with-opt">年级 <em>可选</em></span>
                </template>
                <el-input v-model="form.grade" placeholder="如 四年级" />
              </el-form-item>
              <el-form-item>
                <template #label>
                  <span class="label-with-opt">科目 <em>可选</em></span>
                </template>
                <el-input v-model="form.subject" placeholder="如 数学" />
              </el-form-item>
            </div>

            <el-form-item label="家长授权" prop="auth_status">
              <div class="auth-grid" :class="{ 'is-compact': isApp }">
                <button
                  v-for="opt in authOptions"
                  :key="opt.value"
                  type="button"
                  class="auth-card"
                  :class="{ active: form.auth_status === opt.value }"
                  @click="selectAuth(opt.value)"
                >
                  <strong>{{ opt.label }}</strong>
                  <span>{{ opt.desc }}</span>
                </button>
              </div>
            </el-form-item>
          </section>

          <section v-show="!isApp || uploadStep === 'scene'" class="panel">
            <div class="panel-head">
              <div>
                <h2 class="panel-title">场景内容</h2>
                <p class="panel-sub">痛点 · 处理 · 下一步（生成文案会用到）</p>
              </div>
            </div>

            <el-form-item>
              <template #label>
                <span class="label-with-opt">家长痛点 <em>可选</em></span>
              </template>
              <el-input
                v-model="form.pain_point"
                type="textarea"
                :rows="3"
                resize="none"
                placeholder="例如：孩子畏难、作业拖拉、成绩波动…"
              />
            </el-form-item>
            <el-form-item>
              <template #label>
                <span class="label-with-opt">老师处理 <em>可选</em></span>
              </template>
              <el-input
                v-model="form.teacher_action"
                type="textarea"
                :rows="3"
                resize="none"
                placeholder="例如：当堂鼓励、拆解步骤、家校沟通…"
              />
            </el-form-item>
            <el-form-item>
              <template #label>
                <span class="label-with-opt">下一步行动 <em>可选</em></span>
              </template>
              <el-input
                v-model="form.next_step"
                type="textarea"
                :rows="3"
                resize="none"
                placeholder="例如：本周巩固练习、约家长沟通…"
              />
            </el-form-item>
          </section>

          <!-- compact：图片区落在主列底部（PC 在右侧） -->
          <section v-if="isApp" v-show="uploadStep === 'images'" class="panel">
            <div class="panel-head">
              <div>
                <h2 class="panel-title">图片</h2>
                <p class="panel-sub">可多选 · 提交时一并上传</p>
              </div>
              <el-tag v-if="imageCount" size="small" effect="plain" type="warning" round>
                已选 {{ imageCount }} 张
              </el-tag>
            </div>
            <div class="upload-zone">
              <el-upload
                v-model:file-list="fileList"
                list-type="picture-card"
                :auto-upload="false"
                accept="image/*"
                multiple
              >
                <div class="upload-trigger">
                  <el-icon :size="22"><Plus /></el-icon>
                  <span>添加图片</span>
                </div>
              </el-upload>
              <p class="upload-hint">支持多选；建议清晰课堂 / 作品照</p>
            </div>
          </section>
        </div>

        <aside v-if="!isApp" class="side-col">
          <section class="panel sticky-panel">
            <div class="panel-head">
              <div>
                <h2 class="panel-title">图片与提交</h2>
                <p class="panel-sub">可多选 · 提交后进入素材详情</p>
              </div>
              <el-tag v-if="imageCount" size="small" effect="plain" type="warning" round>
                已选 {{ imageCount }} 张
              </el-tag>
            </div>
            <div class="upload-zone">
              <el-upload
                v-model:file-list="fileList"
                list-type="picture-card"
                :auto-upload="false"
                accept="image/*"
                multiple
              >
                <div class="upload-trigger">
                  <el-icon :size="22"><Plus /></el-icon>
                  <span>添加图片</span>
                </div>
              </el-upload>
              <p class="upload-hint">支持多选；建议清晰课堂 / 作品照，单张不宜过大</p>
            </div>
            <el-button
              class="submit-btn"
              type="primary"
              size="large"
              :loading="loading"
              @click="submit"
            >
              提交素材
            </el-button>
            <p class="side-tip">提交成功后将打开该素材详情，可继续生成文案。</p>
          </section>
        </aside>
      </div>
    </el-form>

    <MobileActionBar v-if="isApp">
      <el-button v-if="uploadStep === 'basic'" @click="goBack()">取消</el-button>
      <el-button v-else @click="uploadStep = uploadStep === 'images' ? 'scene' : 'basic'">
        上一步
      </el-button>
      <el-button
        v-if="uploadStep !== 'images'"
        type="primary"
        @click="uploadStep = uploadStep === 'basic' ? 'scene' : 'images'"
      >
        下一步
      </el-button>
      <el-button v-else type="primary" :loading="loading" @click="submit">
        提交素材
      </el-button>
    </MobileActionBar>
  </div>
</template>

<style scoped>
.upload-page {
  padding-bottom: 24px;
}

.page-title {
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.page-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.btn-ico {
  margin-right: 4px;
}

/* ── Hero ── */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: 16px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: linear-gradient(135deg, #fffdf8 0%, #faf6ee 45%, #f5e6c8 120%);
  box-shadow: 0 10px 28px rgba(41, 37, 36, 0.05);
  margin-bottom: 14px;
}

.hero-ornament {
  position: absolute;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.12);
  right: -40px;
  top: -70px;
  pointer-events: none;
}

.hero-ornament::after {
  content: '';
  position: absolute;
  inset: 26px;
  border-radius: 50%;
  border: 1px solid rgba(161, 98, 7, 0.08);
}

.hero-body {
  position: relative;
  z-index: 1;
  padding: 18px 20px 16px;
}

.hero-kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--oc-primary, #a16207);
  margin-bottom: 8px;
}

.hero-title {
  margin: 0;
  font-size: clamp(1.15rem, 1vw + 0.85rem, 1.45rem);
  font-weight: 750;
  color: var(--oc-ink, #44403c);
  line-height: 1.3;
  letter-spacing: 0.01em;
}

.hero-desc {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--oc-muted, #78716c);
  max-width: 52rem;
}

.hero-steps {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}

.step {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-primary, #a16207);
  background: rgba(255, 253, 248, 0.85);
  border: 1px solid rgba(232, 224, 208, 0.95);
}

.step-line {
  width: 16px;
  height: 1px;
  background: rgba(161, 98, 7, 0.28);
}

/* ── 布局 ── */
.upload-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.75fr);
  gap: 16px;
  align-items: start;
}

.upload-layout.is-compact {
  grid-template-columns: 1fr;
  gap: 14px;
}

.compact-hero {
  margin: 0 auto 12px;
  width: min(100%, 720px);
  padding: 14px 14px 12px;
  border-radius: 16px;
  border: 1px solid rgba(181, 145, 83, 0.32);
  background:
    linear-gradient(125deg, #ffffff 0%, #fffdf8 42%, #faf3e6 100%);
  box-shadow:
    0 10px 24px rgba(88, 60, 24, 0.08),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.compact-hero__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.compact-hero__kicker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 700;
  color: var(--oc-primary, #a16207);
}

.compact-hero__progress {
  flex-shrink: 0;
  min-width: 42px;
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #86530a;
  background: rgba(245, 230, 200, 0.85);
  border: 1px solid rgba(181, 145, 83, 0.28);
}

.compact-hero__hint {
  margin: 8px 0 12px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

.step-dots {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.step-dot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-height: 64px;
  padding: 10px 6px;
  border-radius: 14px;
  border: 1.5px solid rgba(232, 224, 208, 0.95);
  background: rgba(255, 253, 248, 0.85);
  color: var(--oc-muted, #78716c);
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s;
  -webkit-tap-highlight-color: transparent;
}

.step-dot__num {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 750;
  background: #f5f0e6;
  color: #78716c;
}

.step-dot__label {
  font-size: 11px;
  font-weight: 650;
  line-height: 1.2;
  text-align: center;
}

.step-dot.done {
  border-color: rgba(103, 194, 58, 0.35);
  background: linear-gradient(180deg, #f6fbf3, #eef8ea);
}

.step-dot.done .step-dot__num {
  background: #67c23a;
  color: #fff;
}

.step-dot.active {
  border-color: var(--oc-primary, #a16207);
  background: linear-gradient(180deg, #faf6ee, #f2e8d6);
  color: var(--oc-primary, #a16207);
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.12);
}

.step-dot.active .step-dot__num {
  background: linear-gradient(145deg, #c98718, #a16207);
  color: #fffdf8;
}

.step-dot.active .step-dot__label {
  color: #86530a;
}

.upload-page.is-compact .upload-form {
  width: min(100%, 720px);
  margin: 0 auto;
}

.upload-page.is-compact .panel {
  border-radius: 16px;
  border-color: rgba(181, 145, 83, 0.28);
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.88) 0%, transparent 46%),
    #fffdf8;
  box-shadow:
    0 12px 28px rgba(88, 60, 24, 0.08),
    0 2px 0 rgba(255, 255, 255, 0.9) inset;
  padding: 16px 14px 8px;
}

.upload-page.is-compact .panel-head {
  margin-bottom: 14px;
  padding-bottom: 12px;
}

.upload-page.is-compact .auth-card {
  min-height: 72px;
  border-radius: 14px;
  padding: 12px;
}

.upload-page.is-compact .auth-card strong {
  font-size: 13px;
}

.upload-page.is-compact .upload-zone :deep(.el-upload--picture-card),
.upload-page.is-compact .upload-zone :deep(.el-upload-list--picture-card .el-upload-list__item) {
  width: 96px;
  height: 96px;
  border-radius: 14px;
}

.upload-page.is-compact :deep(.el-input__wrapper),
.upload-page.is-compact :deep(.el-textarea__inner) {
  min-height: 44px;
  border-radius: 12px;
}

.upload-page.is-compact :deep(.el-textarea__inner) {
  min-height: 96px;
  padding: 12px 14px;
}

.main-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.side-col {
  min-width: 0;
}

.panel {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  padding: 16px 18px 8px;
}

.sticky-panel {
  position: sticky;
  top: 12px;
  padding-bottom: 16px;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(232, 224, 208, 0.85);
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.01em;
}

.panel-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.4;
}

.label-with-opt {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
}

.label-with-opt em {
  font-style: normal;
  font-size: 12px;
  font-weight: 400;
  color: var(--oc-muted, #78716c);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.form-grid.is-compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

/* ── 授权卡片 ── */
.auth-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
}

.auth-grid.is-compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.auth-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  text-align: left;
  padding: 12px 12px 11px;
  border-radius: 12px;
  border: 1.5px solid var(--oc-border, #e8e0d0);
  background: #fffdfb;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
  color: inherit;
  font: inherit;
}

.auth-card:hover {
  border-color: #dbbf94;
}

.auth-card.active {
  border-color: var(--oc-primary, #a16207);
  background: linear-gradient(180deg, #faf6ee 0%, #f2e8d6 100%);
  box-shadow: 0 0 0 1px rgba(161, 98, 7, 0.12);
}

.auth-card strong {
  font-size: 13px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.auth-card span {
  font-size: 11px;
  line-height: 1.4;
  color: var(--oc-muted, #78716c);
}

/* ── 上传 ── */
.upload-zone {
  margin-bottom: 4px;
}

.upload-trigger {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  height: 100%;
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  font-weight: 550;
}

.upload-zone :deep(.el-upload--picture-card) {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: linear-gradient(180deg, #fffdfb, #faf6ee);
  width: 104px;
  height: 104px;
}

.upload-zone :deep(.el-upload-list--picture-card .el-upload-list__item) {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  width: 104px;
  height: 104px;
}

.upload-hint {
  margin: 8px 0 4px;
  font-size: 12px;
  line-height: 1.45;
  color: var(--oc-muted, #78716c);
}

.submit-btn {
  width: 100%;
  margin-top: 12px;
  height: 44px;
  border-radius: 10px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(161, 98, 7, 0.22);
}

.side-tip {
  margin: 10px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--oc-muted, #78716c);
}

/* 表单项间距 */
.upload-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.upload-form :deep(.el-form-item__label) {
  font-weight: 550;
  color: var(--oc-ink, #44403c);
}

@media (max-width: 767px) {
  .hero-body {
    padding: 16px 14px 14px;
  }

  .panel {
    padding: 14px 14px 4px;
    border-radius: 12px;
  }

  .auth-grid.is-compact {
    grid-template-columns: 1fr 1fr;
  }

  .step-line {
    display: none;
  }

  .form-grid.is-compact {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .upload-page.is-compact .toolbar-actions {
    width: 100%;
  }

  .upload-page.is-compact .toolbar-actions .el-button {
    width: 100%;
    min-height: 40px;
    border-radius: 12px;
  }
}

@media (min-width: 768px) and (max-width: 1199px) {
  .upload-page.is-compact .compact-hero,
  .upload-page.is-compact .upload-form {
    width: min(100%, 820px);
  }

  .auth-grid.is-compact {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

</style>
