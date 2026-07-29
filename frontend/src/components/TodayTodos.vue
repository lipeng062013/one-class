<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createTodoApi,
  deleteTodoApi,
  listTodosApi,
  patchTodoApi,
  type TodoItem,
} from '../api/todos'

const loading = ref(false)
const rows = ref<TodoItem[]>([])
const newTitle = ref('')
const newContent = ref('')
const adding = ref(false)

const pending = computed(() => rows.value.filter((t) => !t.is_done))
const done = computed(() => rows.value.filter((t) => t.is_done))

async function load() {
  loading.value = true
  try {
    rows.value = await listTodosApi()
  } finally {
    loading.value = false
  }
}

async function addTodo() {
  const title = newTitle.value.trim()
  if (!title) {
    ElMessage.warning('请填写待办内容')
    return
  }
  adding.value = true
  try {
    await createTodoApi({ title, content: newContent.value.trim() })
    newTitle.value = ''
    newContent.value = ''
    ElMessage.success('已添加')
    await load()
  } catch {
    /* interceptor */
  } finally {
    adding.value = false
  }
}

async function toggleDone(item: TodoItem) {
  await patchTodoApi(item.id, { is_done: !item.is_done })
  await load()
}

async function remove(item: TodoItem) {
  try {
    await ElMessageBox.confirm(`删除待办「${item.title}」？`, '确认', { type: 'warning' })
    await deleteTodoApi(item.id)
    ElMessage.success('已删除')
    await load()
  } catch {
    /* cancel */
  }
}

onMounted(load)
</script>

<template>
  <el-card class="todo-card" v-loading="loading">
    <template #header>
      <div class="head">
        <span>今日待办</span>
        <el-tag size="small" effect="plain">{{ pending.length }} 未完成</el-tag>
      </div>
    </template>

    <div class="add-row">
      <el-input v-model="newTitle" placeholder="添加待办事项…" clearable @keyup.enter="addTodo" />
      <el-button type="primary" :loading="adding" @click="addTodo">添加</el-button>
    </div>
    <el-input
      v-model="newContent"
      class="add-note"
      type="textarea"
      :rows="1"
      placeholder="备注（可选）"
    />

    <el-empty v-if="!rows.length" description="暂无待办，自己添加一条吧" :image-size="64" />

    <ul class="todo-list">
      <li v-for="item in pending" :key="item.id" class="todo-item">
        <el-checkbox :model-value="false" @change="toggleDone(item)" />
        <div class="body">
          <div class="title">{{ item.title }}</div>
          <div v-if="item.content" class="note">{{ item.content }}</div>
        </div>
        <el-button link type="danger" @click="remove(item)">删除</el-button>
      </li>
      <li v-for="item in done" :key="'d-' + item.id" class="todo-item done">
        <el-checkbox :model-value="true" @change="toggleDone(item)" />
        <div class="body">
          <div class="title">{{ item.title }}</div>
          <div v-if="item.content" class="note">{{ item.content }}</div>
        </div>
        <el-tag size="small" type="success" effect="plain">已完成</el-tag>
        <el-button link type="danger" @click="remove(item)">删除</el-button>
      </li>
    </ul>
  </el-card>
</template>

<style scoped>
.todo-card {
  border-color: var(--oc-border, #e8e0d0);
}

.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.add-note {
  margin-bottom: 12px;
}

.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--oc-border, #e8e0d0);
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-item.done .title {
  text-decoration: line-through;
  color: var(--oc-muted, #78716c);
}

.body {
  flex: 1;
  min-width: 0;
}

.title {
  font-size: 14px;
  color: var(--oc-ink, #44403c);
}

.note {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-top: 2px;
}
</style>
