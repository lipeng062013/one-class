<script setup lang="ts">
export interface AppNavItem {
  index: string
  title: string
  icon: string
}

const props = withDefaults(
  defineProps<{
    items: AppNavItem[]
    active?: string
    moreTitle?: string
    moreIcon?: string
    /** 更多页激活（如 /more） */
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
  <nav class="app-tabbar" aria-label="主导航">
    <button
      v-for="item in items"
      :key="item.index"
      type="button"
      class="app-tabbar__item"
      :class="{ 'is-active': isActive(item) }"
      :aria-current="isActive(item) ? 'page' : undefined"
      @click="emit('select', item.index)"
    >
      <span class="app-tabbar__icon" aria-hidden="true">
        <el-icon :size="22"><component :is="item.icon" /></el-icon>
      </span>
      <span class="app-tabbar__label">{{ item.title }}</span>
    </button>
    <button
      type="button"
      class="app-tabbar__item app-tabbar__more"
      :class="{ 'is-active': moreActive }"
      :aria-current="moreActive ? 'page' : undefined"
      aria-label="打开更多模块"
      @click="emit('more')"
    >
      <span class="app-tabbar__icon" aria-hidden="true">
        <el-icon :size="22"><component :is="moreIcon" /></el-icon>
      </span>
      <span class="app-tabbar__label">{{ moreTitle }}</span>
    </button>
  </nav>
</template>

<style scoped>
.app-tabbar {
  display: flex;
  align-items: stretch;
  justify-content: space-around;
  gap: 2px;
  min-height: 64px;
  padding: 6px 6px calc(6px + env(safe-area-inset-bottom, 0px));
  background:
    linear-gradient(180deg, rgba(255, 253, 249, 0.98) 0%, rgba(250, 246, 238, 0.99) 100%);
  border-top: 1px solid rgba(181, 145, 83, 0.28);
  box-shadow:
    0 -10px 28px rgba(88, 60, 24, 0.1),
    0 -1px 0 rgba(255, 255, 255, 0.8) inset;
  backdrop-filter: blur(16px);
}

.app-tabbar__item {
  position: relative;
  display: flex;
  flex: 1 1 0;
  min-width: 0;
  min-height: 52px;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  margin: 0;
  padding: 6px 4px;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: #8a847c;
  font: inherit;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition:
    color 0.16s ease,
    background 0.16s ease,
    transform 0.16s ease;
}

.app-tabbar__item:active {
  transform: scale(0.97);
}

.app-tabbar__item.is-active {
  color: #8b5406;
  font-weight: 720;
  background: linear-gradient(180deg, rgba(255, 247, 232, 0.95), rgba(245, 230, 200, 0.55));
  box-shadow:
    inset 0 0 0 1px rgba(161, 98, 7, 0.14),
    0 4px 12px rgba(161, 98, 7, 0.08);
}

.app-tabbar__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 10px;
  color: inherit;
  transition: color 0.16s ease, transform 0.16s ease;
}

.app-tabbar__item.is-active .app-tabbar__icon {
  color: #a16207;
  transform: translateY(-0.5px);
}

.app-tabbar__label {
  max-width: 100%;
  overflow: hidden;
  font-size: 11px;
  line-height: 1.15;
  letter-spacing: 0.01em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-tabbar__item.is-active .app-tabbar__label {
  font-weight: 720;
}
</style>
