<template>
  <div class="page">
    <!-- 顶部操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="search"
          placeholder="搜索名称/URL"
          clearable
          style="width: 260px"
          :prefix-icon="Search"
        />
        <el-select
          v-model="filterType"
          placeholder="按类型筛选"
          clearable
          style="width: 140px"
        >
          <el-option label="web" value="web" />
          <el-option label="api" value="api" />
          <el-option label="rss" value="rss" />
        </el-select>
        <el-button type="primary" :icon="Refresh" @click="loadSources">
          刷新
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" @click="openCreate">
          新增数据源
        </el-button>
      </div>
    </div>

    <!-- 数据源列表 -->
    <el-card shadow="never" class="card">
      <el-table
        v-loading="loading"
        :data="filteredSources"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column label="名称" prop="name" min-width="120">
          <template #default="{ row }: { row: any }">
            <span class="source-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" prop="source_type" width="90">
          <template #default="{ row }: { row: any }">
            <el-tag :type="typeTag(row.source_type)" size="small" effect="plain">
              {{ row.source_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="选择器来源" width="110" align="center">
          <template #default="{ row }: { row: any }">
            <el-tag :type="sourceTag(row.selector_source)" size="small" effect="dark">
              {{ sourceLabel(row.selector_source) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="URL" prop="url" min-width="260" show-overflow-tooltip />
        <el-table-column label="描述" prop="description" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }: { row: any }">
            <el-switch
              :model-value="row.enabled"
              @change="(v) => toggleEnabled(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="160">
          <template #default="{ row }: { row: any }">
            <span class="muted">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }: { row: any }">
            <el-button size="small" link :icon="View" @click="openPreview(row)">
              选择器测试
            </el-button>
            <el-button size="small" link :icon="VideoPause" @click="onTest(row)">
              连通测试
            </el-button>
            <el-button size="small" link type="primary" :icon="Edit" @click="openEdit(row)">
              编辑
            </el-button>
            <el-button size="small" link type="danger" :icon="Delete" @click="onDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑数据源' : '新增数据源'"
      width="620px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
        label-position="right"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" :disabled="editing" placeholder="唯一标识，如 bbc" />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input v-model="form.url" placeholder="https://example.com" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>

        <el-collapse v-model="advancedOpen" class="advanced-collapse">
          <el-collapse-item title="高级配置（手动指定 CSS 选择器）" name="advanced">
            <el-alert
              type="info"
              :closable="false"
              show-icon
              title="留空则系统自动检测/匹配预设；手动填写后保存即标记为 manual 来源"
              style="margin-bottom: 12px"
            />
            <el-input
              v-model="selectorsText"
              type="textarea"
              :rows="8"
              placeholder='{"article_selector": "li.news", "title_selector": "h3 a", "link_selector": "a", "content_selector": ".article-body"}'
              class="mono-input"
            />
            <div class="form-actions">
              <el-button
                size="small"
                type="primary"
                :icon="View"
                :loading="previewLoading"
                @click="testSelectorsInDialog"
              >
                测试选择器
              </el-button>
              <el-button v-if="selectorsText" size="small" @click="selectorsText = ''">
                清空（用自动检测）
              </el-button>
            </div>
          </el-collapse-item>
        </el-collapse>

        <el-form-item v-if="!editing && !advancedOpen.includes('advanced')" label="">
          <el-alert
            type="info"
            :closable="false"
            show-icon
            title="系统会根据 URL 自动检测类型（web/api）和 CSS 选择器"
          />
        </el-form-item>
        <el-form-item v-if="editing" label="启用状态">
          <el-switch v-model="form.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">
          {{ editing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 选择器预览抽屉 -->
    <el-drawer
      v-model="previewVisible"
      title="选择器抓取预览"
      direction="rtl"
      size="70%"
    >
      <div v-loading="previewLoading" class="preview-container">
        <div v-if="previewResult" class="preview-layout">
          <!-- 左侧：样本卡片 -->
          <div class="preview-samples">
            <div class="preview-header">
              <h3>抓取样本（{{ previewResult.samples.length }} 条）</h3>
              <el-tag
                :type="previewResult.validation.passed ? 'success' : 'danger'"
                effect="dark"
                size="small"
              >
                验证 {{ previewResult.validation.valid }}/{{ previewResult.validation.total }}
              </el-tag>
            </div>
            <div
              v-for="(s, i) in previewResult.samples"
              :key="i"
              class="sample-card"
            >
              <div class="sample-title">
                <span class="sample-idx">#{{ i + 1 }}</span>
                <a :href="s.url" target="_blank" rel="noopener" class="sample-link">
                  {{ s.title || '(无标题)' }}
                </a>
              </div>
              <div v-if="s.summary" class="sample-summary">{{ s.summary }}</div>
              <div v-if="s.content_preview" class="sample-content">
                {{ s.content_preview }}
              </div>
              <div class="sample-meta">
                <span>正文长度: <b>{{ s.content_length }}</b></span>
                <span v-if="s.published_at">发布: {{ s.published_at }}</span>
              </div>
            </div>
            <el-empty
              v-if="previewResult.samples.length === 0"
              description="未抓取到样本，请检查选择器或 URL"
            />
          </div>

          <!-- 右侧：选择器配置 -->
          <div class="preview-config">
            <div class="config-section">
              <div class="config-label">来源</div>
              <el-tag :type="sourceTag(previewResult.selector_source)" effect="dark" size="small">
                {{ sourceLabel(previewResult.selector_source) }}
              </el-tag>
              <span class="config-time">耗时 {{ previewResult.elapsed_ms }}ms</span>
            </div>

            <div v-if="previewResult.js_rendered" class="config-section">
              <el-alert
                type="warning"
                :closable="false"
                show-icon
                title="疑似 JS 渲染页面"
                description="正文提取失败或过短，建议配置专用 content_selector 或启用 JS 渲染"
              />
            </div>

            <div class="config-section">
              <div class="config-label">当前选择器</div>
              <el-input
                v-model="previewSelectorsText"
                type="textarea"
                :rows="12"
                class="mono-input"
              />
              <div class="config-actions">
                <el-button
                  size="small"
                  type="primary"
                  :loading="previewLoading"
                  @click="retestPreview"
                >
                  重新测试
                </el-button>
                <el-button size="small" @click="copySelectors">
                  复制
                </el-button>
              </div>
            </div>

            <div class="config-section">
              <div class="config-label">验证结果</div>
              <div class="validation-grid">
                <div class="validation-item">
                  <span class="muted">总样本</span>
                  <b>{{ previewResult.validation.total }}</b>
                </div>
                <div class="validation-item">
                  <span class="muted">有效</span>
                  <b class="success-text">{{ previewResult.validation.valid }}</b>
                </div>
                <div class="validation-item">
                  <span class="muted">通过</span>
                  <b :class="previewResult.validation.passed ? 'success-text' : 'danger-text'">
                    {{ previewResult.validation.passed ? '是' : '否' }}
                  </b>
                </div>
              </div>
            </div>

            <div v-if="previewResult.failure_reasons.length" class="config-section">
              <div class="config-label">
                失败原因
                <span class="config-hint">（参考以下原因调整选择器）</span>
              </div>
              <el-alert
                type="error"
                :closable="false"
                show-icon
                class="reasons-alert"
              >
                <template #title>
                  <ul class="reason-list">
                    <li v-for="(r, i) in previewResult.failure_reasons" :key="i">{{ r }}</li>
                  </ul>
                </template>
              </el-alert>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, ElLoading, type FormInstance, type FormRules } from 'element-plus'
import {
  Search, Refresh, Plus, Edit, Delete, VideoPause, View,
} from '@element-plus/icons-vue'
import {
  listSources, createSource, updateSource, deleteSource, testUrl, previewSource,
} from '@/api/sources'
import type {
  SourceInfo,
  SourceCreatePayload,
  SourceUpdatePayload,
  SelectorSource,
  PreviewResponse,
} from '@/types'

const sources = ref<SourceInfo[]>([])
const loading = ref(false)
const search = ref('')
const filterType = ref<string>('')

// 弹窗状态
const dialogVisible = ref(false)
const editing = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  url: '',
  description: '',
  enabled: true,
})

// 高级配置
const advancedOpen = ref<string[]>([])
const selectorsText = ref('')

// 预览抽屉
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewResult = ref<PreviewResponse | null>(null)
const previewSelectorsText = ref('')
const previewUrl = ref('')

const rules: FormRules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入 URL', trigger: 'blur' }],
}

const filteredSources = computed(() => {
  const kw = search.value.trim().toLowerCase()
  return sources.value.filter((s) => {
    const matchKw =
      !kw ||
      s.name.toLowerCase().includes(kw) ||
      s.url.toLowerCase().includes(kw)
    const matchType = !filterType.value || s.source_type === filterType.value
    return matchKw && matchType
  })
})

function typeTag(t: string) {
  if (t === 'api') return 'success'
  if (t === 'rss') return 'warning'
  return 'info'
}

function sourceLabel(s: SelectorSource | string): string {
  const map: Record<string, string> = {
    detector: '自动检测',
    preset: '预设匹配',
    fallback: '通用兜底',
    manual: '手动配置',
  }
  return map[s] || s
}

function sourceTag(s: SelectorSource | string) {
  if (s === 'detector') return 'success'
  if (s === 'preset') return 'primary'
  if (s === 'manual') return 'warning'
  return 'info'
}

function formatTime(s: string) {
  if (!s) return '-'
  return s.replace('T', ' ').split('.')[0]
}

function parseSelectors(text: string): Record<string, string> | null {
  const t = text.trim()
  if (!t) return null
  try {
    const obj = JSON.parse(t)
    if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
      return obj
    }
    ElMessage.error('选择器必须是 JSON 对象')
    return null
  } catch {
    ElMessage.error('选择器 JSON 格式错误')
    return null
  }
}

async function loadSources() {
  loading.value = true
  try {
    sources.value = await listSources()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = false
  Object.assign(form, { name: '', url: '', description: '', enabled: true })
  selectorsText.value = ''
  advancedOpen.value = []
  dialogVisible.value = true
}

function openEdit(row: SourceInfo) {
  editing.value = true
  Object.assign(form, {
    name: row.name,
    url: row.url,
    description: row.description,
    enabled: row.enabled,
  })
  selectorsText.value = row.selectors ? JSON.stringify(row.selectors, null, 2) : ''
  advancedOpen.value = row.selectors ? ['advanced'] : []
  dialogVisible.value = true
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const manualSelectors = parseSelectors(selectorsText.value)

      if (editing.value) {
        const payload: SourceUpdatePayload = {
          url: form.url,
          description: form.description,
          enabled: form.enabled,
        }
        if (manualSelectors) payload.selectors = manualSelectors
        await updateSource(form.name, payload)
        ElMessage.success('已保存')
      } else {
        const payload: SourceCreatePayload = {
          name: form.name,
          url: form.url,
          description: form.description,
        }
        if (manualSelectors) payload.selectors = manualSelectors
        const res = await createSource(payload)
        const validInfo = res.selector_source === 'manual'
          ? '手动配置'
          : `自动${res.selector_source === 'detector' ? '检测' : res.selector_source === 'preset' ? '预设' : '兜底'}`
        ElMessage.success(`已创建（${res.source_type} 类型，选择器来源：${validInfo}）`)
      }
      dialogVisible.value = false
      await loadSources()
    } finally {
      submitting.value = false
    }
  })
}

async function toggleEnabled(row: SourceInfo, value: boolean) {
  try {
    await updateSource(row.name, { enabled: value })
    row.enabled = value
    ElMessage.success(value ? '已启用' : '已禁用')
  } catch {
    // 错误已由拦截器提示
  }
}

async function onDelete(row: SourceInfo) {
  await ElMessageBox.confirm(
    `确认删除数据源「${row.name}」？\n该操作会同时删除其下所有已爬取数据。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteSource(row.name)
  ElMessage.success('已删除')
  await loadSources()
}

async function onTest(row: SourceInfo) {
  const loading = ElLoading.service({ text: '连通测试中...', background: 'rgba(0,0,0,0.4)' })
  try {
    const res = await testUrl(row.url)
    if (res.success) {
      ElMessage.success(`连通正常 (${res.latency_ms}ms)`)
    } else {
      ElMessage.warning(`无法访问: ${res.message}`)
    }
  } finally {
    loading.close()
  }
}

// ===== 选择器预览 =====
async function openPreview(row: SourceInfo) {
  previewUrl.value = row.url
  previewSelectorsText.value = row.selectors ? JSON.stringify(row.selectors, null, 2) : ''
  previewResult.value = null
  previewVisible.value = true
  await runPreview(row.url, row.selectors)
}

async function testSelectorsInDialog() {
  if (!form.url) {
    ElMessage.warning('请先填写 URL')
    return
  }
  const manualSelectors = parseSelectors(selectorsText.value)
  previewUrl.value = form.url
  previewSelectorsText.value = selectorsText.value
  previewResult.value = null
  previewVisible.value = true
  dialogVisible.value = false
  await runPreview(form.url, manualSelectors)
}

async function retestPreview() {
  const manualSelectors = parseSelectors(previewSelectorsText.value)
  if (manualSelectors === null && previewSelectorsText.value.trim()) return
  await runPreview(previewUrl.value, manualSelectors)
}

async function runPreview(url: string, selectors?: Record<string, string> | null) {
  previewLoading.value = true
  try {
    const res = await previewSource({
      url,
      selectors: selectors || undefined,
      sample_size: 3,
    })
    previewResult.value = res
    previewSelectorsText.value = JSON.stringify(res.selectors, null, 2)
    if (res.validation.passed) {
      ElMessage.success(`验证通过 ${res.validation.valid}/${res.validation.total}（${res.elapsed_ms}ms）`)
    } else if (res.samples.length > 0) {
      ElMessage.warning(`验证未通过 ${res.validation.valid}/${res.validation.total}，请查看失败原因`)
    } else if (res.failure_reasons.length) {
      ElMessage.warning(`未抓取到样本：${res.failure_reasons[0]}`)
    } else {
      ElMessage.warning('未抓取到样本，请检查选择器')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function copySelectors() {
  try {
    await navigator.clipboard.writeText(previewSelectorsText.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择文本')
  }
}

onMounted(loadSources)
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.card {
  border-radius: 8px;
}

.source-name {
  font-weight: 600;
  color: #1f2937;
}

.muted {
  color: #6b7280;
  font-size: 13px;
}

/* 高级配置折叠区 */
.advanced-collapse {
  margin: 8px 0 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.form-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.mono-input :deep(textarea) {
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 12px;
}

/* 预览抽屉 */
.preview-container {
  height: 100%;
}

.preview-layout {
  display: flex;
  gap: 20px;
  height: 100%;
}

.preview-samples {
  flex: 3;
  min-width: 0;
  overflow-y: auto;
  padding-right: 8px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.preview-header h3 {
  margin: 0;
  font-size: 15px;
  color: #1f2937;
}

.sample-card {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
  background: #fafafa;
}

.sample-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.sample-idx {
  color: #9ca3af;
  font-size: 12px;
  font-weight: 600;
}

.sample-link {
  color: #2563eb;
  text-decoration: none;
  font-weight: 500;
  font-size: 14px;
  word-break: break-all;
}

.sample-link:hover {
  text-decoration: underline;
}

.sample-summary {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
  line-height: 1.5;
}

.sample-content {
  font-size: 12px;
  color: #374151;
  line-height: 1.5;
  max-height: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  margin-bottom: 6px;
}

.sample-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #6b7280;
}

.sample-meta b {
  color: #1f2937;
}

.preview-config {
  flex: 2;
  min-width: 0;
  border-left: 1px solid #e5e7eb;
  padding-left: 20px;
  overflow-y: auto;
}

.config-section {
  margin-bottom: 20px;
}

.config-label {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  margin-bottom: 8px;
}

.config-time {
  margin-left: 12px;
  font-size: 12px;
  color: #9ca3af;
}

.config-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.validation-grid {
  display: flex;
  gap: 20px;
}

.validation-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: center;
}

.validation-item b {
  font-size: 18px;
  color: #1f2937;
}

.success-text {
  color: #10b981;
}

.danger-text {
  color: #ef4444;
}

.config-hint {
  font-size: 12px;
  font-weight: 400;
  color: #9ca3af;
  margin-left: 4px;
}

.reasons-alert {
  margin-top: 4px;
}

.reason-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.8;
  font-size: 13px;
}

.reason-list li {
  word-break: break-all;
}
</style>
