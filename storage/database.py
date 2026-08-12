"""MySQL 数据库管理

DataGrab 数据库：
- source 表：数据源配置
- scrape_job 表：爬取任务（持久化，避免重启丢失）
- grab 表：爬取结果（关联 job_id，可按任务回溯）
"""

import json
from datetime import datetime
from typing import Optional, List

import pymysql
from loguru import logger

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "123456",
    "charset": "utf8mb4",
}


def get_connection() -> pymysql.Connection:
    """获取 MySQL 连接（连接到 DataGrab 数据库）。"""
    return pymysql.connect(**DB_CONFIG, database="DataGrab", cursorclass=pymysql.cursors.DictCursor)


def init_database():
    """初始化数据库和表结构。"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE DATABASE IF NOT EXISTS DataGrab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            cur.execute("USE DataGrab")

            # source 表：数据源配置
            cur.execute("""
                CREATE TABLE IF NOT EXISTS source (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    name        VARCHAR(50)  NOT NULL UNIQUE COMMENT '数据源唯一名称',
                    url         VARCHAR(500) NOT NULL COMMENT '目标网址',
                    description VARCHAR(200) DEFAULT '' COMMENT '描述',
                    source_type VARCHAR(20)  NOT NULL DEFAULT 'web' COMMENT '类型: web / rss / api',
                    selectors   JSON         DEFAULT NULL COMMENT '类型相关配置（web=CSS选择器，api=查询参数）',
                    selector_source VARCHAR(20) DEFAULT 'manual' COMMENT '选择器来源: detector|preset|fallback|manual',
                    enabled     TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否启用',
                    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 兼容已有数据库：如果旧 source 表缺少 selector_source 列则补上
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'DataGrab'
                  AND TABLE_NAME = 'source'
                  AND COLUMN_NAME = 'selector_source'
            """)
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "ALTER TABLE source ADD COLUMN selector_source VARCHAR(20) "
                    "DEFAULT 'manual' COMMENT '选择器来源: detector|preset|fallback|manual' "
                    "AFTER selectors"
                )
                logger.info("Added selector_source column to existing source table")

            # scrape_job 表：爬取任务（持久化，支持历史回溯）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS scrape_job (
                    job_id       VARCHAR(36)  NOT NULL PRIMARY KEY COMMENT '任务 UUID',
                    source_id    INT          NOT NULL COMMENT '关联 source.id',
                    source_name  VARCHAR(50)  NOT NULL COMMENT '数据源名称（冗余）',
                    status       VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending|running|completed|failed',
                    limit_count  INT          NOT NULL DEFAULT 20 COMMENT '请求的抓取上限',
                    total        INT          NOT NULL DEFAULT 0 COMMENT '实际入库条数',
                    params       JSON         DEFAULT NULL COMMENT '调用参数快照',
                    error        TEXT         DEFAULT NULL COMMENT '失败原因',
                    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    started_at   DATETIME     DEFAULT NULL COMMENT '开始执行时间',
                    completed_at DATETIME     DEFAULT NULL COMMENT '完成时间',
                    FOREIGN KEY (source_id) REFERENCES source(id) ON DELETE CASCADE,
                    INDEX idx_job_status (status),
                    INDEX idx_job_created (created_at),
                    INDEX idx_job_source (source_name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # grab 表：爬取结果（新增 job_id 列）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS grab (
                    id          INT AUTO_INCREMENT PRIMARY KEY,
                    source_id   INT          NOT NULL COMMENT '关联 source.id',
                    job_id      VARCHAR(36)  DEFAULT NULL COMMENT '关联 scrape_job.job_id',
                    source_name VARCHAR(50)  NOT NULL COMMENT '数据源名称（冗余）',
                    title       VARCHAR(500) DEFAULT '' COMMENT '标题',
                    content     MEDIUMTEXT   COMMENT '正文内容',
                    summary     VARCHAR(1000) DEFAULT '' COMMENT '摘要',
                    source_url  VARCHAR(500) DEFAULT '' COMMENT '原始URL',
                    language    VARCHAR(10)  DEFAULT '' COMMENT '语言',
                    category    VARCHAR(50)  DEFAULT '' COMMENT '分类',
                    tags        JSON         DEFAULT NULL COMMENT '标签列表',
                    published_at DATETIME    DEFAULT NULL COMMENT '发布时间',
                    grabbed_at  DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '抓取时间',
                    raw_json    JSON         DEFAULT NULL COMMENT '原始JSON数据',
                    FOREIGN KEY (source_id) REFERENCES source(id) ON DELETE CASCADE,
                    INDEX idx_source (source_name),
                    INDEX idx_grabbed (grabbed_at),
                    INDEX idx_job (job_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # 兼容已有数据库：如果旧 grab 表缺少 job_id 列则补上
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'DataGrab'
                  AND TABLE_NAME = 'grab'
                  AND COLUMN_NAME = 'job_id'
            """)
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "ALTER TABLE grab ADD COLUMN job_id VARCHAR(36) DEFAULT NULL "
                    "COMMENT '关联 scrape_job.job_id' AFTER source_id"
                )
                cur.execute("ALTER TABLE grab ADD INDEX idx_job (job_id)")
                logger.info("Added job_id column to existing grab table")
        conn.commit()
        logger.info("Database initialized: DataGrab (source + scrape_job + grab tables)")
    finally:
        conn.close()


# ============================
#  Source CRUD
# ============================

def source_list() -> List[dict]:
    """列出所有数据源。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM source ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()


def source_get(name: str) -> Optional[dict]:
    """按名称获取数据源。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM source WHERE name = %s", (name,))
            return cur.fetchone()
    finally:
        conn.close()


def source_create(name: str, url: str, description: str = "",
                  source_type: str = "web", selectors: dict = None,
                  selector_source: str = "manual") -> int:
    """创建数据源，返回 id。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO source (name, url, description, source_type, selectors, selector_source) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (name, url, description, source_type,
                 json.dumps(selectors, ensure_ascii=False) if selectors else None,
                 selector_source)
            )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def source_update(name: str, **kwargs):
    """更新数据源配置。"""
    allowed = {"url", "description", "source_type", "selectors", "selector_source", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    if "selectors" in updates and isinstance(updates["selectors"], dict):
        updates["selectors"] = json.dumps(updates["selectors"], ensure_ascii=False)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            set_clause = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [name]
            cur.execute(f"UPDATE source SET {set_clause} WHERE name = %s", values)
        conn.commit()
    finally:
        conn.close()


def source_delete(name: str):
    """删除数据源。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM source WHERE name = %s", (name,))
        conn.commit()
    finally:
        conn.close()


# ============================
#  Grab CRUD
# ============================

def grab_insert(source_id: int, source_name: str, title: str = "",
                content: str = "", summary: str = "", source_url: str = "",
                language: str = "", category: str = "", tags: list = None,
                published_at: datetime = None, raw_json: dict = None,
                job_id: str = None) -> int:
    """插入一条抓取结果，返回 id。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO grab (source_id, job_id, source_name, title, content, summary, "
                "source_url, language, category, tags, published_at, grabbed_at, raw_json) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)",
                (source_id, job_id, source_name, title, content, summary,
                 source_url, language, category,
                 json.dumps(tags, ensure_ascii=False) if tags else None,
                 published_at,
                 json.dumps(raw_json, ensure_ascii=False) if raw_json else None)
            )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def grab_list(source_name: str = None, job_id: str = None,
              limit: int = 50, offset: int = 0,
              data_type: str = None) -> List[dict]:
    """查询抓取结果，可按数据源或任务 ID 过滤。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            if source_name:
                conditions.append("source_name = %s")
                params.append(source_name)
            if job_id:
                conditions.append("job_id = %s")
                params.append(job_id)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT * FROM grab {where} ORDER BY grabbed_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset]
            )
            return cur.fetchall()
    finally:
        conn.close()


def grab_count(source_name: str = None, job_id: str = None) -> int:
    """统计抓取结果数量，可按数据源或任务 ID 过滤。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            if source_name:
                conditions.append("source_name = %s")
                params.append(source_name)
            if job_id:
                conditions.append("job_id = %s")
                params.append(job_id)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(f"SELECT COUNT(*) as cnt FROM grab {where}", params)
            return cur.fetchone()["cnt"]
    finally:
        conn.close()


def grab_delete_by_source(source_name: str):
    """删除指定数据源的所有抓取结果。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM grab WHERE source_name = %s", (source_name,))
        conn.commit()
    finally:
        conn.close()


# ============================
#  ScrapeJob CRUD
# ============================

def job_create(job_id: str, source_id: int, source_name: str,
               limit_count: int = 20, params: dict = None) -> str:
    """创建爬取任务记录（status=pending），返回 job_id。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO scrape_job (job_id, source_id, source_name, status, "
                "limit_count, params) VALUES (%s, %s, %s, 'pending', %s, %s)",
                (job_id, source_id, source_name, limit_count,
                 json.dumps(params, ensure_ascii=False) if params else None)
            )
        conn.commit()
        return job_id
    finally:
        conn.close()


def job_update(job_id: str, **kwargs):
    """更新任务字段，支持 status/total/error/started_at/completed_at。"""
    allowed = {"status", "total", "error", "started_at", "completed_at"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            set_clause = ", ".join(f"{k} = %s" for k in updates)
            values = list(updates.values()) + [job_id]
            cur.execute(f"UPDATE scrape_job SET {set_clause} WHERE job_id = %s", values)
        conn.commit()
    finally:
        conn.close()


def job_get(job_id: str) -> Optional[dict]:
    """按 job_id 获取任务。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM scrape_job WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            if row and isinstance(row.get("params"), str):
                try:
                    row["params"] = json.loads(row["params"])
                except (json.JSONDecodeError, TypeError):
                    pass
            return row
    finally:
        conn.close()


def job_list(source_name: str = None, status: str = None,
             limit: int = 50, offset: int = 0) -> List[dict]:
    """列出任务，可按数据源/状态过滤，按创建时间倒序。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            if source_name:
                conditions.append("source_name = %s")
                params.append(source_name)
            if status:
                conditions.append("status = %s")
                params.append(status)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(
                f"SELECT * FROM scrape_job {where} "
                f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset]
            )
            rows = cur.fetchall()
            for r in rows:
                if isinstance(r.get("params"), str):
                    try:
                        r["params"] = json.loads(r["params"])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return rows
    finally:
        conn.close()


def job_count(source_name: str = None, status: str = None) -> int:
    """统计任务数量。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            conditions = []
            params = []
            if source_name:
                conditions.append("source_name = %s")
                params.append(source_name)
            if status:
                conditions.append("status = %s")
                params.append(status)
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            cur.execute(f"SELECT COUNT(*) as cnt FROM scrape_job {where}", params)
            return cur.fetchone()["cnt"]
    finally:
        conn.close()
