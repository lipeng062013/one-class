<script setup lang="ts">
import AppSheet from './AppSheet.vue'

withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    activeCount?: number
    applyText?: string
    resetText?: string
  }>(),
  {
    title: '筛选条件',
    activeCount: 0,
    applyText: '查看结果',
    resetText: '重置',
  },
)

const emit = defineEmits<{
  'update:modelValue': [boolean]
  apply: []
  reset: []
}>()

function apply() {
  emit('apply')
  emit('update:modelValue', false)
}
</script>

<template>
  <AppSheet
    :model-value="modelValue"
    :title="activeCount ? `${title} (${activeCount})` : title"
    compact-size="min(78%, 640px)"
    force-bottom
    modal-class="oc-mobile-filter-sheet"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="mobile-filter-sheet__content">
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
  gap: 16px;
}

.mobile-filter-sheet__reset,
.mobile-filter-sheet__apply {
  min-height: 44px;
}

.mobile-filter-sheet__reset {
  flex: 0 0 96px;
}

.mobile-filter-sheet__apply {
  flex: 1 1 auto;
}
</style>
