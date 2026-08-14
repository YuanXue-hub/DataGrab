<template>
  <el-container class="layout">
    <!-- 侧边栏 -->
    <el-aside :width="collapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <img src="/datagrab-logo.jpg" alt="DataGrab" class="logo-img" />
        <span v-if="!collapsed" class="logo-text">DataGrab</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="collapsed"
        :collapse-transition="false"
        background-color="#1f2937"
        text-color="#e5e7eb"
        active-text-color="#60a5fa"
        router
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="collapsed = !collapsed">
            <Fold v-if="!collapsed" />
            <Expand v-else />
          </el-icon>
          <span class="page-title">{{ currentTitle }}</span>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Fold, Expand } from '@element-plus/icons-vue'

const route = useRoute()
const collapsed = ref(false)

const menuItems = [
  { path: '/sources', title: '数据源管理', icon: 'Connection' },
  { path: '/scrape', title: '爬取任务', icon: 'Download' },
  { path: '/data', title: '数据查看', icon: 'Document' },
  { path: '/export', title: '数据导出', icon: 'Upload' },
]

const activeMenu = computed(() => route.path)
const currentTitle = computed(
  () => (route.meta.title as string) || 'DataGrab',
)
</script>

<style scoped>
.layout {
  height: 100vh;
}

.sidebar {
  background-color: var(--dg-sidebar);
  transition: width 0.25s ease;
  overflow-x: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #fff;
  font-weight: 700;
  font-size: 20px;
  border-bottom: 1px solid #374151;
  padding: 0 12px;
  overflow: hidden;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.logo-text {
  white-space: nowrap;
}

.sidebar :deep(.el-menu) {
  border-right: none;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
  color: #4b5563;
}

.collapse-btn:hover {
  color: #2563eb;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
}

.main {
  padding: 20px;
  overflow-y: auto;
}
</style>
