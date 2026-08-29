import client from './client'
import type {
  Topic, TopicCreate, TopicUpdate,
  Keyword, KeywordCreate, KeywordUpdate,
  KeywordImportPayload, KeywordImportResult,
} from '@/types'

// ==================== 主题 ====================
export function listTopics(includeDisabled = false) {
  return client.get<unknown, Topic[]>('/topics', { params: { include_disabled: includeDisabled ? 1 : 0 } })
}

export function createTopic(payload: TopicCreate) {
  return client.post<unknown, Topic>('/topics', payload)
}

export function updateTopic(id: number, payload: TopicUpdate) {
  return client.patch<unknown, Topic>(`/topics/${id}`, payload)
}

export function deleteTopic(id: number) {
  return client.delete<unknown, { ok: boolean }>(`/topics/${id}`)
}

// ==================== 关键词 ====================
export function listKeywords(topicId?: number, includeDisabled = false) {
  return client.get<unknown, Keyword[]>('/keywords', {
    params: {
      topic_id: topicId,
      include_disabled: includeDisabled ? 1 : 0,
    },
  })
}

export function createKeyword(payload: KeywordCreate) {
  return client.post<unknown, Keyword>('/keywords', payload)
}

export function updateKeyword(id: number, payload: KeywordUpdate) {
  return client.patch<unknown, Keyword>(`/keywords/${id}`, payload)
}

export function deleteKeyword(id: number) {
  return client.delete<unknown, { ok: boolean }>(`/keywords/${id}`)
}

export function importKeywords(payload: KeywordImportPayload) {
  return client.post<unknown, KeywordImportResult>('/keywords/import', payload)
}
