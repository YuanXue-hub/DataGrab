<template>
  <div class="kw-page">
    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchWord" placeholder="搜索热点词..." :prefix-icon="Search"
          clearable style="width: 240px"
        />
        <el-select v-model="filterLang" placeholder="语言" clearable style="width: 120px">
          <el-option label="中文" value="zh" />
          <el-option label="英文" value="en" />
          <el-option label="俄语" value="ru" />
          <el-option label="乌克兰语" value="uk" />
        </el-select>
        <el-select v-model="filterMode" placeholder="匹配模式" clearable style="width: 130px">
          <el-option label="模糊" value="fuzzy" />
          <el-option label="精确" value="exact" />
          <el-option label="正则" value="regex" />
        </el-select>
        <el-select v-model="filterEnabled" placeholder="状态" clearable style="width: 110px">
          <el-option label="启用" :value="1" />
          <el-option label="停用" :value="0" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button :icon="Upload" @click="openImportDialog">批量导入</el-button>
        <el-button type="primary" :icon="Plus" @click="openKeywordDialog()">新增热点词</el-button>
      </div>
    </div>

    <!-- 统计条 -->
    <div class="stat-bar">
      <div class="stat-chip">
        <span class="chip-label">总词数</span>
        <strong class="chip-val">{{ allKeywords.length }}</strong>
      </div>
      <div class="stat-chip ok">
        <span class="chip-label">启用</span>
        <strong class="chip-val">{{ enabledCount }}</strong>
      </div>
      <div class="stat-chip off">
        <span class="chip-label">停用</span>
        <strong class="chip-val">{{ allKeywords.length - enabledCount }}</strong>
      </div>
      <div class="stat-chip variant">
        <span class="chip-label">带变体</span>
        <strong class="chip-val">{{ variantCount }}</strong>
      </div>
      <div class="stat-chip cyan">
        <span class="chip-label">筛选结果</span>
        <strong class="chip-val">{{ filteredKeywords.length }}</strong>
      </div>
    </div>

    <!-- 表格 -->
    <el-table
      :data="pagedKeywords" v-loading="loading" stripe
      style="width: 100%" empty-text="暂无热点词，点击右上角「新增热点词」开始监控"
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="热点词" min-width="200">
        <template #default="{ row }">
          <span class="kw-word">{{ row.word }}</span>
          <el-tag v-if="row.variants && row.variants.length" size="small" type="info" effect="plain" style="margin-left:8px">
            +{{ row.variants.length }} 变体
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="语言" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.language" size="small" effect="plain">{{ langLabel(row.language) }}</el-tag>
          <span v-else class="muted">不限</span>
        </template>
      </el-table-column>
      <el-table-column label="匹配模式" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="modeType(row.match_mode)">{{ modeLabel(row.match_mode) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="权重" width="110">
        <template #default="{ row }">
          <el-rate :model-value="row.weight" disabled :max="10" :show-score="true" text-color="#ff9900" />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-switch
            :model-value="!!row.enabled" size="small"
            active-text="启用" inactive-text="停用"
            @change="(val: any) => toggleKeyword(row as Keyword, !!val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openKeywordDialog(row as Keyword)">编辑</el-button>
          <el-popconfirm title="确定删除该热点词？" @confirm="delKeyword(row as Keyword)">
            <template #reference>
              <el-button link type="danger" size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pager">
      <el-pagination
        background layout="total, prev, pager, next, sizes"
        :total="filteredKeywords.length"
        :page-sizes="[20, 50, 100]"
        v-model:current-page="page"
        v-model:page-size="pageSize"
      />
    </div>

    <!-- 新增/编辑关键词对话框 -->
    <el-dialog v-model="kwDialogVisible" :title="kwEditing ? '编辑热点词' : '新增热点词'" width="560px">
      <el-form :model="kwForm" label-width="90px">
        <el-form-item label="热点词" required>
          <el-input v-model="kwForm.word" placeholder="如：反攻 / counteroffensive" maxlength="100" show-word-limit />
        </el-form-item>
        <el-form-item label="限定语言">
          <el-select v-model="kwForm.language" placeholder="空=不限制">
            <el-option label="不限" value="" />
            <el-option label="中文" value="zh" />
            <el-option label="英文" value="en" />
            <el-option label="俄语" value="ru" />
            <el-option label="乌克兰语" value="uk" />
          </el-select>
        </el-form-item>
        <el-form-item label="匹配模式">
          <el-radio-group v-model="kwForm.match_mode">
            <el-radio-button value="fuzzy">模糊（子串）</el-radio-button>
            <el-radio-button value="exact">精确</el-radio-button>
            <el-radio-button value="regex">正则</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="权重">
          <el-input-number v-model="kwForm.weight" :min="1" :max="10" />
          <span class="form-hint">权重越高，命中得分越高（1-10）</span>
        </el-form-item>
        <el-form-item label="查询变体">
          <el-input
            v-model="kwVariantsText" type="textarea" :rows="2"
            placeholder="逗号分隔的变体词，用于 Query Expansion 扩展匹配（可留空）"
          />
          <span class="form-hint">例如：反攻 的变体可填 counteroffensive,offensive</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="kwForm.enabled" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kwDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitKeyword">确认</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入对话框 -->
    <el-dialog v-model="importDialogVisible" title="批量导入热点词" width="620px">
      <div class="import-hint">
        <strong>格式说明：</strong>每行一个热点词，可附加参数用逗号分隔：<br>
        <code>词</code> → 默认模糊匹配，权重 1<br>
        <code>词,zh</code> → 指定中文<br>
        <code>词,zh,fuzzy,3</code> → 指定模糊、权重 3
      </div>
      <el-input
        v-model="importForm.words_text" type="textarea" :rows="12"
        placeholder="反攻,zh,fuzzy,3&#10;导弹&#10;counteroffensive,en,fuzzy,3&#10;sanction,en"
      />
      <div class="import-footer">
        <el-form inline label-position="left" size="default">
          <el-form-item label="默认语言">
            <el-select v-model="importForm.default_language" placeholder="空">
              <el-option label="不限" value="" />
              <el-option label="中文" value="zh" />
              <el-option label="英文" value="en" />
            </el-select>
          </el-form-item>
          <el-form-item label="默认模式">
            <el-radio-group v-model="importForm.default_match_mode">
              <el-radio-button value="fuzzy">模糊</el-radio-button>
              <el-radio-button value="exact">精确</el-radio-button>
              <el-radio-button value="regex">正则</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="默认权重">
            <el-input-number v-model="importForm.default_weight" :min="1" :max="10" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { Plus, Upload, Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  listKeywords, createKeyword, updateKeyword, deleteKeyword,
  importKeywords,
} from '@/api/topics'
import type { Keyword, KeywordCreate, KeywordUpdate, KeywordImportPayload, MatchMode } from '@/types'

// ============ 状态 ============
const allKeywords = ref<Keyword[]>([])
const loading = ref(false)
const searchWord = ref('')
const filterLang = ref('')
const filterMode = ref('')
const filterEnabled = ref<number | ''>('')
const page = ref(1)
const pageSize = ref(20)

const enabledCount = computed(() => allKeywords.value.filter(k => k.enabled).length)
const variantCount = computed(() => allKeywords.value.filter(k => k.variants && k.variants.length).length)

const filteredKeywords = computed(() => {
  let list = allKeywords.value
  if (searchWord.value.trim()) {
    const q = searchWord.value.trim().toLowerCase()
    list = list.filter(k => k.word.toLowerCase().includes(q))
  }
  if (filterLang.value) list = list.filter(k => k.language === filterLang.value)
  if (filterMode.value) list = list.filter(k => k.match_mode === filterMode.value)
  if (filterEnabled.value !== '') list = list.filter(k => k.enabled === filterEnabled.value)
  return [...list].sort((a, b) => (b.weight - a.weight) || a.id - b.id)
})

const pagedKeywords = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredKeywords.value.slice(start, start + pageSize.value)
})

async function loadAll() {
  loading.value = true
  try {
    allKeywords.value = await listKeywords(undefined, true)
  } finally {
    loading.value = false
  }
}

// ============ 关键词对话框 ============
const kwDialogVisible = ref(false)
const kwEditing = ref(false)
const kwVariantsText = ref('')
const kwForm = reactive<{
  id?: number
  word: string
  language: string
  match_mode: MatchMode
  weight: number
  enabled: number
}>({ word: '', language: '', match_mode: 'fuzzy', weight: 1, enabled: 1 })

function openKeywordDialog(k?: Keyword) {
  if (k) {
    kwEditing.value = true
    Object.assign(kwForm, {
      id: k.id, word: k.word, language: k.language,
      match_mode: k.match_mode, weight: k.weight, enabled: k.enabled,
    })
    kwVariantsText.value = (k.variants || []).join(', ')
  } else {
    kwEditing.value = false
    Object.assign(kwForm, { id: undefined, word: '', language: '', match_mode: 'fuzzy', weight: 1, enabled: 1 })
    kwVariantsText.value = ''
  }
  kwDialogVisible.value = true
}

async function submitKeyword() {
  if (!kwForm.word.trim()) return ElMessage.warning('热点词必填')
  const variants = kwVariantsText.value.split(',').map(s => s.trim()).filter(Boolean)
  try {
    if (kwEditing.value && kwForm.id) {
      const payload: KeywordUpdate = {
        word: kwForm.word, language: kwForm.language,
        match_mode: kwForm.match_mode, weight: kwForm.weight,
        enabled: kwForm.enabled, variants: variants.length ? variants : null,
      }
      await updateKeyword(kwForm.id, payload)
    } else {
      const payload: KeywordCreate = {
        word: kwForm.word, language: kwForm.language,
        match_mode: kwForm.match_mode, weight: kwForm.weight,
        enabled: kwForm.enabled, variants: variants.length ? variants : null,
      }
      await createKeyword(payload)
    }
    ElMessage.success('保存成功')
    kwDialogVisible.value = false
    await loadAll()
  } catch (e: any) {}
}

async function toggleKeyword(row: Keyword, val: boolean) {
  await updateKeyword(row.id, { enabled: val ? 1 : 0 })
  ElMessage.success(val ? '已启用' : '已停用')
  await loadAll()
}

async function delKeyword(row: Keyword) {
  await deleteKeyword(row.id)
  ElMessage.success('已删除')
  await loadAll()
}

// ============ 批量导入 ============
const importDialogVisible = ref(false)
const importForm = reactive<Omit<KeywordImportPayload, 'topic_id'>>({
  words_text: '', default_language: '', default_match_mode: 'fuzzy', default_weight: 1,
})

function openImportDialog() {
  importForm.words_text = ''
  importDialogVisible.value = true
}

async function submitImport() {
  if (!importForm.words_text.trim()) return ElMessage.warning('内容为空')
  try {
    const res = await importKeywords({ ...importForm } as KeywordImportPayload)
    ElMessage.success(`成功导入 ${res.inserted} 个，跳过重复 ${res.skipped} 个`)
    importDialogVisible.value = false
    await loadAll()
  } catch (e: any) {}
}

// ============ 工具函数 ============
function langLabel(l: string) {
  return ({ zh: '中文', en: '英文', ru: '俄语', uk: '乌语' } as any)[l] || l
}
function modeLabel(m: string) {
  return ({ fuzzy: '模糊', exact: '精确', regex: '正则' } as any)[m] || m
}
function modeType(m: string) {
  return ({ fuzzy: 'info', exact: 'success', regex: 'warning' } as any)[m] || ''
}

onMounted(loadAll)
</script>

<style scoped>
.kw-page { color: var(--dg-text-primary); display: flex; flex-direction: column; gap: 16px; }

/* 工具栏 */
.toolbar {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; flex-wrap: wrap;
  background: var(--dg-surface); border: 1px solid var(--dg-border);
  border-radius: 12px; padding: 14px 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
}
.toolbar-left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; gap: 10px; }

/* 统计条 */
.stat-bar {
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}
.stat-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 8px 16px; border-radius: 10px;
  background: var(--dg-surface); border: 1px solid var(--dg-border);
  font-size: 13px;
}
.chip-label { color: var(--dg-text-muted); }
.chip-val { color: var(--dg-text-bright); font-size: 16px; font-family: 'JetBrains Mono', monospace; }
.stat-chip.ok .chip-val { color: var(--dg-success, #67c23a); }
.stat-chip.off .chip-val { color: var(--dg-text-dim); }
.stat-chip.variant .chip-val { color: var(--dg-cyan); }
.stat-chip.cyan { border-color: var(--dg-cyan-dim, rgba(0,240,255,0.3)); }
.stat-chip.cyan .chip-val { color: var(--dg-cyan); }

.kw-word { font-family: 'JetBrains Mono', monospace; color: var(--dg-cyan); font-weight: 600; }
.muted { color: var(--dg-text-muted); font-size: 12px; }
.form-hint { margin-left: 12px; font-size: 12px; color: var(--dg-text-dim); }

.pager { display: flex; justify-content: flex-end; padding: 8px 0; }

.import-hint {
  background: var(--dg-surface-2); border: 1px solid var(--dg-border);
  border-radius: 8px; padding: 12px; font-size: 12px;
  color: var(--dg-text-secondary); line-height: 1.7; margin-bottom: 12px;
}
.import-hint code {
  background: rgba(0, 240, 255, 0.08); color: var(--dg-cyan);
  padding: 1px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace;
}
.import-footer { margin-top: 12px; }
</style>
