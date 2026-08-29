import axios from 'axios'
import { ElMessage } from 'element-plus'
import type { ExportFormat } from '@/types'

export interface ExportParams {
  format: ExportFormat
  source_name?: string
  keyword_id?: number
  search?: string
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
  // 调试日志：方便排查真实请求参数
  console.log('[Export] 发起导出请求，参数:', JSON.stringify(params))

  let response
  try {
    response = await axios.get('/api/export', {
      params,
      responseType: 'blob',
      timeout: 120000, // docx 生成较慢，超时延长到 2 分钟
    })
  } catch (err: any) {
    console.error('[Export] 请求异常:', err?.message, 'status:', err?.response?.status)
    // 错误响应也是 blob，需要读取
    if (err.response?.data instanceof Blob) {
      const text = await err.response.data.text()
      console.error('[Export] 错误响应体:', text.slice(0, 500))
      let detail = '导出失败，请稍后重试'
      try {
        const parsed = JSON.parse(text)
        detail = parsed.detail || detail
      } catch {
        // 如果是 404/500 但返回非 JSON（例如 HTML 错误页），取前 80 字
        if (text) detail = text.replace(/<[^>]+>/g, ' ').trim().slice(0, 80) || detail
      }

      // 友好化常见错误提示
      let msg = detail
      if (/no data to export/i.test(detail) || detail.includes('没有数据')) {
        const scopeParts: string[] = []
        if (params.source_name) scopeParts.push(`数据源「${params.source_name}」`)
        if (params.keyword_id) scopeParts.push(`所选关键词`)
        if (params.search) scopeParts.push(`搜索词「${params.search}」`)
        const scope = scopeParts.length ? scopeParts.join('、') : '全部数据'
        msg = `${scope} 下暂无可导出的数据，请先执行爬取任务，或调整筛选条件 / 最大条数。`
        ElMessage.warning(msg)
      } else {
        ElMessage.error(`导出失败: ${msg}`)
      }
    } else if (err.code === 'ECONNABORTED') {
      ElMessage.error('导出超时：DOCX 报告生成较慢，建议减少条数后重试')
    } else {
      ElMessage.error(`导出失败: ${err.message || '网络异常'}`)
    }
    throw err
  }

  // 从 Content-Disposition 提取文件名（优先 RFC 5987 filename*=UTF-8''...）
  const disposition = response.headers['content-disposition'] || ''
  let filename = 'datagrab_export'
  const starMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (starMatch) {
    filename = decodeURIComponent(starMatch[1])
  } else {
    const match = disposition.match(/filename="?([^";]+)"?/i)
    if (match) {
      try {
        filename = decodeURIComponent(match[1])
      } catch {
        filename = match[1]
      }
    }
  }

  // 从自定义 header 读取条数
  const count = parseInt(response.headers['x-export-count'] || '0', 10)
  const format = (response.headers['x-export-format'] || params.format) as ExportFormat

  console.log(`[Export] 成功：${format} ${count} 条 → ${filename}，大小: ${response.data?.size ?? '?'} bytes`)

  return {
    blob: response.data as Blob,
    filename,
    count,
    format,
  }
}
