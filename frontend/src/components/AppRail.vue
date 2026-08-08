<script setup lang="ts">
import type { AppNavItem } from './AppTabBar.vue'

const props = withDefaults(
  defineProps<{
    items: AppNavItem[]
    active?: string
    moreTitle?: string
    moreIcon?: string
    moreActive?: boolean
  }>(),
  {
    active: '/',
    moreTitle: '更多',
    moreIcon: 'Grid',
    moreActive: false,
  },
)

const emit = defineEmits<{
  select: [index: string]
  more: []
}>()

function isActive(item: AppNavItem) {
  if (props.moreActive) return false
  if (item.index === '/') return props.active === '/'
  return props.active === item.index || props.active.startsWith(`${item.index}/`)
}
</script>

<template>
  <aside class="app-rail" aria-label="Pad 主导航">
    <div class="app-rail__brand">
      <img src="/brand-mark.png" alt="嘉壹启航" width="34" height="34" />
    </div>
    <div class="app-rail__items">
      <button
        v-for="item in items"
        :key="item.index"
        type="button"
        class="app-rail__item"
        :class="{ 'is-active': isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
        :title="item.title"
        @click="emit('select', item.index)"
      >
        <el-icon :size="21"><component :is="item.icon" /></el-icon>
        <span>{{ item.title }}</span>
      </button>
    </div>
    <button
      type="button"
      class="app-rail__item app-rail__more"
      :class="{ 'is-active': moreActive }"
      :title="moreTitle"
      :aria-current="moreActive ? 'page' : undefined"
      @click="emit('more')"
    >
      <el-icon :size="21"><component :is="moreIcon" /></el-icon>
      <span>{{ moreTitle }}</span>
    </button>
  </aside>
</template>

<style scoped>
.app-rail {
  display: flex;
  flex: 0 0 76px;
  width: 76px;
  min-height: 0;
  flex-direction: column;
  align-items: center;
  border-right: 1px solid rgba(181, 145, 83, 0.3);
  background:
    linear-gradient(180deg, rgba(255, 253, 249, 0.98) 0%, rgba(250, 246, 238, 0.96) 100%);
  color: #57534e;
  box-shadow:
    6px 0 22px rgba(88, 60, 24, 0.08),
    1px 0 0 rgba(255, 255, 255, 0.5) inset;
  z-index: 60;
  backdrop-filter: blur(12px);
}

.app-rail__brand {
  display: flex;
  flex: 0 0 64px;
  align-items: center;
  justify-content: center;
  width: 100%;
  border-bottom: 1px solid #e8e0d0;
}

.app-rail__brand img {
  display: block;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(245, 230, 200, 0.24), 0 4px 10px rgba(0, 0, 0, 0.24);
}

.app-rail__items {
  display: flex;
  flex: 1 1 auto;
  width: 100%;
  min-height: 0;
  flex-direction: column;
  gap: 6px;
  padding: 14px 8px;
  overflow-y: auto;
}

.app-rail__item {
  position: relative;
  display: flex;
  flex: 0 0 58px;
  align-items: center;
  justify-content: center;
  width: 100%;
  flex-direction: column;
  gap: 4px;
  padding: 5px 2px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #78716c;
  font: inherit;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: color 0.16s ease, background 0.16s ease;
}

.app-rail__item span {
  max-width: 100%;
  overflow: hidden;
  font-size: 10px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-rail__item:hover,
.app-rail__item:active {
  background: rgba(161, 98, 7, 0.08);
  color: #8b5406;
}

.app-rail__item.is-active {
  background: linear-gradient(160deg, #f8ecd4, #f0d9a8);
  color: #8b5406;
  box-shadow:
    inset 0 0 0 1px rgba(161, 98, 7, 0.2),
    0 4px 12px rgba(161, 98, 7, 0.12);
  font-weight: 650;
}

.app-rail__item.is-active::before {
  content: '';
  position: absolute;
  left: -8px;
  width: 3px;
  height: 28px;
  border-radius: 0 3px 3px 0;
  background: #a16207;
}

.app-rail__more {
  flex: 0 0 66px;
  border-top: 1px solid #e8e0d0;
  border-radius: 0;
}
</style>
