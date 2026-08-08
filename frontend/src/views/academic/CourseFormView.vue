<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createCourseApi, getCourseApi, updateCourseApi } from '../../api/academic'
import { usePageBack } from '../../composables/usePageBack'
import { useBreakpoint } from '../../composables/useBreakpoint'
import MobileActionBar from '../../components/MobileActionBar.vue'

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/academic/courses')
const { isApp } = useBreakpoint()
const saving = ref(false)
const loading = ref(false)

const editId = computed(() => {
  const raw = route.params.id
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
})
const isEdit = computed(() => editId.value != null)

const form = reactive({
  name: '',
  type: '一对多' as '一对多' | '一对一',
  grade: '',
  subject: '',
  term: '',
  color: '#a16207',
  hour_billing: true,
  leave_rule: 'no_deduct' as 'deduct' | 'no_deduct' | 'partial',
  absent_rule: 'no_deduct' as 'deduct' | 'no_deduct',
  price_name: '单价',
  price_hours: '1',
  price_total: '',
  month_billing: false,
  day_billing: false,
  remark: '',
  enabled: true,
})

const colors = ['#a16207', '#e6a23c', '#67c23a', '#13c2c2', '#f56c6c', '#b37feb', '#409eff']

function calcUnit(): number | null {
  const total = Number(form.price_total)
  const hours = Number(form.price_hours) || 1
  if (!total || !hours) return null
  return total / hours
}

function calcUnitLabel() {
  const u = calcUnit()
  return u == null ? '自动计算' : u.toFixed(2)
}

async function loadCourse() {
  if (editId.value == null) return
  loading.value = true
  try {
    const c = await getCourseApi(editId.value)
    form.name = c.name
    form.type = c.course_type === 'one_to_one' ? '一对一' : '一对多'
    form.grade = c.grade || ''
    form.subject = c.subject || ''
    form.term = c.term || ''
    form.color = c.color || '#a16207'
    form.leave_rule = 'no_deduct'
    form.absent_rule = 'no_deduct'
    form.price_hours = '1'
    form.price_total = String(c.unit_price || '')
    form.remark = c.remark || ''
    form.enabled = c.enabled
    form.hour_billing = true
  } catch {
    ElMessage.error('课程不存在或加载失败')
    void router.replace('/academic/courses')
  } finally {
    loading.value = false
  }
}

async function onSave() {
  if (!form.name.trim()) {
    ElMessage.warning('请输入课程名称')
    return
  }
  if (!form.hour_billing) {
    ElMessage.warning('当前仅支持按课时收费，请开启「按课时收费」')
    return
  }
  const unit = calcUnit()
  if (unit == null || unit < 0) {
    ElMessage.warning('请填写定价标准总价（数量为课时，将自动算单价）')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      course_type: (form.type === '一对一' ? 'one_to_one' : 'group') as 'group' | 'one_to_one',
      grade: form.grade,
      subject: form.subject,
      term: form.term,
      billing_mode: 'hour',
      unit_price: unit,
      leave_rule: 'no_deduct',
      absent_rule: 'no_deduct',
      color: form.color,
      enabled: form.enabled,
      remark: form.remark.trim(),
    }
    if (isEdit.value && editId.value != null) {
      await updateCourseApi(editId.value, payload)
      ElMessage.success('课程已更新')
    } else {
      await createCourseApi(payload)
      ElMessage.success('课程已创建')
    }
    void router.push('/academic/courses')
  } catch {
    /* interceptor */
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadCourse()
})
</script>

<template>
  <div class="course-form-page oc-page-shell" :class="{ 'is-app-form': isApp }" v-loading="loading">
    <div class="page-toolbar">
      <el-page-header :content="isEdit ? '编辑课程' : '新增课程'" @back="goBack" />
    </div>

    <div class="form-stack">
      <section class="form-section">
        <div class="section-title">基本信息</div>
        <el-form
          :label-position="isApp ? 'top' : 'right'"
          :label-width="isApp ? undefined : '110px'"
          class="main-form"
        >
          <el-form-item label="课程名称" required>
            <el-input v-model="form.name" placeholder="请输入" :style="isApp ? 'width: 100%' : 'max-width: 360px'" />
          </el-form-item>
          <el-form-item label="课程类型">
            <el-radio-group v-model="form.type" :disabled="isEdit" class="type-radios">
              <el-radio value="一对多">一对多</el-radio>
              <el-radio value="一对一">一对一</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="年级">
            <el-select
              v-model="form.grade"
              clearable
              placeholder="请选择"
              :style="isApp ? 'width: 100%' : 'width: 200px'"
            >
              <el-option
                v-for="g in ['一年级','二年级','三年级','四年级','五年级','六年级','预初','初一','初二','初三','高一','高二','高三']"
                :key="g"
                :label="g"
                :value="g"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="科目">
            <el-select
              v-model="form.subject"
              clearable
              placeholder="请选择"
              :style="isApp ? 'width: 100%' : 'width: 200px'"
            >
              <el-option
                v-for="s in ['语文','数学','英语','物理','化学','生物','历史','地理','政治']"
                :key="s"
                :label="s"
                :value="s"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="学期">
            <el-select
              v-model="form.term"
              clearable
              placeholder="请选择"
              :style="isApp ? 'width: 100%' : 'width: 200px'"
            >
              <el-option label="2026 暑假" value="2026暑假" />
              <el-option label="2026 秋季" value="2026秋季" />
              <el-option label="2026 寒假" value="2026寒假" />
              <el-option label="2027 春季" value="2027春季" />
            </el-select>
          </el-form-item>
          <el-form-item label="课表颜色">
            <div class="color-row">
              <button
                v-for="c in colors"
                :key="c"
                type="button"
                class="color-dot"
                :class="{ 'is-active': form.color === c }"
                :style="{ background: c }"
                :aria-label="`选择课表颜色 ${c}`"
                :title="`选择课表颜色 ${c}`"
                @click="form.color = c"
              />
            </div>
          </el-form-item>
          <el-form-item v-if="isEdit" label="启用状态">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </el-form>
      </section>

      <section class="form-section">
        <div class="section-title">收费方式</div>
        <div class="billing-block">
          <div class="billing-head">
            <span>按课时收费</span>
            <el-switch v-model="form.hour_billing" />
          </div>
          <template v-if="form.hour_billing">
            <el-form
              :label-position="isApp ? 'top' : 'right'"
              :label-width="isApp ? undefined : '110px'"
              class="billing-form"
            >
              <el-form-item label="扣课时规则">
                <el-alert
                  type="info"
                  :closable="false"
                  show-icon
                  title="点名固定规则：出勤/迟到扣课；请假/缺勤不扣课时。"
                  class="tip"
                />
              </el-form-item>
            </el-form>
            <el-alert
              type="warning"
              :closable="false"
              show-icon
              title="建议在定价标准中保留数量为 1 的单价价目，便于报名灵活选购课时。"
              class="tip"
            />
            <div v-if="isApp" class="mobile-price-editor">
              <label class="mobile-price-field">
                <span>名称</span>
                <el-input v-model="form.price_name" placeholder="单价" />
              </label>
              <label class="mobile-price-field">
                <span>数量（课时）</span>
                <el-input v-model="form.price_hours" inputmode="decimal" />
              </label>
              <label class="mobile-price-field">
                <span>总价（元）</span>
                <el-input v-model="form.price_total" inputmode="decimal" placeholder="请输入" />
              </label>
              <div class="mobile-price-field mobile-price-unit">
                <span>单价（元/课时）</span>
                <strong>{{ calcUnitLabel() }}</strong>
              </div>
            </div>
            <el-table v-else :data="[{}]" border size="small" class="price-table">
              <el-table-column label="名称" min-width="120">
                <template #default>
                  <el-input v-model="form.price_name" placeholder="单价" />
                </template>
              </el-table-column>
              <el-table-column label="数量(课时)" width="120">
                <template #default>
                  <el-input v-model="form.price_hours" />
                </template>
              </el-table-column>
              <el-table-column label="总价(元)" width="140">
                <template #default>
                  <el-input v-model="form.price_total" placeholder="请输入" />
                </template>
              </el-table-column>
              <el-table-column label="单价(元/课时)" width="130">
                <template #default>
                  <span class="pc-muted">{{ calcUnitLabel() }}</span>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </div>

        <div class="billing-block dim">
          <div class="billing-head">
            <span>按月收费</span>
            <el-switch v-model="form.month_billing" disabled />
          </div>
          <p class="dim-hint">暂未开放，后续版本支持</p>
        </div>
        <div class="billing-block dim">
          <div class="billing-head">
            <span>按天收费</span>
            <el-switch v-model="form.day_billing" disabled />
          </div>
        </div>
      </section>

      <section class="form-section">
        <div class="section-title">其他信息</div>
        <el-form
          :label-position="isApp ? 'top' : 'right'"
          :label-width="isApp ? undefined : '110px'"
        >
          <el-form-item label="备注">
            <el-input
              v-model="form.remark"
              type="textarea"
              :rows="isApp ? 4 : 3"
              placeholder="请输入（选填）"
              :style="isApp ? 'width: 100%' : 'max-width: 480px'"
            />
          </el-form-item>
        </el-form>
      </section>

      <div v-if="!isApp" class="form-actions">
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
        <el-button @click="goBack">取消</el-button>
      </div>
    </div>

    <MobileActionBar v-if="isApp">
      <el-button @click="goBack">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
    </MobileActionBar>
  </div>
</template>

<style scoped>
.course-form-page {
  width: 100%;
}

.page-toolbar {
  margin-bottom: 8px;
}

.form-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-section {
  border-radius: 14px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  padding: 14px 16px 8px;
  box-shadow: 0 4px 14px rgba(68, 64, 60, 0.04);
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  margin: 0 0 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.color-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}

.color-dot.is-active {
  box-shadow:
    0 0 0 2px #fff,
    0 0 0 4px var(--oc-primary, #a16207);
}

.billing-block {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
  background: #fffdfb;
}

.billing-block.dim {
  background: #faf8f3;
  opacity: 0.9;
}

.dim-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.billing-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  min-height: 36px;
}

.tip {
  margin: 8px 0 12px;
  width: 100%;
}

.price-table {
  margin-bottom: 4px;
}

.pc-muted {
  color: var(--oc-muted, #78716c);
}

.mobile-price-editor {
  display: grid;
  gap: 14px;
  padding: 14px;
  margin-bottom: 4px;
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 12px;
  background: #fff;
}

.mobile-price-field {
  display: grid;
  gap: 7px;
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  font-weight: 600;
}

.mobile-price-unit {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  min-height: 48px;
  padding: 0 14px;
  border-radius: 10px;
  background: #f8f6f1;
}

.mobile-price-unit strong {
  color: var(--oc-primary, #a16207);
  font-size: 17px;
}

.form-actions {
  margin-top: 8px;
  display: flex;
  gap: 10px;
}

.type-radios {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}

.is-app-form .form-section {
  border-radius: 16px;
  padding: 16px 14px 10px;
  background:
    linear-gradient(180deg, rgba(255, 253, 248, 0.98), rgba(250, 246, 238, 0.92));
  box-shadow: 0 8px 20px rgba(88, 60, 24, 0.06);
}

.is-app-form .section-title {
  font-size: 16px;
  margin-bottom: 12px;
}

.is-app-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.is-app-form :deep(.el-form-item__label) {
  font-weight: 650;
  color: #57534e;
  padding-bottom: 4px !important;
  line-height: 1.3;
}

.is-app-form :deep(.el-input__wrapper),
.is-app-form :deep(.el-select__wrapper),
.is-app-form :deep(.el-textarea__inner) {
  min-height: 44px;
  border-radius: 12px;
}

.is-app-form :deep(.el-textarea__inner) {
  min-height: 96px;
  padding-top: 10px;
}

.is-app-form .color-dot {
  width: 32px;
  height: 32px;
}

.is-app-form .billing-block {
  border-radius: 14px;
  padding: 14px;
}

@media (max-width: 1199px) {
  .form-stack {
    gap: 12px;
  }

  .form-section {
    border-radius: 16px;
  }
}
</style>
