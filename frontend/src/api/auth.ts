import client from './client'

export interface UserInfo {
  id: number
  username: string
  display_name: string
  role: string
  is_active: boolean
  /** Effective permissions = role defaults ∪ extra grants */
  permissions?: string[]
  /** Extra grants beyond role (admin empty) */
  extra_permissions?: string[]
}

export interface LoginResult {
  access_token: string
  token_type: string
  user: UserInfo
}

export async function loginApi(username: string, password: string): Promise<LoginResult> {
  const res = await client.post('/auth/login', { username, password })
  return res.data.data
}

export async function meApi(): Promise<UserInfo> {
  const res = await client.get('/auth/me')
  return res.data.data
}

export async function changePasswordApi(current_password: string, new_password: string) {
  const res = await client.post('/auth/change-password', { current_password, new_password })
  return res.data.data
}
