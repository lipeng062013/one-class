<script setup lang="ts">
import { Filter } from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    activeCount?: number
    total?: number
    label?: string
    summary?: string
  }>(),
  {
    activeCount: 0,
    total: undefined,
    label: '条结果',
    summary: '',
  },
)

const emit = defineEmits<{
  open: []
}>()
</script>

<template>
  <div class="compact-filter-bar" :class="{ 'has-active': activeCount > 0 }">
    <div class="compact-filter-bar__accent" aria-hidden="true" />
    <div class="compact-filter-bar__main">
      <span class="compact-filter-bar__kicker">列表结果</span>
      <span v-if="summary" class="compact-filter-bar__summary">{{ summary }}</span>
      <span v-else-if="total !== undefined" class="compact-filter-bar__summary">
        <strong>{{ total }}</strong>
        <em>{{ label }}</em>
      </span>
      <span v-else class="compact-filter-bar__summary">查看结果</span>
      <span v-if="activeCount" class="compact-filter-bar__hint">已选 {{ activeCount }} 项条件</span>
    </div>
    <button
      type="button"
      class="compact-filter-bar__button"
      :class="{ 'is-active': activeCount > 0 }"
      :aria-label="activeCount ? `筛选，${activeCount} 项条件生效` : '打开筛选'"
      :title="activeCount ? `${activeCount} 项筛选条件生效` : '筛选'"
      @click="emit('open')"
    >
      <el-icon class="compact-filter-bar__icon"><Filter /></el-icon>
      <span class="compact-filter-bar__btn-text">筛选</span>
      <span v-if="activeCount" class="compact-filter-bar__badge">{{ activeCount }}</span>
    </button>
  </div>
</template>

<style scoped>
.compact-filter-bar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 64px;
  margin: 0 0 14px;
  padding: 12px 12px 12px 18px;
  overflow: hidden;
  border: 1px solid rgba(161, 98, 7, 0.28);
  border-radius: 18px;
  background:
    linear-gradient(125deg, #ffffff 0%, #fffdf8 42%, #faf3e6 100%);
  box-shadow:
    0 12px 28px rgba(88, 60, 24, 0.1),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.compact-filter-bar.has-active {
  border-color: rgba(161, 98, 7, 0.45);
  box-shadow:
    0 14px 32px rgba(161, 98, 7, 0.14),
    0 1px 0 rgba(255, 255, 255, 0.9) inset;
}

.compact-filter-bar__accent {
  position: absolute;
  top: 10px;
  bottom: 10px;
  left: 0;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: linear-gradient(180deg, #e8c98a, #a16207 55%, #c9a066);
}

.compact-filter-bar__main {
  display: flex;
  min-width: 0;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 2px;
}

.compact-filter-bar__kicker {
  color: #a16207;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: none;
  line-height: 1.2;
}

.compact-filter-bar__summary {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 4px;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  line-height: 1.25;
  font-weight: 600;
}

.compact-filter-bar__summary strong {
  color: #6b4f25;
  font-size: 22px;
  font-weight: 780;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1;
}

.compact-filter-bar__summary em {
  font-style: normal;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  font-weight: 550;
}

.compact-filter-bar__hint {
  color: #a16207;
  font-size: 11px;
  font-weight: 650;
}

.compact-filter-bar__button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex: 0 0 auto;
  min-width: 96px;
  height: 44px;
  min-height: 44px;
  padding: 0 16px;
  border: 1px solid rgba(161, 98, 7, 0.35);
  border-radius: 14px;
  background: linear-gradient(180deg, #fffefb, #f5e6c8);
  color: #6b4f25;
  box-shadow:
    0 6px 14px rgba(161, 98, 7, 0.14),
    0 1px 0 rgba(255, 255, 255, 0.85) inset;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  transition:
    transform 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}

.compact-filter-bar__button:active {
  transform: translateY(1px) scale(0.98);
}

.compact-filter-bar__button.is-active {
  border-color: #814e06;
  color: #fffdf8;
  background: linear-gradient(145deg, #c98718, #a16207 48%, #7a4c08);
  box-shadow:
    0 10px 20px rgba(161, 98, 7, 0.32),
    0 1px 0 rgba(255, 255, 255, 0.2) inset;
}

.compact-filter-bar__icon {
  font-size: 16px;
}

.compact-filter-bar__btn-text {
  line-height: 1;
}

.compact-filter-bar__badge {
  position: absolute;
  top: -7px;
  right: -7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border: 2px solid #fffdf8;
  border-radius: 10px;
  background: #b45309;
  color: #fff;
  font-size: 11px;
  font-weight: 760;
  line-height: 1;
  box-shadow: 0 4px 10px rgba(180, 83, 9, 0.35);
}

.compact-filter-bar__button.is-active .compact-filter-bar__badge {
  background: #fffdf8;
  color: #a16207;
  border-color: #a16207;
}
</style>
