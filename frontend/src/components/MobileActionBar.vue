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
  height: calc(72px + env(safe-area-inset-bottom, 0px) + var(--oc-app-bottom-inset, 0px));
}

.mobile-action-bar {
  position: fixed;
  z-index: 40;
  bottom: var(--oc-app-bottom-inset, 0px);
  left: var(--oc-app-content-left, 0px);
  right: 0;
  margin: 0;
  padding:
    12px max(var(--oc-page-pad-x, 14px), env(safe-area-inset-right, 0px))
    max(12px, env(safe-area-inset-bottom, 0px))
    max(var(--oc-page-pad-x, 14px), env(safe-area-inset-left, 0px));
  border-top: 1px solid rgba(181, 145, 83, 0.32);
  background:
    linear-gradient(180deg, rgba(255, 253, 249, 0.88), rgba(250, 246, 238, 0.98));
  backdrop-filter: blur(18px);
  transition: left 0.22s cubic-bezier(0.4, 0, 0.2, 1);
}

.mobile-action-bar.is-elevated {
  box-shadow:
    0 -16px 36px rgba(88, 60, 24, 0.12),
    0 -1px 0 rgba(255, 255, 255, 0.8) inset;
}

.mobile-action-bar__inner {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  max-width: 920px;
  margin: 0 auto;
  padding: 4px;
  border-radius: 18px;
  background: rgba(255, 253, 248, 0.72);
  border: 1px solid rgba(181, 145, 83, 0.18);
  box-shadow: 0 8px 20px rgba(88, 60, 24, 0.06);
}

.mobile-action-bar__inner :deep(.el-button) {
  flex: 1 1 0;
  min-width: 0;
  min-height: 48px;
  margin: 0;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 700;
}

.mobile-action-bar__inner :deep(.el-button--primary:not(.is-plain)) {
  border-color: #814e06;
  background: linear-gradient(145deg, #c98718, #a16207 50%, #7a4c08);
  box-shadow: 0 8px 18px rgba(161, 98, 7, 0.28);
  color: #fffdf8;
}

.mobile-action-bar__inner :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
