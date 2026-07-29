<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadUserFile } from 'element-plus'
import { createMaterialApi, uploadMaterialFileApi } from '../../api/materials'

const router = useRouter()
const formRef = ref<FormInstance>()
const loading = ref(false)
const fileList = ref<UploadUserFile[]>([])

const form = reactive({
  title: '',
  grade: '',
  subject: '',
  pain_point: '',
  teacher_action: '',
  next_step: '',
  auth_status: 'authorized',
})

const rules: FormRules = {
  title: [{ required: true, message: '请填写场景标题', trigger: 'blur' }],
  auth_status: [{ required: true, message: '请选择授权状态', trigger: 'change' }],
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  loading.value = true
  try {
    const material = await createMaterialApi({ ...form })
    for (const item of fileList.value) {
      const raw = item.raw
      if (raw) {
        await uploadMaterialFileApi(material.id, raw as File)
      }
    }
    ElMessage.success('素材已提交')
    form.title = ''
    form.grade = ''
    form.subject = ''
    form.pain_point = ''
    form.teacher_action = ''
    form.next_step = ''
    form.auth_status = 'authorized'
    fileList.value = []
    await router.push('/m/materials')
  } catch {
    /* interceptor */
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <h2>上传素材</h2>
    <el-card>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="场景标题" prop="title">
          <el-input v-model="form.title" placeholder="例如：课堂进步 / 试听反馈" />
        </el-form-item>
        <el-form-item label="年级">
          <el-input v-model="form.grade" placeholder="如 四年级" />
        </el-form-item>
        <el-form-item label="科目">
          <el-input v-model="form.subject" placeholder="如 数学" />
        </el-form-item>
        <el-form-item label="家长痛点">
          <el-input v-model="form.pain_point" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="老师处理">
          <el-input v-model="form.teacher_action" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="下一步行动">
          <el-input v-model="form.next_step" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="家长授权" prop="auth_status">
          <el-select v-model="form.auth_status" style="width: 100%">
            <el-option label="已授权可发" value="authorized" />
            <el-option label="待确认" value="pending" />
            <el-option label="已脱敏" value="anonymized" />
            <el-option label="不可用" value="denied" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片（可多选）">
          <el-upload
            v-model:file-list="fileList"
            list-type="picture-card"
            :auto-upload="false"
            accept="image/*"
            multiple
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="submit">
          提交素材
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  padding: 16px 16px 80px;
}

h2 {
  margin: 0 0 12px;
  font-size: 1.25rem;
}
</style>
