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
  }>(),
  {
    title: '',
    size: '460px',
    compactSize: '90%',
    destroyOnClose: true,
    appendToBody: true,
    forceBottom: false,
    modalClass: '',
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
const { isCompact, isMobile } = useBreakpoint()

const visible = computed({
  get: () => props.modelValue,
  set: (v: boolean) => emit('update:modelValue', v),
})

const useBottom = computed(() => props.forceBottom || isCompact.value)

const direction = computed(() => (useBottom.value ? 'btt' : 'rtl'))

const resolvedSize = computed(() => {
  if (!useBottom.value) return props.size
  // 手机再高一点，接近全屏表单体验
  if (isMobile.value) return props.compactSize === '90%' ? '94%' : props.compactSize
  return props.compactSize
})

const sheetClass = computed(() => [
  'oc-app-sheet',
  useBottom.value ? 'is-bottom-sheet' : 'is-side-sheet',
  isMobile.value ? 'is-mobile' : '',
  props.modalClass,
])
</script>

<template>
  <el-drawer
    v-model="visible"
    :title="title"
    :size="resolvedSize"
    :direction="direction"
    :destroy-on-close="destroyOnClose"
    :append-to-body="appendToBody"
    :class="sheetClass"
    @open="emit('open')"
    @close="emit('close')"
    @opened="emit('opened')"
    @closed="emit('closed')"
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
  min-height: 0;
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
