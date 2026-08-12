import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/DefaultLayout.vue'),
      redirect: '/sources',
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
          path: 'export',
          name: 'export',
          component: () => import('@/views/ExportView.vue'),
          meta: { title: '数据导出', icon: 'Upload' },
        },
      ],
    },
  ],
})

export default router
