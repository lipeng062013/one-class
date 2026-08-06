<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createCourseApi, getCourseApi, updateCourseApi } from '../../api/academic'
import { usePageBack } from '../../composables/usePageBack'

const route = useRoute()
const router = useRouter()
const { goBack } = usePageBack('/academic/courses')
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
  <div class="course-form-page oc-page-shell" v-loading="loading">
    <div class="page-toolbar">
      <el-page-header :content="isEdit ? '编辑课程' : '新增课程'" @back="goBack" />
    </div>

    <el-card class="form-card" shadow="never">
      <div class="section-title">基本信息</div>
      <el-form label-width="110px" class="main-form">
        <el-form-item label="课程名称" required>
          <el-input v-model="form.name" placeholder="请输入" style="max-width: 360px" />
        </el-form-item>
        <el-form-item label="课程类型">
          <el-radio-group v-model="form.type" :disabled="isEdit">
            <el-radio value="一对多">一对多</el-radio>
            <el-radio value="一对一">一对一</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade" clearable placeholder="请选择" style="width: 200px">
            <el-option
              v-for="g in ['一年级','二年级','三年级','四年级','五年级','六年级','预初','初一','初二','初三','高一','高二','高三']"
              :key="g"
              :label="g"
              :value="g"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="科目">
          <el-select v-model="form.subject" clearable placeholder="请选择" style="width: 200px">
            <el-option
              v-for="s in ['语文','数学','英语','物理','化学','生物','历史','地理','政治']"
              :key="s"
              :label="s"
              :value="s"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="form.term" clearable placeholder="请选择" style="width: 200px">
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
              @click="form.color = c"
            />
          </div>
        </el-form-item>
        <el-form-item v-if="isEdit" label="启用状态">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>

      <div class="section-title">收费方式</div>
      <div class="billing-block">
        <div class="billing-head">
          <span>按课时收费</span>
          <el-switch v-model="form.hour_billing" />
        </div>
        <template v-if="form.hour_billing">
          <el-form label-width="110px" class="billing-form">
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
          <el-table :data="[{}]" border size="small" class="price-table">
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

      <div class="section-title">其他信息</div>
      <el-form label-width="110px">
        <el-form-item label="备注">
          <el-input
            v-model="form.remark"
            type="textarea"
            placeholder="请输入（选填）"
            style="max-width: 480px"
          />
        </el-form-item>
      </el-form>

      <div class="form-actions">
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
        <el-button @click="goBack">取消</el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.course-form-page {
  width: 100%;
}

.page-toolbar {
  margin-bottom: 8px;
}

.form-card {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
}

.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  margin: 8px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.ml {
  margin-left: 10px;
}

.color-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.color-dot {
  width: 22px;
  height: 22px;
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
  border-radius: 10px;
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
}

.hint {
  color: var(--oc-muted, #78716c);
  font-size: 13px;
  margin-right: 8px;
}

.tip {
  margin: 8px 0 12px;
}

.price-table {
  margin-bottom: 4px;
}

.form-actions {
  margin-top: 24px;
  display: flex;
  gap: 10px;
}
</style>
