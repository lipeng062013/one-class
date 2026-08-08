<script setup lang="ts">
/**
 * WAP/Pad 列表底部加载状态（替代页码条）。
 * 使用 setter 回调：父级把根节点通过 callback 写入 sentinelRef
 */
import { computed, type ComponentPublicInstance } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 是否还有下一页 */
    hasMore?: boolean
    /** 追加加载中 */
    loading?: boolean
    /** 已加载条数 */
    loaded?: number
    /** 服务端总数 */
    total?: number
    /** 加载失败 */
    error?: boolean
    /** 无数据时是否隐藏；默认 true */
    hideWhenEmpty?: boolean
    /** 是否可点击「加载更多」 */
    clickable?: boolean
    /** 触底观察：父级把 HTMLElement 写入 sentinelRef */
    setSentinel?: (el: HTMLElement | null) => void
  }>(),
  {
    hasMore: false,
    loading: false,
    loaded: 0,
    total: 0,
    error: false,
    hideWhenEmpty: true,
    clickable: true,
  },
)

const emit = defineEmits<{
  more: []
  retry: []
}>()

const show = computed(() => {
  if (props.error) return true
  if (props.hideWhenEmpty && props.total <= 0 && !props.loading) return false
  return props.total > 0 || props.loading || props.hasMore
})

const statusText = computed(() => {
  if (props.error) return '加载失败，点击重试'
  if (props.loading) return '加载中…'
  if (props.hasMore) {
    if (props.total > 0) return `上拉加载更多 · 已显示 ${props.loaded} / ${props.total}`
    return '上拉加载更多'
  }
  if (props.total > 0) return `已加载全部 ${props.total} 条`
  return ''
})

const interactive = computed(
  () => props.error || (props.clickable && props.hasMore && !props.loading),
)

function bindRoot(el: Element | ComponentPublicInstance | null) {
  const node = el && el instanceof HTMLElement ? el : null
  props.setSentinel?.(node)
}

function onActivate() {
  if (props.error) {
    emit('retry')
    return
  }
  if (props.hasMore && !props.loading) emit('more')
}
</script>

<template>
  <div
    v-if="show"
    :ref="bindRoot"
    class="list-load-status"
    :class="{
      'is-loading': loading,
      'is-error': error,
      'is-done': !hasMore && !error && !loading,
      'is-interactive': interactive,
    }"
    role="status"
    :aria-busy="loading"
    :tabindex="interactive ? 0 : undefined"
    @click="interactive ? onActivate() : undefined"
    @keydown.enter.prevent="interactive ? onActivate() : undefined"
  >
    <span class="list-load-status__text">{{ statusText }}</span>
  </div>
</template>

<style scoped>
.list-load-status {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  margin: 6px 0 10px;
  padding: 12px 14px calc(12px + env(safe-area-inset-bottom, 0px));
  border: 1px dashed rgba(181, 145, 83, 0.28);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255, 253, 248, 0.72), rgba(250, 246, 238, 0.5));
  color: var(--oc-muted, #78716c);
  font-size: 12px;
  line-height: 1.45;
  text-align: center;
  user-select: none;
}

.list-load-status.is-interactive {
  cursor: pointer;
  color: var(--oc-primary, #a16207);
  border-style: solid;
  border-color: rgba(161, 98, 7, 0.28);
  font-weight: 620;
  box-shadow: 0 4px 12px rgba(161, 98, 7, 0.08);
}

.list-load-status.is-loading {
  color: var(--oc-muted, #78716c);
  cursor: default;
}

.list-load-status.is-error {
  color: var(--el-color-danger, #dc2626);
  border-color: rgba(194, 65, 59, 0.3);
  cursor: pointer;
}

.list-load-status.is-done {
  color: var(--oc-muted, #78716c);
  border-style: dashed;
  opacity: 0.92;
}

.list-load-status__text {
  max-width: 100%;
}
</style>
