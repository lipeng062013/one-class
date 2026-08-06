<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  addLeadCollaborator,
  createLeadFollow,
  getLead,
  joinLeadCollaborator,
  listLeadActivities,
  listLeadAssignees,
  patchLead,
  removeLeadCollaborator,
  type Lead,
  type LeadActivity,
  type LeadAssignee,
  type LeadContactMethod,
  type LeadSource,
  type LeadStatus,
} from '../../api/leads'
import { useAuthStore } from '../../stores/auth'
import { useBreakpoint } from '../../composables/useBreakpoint'
import { useListDetailStateCleanup } from '../../composables/useListScrollRestore'
import { usePageBack } from '../../composables/usePageBack'
import {
  isValidOptionalPhone,
  PHONE_INPUT_MESSAGE,
  sanitizePhoneInput,
} from '../../utils/phone'

const route = useRoute()
const { goBack } = usePageBack('/leads')
useListDetailStateCleanup('leads', 'oc-lead-list-state')
const auth = useAuthStore()
const { isMobile } = useBreakpoint()
const descCols = computed(() => (isMobile.value ? 1 : 2))

const leadId = computed(() => Number(route.params.id))
const loading = ref(false)
const actLoading = ref(false)
const lead = ref<Lead | null>(null)
const activities = ref<LeadActivity[]>([])
const activityFilter = ref('all')
const assignees = ref<LeadAssignee[]>([])

const sourceLabels: Record<string, string> = {
  referral: '老带新',
  dianping: '大众点评',
  wechat: '微信',
  walkin: '到店',
  other: '其他',
}
const statusLabels: Record<string, string> = {
  new: '新建',
  contacted: '已联系',
  visited: '已到访',
  enrolled: '已报名',
  lost: '已流失',
}
const contactLabels: Record<string, string> = {
  phone: '电话',
  wechat: '微信',
  visit: '到访/面谈',
  sms: '短信',
  other: '其他',
}
const statusOptions: LeadStatus[] = ['new', 'contacted', 'visited', 'enrolled', 'lost']

function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  switch (status) {
    case 'enrolled':
      return 'success'
    case 'visited':
      return 'warning'
    case 'contacted':
      return 'primary'
    case 'lost':
      return 'info'
    case 'new':
    default:
      return 'danger'
  }
}

function kindTagType(kind: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  switch (kind) {
    case 'follow':
      return 'primary'
    case 'owner':
      return 'warning'
    case 'collaborator':
      return 'success'
    case 'update':
      return 'info'
    case 'create':
      return 'danger'
    default:
      return 'info'
  }
}

function formatTime(v?: string | null) {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString()
  } catch {
    return v
  }
}

function toIso(value: Date | string | null | undefined): string | null {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return d.toISOString()
}

const followerCount = computed(() => lead.value?.followers?.length ?? 0)
const multiFollow = computed(() => followerCount.value >= 2)

const isOnTeam = computed(() => {
  const me = auth.user?.id
  if (!me || !lead.value) return false
  if (lead.value.owner_id === me) return true
  return (lead.value.followers || []).some((f) => f.user_id === me)
})

const filteredActivities = computed(() => {
  const list = activities.value
  if (activityFilter.value === 'all') return list
  return list.filter((a) => a.kind === activityFilter.value)
})

const collabCandidates = computed(() => {
  const onTeam = new Set((lead.value?.followers || []).map((f) => f.user_id))
  if (lead.value?.owner_id) onTeam.add(lead.value.owner_id)
  return assignees.value.filter((a) => !onTeam.has(a.id))
})

// ── 写跟进 ──
const followVisible = ref(false)
const followSaving = ref(false)
const followFormRef = ref<FormInstance>()
const followForm = reactive({
  content: '',
  contact_method: 'phone' as LeadContactMethod | string,
  status: '' as string,
  next_follow_at: null as Date | null,
  join_as_collaborator: true,
})
const followRules: FormRules = {
  content: [{ required: true, message: '请填写跟进内容', trigger: 'blur' }],
}

// ── 编辑资料 ──
const editVisible = ref(false)
const editSaving = ref(false)
const editFormRef = ref<FormInstance>()
const editForm = reactive({
  student_or_parent_name: '',
  phone: '',
  source: 'other' as LeadSource | string,
  referrer_name: '',
  channel_note: '',
  need: '',
  status: 'new' as LeadStatus | string,
  next_follow_at: null as Date | null,
  owner_id: undefined as number | undefined,
  notes: '',
})

function validateEditedPhone(
  _rule: unknown,
  value: unknown,
  callback: (error?: Error) => void,
) {
  const phone = String(value ?? '')
  const originalPhone = lead.value?.phone || ''
  if (phone === originalPhone && !isValidOptionalPhone(phone)) {
    callback()
    return
  }
  callback(isValidOptionalPhone(phone) ? undefined : new Error(PHONE_INPUT_MESSAGE))
}

const editRules: FormRules = {
  student_or_parent_name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  source: [{ required: true, message: '请选择来源', trigger: 'change' }],
  phone: [{ required: true, validator: validateEditedPhone, trigger: 'blur' }],
}

// ── 添加协作 ──
const collabVisible = ref(false)
const collabSaving = ref(false)
const collabUserId = ref<number | undefined>()
const collabNote = ref('')

async function loadAssignees() {
  assignees.value = await listLeadAssignees().catch(() => [])
}

async function loadLead() {
  if (!leadId.value) return
  loading.value = true
  try {
    lead.value = await getLead(leadId.value)
  } catch {
    lead.value = null
    ElMessage.error('线索不存在或无权查看')
  } finally {
    loading.value = false
  }
}

async function loadActivities() {
  if (!leadId.value) return
  actLoading.value = true
  try {
    const res = await listLeadActivities(leadId.value, { limit: 100 })
    activities.value = res.items || []
  } catch {
    activities.value = []
  } finally {
    actLoading.value = false
  }
}

async function reloadAll() {
  await Promise.all([loadLead(), loadActivities()])
}

function openFollow() {
  followForm.content = ''
  followForm.contact_method = 'phone'
  followForm.status = lead.value?.status || ''
  followForm.next_follow_at = lead.value?.next_follow_at
    ? new Date(lead.value.next_follow_at)
    : null
  followForm.join_as_collaborator = true
  followVisible.value = true
}

async function submitFollow() {
  const ok = await followFormRef.value?.validate().catch(() => false)
  if (!ok || !lead.value) return
  followSaving.value = true
  try {
    const res = await createLeadFollow(lead.value.id, {
      content: followForm.content.trim(),
      contact_method: followForm.contact_method || '',
      status: followForm.status || null,
      next_follow_at: toIso(followForm.next_follow_at),
      join_as_collaborator: followForm.join_as_collaborator,
    })
    lead.value = res.lead
    ElMessage.success('跟进已记录')
    followVisible.value = false
    await loadActivities()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    followSaving.value = false
  }
}

function openEdit() {
  if (!lead.value) return
  const L = lead.value
  editForm.student_or_parent_name = L.student_or_parent_name
  editForm.phone = L.phone || ''
  editForm.source = L.source
  editForm.referrer_name = L.referrer_name || ''
  editForm.channel_note = L.channel_note || ''
  editForm.need = L.need || ''
  editForm.status = L.status
  editForm.next_follow_at = L.next_follow_at ? new Date(L.next_follow_at) : null
  editForm.owner_id = L.owner_id ?? undefined
  editForm.notes = L.notes || ''
  editVisible.value = true
}

async function submitEdit() {
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok || !lead.value) return
  editSaving.value = true
  try {
    lead.value = await patchLead(lead.value.id, {
      student_or_parent_name: editForm.student_or_parent_name.trim(),
      ...(editForm.phone === (lead.value.phone || '')
        ? {}
        : { phone: editForm.phone.trim() || null }),
      source: editForm.source,
      referrer_name: editForm.referrer_name.trim() || null,
      channel_note: editForm.channel_note,
      need: editForm.need,
      status: editForm.status,
      next_follow_at: toIso(editForm.next_follow_at),
      owner_id: editForm.owner_id ?? null,
      notes: editForm.notes,
    })
    ElMessage.success('线索已更新')
    editVisible.value = false
    await loadActivities()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    editSaving.value = false
  }
}

async function onJoinTeam() {
  if (!lead.value) return
  try {
    lead.value = await joinLeadCollaborator(lead.value.id)
    ElMessage.success('已加入协作跟进')
    await loadActivities()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加入失败')
  }
}

function openAddCollab() {
  collabUserId.value = undefined
  collabNote.value = ''
  collabVisible.value = true
}

async function submitAddCollab() {
  if (!lead.value || !collabUserId.value) {
    ElMessage.warning('请选择协作人')
    return
  }
  collabSaving.value = true
  try {
    lead.value = await addLeadCollaborator(lead.value.id, {
      user_id: collabUserId.value,
      note: collabNote.value.trim(),
    })
    ElMessage.success('已添加协作人')
    collabVisible.value = false
    await loadActivities()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '添加失败')
  } finally {
    collabSaving.value = false
  }
}

async function onRemoveCollab(userId: number, name: string) {
  if (!lead.value) return
  const isMe = userId === auth.user?.id
  try {
    await ElMessageBox.confirm(
      isMe
        ? '确定退出本线索协作？退出后仍可在动态中查看历史记录。'
        : `确定将「${name}」移出协作名单？`,
      '协作调整',
      { type: 'warning' },
    )
    lead.value = await removeLeadCollaborator(lead.value.id, userId)
    ElMessage.success(isMe ? '已退出协作' : '已移出协作')
    await loadActivities()
  } catch {
    /* cancel */
  }
}

function canRemove(f: { user_id: number; is_owner: boolean }) {
  if (f.is_owner) return false
  const me = auth.user?.id
  if (!me) return false
  if (f.user_id === me) return true
  if (auth.user?.role === 'admin') return true
  if (lead.value?.owner_id === me) return true
  return false
}

watch(leadId, () => {
  void reloadAll()
})

onMounted(async () => {
  await loadAssignees()
  await reloadAll()
  if (route.query.edit === '1') {
    // 等 lead 加载后打开编辑
    const stop = watch(
      lead,
      (v) => {
        if (v) {
          openEdit()
          stop()
        }
      },
      { immediate: true },
    )
  }
})
</script>

<template>
  <div v-loading="loading" class="lead-detail-page oc-page-shell">
    <div class="page-toolbar">
      <el-page-header @back="goBack">
        <template #content>
          <span>线索详情{{ lead ? ` · ${lead.student_or_parent_name}` : '' }}</span>
        </template>
      </el-page-header>
      <div class="toolbar-actions">
        <el-button v-if="lead && !isOnTeam" type="warning" plain @click="onJoinTeam">
          加入协作
        </el-button>
        <el-button @click="openEdit">编辑资料</el-button>
        <el-button type="primary" class="tb-btn tb-btn--primary" @click="openFollow">
          写跟进
        </el-button>
      </div>
    </div>

    <template v-if="lead">
      <!-- 多人协作提示 -->
      <el-alert
        v-if="multiFollow"
        class="collab-alert"
        type="warning"
        show-icon
        :closable="false"
        title="多人正在跟进此线索"
        :description="`当前共 ${followerCount} 人登记跟进。联系家长前请先查看下方最新动态，统一口径，避免重复打扰导致印象分下降。`"
      />

      <div class="detail-grid">
        <!-- 左侧：档案 + 动态 -->
        <div class="detail-main">
          <el-card class="profile-card" shadow="never">
            <div class="profile-head">
              <div class="profile-avatar">
                {{ (lead.student_or_parent_name || '?').slice(0, 1) }}
              </div>
              <div class="profile-who">
                <div class="profile-name">
                  {{ lead.student_or_parent_name }}
                  <el-tag
                    :type="statusTagType(lead.status)"
                    size="small"
                    effect="plain"
                    round
                    class="status-tag"
                  >
                    {{ statusLabels[lead.status] || lead.status }}
                  </el-tag>
                </div>
                <div class="profile-sub">
                  <span>{{ sourceLabels[lead.source] || lead.source }}</span>
                  <span v-if="lead.phone"> · {{ lead.phone }}</span>
                  <span v-if="lead.owner_name"> · 主责 {{ lead.owner_name }}</span>
                </div>
              </div>
            </div>

            <el-descriptions :column="descCols" border class="profile-desc">
              <el-descriptions-item label="姓名">
                {{ lead.student_or_parent_name }}
              </el-descriptions-item>
              <el-descriptions-item label="电话">{{ lead.phone || '—' }}</el-descriptions-item>
              <el-descriptions-item label="来源">
                {{ sourceLabels[lead.source] || lead.source }}
              </el-descriptions-item>
              <el-descriptions-item label="介绍人">
                {{ lead.referrer_name || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="需求" :span="2">
                {{ lead.need || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="主跟进人">
                {{ lead.owner_name || '未指定' }}
              </el-descriptions-item>
              <el-descriptions-item label="下次跟进">
                {{ formatTime(lead.next_follow_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="最近联系" :span="2">
                <template v-if="lead.last_contact_at">
                  {{ formatTime(lead.last_contact_at) }}
                  <span v-if="lead.last_contact_by_name"> · {{ lead.last_contact_by_name }}</span>
                  <span v-if="lead.last_contact_method">
                    · {{ contactLabels[lead.last_contact_method] || lead.last_contact_method }}
                  </span>
                </template>
                <template v-else>—</template>
              </el-descriptions-item>
              <el-descriptions-item label="渠道备注" :span="2">
                {{ lead.channel_note || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="内部备注" :span="2">
                {{ lead.notes || '—' }}
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatTime(lead.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="更新时间">
                {{ formatTime(lead.updated_at) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card class="activity-card" shadow="never" v-loading="actLoading">
            <div class="section-row">
              <h3 class="section-title">跟进动态</h3>
              <el-button type="primary" link @click="openFollow">写跟进</el-button>
            </div>
            <p class="section-hint">
              记录每一次联系与资料变更，团队共享同一时间线，减少撞单与口径不一致。
            </p>

            <div class="activity-filters">
              <el-radio-group v-model="activityFilter" size="small">
                <el-radio-button value="all">全部</el-radio-button>
                <el-radio-button value="follow">跟进</el-radio-button>
                <el-radio-button value="update">变更</el-radio-button>
                <el-radio-button value="owner">主责</el-radio-button>
                <el-radio-button value="collaborator">协作</el-radio-button>
              </el-radio-group>
            </div>

            <el-empty v-if="!filteredActivities.length" description="暂无动态，点击「写跟进」开始记录" />
            <el-timeline v-else class="activity-timeline">
              <el-timeline-item
                v-for="e in filteredActivities"
                :key="e.id"
                :timestamp="formatTime(e.created_at)"
                placement="top"
              >
                <el-card shadow="never" class="act-card">
                  <div class="act-head">
                    <el-tag size="small" effect="plain" :type="kindTagType(e.kind)">
                      {{ e.kind_label }}
                    </el-tag>
                    <span class="act-title">{{ e.title }}</span>
                    <el-tag
                      v-if="e.actor_name"
                      size="small"
                      effect="plain"
                      type="info"
                      class="act-actor"
                    >
                      {{ e.actor_name }}
                    </el-tag>
                    <el-tag
                      v-if="e.contact_method_label"
                      size="small"
                      effect="plain"
                      type="warning"
                    >
                      {{ e.contact_method_label }}
                    </el-tag>
                  </div>
                  <div v-if="e.content" class="act-content">{{ e.content }}</div>
                </el-card>
              </el-timeline-item>
            </el-timeline>
            <div v-if="filteredActivities.length" class="tab-foot">
              共 {{ filteredActivities.length }} 条动态
            </div>
          </el-card>
        </div>

        <!-- 右侧：协作人 -->
        <aside class="detail-side">
          <el-card class="team-card" shadow="never">
            <div class="section-row">
              <h3 class="section-title">跟进团队</h3>
              <el-button type="primary" link @click="openAddCollab">添加</el-button>
            </div>
            <p class="section-hint">
              多人跟同一资源时请在此登记，并在动态中同步沟通结果。
            </p>

            <div v-if="!lead.followers?.length" class="team-empty">暂无跟进人，建议指定主责</div>
            <ul v-else class="team-list">
              <li v-for="f in lead.followers" :key="`${f.user_id}-${f.role}`" class="team-item">
                <div class="team-avatar">{{ (f.name || '?').slice(0, 1) }}</div>
                <div class="team-meta">
                  <div class="team-name">
                    {{ f.name }}
                    <el-tag
                      size="small"
                      :type="f.is_owner ? 'warning' : 'info'"
                      effect="plain"
                      round
                    >
                      {{ f.role_label }}
                    </el-tag>
                  </div>
                  <div class="team-sub">
                    <span v-if="f.joined_at">加入 {{ formatTime(f.joined_at) }}</span>
                    <span v-if="f.note"> · {{ f.note }}</span>
                  </div>
                </div>
                <el-button
                  v-if="canRemove(f)"
                  link
                  type="danger"
                  size="small"
                  @click="onRemoveCollab(f.user_id, f.name)"
                >
                  {{ f.user_id === auth.user?.id ? '退出' : '移出' }}
                </el-button>
              </li>
            </ul>

            <el-button
              v-if="!isOnTeam"
              class="join-btn"
              type="warning"
              plain
              @click="onJoinTeam"
            >
              我要加入协作
            </el-button>
          </el-card>

          <el-card class="tips-card" shadow="never">
            <h3 class="section-title">协作小贴士</h3>
            <ul class="tips-list">
              <li>联系前先看「最近联系」与最新跟进，避免重复致电。</li>
              <li>谈妥意向、改约时间务必写进动态，方便同事接续。</li>
              <li>主责变更会单独记日志，业绩与回访口径更清晰。</li>
            </ul>
          </el-card>
        </aside>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="线索不存在" />

    <!-- 写跟进 -->
    <el-dialog
      v-model="followVisible"
      title="写跟进"
      width="90%"
      style="max-width: 520px"
      destroy-on-close
    >
      <el-alert
        v-if="multiFollow"
        type="warning"
        :closable="false"
        show-icon
        title="多人协作中：请写清沟通结果与下次计划，避免同事不知情再次联系家长。"
        class="dialog-tip"
      />
      <el-form ref="followFormRef" :model="followForm" :rules="followRules" label-position="top">
        <el-form-item label="跟进内容" prop="content">
          <el-input
            v-model="followForm.content"
            type="textarea"
            :rows="4"
            placeholder="例如：电话沟通，家长关心师资与价格，约本周六到访试听"
          />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-radio-group v-model="followForm.contact_method">
            <el-radio-button value="phone">电话</el-radio-button>
            <el-radio-button value="wechat">微信</el-radio-button>
            <el-radio-button value="visit">到访</el-radio-button>
            <el-radio-button value="sms">短信</el-radio-button>
            <el-radio-button value="other">其他</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="更新状态">
          <el-select v-model="followForm.status" clearable placeholder="可选，同步状态" style="width: 100%">
            <el-option v-for="s in statusOptions" :key="s" :label="statusLabels[s]" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="下次跟进">
          <el-date-picker
            v-model="followForm.next_follow_at"
            type="datetime"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item v-if="!isOnTeam">
          <el-checkbox v-model="followForm.join_as_collaborator">
            写跟进后自动加入协作名单
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="followVisible = false">取消</el-button>
        <el-button type="primary" :loading="followSaving" @click="submitFollow">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑资料 -->
    <el-dialog
      v-model="editVisible"
      title="编辑线索"
      width="90%"
      style="max-width: 560px"
      destroy-on-close
    >
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-position="top">
        <el-form-item label="学生/家长姓名" prop="student_or_parent_name">
          <el-input v-model="editForm.student_or_parent_name" />
        </el-form-item>
        <el-form-item label="电话" prop="phone">
          <el-input
            v-model="editForm.phone"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="11"
            placeholder="请输入11位手机号"
            @input="editForm.phone = sanitizePhoneInput(editForm.phone)"
          />
        </el-form-item>
        <div class="form-row-2">
          <el-form-item label="来源" prop="source">
            <el-select v-model="editForm.source" style="width: 100%">
              <el-option
                v-for="(label, key) in sourceLabels"
                :key="key"
                :label="label"
                :value="key"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="editForm.status" style="width: 100%">
              <el-option
                v-for="s in statusOptions"
                :key="s"
                :label="statusLabels[s]"
                :value="s"
              />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="主跟进人">
          <el-select
            v-model="editForm.owner_id"
            clearable
            filterable
            placeholder="选择主责"
            style="width: 100%"
          >
            <el-option
              v-for="a in assignees"
              :key="a.id"
              :label="`${a.name}（${a.role_label}）`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="介绍人">
          <el-input v-model="editForm.referrer_name" />
        </el-form-item>
        <el-form-item label="需求">
          <el-input v-model="editForm.need" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="下次跟进">
          <el-date-picker
            v-model="editForm.next_follow_at"
            type="datetime"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="渠道备注">
          <el-input v-model="editForm.channel_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="内部备注">
          <el-input v-model="editForm.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 添加协作人 -->
    <el-dialog
      v-model="collabVisible"
      title="添加协作人"
      width="90%"
      style="max-width: 420px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="协作人" required>
          <el-select
            v-model="collabUserId"
            filterable
            placeholder="选择运营/负责人"
            style="width: 100%"
          >
            <el-option
              v-for="a in collabCandidates"
              :key="a.id"
              :label="`${a.name}（${a.role_label}）`"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="collabNote" placeholder="如：协助周末到访接待" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="collabVisible = false">取消</el-button>
        <el-button type="primary" :loading="collabSaving" @click="submitAddCollab">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.lead-detail-page {
  min-width: 0;
}

.page-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.collab-alert {
  margin-top: 12px;
  border-radius: 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  margin-top: 14px;
}

@media (min-width: 1100px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1fr) 300px;
    align-items: start;
  }
}

.detail-main,
.detail-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.profile-card,
.activity-card,
.team-card,
.tips-card {
  border-radius: 12px;
  border-color: var(--oc-border, #e8e0d0);
  background: var(--oc-card, #fffdf8);
  margin: 0;
}

.profile-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.profile-avatar {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
  flex-shrink: 0;
}

.profile-name {
  font-size: 18px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.profile-sub {
  margin-top: 4px;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.profile-desc {
  margin-top: 4px;
}

.section-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 650;
  color: var(--oc-ink, #44403c);
}

.section-hint {
  margin: 6px 0 12px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  line-height: 1.5;
}

.activity-filters {
  margin-bottom: 14px;
}

.activity-timeline {
  padding-left: 4px;
}

.act-card {
  border-radius: 10px;
  border: 1px solid var(--oc-border, #e8e0d0);
  background: #fffdfb;
}

.act-card :deep(.el-card__body) {
  padding: 12px 14px;
}

.act-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.act-title {
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  font-size: 14px;
}

.act-content {
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.55;
  color: var(--oc-ink, #44403c);
}

.tab-foot {
  margin-top: 8px;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.team-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.team-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  background: #faf6ee;
  border: 1px solid var(--oc-border, #e8e0d0);
}

.team-avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #e8d5b0, #c9a066);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.team-meta {
  flex: 1;
  min-width: 0;
}

.team-name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--oc-ink, #44403c);
  font-size: 13px;
}

.team-sub {
  margin-top: 2px;
  font-size: 11px;
  color: var(--oc-muted, #78716c);
}

.team-empty {
  padding: 16px 8px;
  text-align: center;
  font-size: 13px;
  color: var(--oc-muted, #78716c);
}

.join-btn {
  width: 100%;
  margin-top: 12px;
}

.tips-list {
  margin: 8px 0 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--oc-muted, #78716c);
}

.dialog-tip {
  margin-bottom: 12px;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}

@media (max-width: 520px) {
  .form-row-2 {
    grid-template-columns: 1fr;
  }

  .toolbar-actions {
    width: 100%;
  }

  .toolbar-actions .el-button {
    flex: 1;
  }
}
</style>
