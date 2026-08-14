<template>
  <div class="page">
    <!-- 顶部：触发新任务 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Download /></el-icon> 触发爬取任务</span>
        </div>
      </template>
      <el-form :model="form" label-width="100px" inline>
        <el-form-item label="数据源">
          <el-select
            v-model="form.source_name"
            placeholder="选择数据源"
            style="width: 260px"
            :loading="sourceLoading"
          >
            <el-option
              v-for="s in sources"
              :key="s.name"
              :label="`${s.name} (${s.source_type})`"
              :value="s.name"
              :disabled="!s.enabled"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="抓取条数">
          <el-input-number
            v-model="form.limit"
            :min="1"
            :max="500"
            :step="10"
            style="width: 140px"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :icon="VideoPlay"
            :loading="submitting"
            @click="onTrigger"
          >
            开始爬取
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务历史 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span><el-icon><List /></el-icon> 任务历史（持久化）</span>
          <div class="header-actions">
            <el-tag type="info" size="small">共 {{ total }} 个任务</el-tag>
            <el-button size="small" link :icon="Refresh" @click="loadJobs">刷新</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选 -->
      <div class="filter-bar">
        <el-select
          v-model="filters.source_name"
          placeholder="按数据源筛选"
          clearable
          style="width: 180px"
          @change="loadJobs"
        >
          <el-option v-for="s in sources" :key="s.name" :label="s.name" :value="s.name" />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="按状态筛选"
          clearable
          style="width: 140px"
          @change="loadJobs"
        >
          <el-option label="等待" value="pending" />
          <el-option label="运行中" value="running" />
          <el-option label="已完成" value="completed" />
          <el-option label="失败" value="failed" />
        </el-select>
      </div>

      <el-empty v-if="!jobs.length && !loading" description="暂无任务，从上方触发一个吧" />

      <el-table v-else v-loading="loading" :data="jobs" stripe border>
        <el-table-column label="任务 ID" min-width="220">
          <template #default="{ row }: { row: any }">
            <span class="mono">{{ row.job_id.slice(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column label="数据源" min-width="110" prop="source_name" />
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }: { row: any }">
            <el-tag :type="statusTag(row.status)" size="small" effect="dark">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已抓取" width="90" align="center">
          <template #default="{ row }: { row: any }">
            <span class="num">{{ row.total }}</span>
            <span class="muted">/{{ row.limit_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="150">
          <template #default="{ row }: { row: any }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="完成时间" min-width="150">
          <template #default="{ row }: { row: any }">
            {{ row.completed_at ? formatTime(row.completed_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }: { row: any }">
            <el-button
              v-if="row.status === 'pending' || row.status === 'running'"
              size="small"
              link
              :icon="Refresh"
              @click="refreshOne(row)"
            >
              刷新
            </el-button>
            <el-button
              v-if="row.status === 'completed'"
              size="small"
              link
              type="primary"
              :icon="View"
              @click="viewResult(row)"
            >
              查看结果
            </el-button>
            <el-button
              v-if="row.status === 'failed'"
              size="small"
              link
              type="danger"
              :icon="Warning"
              @click="viewError(row)"
            >
              查看错误
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page.current"
          v-model:page-size="page.size"
          :page-sizes="[20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="loadJobs"
          @current-change="loadJobs"
        />
      </div>
    </el-card>

    <!-- 结果对话框 -->
    <el-dialog
      v-model="resultVisible"
      title="爬取结果"
      width="780px"
      :close-on-click-modal="false"
    >
      <div v-loading="resultLoading">
        <el-empty v-if="!currentResults.length && !resultLoading" description="无结果数据" />
        <template v-else>
          <div class="result-meta">共 {{ currentResults.length }} 条数据</div>
          <el-table :data="currentResults" max-height="500" border>
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }: { row: any }">
            {{ row.title || '(无标题)' }}
          </template>
        </el-table-column>
        <el-table-column label="语言" width="80" prop="language" />
        <el-table-column label="摘要" min-width="240" show-overflow-tooltip>
          <template #default="{ row }: { row: any }">
            {{ row.summary || row.content?.slice(0, 80) || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="链接" width="100">
          <template #default="{ row }: { row: any }">
            <el-link
              v-if="row.source_url"
              :href="row.source_url"
              target="_blank"
              type="primary"
            >
              打开
            </el-link>
          </template>
        </el-table-column>
          </el-table>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Download, VideoPlay, List, Refresh, View, Warning,
} from '@element-plus/icons-vue'
import { listSources } from '@/api/sources'
import { triggerScrape, getScrapeJob, listJobs, getJobData } from '@/api/scrape'
import type {
  SourceInfo,
  ScrapeJobResponse,
  ScrapeJobStatus,
  DataItem,
} from '@/types'

const sources = ref<SourceInfo[]>([])
const sourceLoading = ref(false)
const submitting = ref(false)

const form = reactive({
  source_name: '',
  limit: 20,
})

const jobs = ref<ScrapeJobResponse[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  source_name: '',
  status: '',
})

const page = reactive({
  current: 1,
  size: 20,
})

const resultVisible = ref(false)
const resultLoading = ref(false)
const currentResults = ref<DataItem[]>([])

let pollTimer: ReturnType<typeof setInterval> | null = null

function statusText(s: ScrapeJobStatus) {
  return { pending: '等待', running: '运行中', completed: '已完成', failed: '失败' }[s]
}

function statusTag(s: ScrapeJobStatus) {
  return {
    pending: 'info',
    running: 'warning',
    completed: 'success',
    failed: 'danger',
  }[s] as 'info' | 'warning' | 'success' | 'danger'
}

function formatTime(s: string | null | undefined) {
  if (!s) return '-'
  return String(s).replace('T', ' ').split('.')[0]
}

async function loadSources() {
  sourceLoading.value = true
  try {
    const list = await listSources()
    sources.value = list
    if (!form.source_name && list.length > 0) {
      form.source_name = list[0].name
    }
  } finally {
    sourceLoading.value = false
  }
}

async function loadJobs() {
  loading.value = true
  try {
    const res = await listJobs({
      source_name: filters.source_name || undefined,
      status: filters.status || undefined,
      limit: page.size,
      offset: (page.current - 1) * page.size,
    })
    jobs.value = res.items
    total.value = res.total
    startPolling()
  } finally {
    loading.value = false
  }
}

async function onTrigger() {
  if (!form.source_name) {
    ElMessage.warning('请选择数据源')
    return
  }
  submitting.value = true
  try {
    const job = await triggerScrape({
      source_name: form.source_name,
      limit: form.limit,
    })
    ElMessage.success(`任务已创建: ${job.job_id.slice(0, 8)}...`)
    await loadJobs()
    startPolling()
  } finally {
    submitting.value = false
  }
}

async function refreshOne(job: ScrapeJobResponse) {
  try {
    const updated = await getScrapeJob(job.job_id)
    Object.assign(job, updated)
  } catch {
    /* ignore */
  }
}

async function viewResult(job: ScrapeJobResponse) {
  resultVisible.value = true
  resultLoading.value = true
  currentResults.value = []
  try {
    const res = await getJobData(job.job_id, 100)
    currentResults.value = res.items
  } catch {
    ElMessage.error('加载结果数据失败')
  } finally {
    resultLoading.value = false
  }
}

function viewError(job: ScrapeJobResponse) {
  ElMessageBox.alert(job.error || '未知错误', '任务失败原因', {
    type: 'error',
  })
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    const pending = jobs.value.filter(
      (j) => j.status === 'pending' || j.status === 'running',
    )
    if (!pending.length) {
      stopPolling()
      return
    }
    await Promise.all(pending.map((j) => refreshOne(j)))
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(async () => {
  await loadSources()
  await loadJobs()
})
onUnmounted(stopPolling)
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.mono {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  color: #6b7280;
}

.num {
  font-weight: 600;
  color: #2563eb;
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.result-meta {
  margin-bottom: 12px;
  font-size: 13px;
  color: #6b7280;
}
</style>
