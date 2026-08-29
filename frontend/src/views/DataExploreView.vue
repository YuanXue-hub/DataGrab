<template>
  <div class="dg-page">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--slate">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ total }}</span>
            <span class="dg-stat-label">总数据条数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--emerald">
            <el-icon><Filter /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ filteredCount }}</span>
            <span class="dg-stat-label">当前筛选结果数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--amber">
            <el-icon><Document /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ zhCount }}</span>
            <span class="dg-stat-label">中文数据数</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-icon stat-icon--blue">
            <el-icon><Reading /></el-icon>
          </div>
          <div class="dg-stat">
            <span class="dg-stat-value">{{ enCount }}</span>
            <span class="dg-stat-label">英文数据数</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 工具栏 -->
    <div class="dg-toolbar">
      <div class="dg-toolbar-left">
        <el-select
          v-model="filters.source_name"
          placeholder="全部数据源"
          clearable
          style="width: 180px"
          @change="resetAndLoad"
        >
          <el-option
            v-for="s in sources"
            :key="s.name"
            :label="s.name"
            :value="s.name"
          />
        </el-select>
        <el-select
          v-model="filters.topic_id"
          placeholder="全部主题"
          clearable
          style="width: 170px"
          filterable
          @change="onTopicChange"
        >
          <el-option
            v-for="t in topics"
            :key="t.id"
            :label="t.name"
            :value="t.id"
          >
            <span style="display:flex;align-items:center;gap:8px">
              <span class="opt-dot" :style="{ background: t.color }"></span>
              <span>{{ t.name }}</span>
            </span>
          </el-option>
        </el-select>
        <el-select
          v-model="filters.keyword_id"
          placeholder="全部关键词"
          clearable
          style="width: 190px"
          filterable
          @change="resetAndLoad"
        >
          <el-option
            v-for="k in filteredKeywords"
            :key="k.id"
            :label="k.word"
            :value="k.id"
          >
            <span style="display:flex;align-items:center;gap:8px">
              <span class="opt-dot" :style="{ background: k.topic_color || '#409EFF' }"></span>
              <strong>{{ k.word }}</strong>
              <span class="muted">· {{ k.topic_name }}</span>
            </span>
          </el-option>
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="标题 / 正文搜索"
          clearable
          style="width: 200px"
          :prefix-icon="Search"
          @keyup.enter="resetAndLoad"
          @clear="resetAndLoad"
        />
        <el-select
          v-model="filters.language"
          placeholder="全部语言"
          clearable
          style="width: 110px"
          @change="resetAndLoad"
        >
          <el-option label="中文" value="zh" />
          <el-option label="English" value="en" />
          <el-option label="Русский" value="ru" />
          <el-option label="Українська" value="uk" />
        </el-select>
      </div>
      <div class="dg-toolbar-right">
        <el-button type="primary" :icon="Search" @click="resetAndLoad">查询</el-button>
        <el-button :icon="Refresh" @click="onReset">重置</el-button>
      </div>
    </div>

    <!-- 数据表格 -->
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="dg-card-header">
          <span class="card-title">
            <el-icon class="card-title-icon"><Document /></el-icon>
            已爬取数据
          </span>
          <el-tag type="info" size="small" effect="plain">共 {{ total }} 条</el-tag>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="displayItems"
        stripe
        style="width: 100%"
        @row-click="openDetail"
      >
        <el-table-column label="标题 / 命中" min-width="320">
          <template #default="{ row }: { row: any }">
            <div class="title-cell">
              <span class="title">{{ row.title || '(无标题)' }}</span>
              <div class="meta">
                <el-tag v-if="row.language" size="small" effect="plain">{{ row.language }}</el-tag>
                <el-tag v-if="row.category" size="small" type="info" effect="plain">
                  {{ row.category }}
                </el-tag>
                <span v-if="row.published_at" class="time">
                  {{ formatTime(row.published_at) }}
                </span>
              </div>
              <!-- 命中主题/关键词 -->
              <div v-if="row.matched_topics?.length || row.matched_keywords?.length" class="hit-row">
                <el-tag
                  v-for="t in (row.matched_topics || []).slice(0, 3)"
                  :key="'t' + t.topic_id"
                  size="small"
                  effect="dark"
                  class="hit-tag topic-tag"
                  :style="{ background: t.color, borderColor: t.color }"
                ># {{ t.name }}</el-tag>
                <el-tag
                  v-for="k in (row.matched_keywords || []).slice(0, 6)"
                  :key="'k' + k.keyword_id"
                  size="small"
                  effect="plain"
                  class="hit-tag kw-tag"
                >
                  <i class="hit-w-badge">W{{ k.weight }}</i>
                  {{ k.keyword }}
                  <span
                    v-if="k.match_type === 'variant'"
                    class="match-variant"
                    :title="'通过变体匹配：' + (k.matched_variant || '')"
                  >变体</span>
                  <span
                    v-else-if="k.direct_mention"
                    class="match-direct"
                    title="直接提到监控原词（keyword_mentioned 锚点）"
                  >直接</span>
                </el-tag>
                <span
                  v-if="((row.matched_topics?.length || 0) + (row.matched_keywords?.length || 0)) > 9"
                  class="dg-muted"
                  style="font-size:11px"
                >…</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="320" show-overflow-tooltip>
          <template #default="{ row }: { row: any }">
            <span class="dg-muted">{{ row.summary || row.content?.slice(0, 100) || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="相关性" width="170" align="left">
          <template #default="{ row }: { row: any }">
            <div class="rel-col">
              <el-tag
                v-if="row.relevance_score !== null && row.relevance_score !== undefined"
                :type="relevanceTagType(row.relevance_score)"
                effect="dark" round size="small"
              >
                {{ Number(row.relevance_score).toFixed(0) }} / 100
              </el-tag>
              <el-tag v-else type="info" effect="plain" size="small">未打分</el-tag>
              <span
                v-if="row.keyword_mentioned"
                class="km-badge"
                title="keyword_mentioned=True：原文直接提到任一监控原词"
              >锚点✓</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="数据源" width="120" prop="source_name" />
        <el-table-column label="标签" width="180">
          <template #default="{ row }: { row: any }">
            <el-tag
              v-for="t in (row.tags || []).slice(0, 3)"
              :key="t"
              size="small"
              effect="plain"
              style="margin-right: 4px"
            >
              {{ t }}
            </el-tag>
            <span v-if="(row.tags?.length || 0) > 3" class="dg-muted">
              +{{ row.tags.length - 3 }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="抓取时间" width="160">
          <template #default="{ row }: { row: any }">
            <span class="dg-muted">{{ formatTime(row.grabbed_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }: { row: any }">
            <el-button size="small" link type="primary" :icon="View" @click.stop="openDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="dg-empty">
            <div class="dg-empty-title">暂无数据</div>
            <div class="dg-empty-desc">尝试调整筛选条件或抓取新数据</div>
          </div>
        </template>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="page.current"
          v-model:page-size="page.size"
          :page-sizes="[20, 50, 100, 200]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="loadData"
          @current-change="loadData"
        />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="currentItem?.title || '详情'"
      size="50%"
      direction="rtl"
    >
      <div v-if="currentItem" class="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="数据源">{{ currentItem.source_name }}</el-descriptions-item>
          <el-descriptions-item label="语言">{{ currentItem.language || '-' }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ currentItem.category || '-' }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">
            {{ formatTime(currentItem.published_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="抓取时间">
            {{ formatTime(currentItem.grabbed_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="原始链接">
            <el-link
              v-if="currentItem.source_url"
              :href="currentItem.source_url"
              target="_blank"
              type="primary"
            >
              打开原网页
            </el-link>
            <span v-else>-</span>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="currentItem.tags?.length" class="section">
          <div class="section-title">标签</div>
          <div class="tag-list">
            <el-tag
              v-for="t in currentItem.tags"
              :key="t"
              size="small"
              effect="plain"
            >
              {{ t }}
            </el-tag>
          </div>
        </div>

        <div v-if="(currentItem.matched_topics?.length || 0) + (currentItem.matched_keywords?.length || 0) > 0" class="section">
          <div class="section-title">命中主题 / 关键词</div>
          <div class="tag-list">
            <el-tag
              v-for="t in (currentItem.matched_topics || [])"
              :key="'mt' + t.topic_id"
              effect="dark"
              :style="{ background: t.color, borderColor: t.color }"
            ># {{ t.name }}</el-tag>
            <el-tag
              v-for="k in (currentItem.matched_keywords || [])"
              :key="'mk' + k.keyword_id"
              effect="plain"
              class="kw-tag-detail"
            >
              <i>W{{ k.weight }}</i> {{ k.keyword }}
              <span v-if="k.match_type === 'variant'" class="match-variant small">
                变体: {{ k.matched_variant || '' }}
              </span>
              <span v-else-if="k.direct_mention" class="match-direct small">直接提及</span>
            </el-tag>
          </div>
        </div>

        <div
          v-if="currentItem.relevance_score !== null && currentItem.relevance_score !== undefined"
          class="section"
        >
          <div class="section-title">相关性分析 <small class="muted">(教程第 7 节规则启发式评分)</small></div>
          <div class="relevance-panel">
            <div class="rel-score">
              <div class="score-circle" :class="'score-' + relevanceLevel(currentItem.relevance_score)">
                <span class="score-num">{{ Number(currentItem.relevance_score).toFixed(0) }}</span>
                <span class="score-denom">/ 100</span>
              </div>
              <div class="score-descs">
                <div>
                  等级：<el-tag size="small" effect="dark" :type="relevanceTagType(currentItem.relevance_score)">
                    {{ relevanceLevelText(currentItem.relevance_score) }}
                  </el-tag>
                </div>
                <div>
                  锚点证据 (keyword_mentioned)：
                  <el-tag
                    size="small"
                    :effect="currentItem.keyword_mentioned ? 'dark' : 'plain'"
                    :type="currentItem.keyword_mentioned ? 'success' : 'info'"
                  >{{ currentItem.keyword_mentioned ? '原文直接提到原词' : '仅变体命中（弱证据）' }}</el-tag>
                </div>
              </div>
            </div>
            <el-collapse v-if="currentItem.relevance_reason" v-model="reasonExpanded">
              <el-collapse-item title="查看评分推理原因 (relevance_reason)" name="reason">
                <pre class="reason-box">{{ currentItem.relevance_reason }}</pre>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>

        <div v-if="currentItem.summary" class="section">
          <div class="section-title">摘要</div>
          <div class="content-text">{{ currentItem.summary }}</div>
        </div>

        <div class="section">
          <div class="section-title">正文</div>
          <div class="content-text">{{ currentItem.content || '(无正文)' }}</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Document, Search, Refresh, View, Filter, DataAnalysis, Reading,
} from '@element-plus/icons-vue'
import { listSources } from '@/api/sources'
import { queryData } from '@/api/data'
import { listTopics, listKeywords } from '@/api/topics'
import type { SourceInfo, DataItem, Topic, Keyword } from '@/types'

const sources = ref<SourceInfo[]>([])
const topics = ref<Topic[]>([])
const allKeywords = ref<Keyword[]>([])
const items = ref<DataItem[]>([])
const loading = ref(false)
const total = ref(0)

const filters = reactive({
  source_name: '',
  topic_id: undefined as number | undefined,
  keyword_id: undefined as number | undefined,
  keyword: '',
  language: '',
})

const page = reactive({
  current: 1,
  size: 20,
})

const detailVisible = ref(false)
const currentItem = ref<DataItem | null>(null)
const reasonExpanded = ref<string | number | Array<string | number>>([])

function relevanceTagType(score: number): 'success' | 'warning' | 'danger' | 'info' {
  if (score == null) return 'info'
  if (score >= 75) return 'success'
  if (score >= 55) return 'warning'
  if (score > 0) return 'danger'
  return 'info'
}
function relevanceLevel(score: number): 'high' | 'mid' | 'low' | 'none' {
  if (score == null) return 'none'
  if (score >= 75) return 'high'
  if (score >= 55) return 'mid'
  if (score > 0) return 'low'
  return 'none'
}
function relevanceLevelText(score: number) {
  switch (relevanceLevel(score)) {
    case 'high': return '高相关'
    case 'mid': return '中相关'
    case 'low': return '低相关'
    default: return '无关'
  }
}

const filteredKeywords = computed<Keyword[]>(() => {
  let arr = allKeywords.value
  if (filters.topic_id) arr = arr.filter(k => k.topic_id === filters.topic_id)
  return [...arr].sort((a, b) => b.weight - a.weight)
})

// 客户端关键词/语言过滤（后端 /data 仅支持 source_name 过滤）
const displayItems = computed(() => {
  let list = items.value
  if (filters.language) {
    list = list.filter((i) => i.language === filters.language)
  }
  if (filters.keyword) {
    const kw = filters.keyword.toLowerCase()
    list = list.filter(
      (i) =>
        i.title?.toLowerCase().includes(kw) ||
        i.content?.toLowerCase().includes(kw) ||
        i.summary?.toLowerCase().includes(kw),
    )
  }
  return list
})

// 统计卡片
const filteredCount = computed(() => displayItems.value.length)
const zhCount = computed(() => displayItems.value.filter((i) => i.language === 'zh').length)
const enCount = computed(() => displayItems.value.filter((i) => i.language === 'en').length)

function formatTime(s: string | null) {
  if (!s) return '-'
  return s.replace('T', ' ').split('.')[0]
}

async function loadSources() {
  sources.value = await listSources()
}
async function loadTopics() {
  topics.value = await listTopics(true)
  allKeywords.value = await listKeywords(undefined, true)
}

async function loadData() {
  loading.value = true
  try {
    const res = await queryData({
      source_name: filters.source_name || undefined,
      topic_id: filters.topic_id,
      keyword_id: filters.keyword_id,
      limit: page.size,
      offset: (page.current - 1) * page.size,
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function resetAndLoad() {
  page.current = 1
  loadData()
}

function onTopicChange() {
  // 切换主题时清空与之冲突的关键词选择（若所选关键词不在该主题下）
  if (filters.keyword_id) {
    const kw = allKeywords.value.find(k => k.id === filters.keyword_id)
    if (kw && filters.topic_id && kw.topic_id !== filters.topic_id) {
      filters.keyword_id = undefined
    }
  }
  resetAndLoad()
}

function onReset() {
  filters.source_name = ''
  filters.topic_id = undefined
  filters.keyword_id = undefined
  filters.keyword = ''
  filters.language = ''
  resetAndLoad()
}

function openDetail(row: DataItem) {
  currentItem.value = row
  detailVisible.value = true
}

onMounted(async () => {
  await Promise.all([loadSources(), loadTopics()])
  await loadData()
})
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

.stat-icon--blue {
  background: rgba(59, 130, 246, 0.1);
  color: var(--dg-blue);
}

/* 主卡片 */
.main-card :deep(.el-card__body) {
  padding: 0;
}

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

.title-cell {
  cursor: pointer;
}

.title {
  font-weight: 600;
  color: var(--dg-text-bright);
  display: block;
  margin-bottom: 4px;
  transition: color var(--dg-transition);
}

.title-cell:hover .title {
  color: var(--dg-cyan-dim);
}

.meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.time {
  color: var(--dg-text-muted);
  font-size: 12px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  padding: 16px 20px;
}

/* 详情抽屉 */
.detail {
  padding: 0 4px;
}

.section {
  margin-top: 24px;
}

.section-title {
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--dg-text-bright);
  border-left: 3px solid var(--dg-cyan);
  padding-left: 10px;
  font-size: 14px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.content-text {
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--dg-text-secondary);
  background: var(--dg-bg);
  padding: 16px 18px;
  border-radius: var(--dg-radius-sm);
  border-left: 3px solid var(--dg-cyan);
  max-height: 360px;
  overflow-y: auto;
  font-size: 14px;
}

.opt-dot { width: 8px; height: 8px; border-radius: 2px; display: inline-block; flex-shrink: 0; }
.muted { color: var(--dg-text-muted); font-size: 12px; }

.hit-row {
  margin-top: 6px;
  display: flex; flex-wrap: wrap; gap: 5px; align-items: center;
}
.hit-tag { margin-right: 0 !important; font-size: 11px !important; }
.topic-tag {
  font-weight: 600;
  letter-spacing: 0.3px;
  border-radius: 999px !important;
  padding: 0 8px !important;
}
.kw-tag {
  position: relative;
  color: var(--dg-cyan);
  border-color: rgba(0,229,255,0.35) !important;
  background: rgba(0,229,255,0.06) !important;
  padding-left: 26px !important;
}
.kw-tag .hit-w-badge {
  position: absolute; left: 0; top: 50%; transform: translateY(-50%);
  display: inline-flex; align-items: center; justify-content: center;
  height: 100%; padding: 0 5px;
  background: rgba(0,229,255,0.2); color: var(--dg-cyan);
  font-style: normal; font-weight: 700; font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  border-right: 1px solid rgba(0,229,255,0.3);
}
.kw-tag-detail {
  color: var(--dg-cyan);
  border-color: rgba(0,229,255,0.35);
  background: rgba(0,229,255,0.06);
}
.kw-tag-detail i {
  font-style: normal; font-weight: 700; font-size: 11px;
  background: rgba(0,229,255,0.18);
  padding: 1px 5px; border-radius: 4px; margin-right: 4px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--dg-cyan);
}

/* 匹配类型徽章 (Query Expansion) */
.match-variant {
  margin-left: 6px; padding: 0 6px; border-radius: 3px;
  background: rgba(179,127,235,0.15); color: #b37feb;
  font-size: 10px; font-weight: 600;
  border: 1px solid rgba(179,127,235,0.4);
}
.match-variant.small { font-size: 11px; }
.match-direct {
  margin-left: 6px; padding: 0 6px; border-radius: 3px;
  background: rgba(82,196,26,0.18); color: #52c41a;
  font-size: 10px; font-weight: 700;
  border: 1px solid rgba(82,196,26,0.45);
}
.match-direct.small { font-size: 11px; }

/* 相关性列 */
.rel-col { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.km-badge {
  background: rgba(19,194,194,0.18);
  color: #13c2c2;
  padding: 1px 5px; border-radius: 4px;
  font-size: 11px; font-weight: 700;
  border: 1px solid rgba(19,194,194,0.45);
}

/* 相关性面板 */
.relevance-panel { display: flex; flex-direction: column; gap: 16px; }
.rel-score {
  display: flex; align-items: center; gap: 24px;
  padding: 16px; border-radius: 12px;
  background: linear-gradient(135deg, rgba(20,25,36,0.6), rgba(20,25,36,0.3));
  border: 1px solid rgba(64,158,255,0.18);
}
.score-circle {
  width: 108px; height: 108px; border-radius: 50%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: radial-gradient(circle at 50% 50%, rgba(64,158,255,0.25), rgba(64,158,255,0.05));
  border: 3px solid rgba(64,158,255,0.35);
  color: #cdd2db;
}
.score-circle.score-high {
  background: radial-gradient(circle at 50% 50%, rgba(82,196,26,0.3), rgba(82,196,26,0.05));
  border-color: rgba(82,196,26,0.6); color: #67C23A;
}
.score-circle.score-mid {
  background: radial-gradient(circle at 50% 50%, rgba(230,162,60,0.28), rgba(230,162,60,0.05));
  border-color: rgba(230,162,60,0.6); color: #E6A23C;
}
.score-circle.score-low {
  background: radial-gradient(circle at 50% 50%, rgba(245,108,108,0.25), rgba(245,108,108,0.05));
  border-color: rgba(245,108,108,0.5); color: #F56C6C;
}
.score-circle.score-none {
  background: rgba(42,49,66,0.5); border-color: rgba(120,126,146,0.4); color: #878f9e;
}
.score-num { font-size: 38px; font-weight: 800; line-height: 1; font-family: 'JetBrains Mono', monospace; }
.score-denom { font-size: 11px; margin-top: 4px; opacity: 0.7; }
.score-descs { display: flex; flex-direction: column; gap: 8px; font-size: 13px; color: #cdd2db; }
:deep(.el-collapse) {
  --el-collapse-border-color: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px; overflow: hidden;
  background: rgba(20,25,36,0.5);
}
:deep(.el-collapse-item__header) {
  background: rgba(64,158,255,0.08) !important;
  color: #cdd2db !important;
  padding: 0 14px; border-bottom: none !important;
  font-size: 12px !important; font-weight: 600;
}
:deep(.el-collapse-item__wrap) { background: rgba(20,25,36,0.3); border-bottom: none; }
.reason-box {
  margin: 0; padding: 14px;
  white-space: pre-wrap; word-break: break-all;
  font-size: 12.5px; line-height: 1.75;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  color: #cdd2db; background: rgba(0,0,0,0.3);
  border-radius: 6px;
}
.muted { color: #878f9e; font-weight: 400; }
</style>
