<template>
  <div class="dashboard-page">
    <el-tabs v-model="activeTab" class="monitor-tabs">
      <!-- ============ Tab 1: 实时看板 ============ -->
      <el-tab-pane label="实时看板" name="dashboard" lazy>
        <div class="board" v-loading="loading.summary">
          <!-- 空状态引导 -->
          <div v-if="isEmpty" class="empty-hero">
            <div class="empty-icon"><el-icon :size="48"><DataAnalysis /></el-icon></div>
            <h2 class="empty-title">暂无监控数据</h2>
            <p class="empty-desc">看板会在爬取任务产生数据后自动填充。你可以：</p>
            <div class="empty-actions">
              <el-button type="primary" :icon="Download" @click="$router.push('/app/scrape')">去爬取数据</el-button>
              <el-button :icon="RefreshRight" :loading="recalcing" @click="recalc">重算历史分析</el-button>
            </div>
            <p class="empty-hint">当前已配置 <strong>{{ summary.keywords_total }}</strong> 个监控热点词，等待数据入库后即可看到趋势与告警</p>
          </div>

          <template v-else>
            <!-- 仪表盘行：核心健康度一目了然 -->
            <div class="gauge-row">
              <div v-for="g in gauges" :key="g.name" class="gauge-card">
                <v-chart class="chart-gauge" :option="gaugeOption(g)" autoresize />
                <div class="gauge-label">{{ g.name }}</div>
                <div class="gauge-hint">{{ g.hint }}</div>
              </div>
            </div>

            <!-- 统计卡 -->
            <div class="bento-stats">
              <div v-for="card in statCards" :key="card.label" class="stat-card" :class="card.class">
                <div class="stat-icon" :style="{ background: card.color }">
                  <el-icon :size="22"><component :is="card.icon" /></el-icon>
                </div>
                <div class="stat-body">
                  <div class="stat-value">{{ formatNum(card.value) }}</div>
                  <div class="stat-label">{{ card.label }}</div>
                  <div v-if="card.hint" class="stat-hint">{{ card.hint }}</div>
                </div>
              </div>
            </div>

            <!-- Bento 网格：趋势 + Top关键词 -->
            <div class="bento-grid">
              <div class="bento trend">
                <div class="bento-head">
                  <div>
                    <h4 class="bento-title">关键词词频趋势</h4>
                    <div class="bento-sub">近 7 天 · 小时级 · 可多选对比</div>
                  </div>
                  <el-select
                    v-model="trendKeywordIds" multiple collapse-tags collapse-tags-tooltip
                    placeholder="选择热点词（最多 6 个）" style="width: 340px"
                    :multiple-limit="6" filterable
                  >
                    <el-option
                      v-for="k in allKeywordsOpts" :key="k.keyword_id"
                      :label="k.word" :value="k.keyword_id"
                    >
                      <span class="opt-row">
                        <strong>{{ k.word }}</strong>
                        <span class="opt-cnt">{{ k.article_cnt }} 篇</span>
                      </span>
                    </el-option>
                  </el-select>
                </div>
                <v-chart class="chart chart-trend" :option="trendOption" autoresize />
              </div>

              <div class="bento topkw">
                <div class="bento-head">
                  <div>
                    <h4 class="bento-title">命中排行 TOP {{ topLimit }}</h4>
                    <div class="bento-sub">近 {{ hours }} 小时</div>
                  </div>
                  <el-select v-model="topLimit" style="width: 110px" @change="refreshCharts">
                    <el-option label="TOP 10" :value="10" />
                    <el-option label="TOP 20" :value="20" />
                    <el-option label="TOP 30" :value="30" />
                  </el-select>
                </div>
                <v-chart class="chart chart-topkw" :option="topKwOption" autoresize />
              </div>
            </div>

            <!-- 小时入库节奏 -->
            <div class="bento full">
              <div class="bento-head">
                <div>
                  <h4 class="bento-title">入库节奏</h4>
                  <div class="bento-sub">每小时新增文章数，直观反映调度任务触发情况</div>
                </div>
                <el-radio-group v-model="hours" size="default" @change="refreshCharts">
                  <el-radio-button :value="24">24h</el-radio-button>
                  <el-radio-button :value="72">72h</el-radio-button>
                  <el-radio-button :value="168">7d</el-radio-button>
                </el-radio-group>
              </div>
              <v-chart class="chart chart-hourly" :option="hourlyOption" autoresize />
            </div>

            <!-- 热点事件 -->
            <div class="bento full">
              <div class="bento-head">
                <div>
                  <h4 class="bento-title">
                    热点突发告警
                    <el-tag v-if="unreadCount" type="danger" effect="dark" style="margin-left:8px" round>{{ unreadCount }} 未读</el-tag>
                  </h4>
                  <div class="bento-sub">热点词提及量显著高于 7 天基线时触发</div>
                </div>
                <div class="filter-bar">
                  <el-select v-model="eventFilter.level" placeholder="级别" clearable style="width:120px" @change="refreshEvents">
                    <el-option label="低 (≥3x)" value="low" />
                    <el-option label="中 (≥5x)" value="mid" />
                    <el-option label="高 (≥10x)" value="high" />
                  </el-select>
                  <el-checkbox v-model="eventFilter.only_unread" @change="refreshEvents">仅未读</el-checkbox>
                  <el-button type="primary" plain size="small" :icon="Check" :disabled="!unreadCount" @click="readAll">全部已读</el-button>
                </div>
              </div>

              <el-table :data="events" v-loading="eventLoading" stripe empty-text="暂无告警事件">
                <el-table-column label="级别" width="100" align="center">
                  <template #default="{ row }">
                    <el-tag :type="levelTag(row.level)" effect="dark" round>{{ levelText(row.level) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="热点词" min-width="200">
                  <template #default="{ row }">
                    <strong v-if="row.keyword_word" class="kw-hit">{{ row.keyword_word }}</strong>
                    <span v-else class="muted">（聚合）</span>
                  </template>
                </el-table-column>
                <el-table-column label="窗口时间" width="220">
                  <template #default="{ row }">
                    <div class="time-col">
                      <div>{{ formatTime(row.window_start) }} ~</div>
                      <div class="muted">{{ formatTime(row.window_end) }}</div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="文章" width="90" align="right">
                  <template #default="{ row }"><strong class="num">{{ row.article_cnt }}</strong></template>
                </el-table-column>
                <el-table-column label="基线" width="100" align="right">
                  <template #default="{ row }"><span class="muted">{{ row.baseline.toFixed(1) }}</span></template>
                </el-table-column>
                <el-table-column label="倍率" width="100" align="right">
                  <template #default="{ row }">
                    <strong class="ratio" :class="row.level">× {{ row.ratio.toFixed(1) }}</strong>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="90" align="center">
                  <template #default="{ row }">
                    <el-tag v-if="row.is_read" type="info" effect="plain" size="small">已读</el-tag>
                    <el-tag v-else type="warning" effect="dark" size="small">未读</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right" align="center">
                  <template #default="{ row }">
                    <el-button v-if="!row.is_read" link type="primary" size="small" @click="readOne(row.id)">标已读</el-button>
                  </template>
                </el-table-column>
              </el-table>

              <div class="pager">
                <el-pagination
                  background layout="total, prev, pager, next"
                  :total="eventTotal" :page-size="eventPage.limit"
                  :current-page="eventPage.offset / eventPage.limit + 1"
                  @current-change="onEventPageChange"
                />
              </div>
            </div>
          </template>
        </div>
      </el-tab-pane>

      <!-- ============ Tab 2: 热点关键词 ============ -->
      <el-tab-pane label="热点关键词" name="keywords" lazy>
        <TopicsView />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  Warning, Document, Connection, DataAnalysis, Check,
  Download, RefreshRight,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart, GaugeChart } from 'echarts/charts'
import {
  GridComponent, TitleComponent, TooltipComponent, LegendComponent, DatasetComponent,
} from 'echarts/components'
use([CanvasRenderer, BarChart, LineChart, GaugeChart, GridComponent, TitleComponent, TooltipComponent, LegendComponent, DatasetComponent])

import {
  getDashboardSummary, getKeywordTrend, getTopKeywords,
  getHourlyArticles, listEvents, markEventsRead, recalcHistory,
} from '@/api/analytics'
import { listKeywords } from '@/api/topics'
import type {
  Keyword, DashboardSummary, HotspotEvent, HotspotLevel,
  TopKeywordRow, HourlyArticleBucket, KeywordTrendSeries,
} from '@/types'
import TopicsView from './TopicsView.vue'

// ============ 基础状态 ============
const activeTab = ref<'dashboard' | 'keywords'>('dashboard')
const hours = ref(168)  // 默认7天，覆盖更广时间窗口
const topLimit = ref(20)
const loading = reactive({ summary: false, trend: false, hourly: false, top: false })
const eventLoading = ref(false)
const recalcing = ref(false)

const summary = ref<DashboardSummary>({
  today_events: 0, unread_events: 0, articles_24h: 0, active_topics: 0,
  keywords_total: 0, high_level_events: 0, top_keywords: [], topic_distribution: [],
})
const allKeywords = ref<Keyword[]>([])

const isEmpty = computed(() =>
  summary.value.articles_24h === 0 &&
  summary.value.scored_grabs === 0 &&
  summary.value.keywords_total === 0
)

// 关键词选项（趋势选择器 + Top 备选）
const allKeywordsOpts = computed<Array<TopKeywordRow & { article_cnt: number }>>(() => {
  const map = new Map<number, any>()
  for (const row of summary.value.top_keywords) map.set(row.keyword_id, { ...row })
  for (const kw of allKeywords.value) {
    if (!map.has(kw.id)) {
      map.set(kw.id, { keyword_id: kw.id, word: kw.word, article_cnt: 0, hit_cnt: 0 })
    }
  }
  return Array.from(map.values())
})

// 统计卡（去主题维度）
const statCards = computed(() => {
  const s = summary.value
  const thr = s.relevance_threshold ?? 55
  const hr = s.high_relevance_rate ?? 0
  const km = s.keyword_mentioned_rate ?? 0
  const enabledKw = allKeywords.value.filter(k => k.enabled).length
  return [
    { label: '今日热点事件', value: s.today_events,
      hint: `高风险 ${s.high_level_events} · 未读 ${s.unread_events}`,
      icon: Warning, color: 'linear-gradient(135deg,#F56C6C,#E74C3C)', class: 'card-danger' },
    { label: '近 24h 新增文章', value: s.articles_24h,
      hint: `已评分 ${s.scored_grabs ?? 0} · 锚点覆盖 ${(km * 100).toFixed(0)}%`,
      icon: Document, color: 'linear-gradient(135deg,#409EFF,#2962FF)', class: 'card-primary' },
    { label: '监控热点词', value: s.keywords_total,
      hint: `启用 ${enabledKw} · 带变体 ${allKeywords.value.filter(k => k.variants && k.variants.length).length}`,
      icon: Connection, color: 'linear-gradient(135deg,#E6A23C,#F39C12)', class: 'card-warning' },
    { label: '高相关篇数', value: s.high_relevance_grabs ?? 0,
      hint: `≥${thr}分 / 共 ${s.scored_grabs ?? 0} 篇`,
      icon: DataAnalysis, color: 'linear-gradient(135deg,#52C41A,#237804)', class: 'card-success' },
  ]
})

// ============ 仪表盘 Gauge ============
const gauges = computed(() => {
  const s = summary.value
  const hr = Math.round((s.high_relevance_rate ?? 0) * 100)
  const km = Math.round((s.keyword_mentioned_rate ?? 0) * 100)
  const avg = Math.round(s.avg_relevance_score_scored ?? 0)
  // 数据活跃度：24h文章数映射到0-100（50篇=满分）
  const active = Math.min(100, Math.round(((s.articles_24h ?? 0) / 50) * 100))
  return [
    { name: '高相关率', value: hr, max: 100, unit: '%', hint: `≥${s.relevance_threshold ?? 55}分 ${s.high_relevance_grabs ?? 0}/${s.scored_grabs ?? 0}` },
    { name: '锚点覆盖率', value: km, max: 100, unit: '%', hint: `直接提及 ${s.keyword_mentioned_true ?? 0}/${s.scored_grabs ?? 0}` },
    { name: '平均评分', value: avg, max: 100, unit: '', hint: `已评分 ${s.scored_grabs ?? 0} 篇` },
    { name: '数据活跃度', value: active, max: 100, unit: '%', hint: `24h新增 ${s.articles_24h ?? 0} 篇` },
  ]
})

function gaugeOption(g: { name: string; value: number; max: number; unit: string }) {
  // 颜色区间：<40红 / 40-70黄 / ≥70绿
  const val = g.value
  let color = '#52C41A'
  if (val < 40) color = '#F56C6C'
  else if (val < 70) color = '#E6A23C'
  return {
    series: [{
      type: 'gauge',
      startAngle: 200,
      endAngle: -20,
      min: 0,
      max: g.max,
      progress: {
        show: true,
        width: 14,
        roundCap: true,
        itemStyle: { color },
      },
      axisLine: {
        lineStyle: { width: 14, color: [[1, 'rgba(255,255,255,0.08)']] },
      },
      pointer: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      anchor: { show: false },
      detail: {
        valueAnimation: true,
        formatter: '{value}' + g.unit,
        fontSize: 22,
        fontWeight: 700,
        color: '#e6e8eb',
        offsetCenter: [0, '0%'],
      },
      title: { show: false },
      data: [{ value: val }],
    }],
  }
}

function countByLang(l: string) {
  return allKeywords.value.filter(k => k.language === l && k.enabled).length
}
function formatNum(n: string | number) {
  if (typeof n === 'string') return n
  if (n >= 10000) return (n / 10000).toFixed(1) + 'w'
  return n.toLocaleString()
}

// ============ 趋势折线 ============
const trendKeywordIds = ref<number[]>([])
const trendSeries = ref<KeywordTrendSeries[]>([])
watch(trendKeywordIds, loadTrend, { deep: false })
async function loadTrend() {
  if (!trendKeywordIds.value.length) { trendSeries.value = []; return }
  loading.trend = true
  try {
    trendSeries.value = await getKeywordTrend(trendKeywordIds.value, 'hour', 7)
  } finally { loading.trend = false }
}
const trendOption = computed(() => {
  const colors = ['#00E5FF', '#F56C6C', '#67C23A', '#E6A23C', '#B37FEB', '#409EFF']
  return {
    grid: { left: 48, right: 24, top: 48, bottom: 48 },
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(20,25,36,0.95)', borderColor: '#1C2333', textStyle: { color: '#e6e8eb' } },
    legend: { data: trendSeries.value.map(s => s.word || ('kw' + s.keyword_id)), top: 0, textStyle: { color: '#a9b0bd' } },
    xAxis: { type: 'category', data: trendSeries.value[0]?.points.map(p => p.time_bucket) || [],
      axisLabel: { color: '#7a8190', fontSize: 11 }, axisLine: { lineStyle: { color: '#2a3142' } } },
    yAxis: { type: 'value', axisLabel: { color: '#7a8190' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
    series: trendSeries.value.map((s, i) => ({
      name: s.word || ('kw' + s.keyword_id), type: 'line', smooth: true,
      data: s.points.map(p => p.article_cnt), lineStyle: { color: colors[i % 6] },
      itemStyle: { color: colors[i % 6] }, symbolSize: 6,
    })),
  }
})

// ============ Top 关键词柱图 ============
const topKeywords = ref<TopKeywordRow[]>([])
const topKwOption = computed(() => ({
  grid: { left: 8, right: 24, top: 16, bottom: 8, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(20,25,36,0.95)', borderColor: '#1C2333', textStyle: { color: '#e6e8eb' } },
  xAxis: { type: 'value', axisLabel: { color: '#7a8190' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
  yAxis: { type: 'category', data: topKeywords.value.map(k => k.word).reverse(),
    axisLabel: { color: '#a9b0bd', fontSize: 12 }, axisLine: { lineStyle: { color: '#2a3142' } } },
  series: [{
    type: 'bar', data: topKeywords.value.map(k => k.article_cnt).reverse(),
    barMaxWidth: 18, itemStyle: {
      color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [{ offset: 0, color: '#00E5FF' }, { offset: 1, color: '#2962FF' }] },
      borderRadius: [0, 4, 4, 0],
    },
    label: { show: true, position: 'right', color: '#a9b0bd', fontSize: 11 },
  }],
}))

// ============ 小时入库 ============
const hourly = ref<HourlyArticleBucket[]>([])
const hourlyOption = computed(() => ({
  grid: { left: 48, right: 24, top: 24, bottom: 48 },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: 'rgba(20,25,36,0.95)', borderColor: '#1C2333', textStyle: { color: '#e6e8eb' } },
  xAxis: { type: 'category', data: hourly.value.map(h => h.bucket),
    axisLabel: { color: '#7a8190', fontSize: 11 }, axisLine: { lineStyle: { color: '#2a3142' } } },
  yAxis: { type: 'value', axisLabel: { color: '#7a8190' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
  series: [{
    type: 'bar', data: hourly.value.map(h => h.cnt), barMaxWidth: 24,
    itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
      colorStops: [{ offset: 0, color: '#00E5FF' }, { offset: 1, color: '#0a3a4a' }] }, borderRadius: [4, 4, 0, 0] },
  }],
}))

// ============ 热点事件 ============
const events = ref<HotspotEvent[]>([])
const eventTotal = ref(0)
const unreadCount = ref(0)
const eventFilter = reactive<{ level: string; only_unread: boolean }>({ level: '', only_unread: false })
const eventPage = reactive({ limit: 20, offset: 0 })

async function refreshEvents() {
  eventLoading.value = true
  try {
    const res = await listEvents({
      level: (eventFilter.level || undefined) as HotspotLevel | undefined,
      only_unread: eventFilter.only_unread || undefined,
      limit: eventPage.limit, offset: eventPage.offset,
    })
    events.value = res.items
    eventTotal.value = res.total
    unreadCount.value = summary.value.unread_events
  } finally { eventLoading.value = false }
}
function onEventPageChange(p: number) { eventPage.offset = (p - 1) * eventPage.limit; refreshEvents() }
async function readOne(id: number) { await markEventsRead([id], false); await refreshEvents(); await refreshSummary() }
async function readAll() { await markEventsRead([], true); ElMessage.success('已全部标记已读'); await refreshEvents(); await refreshSummary() }

// ============ 加载 ============
async function refreshSummary() {
  loading.summary = true
  try { summary.value = await getDashboardSummary(hours.value) } finally { loading.summary = false }
}
async function refreshCharts() {
  loading.hourly = true; loading.top = true
  try {
    const [h, t] = await Promise.all([
      getHourlyArticles(hours.value), getTopKeywords(hours.value, topLimit.value),
    ])
    hourly.value = h
    topKeywords.value = t
  } finally { loading.hourly = false; loading.top = false }
  await refreshSummary()
}

async function recalc() {
  recalcing.value = true
  try {
    await recalcHistory({ start: '', end: '' })
    ElMessage.success('重算完成')
    await refreshSummary()
    await refreshCharts()
    await refreshEvents()
  } catch { ElMessage.error('重算失败') } finally { recalcing.value = false }
}

async function initialLoad() {
  allKeywords.value = await listKeywords(undefined, true)
  await refreshSummary()
  if (!isEmpty.value) {
    await refreshCharts()
    await refreshEvents()
    // 默认加载 Top 5 关键词趋势（无需手动选择即可看到趋势）
    const top5 = summary.value.top_keywords.slice(0, 5).map(k => k.keyword_id)
    if (top5.length) {
      trendKeywordIds.value = top5
    }
  }
}
onMounted(initialLoad)

// ============ 工具 ============
function levelTag(l: string): any { return ({ high: 'danger', mid: 'warning', low: 'info' } as any)[l] || '' }
function levelText(l: string) { return ({ high: '高', mid: '中', low: '低' } as any)[l] || l }
function formatTime(iso: string) {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.dashboard-page { color: var(--dg-text-primary); }
.board { display: flex; flex-direction: column; gap: 16px; }

/* 空状态 */
.empty-hero {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 16px; padding: 72px 24px; text-align: center;
  background: var(--dg-surface); border: 1px solid var(--dg-border);
  border-radius: 16px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
}
.empty-icon { color: var(--dg-cyan); opacity: .7; animation: float 3s ease-in-out infinite; }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
.empty-title { margin: 0; font-size: 22px; font-weight: 700; color: var(--dg-text-bright); }
.empty-desc { margin: 0; color: var(--dg-text-muted); font-size: 14px; }
.empty-actions { display: flex; gap: 12px; margin-top: 8px; }
.empty-hint { margin: 12px 0 0; font-size: 13px; color: var(--dg-text-dim); }
.empty-hint strong { color: var(--dg-cyan); }

/* 统计卡 */
.bento-stats {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
}

/* 仪表盘 Gauge 行 */
.gauge-row {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
}
.gauge-card {
  background: var(--dg-surface); border: 1px solid var(--dg-border);
  border-radius: 12px; padding: 16px 12px 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.25);
  display: flex; flex-direction: column; align-items: center;
  transition: transform .2s ease, box-shadow .2s ease;
}
.gauge-card:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0,0,0,0.35); }
.chart-gauge { width: 100%; height: 150px; min-height: 150px; }
.gauge-label { font-size: 13px; font-weight: 600; color: var(--dg-text-bright); margin-top: 4px; }
.gauge-hint { font-size: 11px; color: var(--dg-text-dim); margin-top: 2px; text-align: center; }
.stat-card {
  display: flex; align-items: center; gap: 14px; padding: 18px 20px;
  background: var(--dg-surface); border: 1px solid var(--dg-border);
  border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
  position: relative; overflow: hidden; transition: transform .2s ease, box-shadow .2s ease;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(0,0,0,0.35); }
.stat-icon {
  width: 48px; height: 48px; border-radius: 12px; color: #fff;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 16px rgba(0,0,0,0.3); flex-shrink: 0;
}
.stat-body { flex: 1; min-width: 0; }
.stat-value { font-size: 24px; font-weight: 700; color: var(--dg-text-bright); line-height: 1.1; }
.stat-label { font-size: 12px; color: var(--dg-text-muted); margin-top: 4px; }
.stat-hint { font-size: 11px; color: var(--dg-text-dim); margin-top: 2px; }

/* Bento 网格 */
.bento-grid {
  display: grid; grid-template-columns: 2fr 1fr; gap: 16px;
}
.bento {
  background: var(--dg-surface); border: 1px solid var(--dg-border);
  border-radius: 12px; padding: 18px 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.25);
}
.bento.full { grid-column: 1 / -1; }
.bento-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  margin-bottom: 14px; gap: 12px;
}
.bento-title { margin: 0; font-size: 15px; font-weight: 600; color: var(--dg-text-bright); }
.bento-sub { font-size: 12px; color: var(--dg-text-muted); margin-top: 3px; }
.filter-bar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.opt-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; }
.opt-cnt { font-size: 12px; color: var(--dg-text-dim); }

/* chart */
.chart { width: 100%; }
.chart-trend { height: 320px; min-height: 320px; }
.chart-topkw { height: 320px; min-height: 320px; }
.chart-hourly { height: 240px; min-height: 240px; }

.kw-hit { color: var(--dg-cyan); font-family: 'JetBrains Mono', monospace; }
.muted { color: var(--dg-text-muted); font-size: 12px; }
.time-col { font-size: 12px; line-height: 1.5; }
.num { color: var(--dg-text-bright); font-family: 'JetBrains Mono', monospace; }
.ratio { font-family: 'JetBrains Mono', monospace; }
.ratio.high { color: #F56C6C; }
.ratio.mid { color: #E6A23C; }
.ratio.low { color: #909399; }
.pager { display: flex; justify-content: flex-end; padding: 12px 0 0; }

@media (max-width: 1100px) {
  .gauge-row { grid-template-columns: repeat(2, 1fr); }
  .bento-stats { grid-template-columns: repeat(2, 1fr); }
  .bento-grid { grid-template-columns: 1fr; }
}
</style>
