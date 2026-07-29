import client from './client'

export interface TodoItem {
  id: number
  user_id: number
  title: string
  content: string
  is_done: boolean
  created_at?: string | null
  completed_at?: string | null
}

export async function listTodosApi(): Promise<TodoItem[]> {
  const res = await client.get('/todos')
  return res.data.data
}

export async function createTodoApi(payload: { title: string; content?: string }): Promise<TodoItem> {
  const res = await client.post('/todos', payload)
  return res.data.data
}

export async function patchTodoApi(
  id: number,
  payload: { title?: string; content?: string; is_done?: boolean },
): Promise<TodoItem> {
  const res = await client.patch(`/todos/${id}`, payload)
  return res.data.data
}

export async function deleteTodoApi(id: number): Promise<void> {
  await client.delete(`/todos/${id}`)
}
