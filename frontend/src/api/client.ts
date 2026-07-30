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
    // Skip envelope checks for binary downloads (Blob)
    if (typeof Blob !== 'undefined' && body instanceof Blob) {
      return response
    }
    if (body && typeof body === 'object' && 'error' in body && body.error) {
      const message = body.error.message || '请求失败'
      return Promise.reject(new Error(message))
    }
    return response
  },
  async (error) => {
    let data = error.response?.data
    // Blob downloads (PDF/images) still get JSON error bodies as Blob — parse them.
    if (typeof Blob !== 'undefined' && data instanceof Blob) {
      try {
        const text = await data.text()
        data = JSON.parse(text)
      } catch {
        /* keep raw blob */
      }
    }
    const raw =
      data?.error?.message ||
      data?.detail ||
      error.message ||
      '网络错误'
    let message = typeof raw === 'string' ? raw : '请求失败'
    // Friendlier Chinese for common AI config failures
    if (/LLM not configured/i.test(message)) {
      message =
        '大模型未配置：请在项目 .env 填写 LLM_BASE_URL、LLM_API_KEY 后重启后端（见 README-ops-platform.md）'
    } else if (/IMAGE_API not configured|Image API unavailable/i.test(message)) {
      message =
        '图片大模型未配置：请在 .env 填写 IMAGE_API_BASE_URL、IMAGE_API_KEY 后重启后端'
    } else if (/status code 503/i.test(message)) {
      message = 'AI 服务不可用（503）。请检查 .env 中的 LLM_/IMAGE_ 配置，或改用「仅模板 / 版式导出」。'
    }
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
    }
    ElMessage.error(message)
    return Promise.reject(new Error(message))
  },
)

export default client
