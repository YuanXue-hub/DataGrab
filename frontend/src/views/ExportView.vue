<template>
  <div class="page">
    <!-- 导出表单 -->
    <el-card shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Upload /></el-icon> 导出已爬取数据</span>
        </div>
      </template>

      <el-form :model="form" label-width="100px" inline>
        <el-form-item label="数据源">
          <el-select
            v-model="form.source_name"
            placeholder="全部数据源"
            clearable
            style="width: 220px"
          >
            <el-option
              v-for="s in sources"
              :key="s.name"
              :label="s.name"
              :value="s.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="导出格式">
          <el-radio-group v-model="form.format">
            <el-radio-button value="json">
              <el-icon><Document /></el-icon> JSON
            </el-radio-button>
            <el-radio-button value="csv">
              <el-icon><Grid /></el-icon> CSV
            </el-radio-button>
            <el-radio-button value="docx">
              <el-icon><Notebook /></el-icon> Word
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="最大条数">
          <el-input-number
            v-model="form.limit"
            :min="1"
            :max="5000"
            :step="100"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :icon="Download"
            :loading="exporting"
            @click="onExport"
          >
            生成导出
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="JSON 直接在浏览器下载；CSV/Word 由后端写入 output/ 目录，返回文件路径。"
      />
    </el-card>

    <!-- 导出结果展示 -->
    <el-card v-if="lastResult" shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span><el-icon><CircleCheck /></el-icon> 最近一次导出</span>
          <el-tag :type="lastResult.success ? 'success' : 'danger'" size="small">
            {{ lastResult.success ? '成功' : '失败' }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="格式">
          {{ lastResult.format?.toUpperCase() }}
        </el-descriptions-item>
        <el-descriptions-item v-if="lastResult.file_path" label="文件路径">
          <code class="path">{{ lastResult.file_path }}</code>
        </el-descriptions-item>
        <el-descriptions-item v-if="lastResult.message" label="说明">
          {{ lastResult.message }}
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="lastResult.format === 'json' && lastResult.content" style="margin-top: 16px">
        <div class="result-actions">
          <span class="result-label">JSON 预览（前 50 条）</span>
          <el-button type="primary" size="small" :icon="Download" @click="downloadJson">
            下载 JSON 文件
          </el-button>
        </div>
        <pre class="json-preview">{{ jsonPreview }}</pre>
      </div>

      <div v-if="lastResult.format === 'csv' || lastResult.format === 'docx'" style="margin-top: 16px">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          :title="`${lastResult.format.toUpperCase()} 文件已生成于后端服务器：${lastResult.file_path}`"
          description="如需下载，请通过 SSH 或文件共享访问后端 output/ 目录。"
        />
      </div>
    </el-card>

    <!-- 历史导出记录 -->
    <el-card v-if="history.length" shadow="never" class="card">
      <template #header>
        <div class="card-header">
          <span><el-icon><Clock /></el-icon> 本次会话导出历史</span>
          <el-button size="small" link :icon="Delete" @click="history = []">清空</el-button>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(h, idx) in history"
          :key="idx"
          :timestamp="h.time"
          :type="h.success ? 'success' : 'danger'"
          placement="top"
        >
          <span class="hist-format">{{ h.format?.toUpperCase() }}</span>
          <span class="hist-source">{{ h.source_name || '全部数据源' }}</span>
          <span class="hist-meta">{{ h.message || (h.success ? '成功' : '失败') }}</span>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Upload, Download, Document, Grid, CircleCheck, Clock, Delete, Notebook,
} from '@element-plus/icons-vue'
import { listSources } from '@/api/sources'
import { exportData } from '@/api/export'
import type { SourceInfo, ExportResponse, ExportFormat } from '@/types'

const sources = ref<SourceInfo[]>([])
const exporting = ref(false)
const lastResult = ref<ExportResponse | null>(null)

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
  message?: string | null
  file_path?: string | null
}
const history = ref<HistoryItem[]>([])

// JSON 预览（前 50 条）
const jsonPreview = computed(() => {
  if (!lastResult.value?.content) return ''
  try {
    const arr = JSON.parse(lastResult.value.content)
    const head = Array.isArray(arr) ? arr.slice(0, 50) : arr
    return JSON.stringify(head, null, 2)
  } catch {
    return lastResult.value.content
  }
})

async function loadSources() {
  sources.value = await listSources()
}

async function onExport() {
  exporting.value = true
  try {
    const res = await exportData({
      format: form.format,
      source_name: form.source_name || undefined,
      limit: form.limit,
    })
    lastResult.value = res
    history.value.unshift({
      time: new Date().toLocaleString('zh-CN'),
      format: res.format,
      source_name: form.source_name,
      success: res.success,
      message: res.message,
      file_path: res.file_path,
    })
    if (res.success) {
      if (res.format === 'json') {
        ElMessage.success(`已导出 ${JSON.parse(res.content || '[]').length} 条 JSON 数据`)
      } else {
        ElMessage.success(`${res.format.toUpperCase()} 已生成: ${res.file_path}`)
      }
    }
  } finally {
    exporting.value = false
  }
}

function downloadJson() {
  if (!lastResult.value?.content) return
  const blob = new Blob([lastResult.value.content], {
    type: 'application/json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  a.download = `datagrab_export_${ts}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(loadSources)
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

.path {
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #dc2626;
}

.result-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-label {
  font-weight: 600;
  color: #1f2937;
}

.json-preview {
  background: #0f172a;
  color: #e2e8f0;
  padding: 12px;
  border-radius: 6px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  max-height: 360px;
  overflow: auto;
  margin: 0;
}

.hist-format {
  font-weight: 700;
  color: #2563eb;
  margin-right: 10px;
}

.hist-source {
  color: #4b5563;
  margin-right: 10px;
}

.hist-meta {
  color: #6b7280;
  font-size: 13px;
}
</style>
