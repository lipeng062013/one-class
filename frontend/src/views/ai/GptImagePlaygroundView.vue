<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  applyProxyApiToDefaultProfile,
  buildPlaygroundIframeSrc,
  getImagePlaygroundConfig,
  resolveProxyApiUrl,
  type ImagePlaygroundConfig,
} from '../../api/imagePlayground'

const router = useRouter()
const loading = ref(true)
const config = ref<ImagePlaygroundConfig | null>(null)
const iframeSrc = ref('')
const errorMsg = ref('')
const iframeLoaded = ref(false)

const ready = computed(() => Boolean(config.value?.ready && iframeSrc.value))

onMounted(async () => {
  loading.value = true
  errorMsg.value = ''
  iframeLoaded.value = false
  try {
    const token = localStorage.getItem('token')
    if (!token) {
      errorMsg.value = '未登录，无法打开 GPT 生图'
      return
    }
    const cfg = await getImagePlaygroundConfig()
    config.value = cfg
    if (!cfg.ready) {
      errorMsg.value =
        '图片 API 未配置：请在项目 .env 填写 IMAGE_API_BASE_URL、IMAGE_API_KEY 后重启后端'
      return
    }

    // 同源代理：浏览器不直连中转站（避免 CORS Failed to fetch）；真实 URL/Key 只在服务端
    const apiUrl = resolveProxyApiUrl(cfg.api_base_path)
    applyProxyApiToDefaultProfile({
      apiUrl,
      apiKey: token,
      model: cfg.model,
    })
    iframeSrc.value = buildPlaygroundIframeSrc({
      apiUrl,
      apiKey: token,
      model: cfg.model || 'gpt-image-2',
    })
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '加载 GPT Image Playground 失败'
    ElMessage.error(errorMsg.value)
  } finally {
    loading.value = false
  }
})

function openFullscreen() {
  if (!iframeSrc.value) return
  window.open(iframeSrc.value, '_blank', 'noopener,noreferrer')
}

function goPosters() {
  router.push('/posters/generate')
}

function onFrameLoad() {
  iframeLoaded.value = true
}
</script>

<template>
  <div class="page oc-page-shell">
    <!-- 顶栏 -->
    <header class="top">
      <div class="top-left">
        <div class="brand-icon" aria-hidden="true">
          <el-icon :size="20"><MagicStick /></el-icon>
        </div>
        <div class="titles">
          <div class="title-row">
            <h1 class="title">GPT 生图</h1>
            <el-tag
              v-if="config?.ready"
              class="model-tag"
              size="small"
              effect="plain"
              type="success"
            >
              {{ config.model || '已就绪' }}
            </el-tag>
            <el-tag v-else class="model-tag" size="small" effect="plain" type="info">
              未配置
            </el-tag>
          </div>
        </div>
      </div>

      <div class="top-right">
        <el-button class="action-btn" @click="goPosters">
          <el-icon class="btn-ico"><PictureFilled /></el-icon>
          用于海报生成
        </el-button>
        <el-button
          class="action-btn"
          type="primary"
          plain
          :disabled="!iframeSrc"
          @click="openFullscreen"
        >
          <el-icon class="btn-ico"><FullScreen /></el-icon>
          新窗口打开
        </el-button>
      </div>
    </header>

    <!-- 状态条：替代大块 Alert，更省纵向空间 -->
    <div
      v-if="!errorMsg"
      class="status-bar"
      :class="config?.ready ? 'is-ready' : 'is-pending'"
    >
      <el-icon class="status-ico" :size="16">
        <SuccessFilled v-if="config?.ready" />
        <WarningFilled v-else />
      </el-icon>
      <div class="status-text">
        <template v-if="config?.ready">
          已接入项目 <code>.env</code> 生图配置；请求经后端转发到
          <code>IMAGE_API_*</code>。设置里请保持「当前配置 = 默认」。
        </template>
        <template v-else>
          请先在 <code>.env</code> 配置
          <code>IMAGE_API_BASE_URL</code>、<code>IMAGE_API_KEY</code>、<code>IMAGE_MODEL</code>
          并重启后端。
        </template>
      </div>
    </div>

    <!-- 主体 -->
    <div v-if="loading" class="stage state-card">
      <div class="loading-inner">
        <el-skeleton :rows="8" animated />
        <p class="loading-hint">正在加载生图工作台…</p>
      </div>
    </div>

    <div v-else-if="errorMsg" class="stage state-card error-card">
      <el-result icon="warning" title="无法打开生图工作台" :sub-title="errorMsg">
        <template #extra>
          <el-space>
            <el-button type="primary" @click="goPosters">返回海报生成</el-button>
            <el-button @click="router.push('/')">回工作台</el-button>
          </el-space>
        </template>
      </el-result>
    </div>

    <div v-else-if="ready" class="stage frame-shell">
      <div class="frame-chrome">
        <span class="chrome-dot red" />
        <span class="chrome-dot yellow" />
        <span class="chrome-dot green" />
        <span class="chrome-title">GPT Image Playground</span>
        <span class="chrome-spacer" />
        <span v-if="!iframeLoaded" class="chrome-loading">加载中…</span>
        <span v-else class="chrome-ok">已连接</span>
      </div>
      <div class="frame-body" v-loading="!iframeLoaded">
        <iframe
          class="frame"
          :src="iframeSrc"
          title="GPT Image Playground"
          allow="clipboard-read; clipboard-write"
          @load="onFrameLoad"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  /* 吃满主内容区可视高度；宽度由 .oc-page-shell 吃满主区 */
  display: flex;
  flex-direction: column;
  height: calc(100vh - 88px);
  height: calc(100dvh - 88px);
  min-height: 560px;
  gap: 12px;
  /* 避免外层再滚一层，把滚动交给 playground iframe 内部 */
  overflow: hidden;
}

/* ── 顶栏 ── */
.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  flex-shrink: 0;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background:
    linear-gradient(135deg, #fffdf8 0%, #faf6ee 55%, #f5e6c8 140%);
  box-shadow: 0 6px 18px rgba(41, 37, 36, 0.04);
}

.top-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.brand-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #f5e6c8, #e8d4a8);
  color: var(--oc-primary, #a16207);
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.55);
}

.titles {
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
  line-height: 1.25;
}

.model-tag {
  border-radius: 999px;
  font-weight: 550;
}

.top-right {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.btn-ico {
  margin-right: 4px;
}

/* ── 状态条 ── */
.status-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-shrink: 0;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid transparent;
  font-size: 13px;
  line-height: 1.5;
  color: var(--oc-ink, #44403c);
}

.status-bar.is-ready {
  background: linear-gradient(90deg, #f0fdf4, #f7fef9);
  border-color: #bbf7d0;
}

.status-bar.is-pending {
  background: #faf6ee;
  border-color: var(--oc-border, #e8e0d0);
}

.status-ico {
  flex-shrink: 0;
  margin-top: 2px;
}

.is-ready .status-ico {
  color: #16a34a;
}

.is-pending .status-ico {
  color: var(--oc-primary, #a16207);
}

.status-text {
  min-width: 0;
  color: var(--oc-muted, #78716c);
}

.status-text code {
  font-size: 12px;
  padding: 1px 5px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(0, 0, 0, 0.06);
  color: var(--oc-ink, #44403c);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

/* ── 舞台 ── */
.stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.state-card {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
  padding: 20px;
  overflow: auto;
}

.loading-inner {
  max-width: 720px;
}

.loading-hint {
  margin: 16px 0 0;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
  text-align: center;
}

.error-card {
  align-items: center;
  justify-content: center;
}

/* ── iframe 外壳 ── */
.frame-shell {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  box-shadow:
    0 4px 6px rgba(41, 37, 36, 0.03),
    0 12px 32px rgba(41, 37, 36, 0.06);
  overflow: hidden;
  /* 关键 flex 高度链：chrome 固定 + body 吃剩余 */
  min-height: 0;
}

.frame-chrome {
  display: flex;
  align-items: center;
  gap: 7px;
  height: 36px;
  padding: 0 14px;
  flex-shrink: 0;
  background: linear-gradient(180deg, #faf6ee, #f3eee4);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.chrome-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
  opacity: 0.85;
}

.chrome-dot.red {
  background: #f1a8a0;
}
.chrome-dot.yellow {
  background: #e8c98a;
}
.chrome-dot.green {
  background: #a8d4b0;
}

.chrome-title {
  margin-left: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--oc-muted, #78716c);
  letter-spacing: 0.02em;
}

.chrome-spacer {
  flex: 1;
}

.chrome-loading,
.chrome-ok {
  font-size: 11px;
  color: var(--oc-muted, #78716c);
}

.chrome-ok {
  color: #16a34a;
}

.frame-body {
  flex: 1;
  min-height: 0;
  position: relative;
  background: #f8fafc;
  /* 给 absolute iframe 一个确定的包含块 */
  isolation: isolate;
}

/*
 * 绝对铺满 frame-body，避免 height:100% 在仅有 min-height 的祖先上塌缩。
 * Playground 内部大量 position:fixed（顶栏/底栏输入），依赖 iframe 视口尺寸正确。
 */
.frame {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: 0;
  display: block;
  background: #f8fafc;
}

/*
 * wap / pad（≤991）：
 * 根因是旧样式把 .page 设为 height:auto + frame 仅 min-height，
 * flex 高度链断裂 → iframe 视口异常 → Playground 底栏/内容区空白或错位。
 * 这里抵消 main 内边距，用确定高度吃满顶栏以下视口。
 */
@media (max-width: 991px) {
  .page {
    /*
     * AppLayout .header = 58px；.main pad 14px 12px。
     * 注意：.main 在 wap/pad 使用 scrollbar-gutter: both-edges，
     * 负 margin 只抵消 padding，不要用不对称的左右值。
     */
    margin: -14px -12px;
    padding: 10px 12px 12px;
    width: auto;
    max-width: none;
    height: calc(100vh - 58px);
    height: calc(100dvh - 58px);
    max-height: calc(100vh - 58px);
    max-height: calc(100dvh - 58px);
    min-height: 0;
    gap: 8px;
    box-sizing: border-box;
    border-radius: 0;
  }

  .top {
    padding: 10px 12px;
    border-radius: 12px;
    gap: 10px;
  }

  .brand-icon {
    width: 36px;
    height: 36px;
    border-radius: 10px;
  }

  .title {
    font-size: 1.05rem;
  }

  .status-bar {
    padding: 8px 12px;
    font-size: 12px;
    /* 单行截断，少占纵向空间 */
    align-items: center;
  }

  .status-bar .status-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .status-ico {
    margin-top: 0;
  }

  .frame-shell {
    flex: 1;
    min-height: 0;
    border-radius: 12px;
  }

  .frame-chrome {
    height: 32px;
    padding: 0 12px;
  }
}

@media (max-width: 767px) {
  .page {
    /* AppLayout 移动端 .main padding: 10px */
    margin: -10px;
    padding: 8px 10px 10px;
    height: calc(100vh - 58px);
    height: calc(100dvh - 58px);
    max-height: calc(100vh - 58px);
    max-height: calc(100dvh - 58px);
    gap: 6px;
  }

  .top {
    padding: 8px 10px;
    gap: 8px;
  }

  .top-right {
    width: 100%;
  }

  .top-right .el-button {
    flex: 1;
  }

  /* 已连接状态在 frame-chrome 可见，省掉大段说明 */
  .status-bar.is-ready {
    display: none;
  }

  .status-bar.is-pending {
    font-size: 12px;
  }

  .frame-chrome .chrome-dot {
    display: none;
  }

  .chrome-title {
    margin-left: 0;
  }
}

/* PC 大屏：再压一点顶栏占比，把高度留给画布 */
@media (min-width: 1280px) {
  .page {
    height: calc(100vh - 80px);
    height: calc(100dvh - 80px);
    gap: 10px;
  }

  .top {
    padding: 10px 18px;
  }

  .status-bar {
    padding: 8px 14px;
  }
}
</style>
