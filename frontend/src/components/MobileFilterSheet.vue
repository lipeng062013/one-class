<script setup lang="ts">
import AppSheet from './AppSheet.vue'
import { useBreakpoint } from '../composables/useBreakpoint'

withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    activeCount?: number
    applyText?: string
    resetText?: string
    compactSize?: string | number
  }>(),
  {
    title: '筛选条件',
    activeCount: 0,
    applyText: '查看结果',
    resetText: '重置',
    compactSize: 'min(88%, 760px)',
  },
)

const emit = defineEmits<{
  'update:modelValue': [boolean]
  apply: []
  reset: []
}>()

const { isPadLandscape } = useBreakpoint()

function apply() {
  emit('apply')
  emit('update:modelValue', false)
}
</script>

<template>
  <AppSheet
    :model-value="modelValue"
    :title="activeCount ? `${title} · ${activeCount}` : title"
    :compact-size="compactSize"
    :force-bottom="!isPadLandscape"
    modal-class="oc-mobile-filter-sheet"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="mobile-filter-sheet__content">
      <p class="mobile-filter-sheet__tip">选择条件后点「查看结果」，不会自动提交。</p>
      <slot />
    </div>

    <template #footer>
      <el-button class="mobile-filter-sheet__reset" @click="emit('reset')">
        {{ resetText }}
      </el-button>
      <el-button type="primary" class="mobile-filter-sheet__apply" @click="apply">
        {{ applyText }}
      </el-button>
    </template>
  </AppSheet>
</template>

<style scoped>
.mobile-filter-sheet__content {
  display: grid;
  gap: 12px;
  padding-bottom: 6px;
}

.mobile-filter-sheet__tip {
  margin: 0 0 2px;
  padding: 10px 12px;
  border: 1px dashed rgba(161, 98, 7, 0.28);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(255, 249, 235, 0.95), rgba(255, 253, 248, 0.8));
  color: #8b5406;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.45;
}

.mobile-filter-sheet__content :deep(.el-form-item) {
  margin-bottom: 0;
  padding: 12px 14px;
  border: 1px solid rgba(181, 145, 83, 0.22);
  border-radius: 14px;
  background: linear-gradient(180deg, #fffefb, #faf6ee);
}

.mobile-filter-sheet__content :deep(.el-form-item__label) {
  margin-bottom: 8px !important;
  padding: 0 !important;
  color: #6b4f25;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.mobile-filter-sheet__content :deep(.el-input),
.mobile-filter-sheet__content :deep(.el-select),
.mobile-filter-sheet__content :deep(.el-date-editor) {
  width: 100%;
}

.mobile-filter-sheet__content :deep(.el-input__wrapper),
.mobile-filter-sheet__content :deep(.el-select__wrapper) {
  min-height: 44px;
  border-radius: 12px;
}

.mobile-filter-sheet__reset,
.mobile-filter-sheet__apply {
  min-height: 48px !important;
  margin: 0 !important;
  border-radius: 14px !important;
  font-size: 15px !important;
  font-weight: 720 !important;
}

.mobile-filter-sheet__reset {
  flex: 0 0 108px;
}

.mobile-filter-sheet__apply {
  flex: 1 1 auto;
}
</style>
