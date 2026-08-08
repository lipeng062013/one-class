<script setup lang="ts">
/**
 * 教务 / 财务等业务侧栏：
 * - PC：右侧抽屉
 * - wap/pad：底部上滑面板（避免窄屏右侧抽屉难用）
 */
import { computed, useSlots } from 'vue'
import { useBreakpoint } from '../composables/useBreakpoint'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    /** 桌面端宽度，如 460px / 50% */
    size?: string | number
    /** 窄屏高度，默认 90% */
    compactSize?: string | number
    destroyOnClose?: boolean
    appendToBody?: boolean
    /** 强制始终底部（少用） */
    forceBottom?: boolean
    modalClass?: string
    /** 点击遮罩是否关闭，默认 true */
    closeOnClickModal?: boolean
  }>(),
  {
    title: '',
    size: '460px',
    compactSize: 'min(90%, 780px)',
    destroyOnClose: true,
    appendToBody: true,
    forceBottom: false,
    modalClass: '',
    closeOnClickModal: true,
  },
)

const emit = defineEmits<{
  'update:modelValue': [boolean]
  open: []
  close: []
  opened: []
  closed: []
}>()

const slots = useSlots()
const { isApp, isMobile, isPadLandscape } = useBreakpoint()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

// 手机 / Pad 竖屏从底部上滑；Pad 横屏保留右侧面板，方便与列表双栏并用。
const useBottom = computed(
  () => props.forceBottom || (isApp.value && !isPadLandscape.value),
)

const direction = computed(() => (useBottom.value ? 'btt' : 'rtl'))

const resolvedSize = computed(() => {
  if (!useBottom.value) return props.size
  // 手机接近全屏表单；Pad 竖屏也给足高度，避免「矮抽屉」观感
  if (isMobile.value) {
    const raw = String(props.compactSize)
    if (
      raw === '90%' ||
      raw === 'min(78%, 640px)' ||
      raw === 'min(86%, 720px)' ||
      raw === 'min(88%, 760px)' ||
      raw === 'min(90%, 780px)'
    ) {
      return '94%'
    }
    return props.compactSize
  }
  return props.compactSize
})

const sheetClass = computed(() => [
  'oc-app-sheet',
  useBottom.value ? 'is-bottom-sheet' : 'is-side-sheet',
  isMobile.value ? 'is-mobile' : '',
  props.modalClass,
])

/** 底部 Sheet 时锁住页面滚动；多层弹层用计数避免误关 */
function bumpSheetLock(delta: number) {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  const next = Math.max(0, Number(root.dataset.ocSheetCount || 0) + delta)
  root.dataset.ocSheetCount = String(next)
  root.classList.toggle('oc-sheet-open', next > 0)
}

function onOpen() {
  if (useBottom.value) bumpSheetLock(1)
  emit('open')
}

function onClosed() {
  if (useBottom.value) bumpSheetLock(-1)
  emit('closed')
}
</script>

<template>
  <el-drawer
    v-model="visible"
    :title="title"
    :size="resolvedSize"
    :direction="direction"
    :destroy-on-close="destroyOnClose"
    :append-to-body="appendToBody"
    :close-on-click-modal="closeOnClickModal"
    :class="sheetClass"
    @open="onOpen"
    @close="emit('close')"
    @opened="emit('opened')"
    @closed="onClosed"
  >
    <div class="oc-app-sheet__body">
      <slot />
    </div>
    <template v-if="slots.footer" #footer>
      <div class="oc-app-sheet__footer">
        <slot name="footer" />
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.oc-app-sheet__body {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

/* 间距由全局 style.css · --oc-dialog-footer-gap / .oc-app-sheet__footer 统一 */
.oc-app-sheet__footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: var(--oc-dialog-footer-gap, 12px);
  width: 100%;
}

.oc-app-sheet__footer :deep(.el-button) {
  margin: 0 !important;
}
</style>

<!-- 全局：挂在 body 上的 drawer 需要非 scoped 规则，写在 style.css · .oc-app-sheet -->
