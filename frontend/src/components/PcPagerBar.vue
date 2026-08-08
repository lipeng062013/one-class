<script setup lang="ts">
/**
 * PC 列表底部分页条。
 * WAP/Pad 不渲染：移动端统一用无限追加 + ListLoadStatus，禁止页码条。
 */
import { computed } from 'vue'
import { PAGE_SIZES } from '../composables/useServerPager'
import { useBreakpoint } from '../composables/useBreakpoint'

const page = defineModel<number>('page', { required: true })
const pageSize = defineModel<number>('pageSize', { required: true })
const { isApp } = useBreakpoint()

const props = withDefaults(
  defineProps<{
    total: number
    /** 无数据时是否隐藏；默认 true */
    hideWhenEmpty?: boolean
    pageSizes?: number[]
  }>(),
  {
    hideWhenEmpty: true,
    pageSizes: () => [...PAGE_SIZES],
  },
)

const emit = defineEmits<{
  change: []
  'size-change': []
}>()

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / pageSize.value) || 1))

/** 仅桌面显示；WAP/Pad 由 ListLoadStatus 承接 */
const show = computed(() => !isApp.value && (!props.hideWhenEmpty || props.total > 0))

function goFirstPage() {
  if (page.value <= 1) return
  page.value = 1
  emit('change')
}

function goLastPage() {
  if (page.value >= totalPages.value) return
  page.value = totalPages.value
  emit('change')
}

function onPageChange() {
  emit('change')
}

function onSizeChange() {
  page.value = 1
  emit('size-change')
  emit('change')
}
</script>

<template>
  <div v-if="show" class="pager-bar pc-pager">
    <el-button size="small" plain :disabled="page <= 1" @click="goFirstPage">首页</el-button>
    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      :page-sizes="pageSizes"
      :total="total"
      :pager-count="5"
      background
      layout="total, sizes, prev, pager, next, jumper"
      @current-change="onPageChange"
      @size-change="onSizeChange"
    />
    <el-button size="small" plain :disabled="page >= totalPages" @click="goLastPage">末页</el-button>
  </div>
</template>
