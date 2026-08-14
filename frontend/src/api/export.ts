import axios from 'axios'
import { ElMessage } from 'element-plus'
import type { ExportFormat } from '@/types'

export interface ExportParams {
  format: ExportFormat
  source_name?: string
  limit?: number
}

export interface ExportResult {
  blob: Blob
  filename: string
  count: number
  format: ExportFormat
}

// 导出已爬取数据 — 浏览器直接下载，三种格式统一返回文件流
export async function exportData(params: ExportParams): Promise<ExportResult> {
  let response
  try {
    response = await axios.get('/api/export', {
      params,
      responseType: 'blob',
    })
  } catch (err: any) {
    // 错误响应也是 blob，需要读取
    if (err.response?.data instanceof Blob) {
      const text = await err.response.data.text()
      try {
        const detail = JSON.parse(text).detail || '导出失败'
        ElMessage.error(`导出失败: ${detail}`)
      } catch {
        ElMessage.error('导出失败')
      }
    } else {
      ElMessage.error(`导出失败: ${err.message}`)
    }
    throw err
  }

  // 从 Content-Disposition 提取文件名
  const disposition = response.headers['content-disposition'] || ''
  let filename = 'datagrab_export'
  const match = disposition.match(/filename="?([^";]+)"?/i)
  if (match) {
    filename = match[1]
  }

  // 从自定义 header 读取条数
  const count = parseInt(response.headers['x-export-count'] || '0', 10)
  const format = (response.headers['x-export-format'] || params.format) as ExportFormat

  return {
    blob: response.data as Blob,
    filename,
    count,
    format,
  }
}
