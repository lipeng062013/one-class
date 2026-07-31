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
const doneCount = computed(() => done.value.length)
const totalCount = computed(() => rows.value.length)

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
  <section class="todo-panel" v-loading="loading">
    <div class="todo-head">
      <div class="todo-head-left">
        <span class="todo-icon" aria-hidden="true">
          <el-icon :size="18"><List /></el-icon>
        </span>
        <div>
          <h2 class="todo-title">今日待办</h2>
          <p class="todo-sub">把今天要跟进的事记下来</p>
        </div>
      </div>
      <div class="todo-stats">
        <el-tag size="small" effect="plain" class="tag-pending">
          {{ pending.length }} 未完成
        </el-tag>
        <el-tag v-if="doneCount" size="small" type="success" effect="plain">
          {{ doneCount }} 已完成
        </el-tag>
      </div>
    </div>

    <div class="add-box">
      <div class="add-row">
        <el-input
          v-model="newTitle"
          placeholder="添加待办事项…"
          clearable
          @keyup.enter="addTodo"
        />
        <el-button type="primary" :loading="adding" @click="addTodo">添加</el-button>
      </div>
      <el-input
        v-model="newContent"
        class="add-note"
        type="textarea"
        :rows="1"
        placeholder="备注（可选）"
      />
    </div>

    <el-empty
      v-if="!rows.length && !loading"
      description="暂无待办，自己添加一条吧"
      :image-size="64"
    />

    <ul v-else class="todo-list">
      <li v-for="item in pending" :key="item.id" class="todo-item">
        <el-checkbox :model-value="false" @change="toggleDone(item)" />
        <div class="body">
          <div class="title">{{ item.title }}</div>
          <div v-if="item.content" class="note">{{ item.content }}</div>
        </div>
        <el-button class="del-btn" link type="danger" @click="remove(item)">删除</el-button>
      </li>
      <li v-for="item in done" :key="'d-' + item.id" class="todo-item done">
        <el-checkbox :model-value="true" @change="toggleDone(item)" />
        <div class="body">
          <div class="title">{{ item.title }}</div>
          <div v-if="item.content" class="note">{{ item.content }}</div>
        </div>
        <el-tag size="small" type="success" effect="plain" class="done-tag">已完成</el-tag>
        <el-button class="del-btn" link type="danger" @click="remove(item)">删除</el-button>
      </li>
    </ul>

    <p v-if="totalCount > 0" class="todo-foot">共 {{ totalCount }} 条 · 勾选即可完成</p>
  </section>
</template>

<style scoped>
.todo-panel {
  border: 1px solid var(--oc-border, #e8e0d0);
  border-radius: 14px;
  background: var(--oc-card, #fffdf8);
  padding: 16px;
  box-shadow: 0 4px 14px rgba(41, 37, 36, 0.03);
}

.todo-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.todo-head-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.todo-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(145deg, #f5e6c8, #f2e8d6);
  color: var(--oc-primary, #a16207);
  flex-shrink: 0;
}

.todo-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--oc-ink, #44403c);
  letter-spacing: 0.02em;
}

.todo-sub {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
}

.todo-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.tag-pending {
  border-color: var(--oc-border, #e8e0d0);
  color: var(--oc-primary, #a16207);
  background: #f2e8d6;
}

.add-box {
  padding: 12px;
  border-radius: 12px;
  background: #faf6ee;
  border: 1px dashed var(--oc-border, #e8e0d0);
  margin-bottom: 12px;
}

.add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

/* 覆盖全局 textarea 固定 100px，待办备注保持紧凑 */
.add-note :deep(.el-textarea__inner) {
  height: 40px !important;
  min-height: 40px !important;
  max-height: 80px !important;
  background: #fffdf8;
}

.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 11px 12px;
  border-radius: 11px;
  border: 1px solid transparent;
  background: #fff;
  transition: background 0.15s, border-color 0.15s;
}

.todo-item:hover {
  background: #faf6ee;
  border-color: var(--oc-border, #e8e0d0);
}

.todo-item.done {
  opacity: 0.78;
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
  font-weight: 550;
  color: var(--oc-ink, #44403c);
  line-height: 1.4;
}

.note {
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  margin-top: 3px;
  line-height: 1.4;
}

.done-tag {
  flex-shrink: 0;
  margin-top: 2px;
}

.del-btn {
  flex-shrink: 0;
  opacity: 0.55;
}

.todo-item:hover .del-btn {
  opacity: 1;
}

.todo-foot {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--oc-muted, #78716c);
  text-align: center;
}

@media (max-width: 767px) {
  .todo-panel {
    padding: 14px 12px;
  }

  .add-row {
    flex-direction: column;
  }

  .add-row .el-button {
    width: 100%;
  }
}
</style>
