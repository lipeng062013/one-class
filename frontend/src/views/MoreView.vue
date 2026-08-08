<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'
import { useAppMenus, type MenuItem } from '../composables/useAppMenus'

const route = useRoute()
const router = useRouter()
const { auth, menus, displayName, roleText, brandTag } = useAppMenus()
const changePwdVisible = ref(false)

/**
 * 更多页分区：
 * - 不展示「工作台」（底栏 / 侧轨已有）
 * - 单入口合并；分组保留标题
 */
const sections = computed(() => {
  const list: { key: string; title?: string; icon?: string; items: MenuItem[] }[] = []
  for (const entry of menus.value) {
    if (entry.type === 'group') {
      const children = entry.children.filter((c) => c.index !== '/')
      if (!children.length) continue
      list.push({
        key: entry.index,
        title: entry.title,
        icon: entry.icon,
        items: children,
      })
      continue
    }
    if (entry.index === '/') continue
    const last = list[list.length - 1]
    if (last && !last.title) {
      last.items.push(entry)
    } else {
      list.push({ key: `solo-${entry.index}`, items: [entry] })
    }
  }
  return list
})

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path === path || route.path.startsWith(`${path}/`)
}

function go(path: string) {
  if (!path.startsWith('/')) return
  if (route.path !== path) void router.push(path)
}

function logout() {
  auth.logout()
  void router.replace('/login')
}
</script>

<template>
  <div class="more-page">
    <section class="more-account">
      <div class="more-account__profile">
        <div class="more-account__avatar" aria-hidden="true">{{ displayName.slice(0, 1) }}</div>
        <div class="more-account__meta">
          <div class="more-account__name">{{ displayName }}</div>
          <div class="more-account__sub">
            <span v-if="roleText" class="more-account__chip">{{ roleText }}</span>
            <span class="more-account__chip is-muted">{{ brandTag }}</span>
          </div>
        </div>
      </div>

      <div class="more-account__actions">
        <button type="button" class="more-account__btn" @click="changePwdVisible = true">
          <span class="more-account__btn-icon"><el-icon><Lock /></el-icon></span>
          <span class="more-account__btn-text">修改密码</span>
        </button>
        <button type="button" class="more-account__btn is-danger" @click="logout">
          <span class="more-account__btn-icon"><el-icon><SwitchButton /></el-icon></span>
          <span class="more-account__btn-text">退出登录</span>
        </button>
      </div>
    </section>

    <div class="more-sections">
      <section v-for="sec in sections" :key="sec.key" class="more-list">
        <div v-if="sec.title" class="more-list__head">
          <el-icon v-if="sec.icon"><component :is="sec.icon" /></el-icon>
          <span>{{ sec.title }}</span>
        </div>
        <button
          v-for="item in sec.items"
          :key="item.index"
          type="button"
          class="more-row"
          :class="{ 'is-active': isActive(item.index) }"
          @click="go(item.index)"
        >
          <span class="more-row__icon"><el-icon><component :is="item.icon" /></el-icon></span>
          <span class="more-row__label">{{ item.title }}</span>
          <el-icon class="more-row__arrow"><ArrowRight /></el-icon>
        </button>
      </section>
    </div>

    <ChangePasswordDialog v-model="changePwdVisible" />
  </div>
</template>

<style scoped>
.more-page {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 8px;
  overflow-x: hidden;
}

/* ── 账号卡 ── */
.more-account {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  border: 1px solid rgba(181, 145, 83, 0.26);
  border-radius: 16px;
  overflow: hidden;
  background:
    linear-gradient(155deg, rgba(255, 255, 255, 0.78), transparent 48%),
    linear-gradient(165deg, #fffdf8 0%, #faf3e6 100%);
  box-shadow: 0 10px 24px rgba(88, 60, 24, 0.07);
}

.more-account__profile {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  padding: 14px 14px 12px;
}

.more-account__avatar {
  flex: 0 0 48px;
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #c98718, #a16207 55%, #86530a);
  color: #fffdf8;
  font-size: 20px;
  font-weight: 760;
  box-shadow: 0 6px 14px rgba(161, 98, 7, 0.28);
}

.more-account__meta {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
}

.more-account__name {
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 17px;
  font-weight: 740;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-account__sub {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.more-account__chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  border: 1px solid rgba(161, 98, 7, 0.22);
  background: rgba(255, 253, 248, 0.9);
  color: #8b5406;
  font-size: 11px;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-account__chip.is-muted {
  border-color: rgba(181, 145, 83, 0.18);
  background: rgba(245, 240, 230, 0.7);
  color: #78716c;
  font-weight: 600;
}

.more-account__actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-top: 1px solid rgba(181, 145, 83, 0.18);
  background: rgba(255, 253, 248, 0.72);
}

.more-account__btn {
  appearance: none;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  min-height: 46px;
  margin: 0;
  padding: 0 8px;
  border: 0;
  background: transparent;
  color: #6b4f25;
  font: inherit;
  font-size: 13px;
  font-weight: 680;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.more-account__btn + .more-account__btn {
  border-left: 1px solid rgba(181, 145, 83, 0.18);
}

.more-account__btn:active {
  background: rgba(250, 243, 230, 0.9);
}

.more-account__btn-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #f5f0e6;
  color: #a16207;
  font-size: 14px;
}

.more-account__btn-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-account__btn.is-danger .more-account__btn-icon {
  background: #fdf0ef;
  color: #b91c1c;
}

.more-account__btn.is-danger .more-account__btn-text {
  color: #b91c1c;
}

/* ── 分区列表 ── */
.more-sections {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.more-list {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  border: 1px solid rgba(181, 145, 83, 0.18);
  border-radius: 14px;
  background: #fffdf8;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(88, 60, 24, 0.04);
}

.more-list__head {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  padding: 9px 14px 6px;
  color: #8b5406;
  font-size: 12px;
  font-weight: 720;
  background: linear-gradient(180deg, rgba(250, 246, 238, 0.95), rgba(250, 246, 238, 0.55));
  border-bottom: 1px solid rgba(181, 145, 83, 0.12);
}

.more-list__head span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-list__head .el-icon {
  flex-shrink: 0;
  font-size: 14px;
}

.more-row {
  appearance: none;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  max-width: 100%;
  min-width: 0;
  min-height: 48px;
  margin: 0;
  padding: 0 12px;
  border: 0;
  border-bottom: 1px solid rgba(232, 224, 208, 0.85);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.more-row:last-child {
  border-bottom: 0;
}

.more-row:active {
  background: #faf6ee;
}

.more-row__icon {
  flex: 0 0 32px;
  width: 32px;
  height: 32px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #f5f0e6;
  color: #a16207;
  font-size: 16px;
}

.more-row__label {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.more-row__arrow {
  flex-shrink: 0;
  color: #c4b5a0;
  font-size: 14px;
}

.more-row.is-active {
  background: #faf3e6;
}

.more-row.is-active .more-row__icon {
  background: linear-gradient(145deg, #c07a12, #a16207);
  color: #fffdf8;
}

.more-row.is-active .more-row__label {
  color: #8b5406;
  font-weight: 720;
}

/* 手机 */
@media (max-width: 767px) {
  .more-page {
    gap: 10px;
  }

  .more-account__btn {
    font-size: 12px;
    gap: 6px;
  }
}

/* Pad 竖屏：账号通栏 + 分组双列，避免一列过长撑破 */
@media (min-width: 768px) and (max-width: 1199px) {
  .more-page {
    width: 100%;
    max-width: min(920px, 100%);
    margin: 0 auto;
    gap: 14px;
    padding-inline: 0;
  }

  .more-account {
    border-radius: 18px;
  }

  .more-account__profile {
    padding: 16px 18px 14px;
  }

  .more-account__avatar {
    width: 52px;
    height: 52px;
    flex-basis: 52px;
    border-radius: 15px;
    font-size: 22px;
  }

  .more-account__name {
    font-size: 18px;
  }

  .more-account__btn {
    min-height: 48px;
    font-size: 14px;
  }

  .more-sections {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    align-items: start;
  }

  .more-list {
    border-radius: 16px;
    /* 防止 grid 子项被内容撑破横向溢出 */
    max-width: 100%;
  }

  .more-row {
    min-height: 50px;
  }
}

/* Pad 横屏（有左侧轨）：内容区更宽，仍双列且禁溢出 */
@media (min-width: 900px) and (max-width: 1199px) {
  .more-page {
    max-width: min(980px, 100%);
  }
}

/* 桌面若打开 /more：居中限宽，双列更疏朗 */
@media (min-width: 1200px) {
  .more-page {
    max-width: 880px;
    margin: 0 auto;
    gap: 14px;
  }

  .more-sections {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    align-items: start;
  }
}
</style>
