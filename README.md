# DataGrab

多源数据采集与情报管理平台，支持从新闻网站、API 接口等多种数据源自动抓取内容，
提供数据源管理、异步爬取任务、数据浏览和多格式导出等完整功能。
## 系统截图
展示系统首页
![系统首页](assets/%E7%B3%BB%E7%BB%9F%E9%A6%96%E9%A1%B5.png)
数据源管理
![数据源管理](assets/%E6%95%B0%E6%8D%AE%E6%BA%90%E7%AE%A1%E7%90%86.png)
数据爬取
![数据爬取](assets/%E6%95%B0%E6%8D%AE%E7%88%AC%E5%8F%96.png)
数据查看
![数据查看](assets/%E6%95%B0%E6%8D%AE%E6%9F%A5%E7%9C%8B.png)
数据导出
![数据导出](assets/%E6%95%B0%E6%8D%AE%E5%AF%BC%E5%87%BA.png)


## 功能特性

- **数据源管理**：支持 web / api 两种类型，只填 URL 即可自动检测类型和 CSS 选择器
- **智能选择器**：四级兜底链（手动 → 自动检测 → 预设模板 → 通用兜底），内置 32 个主流站点预设
- **选择器测试**：前端预览抽屉实时试抓样本，验证失败时展示具体原因，方便手动微调
- **异步任务**：FastAPI 后台任务 + MySQL 持久化，任务状态可回溯
- **数据浏览**：按数据源 / 关键词 / 语言筛选，抽屉式详情查看
- **多格式导出**：JSON / CSV / DOCX（格式化 Word 报告）
- **多语言识别**：基于 Unicode 字符范围检测中、英、俄、乌克兰语

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.10+ / FastAPI / Uvicorn |
| 数据库 | MySQL 8.0（pymysql 驱动） |
| 爬虫引擎 | httpx / BeautifulSoup4 / Readability |
| 前端 | Vue 3 / TypeScript / Vite / Element Plus |

## 快速开始

### 1. 环境准备

- Python 3.10+
- Node.js 18+
- MySQL 8.0+

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

数据库连接配置在 [storage/database.py](storage/database.py) 的 `DB_CONFIG`：

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",  # 修改为你的 MySQL 密码
    "charset": "utf8mb4",
}
```

首次启动时系统会自动创建 `DataGrab` 数据库及 `source` / `scrape_job` / `grab` 三张表。

### 4. 启动后端服务

```bash
python main.py serve
```

默认监听 `http://localhost:8000`，API 文档在 `http://localhost:8000/docs`。

可选参数：
- `--host 0.0.0.0` 监听地址
- `--port 8000` 监听端口
- `--reload` 开启热重载（开发模式）

### 5. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

默认监听 `http://localhost:5173`。

### 6. 命令行用法

```bash
# 列出所有已注册爬虫
python main.py list-sources

# 直接执行爬取（不走 Web）
python main.py run --sources bbc,xinhua --max 10

# 并行爬取并导出 docx
python main.py run --parallel --export --format docx
```

## 项目结构

```
DataGrab/
├── core/               # 爬虫核心（base_scraper / engine / pipeline）
├── scrapers/           # 爬虫实现
│   ├── news/           # 新闻爬虫（bbc / xinhua 等）
│   ├── military/       # 军事爬虫（isw）
│   ├── social/         # 社交爬虫（reddit）
│   ├── redroom/        # 情报爬虫（tRPC 协议）
│   ├── generic_scraper.py     # 通用爬虫（选择器兜底链）
│   ├── selector_detector.py   # 选择器自动检测 + 验证
│   └── selector_presets.py    # 预设模板库（32 站点）
├── parsers/            # 数据解析器（news / military / social）
├── storage/            # MySQL 持久化（database / repository）
├── server/             # FastAPI 服务（routes / models）
├── exporters/          # 数据导出（csv / word）
├── utils/              # 工具（语言检测 / 限流 / 日志）
├── frontend/           # Vue 3 前端
├── main.py             # 入口（serve / run / list-sources / export）
└── requirements.txt
```

## 选择器配置

详见 [需求分析与方案设计.md](需求分析与方案设计.md) 第 4 节。简要说明：

**web 类型**：配置 CSS 选择器从 HTML 列表页提取文章，关键字段：
- `article_selector`（必填）：文章条目容器
- `title_selector`（必填）：标题元素
- `link_selector`（必填）：详情页链接
- `content_selector`（可选）：详情页正文容器，留空则用 Readability 算法

**api 类型**：通过 JSON 接口获取结构化数据：
- 配置 `endpoint` 字段 → 走 tRPC 模式
- 不配置 `endpoint` → 走通用 REST 模式，自动识别 `title` / `content` / `url` 等字段

## 免责声明

本项目仅供学习交流和技术研究使用，使用者需遵守以下约定：

1. **合法性**：使用本工具抓取数据时，必须遵守目标网站的服务条款、robots.txt 协议及相关法律法规。
   不得用于任何违反法律或侵犯他人合法权益的用途。

2. **版权归属**：本工具抓取的所有数据版权归原网站和内容创作者所有。
   抓取的数据仅用于个人学习研究，不得用于商业用途，不得二次分发或公开传播。

3. **访问频率**：本工具内置了请求限流机制，使用者仍有责任合理控制抓取频率，
   避免对目标网站服务器造成过大压力或影响其正常运行。

4. **数据准确性**：本工具不对抓取数据的准确性、完整性、时效性作任何保证。
   因使用本工具抓取的数据而产生的任何直接或间接损失，本项目不承担责任。

5. **使用风险**：使用者自行承担使用本工具的全部风险。本项目开发者不对因使用本工具
   而导致的任何数据丢失、账户封禁、法律纠纷等后果负责。

6. **内容中立**：本工具抓取的内容仅反映原信息源的观点和立场，不代表本项目开发者的立场。
   抓取特定主题（如冲突、军事）的数据仅为技术研究目的，不代表对任何政治立场的支持或反对。

**使用本工具即表示您已阅读并同意以上免责声明。如不同意，请立即停止使用。**

## License

MIT
