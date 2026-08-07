<script setup lang="ts">
withDefaults(
  defineProps<{
    visible?: boolean
    elevated?: boolean
  }>(),
  {
    visible: true,
    elevated: true,
  },
)
</script>

<template>
  <div v-if="visible" class="mobile-action-bar-spacer" aria-hidden="true" />
  <div v-if="visible" class="mobile-action-bar" :class="{ 'is-elevated': elevated }">
    <div class="mobile-action-bar__inner">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.mobile-action-bar-spacer {
  height: calc(64px + env(safe-area-inset-bottom, 0px));
}

.mobile-action-bar {
  position: fixed;
  z-index: 30;
  bottom: 0;
  left: 0;
  right: 0;
  margin: 0;
  padding:
    10px max(var(--oc-page-pad-x, 16px), env(safe-area-inset-right, 0px))
    max(10px, env(safe-area-inset-bottom, 0px))
    max(var(--oc-page-pad-x, 16px), env(safe-area-inset-left, 0px));
  border-top: 1px solid var(--oc-border, #e8e0d0);
  background: color-mix(in srgb, var(--oc-card, #fffdf8) 96%, transparent);
  backdrop-filter: blur(12px);
}

.mobile-action-bar.is-elevated {
  box-shadow: 0 -8px 24px rgba(41, 37, 36, 0.08);
}

.mobile-action-bar__inner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.mobile-action-bar__inner :deep(.el-button) {
  flex: 1 1 0;
  min-width: 0;
  min-height: 44px;
  margin: 0;
}
</style>
