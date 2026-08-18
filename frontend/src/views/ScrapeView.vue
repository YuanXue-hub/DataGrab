<template>
  <div class="dg-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--slate">
            <el-icon><List /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ total }}</span>
            <span class="dg-stat-label">任务总数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--emerald">
            <el-icon><CircleCheck /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ completedCount }}</span>
            <span class="dg-stat-label">已完成</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--amber">
            <el-icon><Loading /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ runningCount }}</span>
            <span class="dg-stat-label">运行中</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--red">
            <el-icon><Warning /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ failedCount }}</span>
            <span class="dg-stat-label">失败</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 触发爬取 -->
    <el-card shadow="never" class="trigger-card">
      <template #header>
        <div class="dg-card-header">
          <span class="card-title">
            <el-icon class="card-title-icon"><Download /></el-icon>
            触发爬取任务
          </span>
        </div>
      </template>
      <el-form :model="form" label-width="90px" label-position="right" class="trigger-form">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="10" :md="9">
            <el-form-item label="数据源">
              <el-select
                v-model="form.source_name"
                placeholder="选择数据源"
                style="width: 100%"
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
          </el-col>
          <el-col :xs="24" :sm="8" :md="7">
            <el-form-item label="抓取条数">
              <el-input-number
                v-model="form.limit"
                :min="1"
                :max="500"
                :step="10"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="6" :md="6" class="trigger-actions">
            <el-button
              type="primary"
              :icon="VideoPlay"
              :loading="submitting"
              @click="onTrigger"
            >
              开始爬取
            </el-button>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 任务历史 -->
    <el-card shadow="never" class="history-card">
      <template #header>
        <div class="dg-card-header">
          <span class="card-title">
            <el-icon class="card-title-icon"><Clock /></el-icon>
            任务历史（持久化）
          </span>
          <div class="header-actions">
            <el-tag type="info" size="small" effect="plain">共 {{ total }} 个任务</el-tag>
            <el-button size="small" :icon="Refresh" @click="loadJobs">刷新</el-button>
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

      <el-table v-loading="loading" :data="jobs" stripe style="width: 100%">
        <el-table-column label="任务 ID" min-width="180">
          <template #default="{ row }: { row: any }">
            <span class="mono">{{ row.job_id.slice(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column label="数据源" min-width="110" prop="source_name" />
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }: { row: any }">
            <el-tag
              :type="statusTag(row.status)"
              :class="{ 'status-running': row.status === 'running' }"
              size="small"
              effect="dark"
            >
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="已抓取" width="100" align="center">
          <template #default="{ row }: { row: any }">
            <span class="num">{{ row.total }}</span>
            <span class="dg-muted">/{{ row.limit_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="150">
          <template #default="{ row }: { row: any }">
            <span class="dg-muted">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="完成时间" min-width="150">
          <template #default="{ row }: { row: any }">
            <span class="dg-muted">{{ row.completed_at ? formatTime(row.completed_at) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
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
              :loading="loadingJobId === row.job_id"
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
        <template #empty>
          <div class="dg-empty">
            <div class="dg-empty-title">暂无任务</div>
            <div class="dg-empty-desc">从上方触发一个爬取任务开始</div>
          </div>
        </template>
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

    <!-- 结果抽屉 -->
    <el-drawer
      v-model="resultVisible"
      title="爬取结果"
      direction="rtl"
      size="50%"
    >
      <div v-loading="resultLoading" class="result-container">
        <div v-if="!currentResults.length && !resultLoading" class="dg-empty">
          <div class="dg-empty-title">无结果数据</div>
          <div class="dg-empty-desc">该任务未抓取到数据</div>
        </div>
        <template v-else>
          <div class="result-meta">
            共 <b>{{ currentResults.length }}</b> 条数据
          </div>
          <div class="result-list">
            <div
              v-for="item in currentResults"
              :key="item.id"
              class="result-card"
            >
              <div class="result-card-header">
                <a
                  v-if="item.source_url"
                  :href="item.source_url"
                  target="_blank"
                  rel="noopener"
                  class="result-title"
                >
                  {{ item.title || '(无标题)' }}
                </a>
                <span v-else class="result-title result-title--plain">
                  {{ item.title || '(无标题)' }}
                </span>
                <el-tag v-if="item.language" size="small" effect="plain">
                  {{ item.language }}
                </el-tag>
              </div>
              <div class="result-summary">
                {{ item.summary || item.content?.slice(0, 120) || '无摘要' }}
              </div>
              <div class="result-card-meta">
                <span class="result-meta-item">
                  <el-icon><Link /></el-icon>
                  {{ item.source_name }}
                </span>
                <span v-if="item.published_at" class="result-meta-item">
                  <el-icon><Clock /></el-icon>
                  {{ formatTime(item.published_at) }}
                </span>
                <span class="result-meta-item">
                  <el-icon><Document /></el-icon>
                  {{ item.content?.length || 0 }} 字
                </span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Download, VideoPlay, List, Refresh, View, Warning,
  CircleCheck, Loading, Clock, Link, Document,
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
const loadingJobId = ref<string>('')

let pollTimer: ReturnType<typeof setInterval> | null = null

// 统计卡片
const completedCount = computed(() => jobs.value.filter((j) => j.status === 'completed').length)
const runningCount = computed(() => jobs.value.filter((j) => j.status === 'running').length)
const failedCount = computed(() => jobs.value.filter((j) => j.status === 'failed').length)

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
  loadingJobId.value = job.job_id
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
    loadingJobId.value = ''
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
/* 统计卡片 */
.stat-row {
  margin-bottom: 0;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
}

.stat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--dg-radius-sm);
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon--slate {
  background: rgba(100, 116, 139, 0.1);
  color: #64748b;
}

.stat-icon--emerald {
  background: rgba(0, 240, 255, 0.1);
  color: var(--dg-cyan);
}

.stat-icon--amber {
  background: rgba(245, 158, 11, 0.1);
  color: var(--dg-warning);
}

.stat-icon--red {
  background: rgba(239, 68, 68, 0.1);
  color: var(--dg-danger);
}

/* 触发卡片 */
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  color: var(--dg-text-bright);
}

.card-title-icon {
  font-size: 16px;
  color: var(--dg-cyan);
}

.trigger-actions {
  display: flex;
  align-items: flex-end;
  padding-bottom: 18px;
}

/* 历史卡片 */
.history-card :deep(.el-card__body) {
  padding: 20px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.mono {
  font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-size: 13px;
  color: var(--dg-text-secondary);
}

.num {
  font-weight: 600;
  color: var(--dg-cyan);
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 状态运行中动画 */
.status-running {
  animation: dg-status-pulse 1.5s ease-in-out infinite;
}

@keyframes dg-status-pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.55;
  }
}

/* 结果抽屉 */
.result-container {
  min-height: 100%;
}

.result-meta {
  font-size: 13px;
  color: var(--dg-text-secondary);
  margin-bottom: 16px;
}

.result-meta b {
  color: var(--dg-cyan);
  font-size: 15px;
  font-weight: 600;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-card {
  background: var(--dg-surface);
  border: 1px solid var(--dg-border);
  border-radius: var(--dg-radius);
  padding: 16px;
  box-shadow: var(--dg-shadow-sm);
  transition: box-shadow var(--dg-transition);
}

.result-card:hover {
  box-shadow: var(--dg-shadow-md);
}

.result-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.result-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--dg-cyan-dim);
  text-decoration: none;
  word-break: break-all;
  line-height: 1.4;
}

.result-title:hover {
  color: var(--dg-cyan);
  text-decoration: underline;
}

.result-title--plain {
  color: var(--dg-text-bright);
}

.result-summary {
  font-size: 13px;
  color: var(--dg-text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  color: var(--dg-text-muted);
}

.result-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.result-meta-item .el-icon {
  font-size: 13px;
}
</style>
