import client from './client'
import type { ExportFormat, ExportResponse } from '@/types'

export interface ExportParams {
  format: ExportFormat
  source_name?: string
  limit?: number
}

// 导出已爬取数据
export function exportData(params: ExportParams) {
  return client.get<unknown, ExportResponse>('/export', { params })
}
