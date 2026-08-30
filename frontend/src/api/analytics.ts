import client from './client'
import type {
  DashboardSummary,
  KeywordTrendSeries, TopicTrendSeries,
  TopKeywordRow, TopicDistribution, HourlyArticleBucket,
  HotspotEventListResponse, HotspotLevel,
  RecalcRequest, RecalcResponse,
  LatestArticlesResponse,
} from '@/types'

// 顶部统计卡
export function getDashboardSummary(hours = 24) {
  return client.get<unknown, DashboardSummary>('/analytics/summary', { params: { hours } })
}

// 关键词对比趋势（折线图）
export function getKeywordTrend(keywordIds: number[], grain: 'hour' | 'day' = 'hour', days = 7) {
  const ids = keywordIds.join(',')
  return client.get<unknown, KeywordTrendSeries[]>('/analytics/trend/keywords', {
    params: { keyword_ids: ids, grain, days },
  })
}

// 主题聚合趋势
export function getTopicTrend(topicIds: number[], grain: 'hour' | 'day' = 'hour', days = 7) {
  const ids = topicIds.join(',')
  return client.get<unknown, TopicTrendSeries[]>('/analytics/trend/topics', {
    params: { topic_ids: ids, grain, days },
  })
}

// Top N 关键词命中排行
export function getTopKeywords(hours = 24, limit = 20) {
  return client.get<unknown, TopKeywordRow[]>('/analytics/top-keywords', { params: { hours, limit } })
}

// 主题分布（饼图）
export function getTopicDistribution(hours = 24) {
  return client.get<unknown, TopicDistribution[]>('/analytics/topic-dist', { params: { hours } })
}

// 近 N 小时每小时文章量（柱图）
export function getHourlyArticles(hours = 24) {
  return client.get<unknown, HourlyArticleBucket[]>('/analytics/hourly-articles', { params: { hours } })
}

// 热点事件列表
export function listEvents(params: {
  level?: HotspotLevel
  topic_id?: number
  keyword_id?: number
  start?: string
  end?: string
  only_unread?: boolean
  limit?: number
  offset?: number
}) {
  return client.get<unknown, HotspotEventListResponse>('/analytics/events', { params })
}

// 标记事件已读
export function markEventsRead(ids: number[], allRead = false) {
  return client.post<unknown, { ok: boolean; marked: number }>('/analytics/events/read', { ids, all: allRead })
}

// 历史重算
export function recalcHistory(payload: RecalcRequest) {
  return client.post<unknown, RecalcResponse>('/analytics/recalc', payload, {
    timeout: 600000, // 可能非常久
  })
}

// 最新热点文章（看板展示 + 实时通知轮询）
export function getLatestArticles(params: {
  limit?: number
  since_id?: number
  min_score?: number
} = {}) {
  return client.get<unknown, LatestArticlesResponse>('/analytics/latest-articles', { params })
}
