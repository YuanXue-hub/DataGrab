# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

DataGrab 是一个 Python 爬虫工具，从多个数据源采集俄乌冲突相关数据（新闻、军事分析、社交媒体、经济数据），支持中英双语，最终导出为 Word (.docx) 报告。

## 常用命令

```bash
# 安装依赖（推荐使用虚拟环境）
pip install -r requirements.txt

# 查看 CLI 帮助
python main.py --help

# 列出所有可用数据源
python main.py list-sources

# 运行全部已注册的爬虫
python main.py run

# 指定数据源 + 限制抓取条数
python main.py run --sources bbc,isw --max 10

# 并行爬取 + 选择导出格式
python main.py run --parallel --format csv
python main.py run --format json
```

暂无测试套件。修改后通过 `python main.py run --sources <名称> --max 3` 手动验证，检查 `output/` 目录输出。

## 核心架构

**数据管道**：`Scraper.fetch()` → `RawData` → `Parser.parse()` → `DataItem` → `Repository` → `Exporter.export()`

**核心模块**（`datagrab/core/`）：
- `BaseScraper` — 模板方法模式：`scrape()` 调用 `fetch()`（底层走 `utils/http_client.py`），再交给 parser 解析。子类只需实现 `get_source_name()` 和 `scrape()`。
- `BaseParser` — 接收 `RawData`，返回 `List[DataItem]`。每种数据类型对应一个解析器：`NewsParser`、`MilitaryParser`、`SocialParser`。
- `ScraperEngine` — 基于注册表：爬虫按名称注册，引擎编排执行（串行或线程池并行），将结果汇总到 `Repository`。
- `Pipeline` — 可选的后处理管道：解析 → 清洗 → 校验 → 存储。目前引擎内有使用但大部分逻辑内联处理。

**数据模型**（`datagrab/storage/models.py`）：四种 `@dataclass` 类型 — `NewsArticle`、`MilitaryData`、`EconomicData`、`SocialPost`。联合类型 `DataItem = NewsArticle | MilitaryData | EconomicData | SocialPost`。

**爬虫注册表**（`datagrab/scrapers/__init__.py`）：惰性导入模式 — `SCRAPER_REGISTRY` 字典映射 名称 → (模块路径, 类名, 描述)。调用 `get_scraper_class(name)` 按需加载。新增爬虫只需创建类文件并在 `SCRAPER_REGISTRY` 添加条目。

**工具模块**（`datagrab/utils/`）：
- `http_client.py` — httpx 封装，指数退避重试（最多3次），按域名限速，随机 UA 轮换
- `rate_limiter.py` — 域名级令牌桶，全局单例 `_global_limiter`
- `user_agents.py` — 桌面/移动端 UA 池，`get_headers()` 返回完整请求头
- `text_cleaner.py` — HTML 标签剥离、空白规范化、从文本中提取日期

**配置文件**：`config/config.yaml`（全局设置、关键词、导出选项）和 `config/sources.yaml`（每个数据源的 URL、选择器、开关）。注意：目前配置文件已存在但引擎尚未加载——爬虫仍使用硬编码 URL。后续可接入 YAML 配置。

**导出器**：`WordExporter` 生成带样式的 .docx（封面、摘要表格、按来源分组的内容）。`CSVExporter` 按数据类型分别写 CSV。

## 关键设计模式

- **新增爬虫**：在 `datagrab/scrapers/<类别>/<名称>_scraper.py` 创建继承 `BaseScraper` 的类，然后在 `datagrab/scrapers/__init__.py` 的 `SCRAPER_REGISTRY` 注册。
- **依赖隔离**：依赖重型库的爬虫（Reddit 用 PRAW、Twitter 用 playwright）使用惰性导入 —— 在调用 `get_scraper_class()` 之前不会加载类，缺少依赖不会影响整个模块。
- **自动限速**：每次 `HTTPClient.get()` 调用都会经过 `_global_limiter.wait(domain)`，单个爬虫无需手动控制请求间隔。
