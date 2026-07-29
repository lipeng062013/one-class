# 米金轻奢 UI 美化 Implementation Plan

> **For agentic workers:** Inline execution approved by user (后续选择全部推荐；改完上传).

**Goal:** Apply confirmed **I · 米金轻奢** theme across shell, login, and dashboard without changing business logic.

**Architecture:** CSS design tokens in `style.css` override Element Plus primary; layout shells and key pages consume tokens for sidebar/login/dashboard polish.

**Tech Stack:** Vue 3, Element Plus, Vite, CSS variables

---

### Task 1: Global theme tokens

**Files:**
- Modify: `frontend/src/style.css`
- Modify: `docs/superpowers/specs/2026-07-29-mijin-luxury-ui-polish-design.md` (already written)

- [ ] **Step 1:** Set `--oc-*` tokens and Element Plus `--el-color-primary*` palette to amber/gold
- [ ] **Step 2:** Page background `#faf8f3`, text `#44403c`, card helpers

### Task 2: Shell + login + dashboard

**Files:**
- Modify: `frontend/src/layouts/AppLayout.vue`
- Modify: `frontend/src/layouts/MobileLayout.vue`
- Modify: `frontend/src/views/LoginView.vue`
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1:** Dark stone sidebar, gold brand/active menu
- [ ] **Step 2:** Login warm rice gradient + refined card
- [ ] **Step 3:** Dashboard cards use theme borders/hover
- [ ] **Step 4:** Mobile shell matching warm neutrals

### Task 3: Verify and ship

- [ ] **Step 1:** `npm run build` in `frontend`
- [ ] **Step 2:** Commit design docs + frontend changes
- [ ] **Step 3:** `git push` to origin
