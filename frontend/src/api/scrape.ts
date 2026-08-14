import client from './client'
import type {
  ScrapeRequestPayload,
  ScrapeJobResponse,
  ScrapeJobListResponse,
  JobDataResponse,
} from '@/types'

export interface JobListParams {
  source_name?: string
  status?: string
  limit?: number
  offset?: number
}

// 触发爬取任务（后台异步执行，状态持久化到 scrape_job 表）
export function triggerScrape(payload: ScrapeRequestPayload) {
  return client.post<unknown, ScrapeJobResponse>('/scrape', payload)
}

// 查询任务历史列表（从数据库读取，支持按数据源/状态过滤）
export function listJobs(params: JobListParams = {}) {
  return client.get<unknown, ScrapeJobListResponse>('/scrape', { params })
}

// 查询单个任务状态（含结果预览，仅 completed 状态返回 results）
export function getScrapeJob(jobId: string) {
  return client.get<unknown, ScrapeJobResponse>(
    `/scrape/${encodeURIComponent(jobId)}`,
  )
}

// 查询某次任务实际抓取到的数据（从 grab 表按 job_id 过滤，持久化）
export function getJobData(jobId: string, limit = 100) {
  return client.get<unknown, JobDataResponse>(
    `/scrape/${encodeURIComponent(jobId)}/data`,
    { params: { limit } },
  )
}
