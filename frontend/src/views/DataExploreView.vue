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
          style="width: 200px"
          @change="resetAndLoad"
        >
          <el-option
            v-for="s in sources"
            :key="s.name"
            :label="s.name"
            :value="s.name"
          />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="标题 / 正文搜索"
          clearable
          style="width: 240px"
          :prefix-icon="Search"
          @keyup.enter="resetAndLoad"
          @clear="resetAndLoad"
        />
        <el-select
          v-model="filters.language"
          placeholder="全部语言"
          clearable
          style="width: 130px"
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
        <el-table-column label="标题" min-width="280">
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
            </div>
          </template>
        </el-table-column>
        <el-table-column label="摘要" min-width="320" show-overflow-tooltip>
          <template #default="{ row }: { row: any }">
            <span class="dg-muted">{{ row.summary || row.content?.slice(0, 100) || '-' }}</span>
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
import type { SourceInfo, DataItem } from '@/types'

const sources = ref<SourceInfo[]>([])
const items = ref<DataItem[]>([])
const loading = ref(false)
const total = ref(0)

const filters = reactive({
  source_name: '',
  keyword: '',
  language: '',
})

const page = reactive({
  current: 1,
  size: 20,
})

const detailVisible = ref(false)
const currentItem = ref<DataItem | null>(null)

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

async function loadData() {
  loading.value = true
  try {
    const res = await queryData({
      source_name: filters.source_name || undefined,
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

function onReset() {
  filters.source_name = ''
  filters.keyword = ''
  filters.language = ''
  resetAndLoad()
}

function openDetail(row: DataItem) {
  currentItem.value = row
  detailVisible.value = true
}

onMounted(async () => {
  await loadSources()
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

/* 主卡片 */
.main-card :deep(.el-card__body) {
  padding: 0;
}

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

.title-cell {
  cursor: pointer;
}

.title {
  font-weight: 600;
  color: var(--dg-text);
  display: block;
  margin-bottom: 4px;
  transition: color var(--dg-transition);
}

.title-cell:hover .title {
  color: var(--dg-emerald-dark);
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
  color: var(--dg-text);
  border-left: 3px solid var(--dg-emerald);
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
  color: var(--dg-text);
  background: var(--dg-bg);
  padding: 16px 18px;
  border-radius: var(--dg-radius-sm);
  border-left: 3px solid var(--dg-emerald);
  max-height: 360px;
  overflow-y: auto;
  font-size: 14px;
}
</style>
