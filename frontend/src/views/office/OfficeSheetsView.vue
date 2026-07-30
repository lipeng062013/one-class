<script setup lang="ts">
import { computed, ref } from 'vue'

/** 嘉壹启航 — 综合办公表（金山文档 / WPS 云文档共享链接） */
const DEFAULT_URL = 'https://www.kdocs.cn/l/cbCDwO0pLfDN'

const sheetUrl = computed(
  () => (import.meta.env.VITE_KDOCS_OFFICE_URL as string | undefined)?.trim() || DEFAULT_URL,
)

const frameLoaded = ref(false)
const loadTimedOut = ref(false)
let loadTimer: ReturnType<typeof setTimeout> | null = null

function onFrameLoad() {
  frameLoaded.value = true
  loadTimedOut.value = false
  if (loadTimer) {
    clearTimeout(loadTimer)
    loadTimer = null
  }
}

function onFrameStart() {
  frameLoaded.value = false
  loadTimedOut.value = false
  if (loadTimer) clearTimeout(loadTimer)
  // 若被 X-Frame-Options 拦截，onload 可能不触发；超时后提示新窗口打开
  loadTimer = setTimeout(() => {
    if (!frameLoaded.value) loadTimedOut.value = true
  }, 8000)
}

onFrameStart()
</script>

<template>
  <div class="office-page">
    <div class="toolbar">
      <div class="titles">
        <h2 class="title">综合办公表</h2>
        <p class="subtitle">嘉壹启航 · 金山文档 / WPS 云文档（内容在 WPS 中维护，此处实时查看）</p>
      </div>
      <div class="actions">
        <el-button tag="a" :href="sheetUrl" target="_blank" rel="noopener noreferrer" type="primary">
          <el-icon class="btn-icon"><Link /></el-icon>
          在 WPS 中打开
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="loadTimedOut"
      class="hint"
      type="warning"
      :closable="false"
      show-icon
      title="表格未能在页面内加载"
      description="可能是金山文档限制了嵌入，或需要登录 WPS。请点击右上角「在 WPS 中打开」，或在文档分享里开启「获得链接的人可查看」。"
    />

    <div class="frame-wrap">
      <div v-if="!frameLoaded && !loadTimedOut" class="frame-loading">
        <el-icon class="is-loading" :size="28"><Loading /></el-icon>
        <span>正在加载综合办公表…</span>
      </div>
      <iframe
        class="sheet-frame"
        :src="sheetUrl"
        title="嘉壹启航—综合办公表"
        referrerpolicy="no-referrer-when-downgrade"
        allow="fullscreen; clipboard-read; clipboard-write"
        @load="onFrameLoad"
      />
    </div>
  </div>
</template>

<style scoped>
.office-page {
  /* 抵消 layout main 内边距，让表格尽量全屏 */
  margin: -18px -20px;
  height: calc(100vh - 56px);
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--oc-page, #faf8f3);
}

.toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--oc-card, #fffdf8);
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.titles {
  min-width: 0;
}

.title {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
}

.subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.actions {
  flex-shrink: 0;
}

.btn-icon {
  margin-right: 4px;
}

.hint {
  flex-shrink: 0;
  margin: 0;
  border-radius: 0;
}

.frame-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  background: #fff;
}

.frame-loading {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  background: var(--oc-page, #faf8f3);
  pointer-events: none;
}

.sheet-frame {
  display: block;
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

@media (max-width: 768px) {
  .office-page {
    margin: -12px;
    height: calc(100vh - 56px);
  }

  .subtitle {
    display: none;
  }

  .toolbar {
    padding: 10px 12px;
  }
}
</style>
