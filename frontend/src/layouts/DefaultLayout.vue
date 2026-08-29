<template>
  <el-container class="layout">
    <!-- 侧边栏 -->
    <el-aside :width="collapsed ? '72px' : '240px'" class="sidebar">
      <div class="logo" :class="{ collapsed }">
        <img src="/datagrab-logo.jpg" alt="DataGrab" class="logo-img" />
        <transition name="fade">
          <span v-if="!collapsed" class="logo-text">DataGrab</span>
        </transition>
      </div>
      <nav class="nav">
        <RouterLink
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: activeMenu === item.path }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">{{ item.title }}</span>
          </transition>
        </RouterLink>
      </nav>
      <div v-if="!collapsed" class="sidebar-footer">
        <div class="status-indicator">
          <span class="status-dot"></span>
          <span class="status-text">System Online</span>
        </div>
        <div class="version-tag">v1.0.0</div>
      </div>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="header-left">
          <button class="collapse-btn" @click="collapsed = !collapsed">
            <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
          </button>
          <div class="header-titles">
            <h1 class="header-title">{{ currentTitle }}</h1>
            <span class="header-subtitle">{{ currentSubtitle }}</span>
          </div>
        </div>
        <div class="header-right">
          <HotspotBell />
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            class="api-link"
          >
            <el-icon><Link /></el-icon>
            API Docs
          </a>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main">
        <RouterView v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Fold, Expand, Link } from '@element-plus/icons-vue'
import HotspotBell from '@/components/HotspotBell.vue'

const route = useRoute()
const collapsed = ref(false)

const menuItems = [
  { path: '/app/monitor', title: '热点监控', icon: 'DataAnalysis', badge: 'BETA' },
  { path: '/app/sources', title: '数据源管理', icon: 'Connection' },
  { path: '/app/scrape', title: '爬取任务', icon: 'Download' },
  { path: '/app/data', title: '数据查看', icon: 'Document' },
  { path: '/app/export', title: '数据导出', icon: 'Upload' },
]

const activeMenu = computed(() => route.path)
const currentTitle = computed(
  () => (route.meta.title as string) || 'DataGrab',
)
const currentSubtitle = computed(() => {
  const map: Record<string, string> = {
    '/app/monitor': '实时热点监控、关键词管理与告警通知',
    '/app/sources': '管理爬虫数据源与选择器配置',
    '/app/scrape': '执行爬取任务并查看历史记录',
    '/app/data': '浏览与检索已采集的数据',
    '/app/export': '将采集数据导出为多种格式',
  }
  return map[route.path] || '数据采集与情报分析平台'
})
</script>

<style scoped>
.layout {
  height: 100vh;
}

/* ===== Sidebar — Deep Dark ===== */
.sidebar {
  background-color: var(--dg-sidebar-bg);
  background-image:
    linear-gradient(180deg, rgba(0, 240, 255, 0.02) 0%, transparent 100%);
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--dg-border);
  position: relative;
}
.sidebar::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  width: 1px;
  height: 100%;
  background: linear-gradient(180deg,
    transparent,
    rgba(0, 240, 255, 0.15) 30%,
    rgba(0, 240, 255, 0.15) 70%,
    transparent);
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  border-bottom: 1px solid var(--dg-border);
  flex-shrink: 0;
}
.logo.collapsed {
  justify-content: center;
  padding: 0;
}

.logo-img {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
  box-shadow: 0 0 12px rgba(0, 240, 255, 0.25);
  transition: box-shadow 0.3s ease;
}
.logo-img:hover {
  box-shadow: 0 0 20px rgba(0, 240, 255, 0.4);
}

.logo-text {
  font-family: 'Outfit', sans-serif;
  font-size: 19px;
  font-weight: 700;
  color: var(--dg-text-bright);
  white-space: nowrap;
  letter-spacing: -0.02em;
}

/* ===== Nav ===== */
.nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  color: var(--dg-text-muted);
  font-size: 14px;
  font-weight: 500;
  transition: all 180ms ease;
  white-space: nowrap;
  position: relative;
}
.nav-item:hover {
  background: var(--dg-sidebar-hover);
  color: var(--dg-cyan);
}
.nav-item.active {
  background: var(--dg-sidebar-active);
  color: var(--dg-cyan);
  text-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
}
.nav-item.active::before {
  content: '';
  position: absolute;
  left: -12px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--dg-cyan);
  border-radius: 0 3px 3px 0;
  box-shadow: 0 0 8px rgba(0, 240, 255, 0.5);
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.nav-label {
  white-space: nowrap;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--dg-border);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--dg-text-muted);
  font-family: 'JetBrains Mono', monospace;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dg-success);
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
.version-tag {
  font-size: 12px;
  color: var(--dg-text-dim);
  font-family: 'JetBrains Mono', monospace;
}

/* ===== Header ===== */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--dg-surface);
  background-image: linear-gradient(180deg, rgba(0, 240, 255, 0.02), transparent);
  border-bottom: 1px solid var(--dg-border);
  padding: 0 24px;
  height: 64px;
  backdrop-filter: blur(12px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
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
.collapse-btn:hover {
  background: var(--dg-sidebar-hover);
  color: var(--dg-cyan);
  border-color: var(--dg-cyan-dim);
  box-shadow: 0 0 12px rgba(0, 240, 255, 0.15);
}
.collapse-btn:active {
  transform: scale(0.95);
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.header-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--dg-text-bright);
  margin: 0;
  line-height: 1.2;
}
.header-subtitle {
  font-size: 12px;
  color: var(--dg-text-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.api-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--dg-border);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--dg-text-secondary);
  font-family: 'JetBrains Mono', monospace;
  transition: all 180ms ease;
}
.api-link:hover {
  color: var(--dg-cyan);
  border-color: var(--dg-cyan-dim);
  background: var(--dg-sidebar-hover);
  box-shadow: 0 0 12px rgba(0, 240, 255, 0.1);
}

/* ===== Main ===== */
.main {
  padding: 24px;
  overflow-y: auto;
  background: var(--dg-bg);
}
</style>
