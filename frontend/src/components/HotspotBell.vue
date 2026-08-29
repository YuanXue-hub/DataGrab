<template>
  <el-popover
    placement="bottom-end"
    :width="380"
    trigger="click"
    popper-class="hotspot-bell-popover"
    @show="onPopoverShow"
  >
    <template #reference>
      <button class="bell-btn" :class="{ hasunread: unreadCount > 0 }">
        <el-badge :value="unreadCount" :max="99" :hidden="unreadCount === 0">
          <el-icon :size="20"><Bell /></el-icon>
        </el-badge>
      </button>
    </template>

    <div class="bell-panel">
      <div class="bell-head">
        <span class="bell-title">热点告警通知</span>
        <span class="bell-count" v-if="unreadCount > 0">{{ unreadCount }} 条未读</span>
      </div>

      <div class="bell-list" v-loading="loading">
        <div v-if="!loading && events.length === 0" class="bell-empty">
          <el-icon :size="28"><Select /></el-icon>
          <span>暂无未读告警</span>
        </div>

        <div
          v-for="ev in events"
          :key="ev.id"
          class="bell-item"
        >
          <span class="lvl-dot" :style="{ background: levelColor(ev.level) }"></span>
          <div class="item-main">
            <div class="item-top">
              <span class="item-kw">{{ ev.keyword_word || '—' }}</span>
              <span class="item-ratio">×{{ ev.ratio }}</span>
            </div>
            <div class="item-meta">
              <el-tag size="small" effect="plain" :style="{ color: levelColor(ev.level) }">
                {{ levelText(ev.level) }} · {{ ev.article_cnt }}篇
              </el-tag>
              <span class="item-time">{{ formatTime(ev.created_at) }}</span>
            </div>
          </div>
          <el-button
            link size="small" type="primary"
            @click="markOne(ev.id)"
          >已读</el-button>
        </div>
      </div>

      <div class="bell-foot">
        <el-button
          size="small" :disabled="unreadCount === 0"
          @click="markAll"
        >全部已读</el-button>
        <el-button size="small" @click="goMonitor">查看看板</el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Select } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { listEvents, markEventsRead } from '@/api/analytics'
import type { HotspotEvent, HotspotLevel } from '@/types'

const router = useRouter()
const unreadCount = ref(0)
const events = ref<HotspotEvent[]>([])
const loading = ref(false)

let timer: number | undefined

async function loadUnread() {
  try {
    const res = await listEvents({ only_unread: true, limit: 10 })
    events.value = res.items
    unreadCount.value = res.total
  } catch {
    /* 静默失败，不打扰用户 */
  }
}

async function onPopoverShow() {
  loading.value = true
  await loadUnread()
  loading.value = false
}

async function markOne(id: number) {
  try {
    await markEventsRead([id], false)
    await loadUnread()
  } catch {
    ElMessage.error('标记失败')
  }
}

async function markAll() {
  try {
    await markEventsRead([], true)
    ElMessage.success('已全部标记为已读')
    await loadUnread()
  } catch {
    ElMessage.error('标记失败')
  }
}

function goMonitor() {
  router.push('/app/monitor')
}

function levelColor(lvl: HotspotLevel) {
  return lvl === 'high' ? '#f56c6c' : lvl === 'mid' ? '#e6a23c' : '#f0c029'
}
function levelText(lvl: HotspotLevel) {
  return ({ high: '高级', mid: '中级', low: '低级' } as const)[lvl]
}

function formatTime(iso: string) {
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const now = Date.now()
  const diff = now - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  loadUnread()
  timer = window.setInterval(loadUnread, 30000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.bell-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--dg-border);
  border-radius: 8px;
  background: var(--dg-surface-2);
  cursor: pointer;
  color: var(--dg-text-secondary);
  transition: all 180ms ease;
}
.bell-btn:hover {
  color: var(--dg-cyan);
  border-color: var(--dg-cyan-dim);
  background: var(--dg-sidebar-hover);
  box-shadow: 0 0 12px rgba(0, 240, 255, 0.15);
}
.bell-btn.hasunread {
  color: var(--dg-warning, #e6a23c);
  border-color: rgba(230, 162, 60, 0.4);
}
</style>

<style>
.hotspot-bell-popover.el-popover.el-popper {
  padding: 0 !important;
  background: var(--dg-surface) !important;
  border: 1px solid var(--dg-border) !important;
}
</style>

<style scoped>
.bell-panel {
  display: flex;
  flex-direction: column;
  max-height: 460px;
}
.bell-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--dg-border);
}
.bell-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--dg-text-bright);
}
.bell-count {
  font-size: 12px;
  color: var(--dg-warning, #e6a23c);
  font-family: 'JetBrains Mono', monospace;
}
.bell-list {
  flex: 1;
  overflow-y: auto;
  min-height: 80px;
  max-height: 320px;
}
.bell-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 120px;
  color: var(--dg-text-muted);
  font-size: 13px;
}
.bell-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--dg-border);
  transition: background 150ms ease;
}
.bell-item:hover {
  background: var(--dg-sidebar-hover);
}
.lvl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.item-kw {
  font-size: 13px;
  font-weight: 600;
  color: var(--dg-text-bright);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-ratio {
  font-size: 12px;
  font-weight: 700;
  color: var(--dg-warning, #e6a23c);
  font-family: 'JetBrains Mono', monospace;
  flex-shrink: 0;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.item-time {
  font-size: 11px;
  color: var(--dg-text-dim);
  font-family: 'JetBrains Mono', monospace;
}
.bell-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid var(--dg-border);
}
</style>
