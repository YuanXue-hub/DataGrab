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
            <el-tag
              :type="typeTag(row.source_type)"
              size="small"
              effect="plain"
            >
              {{ row.source_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="URL" prop="url" min-width="280" show-overflow-tooltip />
        <el-table-column label="描述" prop="description" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }: { row: any }">
            <el-switch
              :model-value="row.enabled"
              @change="(v) => toggleEnabled(row, Boolean(v))"
            />
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }: { row: any }">
            <span class="muted">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }: { row: any }">
            <el-button size="small" link :icon="VideoPause" @click="onTest(row)">
              测试
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
      width="560px"
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
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item v-if="!editing" label="">
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, ElLoading, type FormInstance, type FormRules } from 'element-plus'
import {
  Search, Refresh, Plus, Edit, Delete, VideoPause,
} from '@element-plus/icons-vue'
import {
  listSources, createSource, updateSource, deleteSource, testUrl,
} from '@/api/sources'
import type { SourceInfo, SourceCreatePayload, SourceUpdatePayload } from '@/types'

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

function formatTime(s: string) {
  if (!s) return '-'
  return s.replace('T', ' ').split('.')[0]
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
  dialogVisible.value = true
}

async function submitForm() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      if (editing.value) {
        const payload: SourceUpdatePayload = {
          url: form.url,
          description: form.description,
          enabled: form.enabled,
        }
        await updateSource(form.name, payload)
        ElMessage.success('已保存')
      } else {
        const payload: SourceCreatePayload = {
          name: form.name,
          url: form.url,
          description: form.description,
        }
        const res = await createSource(payload)
        ElMessage.success(
          `已创建（检测为 ${res.source_type} 类型）`,
        )
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
  const loading = ElLoading.service({ text: '测试中...', background: 'rgba(0,0,0,0.4)' })
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
</style>
