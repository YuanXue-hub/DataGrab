import client from './client'
import type { DataResponse } from '@/types'

export interface DataQueryParams {
  source_name?: string
  limit?: number
  offset?: number
}

// 查询已爬取数据
export function queryData(params: DataQueryParams = {}) {
  return client.get<unknown, DataResponse>('/data', { params })
}
