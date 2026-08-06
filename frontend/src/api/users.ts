import client from './client'
import type { UserInfo } from './auth'
import { asPageResult, type PageParams, type PageResult } from './paging'

export interface UserRow extends UserInfo {
  created_at?: string | null
  permissions?: string[]
  extra_permissions?: string[]
}

export interface UserListParams extends PageParams {
  role?: string
  is_active?: boolean
  username?: string
  display_name?: string
}

export interface PermissionItem {
  code: string
  label: string
  description: string
}

export interface PermissionGroup {
  group: string
  group_label: string
  permissions: PermissionItem[]
}

export interface UserPermissionsDetail {
  role: string
  role_defaults: string[]
  extra_permissions: string[]
  effective_permissions: string[]
}

export async function listUsersApi(params: UserListParams = {}): Promise<PageResult<UserRow>> {
  const res = await client.get('/users', {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
      role: params.role,
      is_active: params.is_active,
      username: params.username,
      display_name: params.display_name,
    },
  })
  return asPageResult<UserRow>(res.data.data, params.page ?? 1, params.page_size ?? 20)
}

export async function createUserApi(payload: {
  username: string
  display_name: string
  role: string
  password: string
  extra_permissions?: string[]
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
  payload: {
    display_name?: string
    role?: string
    is_active?: boolean
    extra_permissions?: string[]
  },
): Promise<UserRow> {
  const res = await client.patch(`/users/${userId}`, payload)
  return res.data.data
}

export async function deleteUserApi(userId: number): Promise<void> {
  await client.delete(`/users/${userId}`)
}

export async function listPermissionCatalogApi(): Promise<PermissionGroup[]> {
  const res = await client.get('/users/permissions/catalog')
  return res.data.data.groups
}

export async function getUserPermissionsApi(userId: number): Promise<UserPermissionsDetail> {
  const res = await client.get(`/users/${userId}/permissions`)
  return res.data.data
}

export async function putUserPermissionsApi(
  userId: number,
  extra_permissions: string[],
): Promise<UserPermissionsDetail> {
  const res = await client.put(`/users/${userId}/permissions`, { extra_permissions })
  return res.data.data
}
