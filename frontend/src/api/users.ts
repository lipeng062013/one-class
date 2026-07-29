import client from './client'
import type { UserInfo } from './auth'

export interface UserRow extends UserInfo {
  created_at?: string | null
}

export async function listUsersApi(): Promise<UserRow[]> {
  const res = await client.get('/users')
  return res.data.data
}

export async function createUserApi(payload: {
  username: string
  display_name: string
  role: string
  password: string
}): Promise<UserRow> {
  const res = await client.post('/users', payload)
  return res.data.data
}

export async function resetPasswordApi(userId: number, new_password: string) {
  const res = await client.post(`/users/${userId}/reset-password`, { new_password })
  return res.data.data
}

export async function patchUserApi(
  userId: number,
  payload: { display_name?: string; role?: string; is_active?: boolean },
): Promise<UserRow> {
  const res = await client.patch(`/users/${userId}`, payload)
  return res.data.data
}
