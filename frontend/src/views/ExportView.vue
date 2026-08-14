<template>
  <div class="dg-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--slate">
            <el-icon><Upload /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ totalExports }}</span>
            <span class="dg-stat-label">本次会话导出次数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--emerald">
            <el-icon><Document /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ jsonCount }}</span>
            <span class="dg-stat-label">JSON 次数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--amber">
            <el-icon><Grid /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ csvCount }}</span>
            <span class="dg-stat-label">CSV 次数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--blue">
            <el-icon><Notebook /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ docxCount }}</span>
            <span class="dg-stat-label">Word 次数</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 导出表单 -->
    <el-card shadow="never">
      <template #header>
        <div class="dg-card-header">
          <span class="card-title">
            <el-icon class="card-title-icon"><Upload /></el-icon>
            导出已爬取数据
          </span>
        </div>
      </template>

      <el-form :model="form" label-position="top" class="export-form">
        <el-row :gutter="20">
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="数据源">
              <el-select
                v-model="form.source_name"
                placeholder="全部数据源"
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="s in sources"
                  :key="s.name"
                  :label="s.name"
                  :value="s.name"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-form-item label="最大条数">
              <el-input-number
                v-model="form.limit"
                :min="1"
                :max="5000"
                :step="100"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="24" :md="8">
            <el-form-item label="操作">
              <el-button
                type="primary"
                :icon="Download"
                :loading="exporting"
                size="large"
                class="export-btn"
                @click="onExport"
              >
                生成导出
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="导出格式">
          <div class="format-cards">
            <div
              v-for="opt in formatOptions"
              :key="opt.value"
              class="format-card"
              :class="{ 'is-active': form.format === opt.value }"
              @click="form.format = opt.value"
            >
              <div class="format-card-head">
                <el-icon class="format-card-icon"><component :is="opt.icon" /></el-icon>
                <el-icon v-if="form.format === opt.value" class="format-card-check">
                  <Select />
                </el-icon>
              </div>
              <div class="format-card-name">{{ opt.label }}</div>
              <div class="format-card-desc">{{ opt.desc }}</div>
            </div>
          </div>
        </el-form-item>
      </el-form>

      <el-alert
        type="success"
        :closable="false"
        show-icon
        title="所有格式均通过浏览器直接下载到本地，不写入服务器目录。"
      />
    </el-card>

    <!-- JSON 预览（仅 JSON 格式且已导出） -->
    <el-card v-if="lastJsonPreview" shadow="never">
      <template #header>
        <div class="dg-card-header">
          <span class="card-title">
            <el-icon class="card-title-icon"><Document /></el-icon>
            JSON 预览（前 50 条）
          </span>
          <el-button type="primary" size="small" :icon="Download" @click="redownloadLast">
            重新下载
          </el-button>
        </div>
      </template>
      <pre class="json-preview">{{ lastJsonPreview }}</pre>
    </el-card>

    <!-- 历史导出记录 -->
    <el-card v-if="history.length" shadow="never">
      <template #header>
        <div class="dg-card-header">
          <span class="card-title">
            <el-icon class="card-title-icon"><Clock /></el-icon>
            本次会话导出历史
          </span>
          <el-button size="small" link :icon="Delete" @click="history = []">清空</el-button>
        </div>
      </template>
      <el-timeline class="history-timeline">
        <el-timeline-item
          v-for="(h, idx) in history"
          :key="idx"
          :timestamp="h.time"
          :type="h.success ? 'success' : 'danger'"
          placement="top"
        >
          <div class="hist-item">
            <span class="hist-format" :class="`hist-format--${h.format}`">
              {{ h.format?.toUpperCase() }}
            </span>
            <span class="hist-source">{{ h.source_name || '全部数据源' }}</span>
            <span class="hist-meta">{{ h.message }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 空状态：无历史记录时 -->
    <el-card v-else shadow="never">
      <div class="dg-empty">
        <div class="dg-empty-title">暂无导出记录</div>
        <div class="dg-empty-desc">配置上方参数并点击「生成导出」开始</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Upload, Download, Document, Grid, Clock, Delete, Notebook, Select,
} from '@element-plus/icons-vue'
import { listSources } from '@/api/sources'
import { exportData } from '@/api/export'
import type { SourceInfo, ExportFormat } from '@/types'

const sources = ref<SourceInfo[]>([])
const exporting = ref(false)
const lastJsonPreview = ref('')
const lastBlob = ref<Blob | null>(null)
const lastFilename = ref('')

const form = reactive({
  source_name: '',
  format: 'json' as ExportFormat,
  limit: 500,
})

interface HistoryItem {
  time: string
  format: ExportFormat
  source_name: string
  success: boolean
  message: string
}
const history = ref<HistoryItem[]>([])

const formatOptions: { value: ExportFormat; label: string; desc: string; icon: any }[] = [
  { value: 'json', label: 'JSON', desc: '结构化数据', icon: Document },
  { value: 'csv', label: 'CSV', desc: '表格文件', icon: Grid },
  { value: 'docx', label: 'Word', desc: '文档报告', icon: Notebook },
]

// 统计卡片
const totalExports = computed(() => history.value.length)
const jsonCount = computed(() => history.value.filter((h) => h.format === 'json').length)
const csvCount = computed(() => history.value.filter((h) => h.format === 'csv').length)
const docxCount = computed(() => history.value.filter((h) => h.format === 'docx').length)

async function loadSources() {
  sources.value = await listSources()
}

async function onExport() {
  exporting.value = true
  try {
    const result = await exportData({
      format: form.format,
      source_name: form.source_name || undefined,
      limit: form.limit,
    })

    // 触发浏览器下载
    triggerDownload(result.blob, result.filename)

    // JSON 格式额外保存用于预览
    if (result.format === 'json') {
      const text = await result.blob.text()
      lastBlob.value = result.blob
      lastFilename.value = result.filename
      try {
        const arr = JSON.parse(text)
        const head = Array.isArray(arr) ? arr.slice(0, 50) : arr
        lastJsonPreview.value = JSON.stringify(head, null, 2)
      } catch {
        lastJsonPreview.value = text.slice(0, 5000)
      }
    } else {
      lastJsonPreview.value = ''
      lastBlob.value = null
      lastFilename.value = ''
    }

    const msg = `已下载 ${result.count} 条数据 → ${result.filename}`
    history.value.unshift({
      time: new Date().toLocaleString('zh-CN'),
      format: result.format,
      source_name: form.source_name,
      success: true,
      message: msg,
    })
    ElMessage.success(msg)
  } catch {
    // 错误已在 exportData 中处理
    history.value.unshift({
      time: new Date().toLocaleString('zh-CN'),
      format: form.format,
      source_name: form.source_name,
      success: false,
      message: '导出失败',
    })
  } finally {
    exporting.value = false
  }
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function redownloadLast() {
  if (lastBlob.value && lastFilename.value) {
    triggerDownload(lastBlob.value, lastFilename.value)
    ElMessage.success('已重新下载')
  }
}

onMounted(loadSources)
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
  background: rgba(16, 185, 129, 0.1);
  color: var(--dg-emerald);
}

.stat-icon--amber {
  background: rgba(245, 158, 11, 0.1);
  color: #d97706;
}

.stat-icon--blue {
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

/* 卡片标题 */
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  color: var(--dg-text);
}

.card-title-icon {
  font-size: 16px;
  color: var(--dg-emerald);
}

/* 导出表单 */
.export-btn {
  width: 100%;
}

/* 格式选择卡片 */
.format-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  width: 100%;
}

.format-card {
  position: relative;
  border: 1.5px solid var(--dg-border);
  border-radius: var(--dg-radius-sm);
  padding: 16px;
  cursor: pointer;
  transition: all var(--dg-transition);
  background: var(--dg-surface);
}

.format-card:hover {
  border-color: var(--dg-emerald-light);
  box-shadow: var(--dg-shadow-sm);
}

.format-card:active {
  transform: scale(0.98);
}

.format-card.is-active {
  border-color: var(--dg-emerald);
  background: var(--el-color-primary-light-9);
  box-shadow: 0 0 0 1px var(--dg-emerald) inset;
}

.format-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.format-card-icon {
  font-size: 22px;
  color: var(--dg-text-secondary);
  transition: color var(--dg-transition);
}

.format-card.is-active .format-card-icon {
  color: var(--dg-emerald);
}

.format-card-check {
  font-size: 16px;
  color: var(--dg-emerald);
}

.format-card-name {
  font-family: 'Outfit', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--dg-text);
}

.format-card-desc {
  font-size: 12px;
  color: var(--dg-text-muted);
  margin-top: 2px;
}

/* JSON 预览 */
.json-preview {
  background: #0f172a;
  color: #e2e8f0;
  padding: 16px;
  border-radius: var(--dg-radius-sm);
  font-family: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
  line-height: 1.6;
  max-height: 400px;
  overflow: auto;
  margin: 0;
  border: 1px solid #1e293b;
}

/* 历史记录 */
.history-timeline {
  padding-top: 4px;
}

.hist-item {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.hist-format {
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 6px;
  letter-spacing: 0.02em;
}

.hist-format--json {
  background: rgba(16, 185, 129, 0.12);
  color: var(--dg-emerald-dark);
}

.hist-format--csv {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.hist-format--docx {
  background: rgba(59, 130, 246, 0.12);
  color: #3b82f6;
}

.hist-source {
  color: var(--dg-text);
  font-weight: 500;
  font-size: 13px;
}

.hist-meta {
  color: var(--dg-text-muted);
  font-size: 13px;
}
</style>
