// ============ 数据源 ============
export type SelectorSource = 'detector' | 'preset' | 'fallback' | 'manual'

export interface SourceInfo {
  name: string
  url: string
  description: string
  source_type: 'web' | 'rss' | 'api'
  selectors: Record<string, any> | null
  selector_source: SelectorSource
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface SourceCreatePayload {
  name: string
  url: string
  description?: string
  selectors?: Record<string, string> | null
}

export interface SourceUpdatePayload {
  url?: string
  description?: string
  enabled?: boolean
  selectors?: Record<string, string> | null
}

export interface SourceCreateResponse {
  success: boolean
  id: number
  name: string
  source_type: string
  selectors: Record<string, any>
  selector_source: SelectorSource
}

// ============ 连通性测试 ============
export interface ConnectionTestResult {
  success: boolean
  message: string
  latency_ms?: number
}

// ============ 选择器预览 ============
export interface PreviewRequest {
  url: string
  selectors?: Record<string, string> | null
  sample_size?: number
}

export interface PreviewSample {
  title: string
  url: string
  summary: string
  content_preview: string
  content_length: number
  published_at?: string | null
}

export interface PreviewResponse {
  success: boolean
  url: string
  selector_source: SelectorSource
  selectors: Record<string, any>
  js_rendered: boolean
  samples: PreviewSample[]
  validation: {
    total: number
    valid: number
    passed: boolean
  }
  failure_reasons: string[]
  elapsed_ms: number
}

// ============ 爬取任务 ============
export type ScrapeJobStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ScrapeRequestPayload {
  source_name: string
  limit?: number
}

export interface ScrapeJobResponse {
  job_id: string
  status: ScrapeJobStatus
  sources: string[]
  source_name: string
  total: number
  limit_count: number
  error?: string | null
  created_at: string
  started_at?: string | null
  completed_at?: string | null
  results?: any[] | null
}

export interface ScrapeJobListResponse {
  total: number
  limit: number
  offset: number
  items: ScrapeJobResponse[]
}

// ============ 任务抓取数据 ============
export interface JobDataResponse {
  job_id: string
  total: number
  items: DataItem[]
}

export interface DataResponse {
  total: number
  limit: number
  offset: number
  items: DataItem[]
}

// ============ 导出 ============
export type ExportFormat = 'json' | 'csv' | 'docx'

export interface ExportResponse {
  success: boolean
  format: ExportFormat
  file_path?: string | null
  content?: string | null
  message?: string | null
}

// ============ 命中关键词（附加到 DataItem）============
export type MatchType = 'word' | 'variant'
export interface MatchedKeyword {
  keyword_id: number
  keyword: string
  topic_id?: number | null
  topic_name: string
  topic_color: string
  hit_count: number
  score: number
  weight: number
  // 教程第 7 节：Query Expansion 字段
  match_type?: MatchType
  matched_variant?: string | null
  direct_mention?: boolean
}
export interface MatchedTopic {
  topic_id?: number | null
  name: string
  color: string
}
export interface DataItem {
  id: number
  source_id: number
  source_name: string
  title: string
  content: string
  summary: string
  source_url: string
  language: string
  category: string
  tags: string[] | null
  published_at: string | null
  grabbed_at: string
  raw_json?: Record<string, any> | null
  matched_keywords?: MatchedKeyword[]
  matched_topics?: MatchedTopic[]
  // 教程第 7 节：相关性
  relevance_score?: number | null
  keyword_mentioned?: number | boolean | null
  relevance_reason?: string | null
}

// ============ 主题 ============
export interface Topic {
  id: number
  name: string
  description: string
  color: string
  enabled: number
  sort_order: number
  created_at: string
}
export interface TopicCreate {
  name: string
  description?: string
  color?: string
  sort_order?: number
  enabled?: number
}
export interface TopicUpdate {
  name?: string
  description?: string
  color?: string
  sort_order?: number
  enabled?: number
}

// ============ 关键词 ============
export type MatchMode = 'exact' | 'fuzzy' | 'regex'
export interface Keyword {
  id: number
  topic_id?: number | null
  word: string
  language: string
  match_mode: MatchMode
  weight: number
  enabled: number
  created_at?: string | null
  updated_at?: string | null
  topic_name?: string | null
  topic_color?: string | null
  // 教程第 7 节：Query Expansion 变体
  variants?: string[] | null
}
export interface KeywordCreate {
  topic_id?: number | null
  word: string
  language?: string
  match_mode?: MatchMode
  weight?: number
  enabled?: number
  variants?: string[] | null
}
export interface KeywordUpdate {
  topic_id?: number
  word?: string
  language?: string
  match_mode?: MatchMode
  weight?: number
  enabled?: number
  variants?: string[] | null
}
export interface KeywordImportPayload {
  topic_id?: number | null
  words_text: string
  default_language?: string
  default_match_mode?: MatchMode
  default_weight?: number
}
export interface KeywordImportResult {
  inserted: number
  skipped: number
}

// ============ 趋势 & 图表 ============
export interface TrendPoint {
  time_bucket: string
  article_cnt: number
  hit_cnt: number
}
export interface KeywordTrendSeries {
  keyword_id: number
  word?: string | null
  topic_id?: number | null
  color?: string | null
  points: TrendPoint[]
}
export interface TopicTrendSeries {
  topic_id?: number | null
  name?: string | null
  color?: string | null
  points: TrendPoint[]
}
export interface TopKeywordRow {
  keyword_id: number
  word: string
  topic_id?: number | null
  topic_name: string
  topic_color: string
  article_cnt: number
  hit_cnt: number
  // 教程第 7 节：Query Expansion 拆分
  direct_hits?: number
  variant_hits?: number
  direct_grabs?: number
  variant_grabs?: number
  variant_count?: number | null
}
export interface TopicDistribution {
  topic_id?: number | null
  name: string
  color: string
  article_cnt: number
}
export interface HourlyArticleBucket {
  bucket: string
  cnt: number
}

// ============ Dashboard Summary ============
export interface DashboardSummary {
  today_events: number
  unread_events: number
  articles_24h: number
  active_topics: number
  keywords_total: number
  high_level_events: number
  top_keywords: TopKeywordRow[]
  topic_distribution: TopicDistribution[]
  // 教程第 7 节：相关性指标
  relevance_threshold?: number
  scored_grabs?: number
  high_relevance_grabs?: number
  high_relevance_rate?: number
  keyword_mentioned_true?: number
  keyword_mentioned_rate?: number
  avg_relevance_score_scored?: number
}

// ============ 热点事件 ============
export type HotspotLevel = 'low' | 'mid' | 'high'
export interface HotspotEvent {
  id: number
  keyword_id: number | null
  topic_id?: number | null
  window_start: string
  window_end: string
  article_cnt: number
  hit_cnt: number
  baseline: number
  ratio: number
  level: HotspotLevel
  is_read: number
  created_at: string
  topic_name?: string | null
  topic_color?: string | null
  keyword_word?: string | null
}
export interface HotspotEventListResponse {
  total: number
  limit: number
  offset: number
  items: HotspotEvent[]
}

// ============ 调度 ============
export interface ScheduleConfig {
  id?: number | null
  source_id: number
  cron_expr: string
  limit_count: number
  enabled: number
  updated_at?: string | null
  source_name?: string | null
  source_url?: string | null
  source_enabled?: number | null
}
export interface ScheduleCreate {
  source_id: number
  cron_expr: string
  limit_count?: number
  enabled?: number
}
export interface ScheduleUpdate {
  cron_expr?: string
  limit_count?: number
  enabled?: number
}
export interface ScheduleStatus {
  running: boolean
  disabled_env: boolean
  aps_available: boolean
  jobs: Array<{
    id: string
    name: string
    next_run_time: string | null
    trigger: string
  }>
}
export interface ScheduleTriggerNowResponse {
  ok: boolean
  job_id?: string | null
  message?: string | null
}

// ============ 历史重算 ============
export interface RecalcRequest {
  start_time?: string
  end_time?: string
  job_ids?: string[]
  re_detect_events?: boolean
  clear_old_trends?: boolean
}
export interface RecalcResponse {
  ok: boolean
  processed_items: number
  new_hits: number
  new_events: number
  trend_granularity: string
  duration_seconds: number
  error?: string | null
}
