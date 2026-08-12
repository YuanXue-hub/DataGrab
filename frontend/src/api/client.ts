import axios from 'axios'
import { ElMessage } from 'element-plus'

// axios 实例：统一 baseURL、超时、错误处理
const client = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截
client.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error),
)

// 响应拦截：FastAPI 抛 HTTPException 时返回 detail 字段
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error?.response?.data?.detail || error.message
    ElMessage.error(`请求失败: ${detail}`)
    return Promise.reject(error)
  },
)

export default client
