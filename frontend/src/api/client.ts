import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 15000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'error' in body && body.error) {
      const message = body.error.message || '请求失败'
      return Promise.reject(new Error(message))
    }
    return response
  },
  (error) => {
    const message =
      error.response?.data?.error?.message ||
      error.response?.data?.detail ||
      error.message ||
      '网络错误'
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
    }
    ElMessage.error(typeof message === 'string' ? message : '请求失败')
    return Promise.reject(error)
  },
)

export default client
