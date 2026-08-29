import client from './client'
import type {
  ScheduleConfig, ScheduleCreate, ScheduleUpdate,
  ScheduleStatus, ScheduleTriggerNowResponse,
} from '@/types'

export function listSchedules() {
  return client.get<unknown, ScheduleConfig[]>('/schedules')
}

export function createSchedule(payload: ScheduleCreate) {
  return client.post<unknown, ScheduleConfig>('/schedules', payload)
}

export function updateSchedule(sourceId: number, payload: ScheduleUpdate) {
  return client.patch<unknown, ScheduleConfig>(`/schedules/${sourceId}`, payload)
}

export function deleteSchedule(sourceId: number) {
  return client.delete<unknown, { ok: boolean }>(`/schedules/${sourceId}`)
}

export function getScheduleStatus() {
  return client.get<unknown, ScheduleStatus>('/schedules/status')
}

export function reloadSchedule() {
  return client.post<unknown, ScheduleStatus>('/schedules/reload')
}

export function triggerSourceNow(sourceName: string, limit = 10) {
  return client.post<unknown, ScheduleTriggerNowResponse>(
    `/schedules/trigger/${encodeURIComponent(sourceName)}`,
    null,
    { params: { limit } },
  )
}
