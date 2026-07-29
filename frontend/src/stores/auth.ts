import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { changePasswordApi, loginApi, meApi, type UserInfo } from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const isTeacher = computed(() => user.value?.role === 'teacher')

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
    login,
    loadMe,
    logout,
    changePassword,
  }
})
