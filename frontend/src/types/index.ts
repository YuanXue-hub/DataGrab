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

// ============ 已爬取数据 ============
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
