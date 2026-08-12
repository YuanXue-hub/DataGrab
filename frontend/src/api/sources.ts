import client from './client'
import type {
  SourceInfo,
  SourceCreatePayload,
  SourceUpdatePayload,
  SourceCreateResponse,
  ConnectionTestResult,
} from '@/types'

// 列出全部数据源
export function listSources() {
  return client.get<unknown, SourceInfo[]>('/sources')
}

// 获取单个数据源
export function getSource(name: string) {
  return client.get<unknown, SourceInfo>(`/sources/${encodeURIComponent(name)}`)
}

// 创建数据源（只需 name + url，类型和选择器自动检测）
export function createSource(payload: SourceCreatePayload) {
  return client.post<unknown, SourceCreateResponse>('/sources', payload)
}

// 更新数据源
export function updateSource(name: string, payload: SourceUpdatePayload) {
  return client.put<unknown, { success: boolean; name: string }>(
    `/sources/${encodeURIComponent(name)}`,
    payload,
  )
}

// 删除数据源（会级联删除 grab 表对应数据）
export function deleteSource(name: string) {
  return client.delete<unknown, { success: boolean; name: string }>(
    `/sources/${encodeURIComponent(name)}`,
  )
}

// 测试 URL 连通性
export function testUrl(url: string) {
  return client.post<unknown, ConnectionTestResult>('/sources/test', { url })
}
