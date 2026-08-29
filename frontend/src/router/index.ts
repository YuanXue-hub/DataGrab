import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/app',
      component: () => import('@/layouts/DefaultLayout.vue'),
      redirect: '/app/sources',
      children: [
        {
          path: 'sources',
          name: 'sources',
          component: () => import('@/views/SourcesView.vue'),
          meta: { title: '数据源管理', icon: 'Connection' },
        },
        {
          path: 'scrape',
          name: 'scrape',
          component: () => import('@/views/ScrapeView.vue'),
          meta: { title: '爬取任务', icon: 'Download' },
        },
        {
          path: 'data',
          name: 'data',
          component: () => import('@/views/DataExploreView.vue'),
          meta: { title: '数据查看', icon: 'Document' },
        },
        {
          path: 'topics',
          redirect: '/app/monitor',
        },
        {
          path: 'monitor',
          name: 'monitor',
          component: () => import('@/views/MonitorDashboard.vue'),
          meta: { title: '热点监控看板', icon: 'DataAnalysis' },
        },
        {
          path: 'export',
          name: 'export',
          component: () => import('@/views/ExportView.vue'),
          meta: { title: '数据导出', icon: 'Upload' },
        },
      ],
    },
    // 兼容旧路径 /sources → /app/sources
    { path: '/sources', redirect: '/app/sources' },
    { path: '/scrape', redirect: '/app/scrape' },
    { path: '/data', redirect: '/app/data' },
    { path: '/topics', redirect: '/app/topics' },
    { path: '/monitor', redirect: '/app/monitor' },
    { path: '/export', redirect: '/app/export' },
  ],
})

export default router
