import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { changePasswordApi, loginApi, meApi, type UserInfo } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isTeacher = computed(() => user.value?.role === 'teacher')
  const isCR = computed(() => user.value?.role === 'cr' || user.value?.role === 'academic_manager')
  const isOperator = computed(() => user.value?.role === 'operator')

  const permissions = computed(() => new Set(user.value?.permissions ?? []))

  function hasPermission(code: string): boolean {
    if (!code) return false
    // Admin always full access even if permissions array missing (old tokens / me)
    if (user.value?.role === 'admin') return true
    return permissions.value.has(code)
  }

  function hasAnyPermission(...codes: string[]): boolean {
    if (user.value?.role === 'admin') return true
    return codes.some((c) => permissions.value.has(c))
  }

  function hasAllPermissions(...codes: string[]): boolean {
    if (user.value?.role === 'admin') return true
    return codes.every((c) => permissions.value.has(c))
  }

  async function login(username: string, password: string) {
    const data = await loginApi(username, password)
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
  }

  async function loadMe() {
    if (!token.value) return
    user.value = await meApi()
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  async function changePassword(current_password: string, new_password: string) {
    await changePasswordApi(current_password, new_password)
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    isTeacher,
    isCR,
    isOperator,
    permissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    login,
    loadMe,
    logout,
    changePassword,
  }
})
