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
                    INDEX idx_job (job_id),
                    INDEX idx_dedup (source_name, source_url)
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

            # 兼容已有数据库：补 (source_name, source_url) 去重索引
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = 'DataGrab'
                  AND TABLE_NAME = 'grab'
                  AND INDEX_NAME = 'idx_dedup'
            """)
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "ALTER TABLE grab ADD INDEX idx_dedup (source_name, source_url)"
                )
                logger.info("Added idx_dedup (source_name, source_url) index to grab table")

            # ==================== 新增 6 张监控相关表 ====================
            # topic 表：主题分类
            cur.execute("""
                CREATE TABLE IF NOT EXISTS topic (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    name         VARCHAR(50)  NOT NULL UNIQUE COMMENT '主题名称',
                    description  VARCHAR(200) NOT NULL DEFAULT '',
                    color        VARCHAR(20)  NOT NULL DEFAULT '#409EFF',
                    enabled      TINYINT(1)   NOT NULL DEFAULT 1,
                    sort_order   INT          NOT NULL DEFAULT 0,
                    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # keyword 表：关键词
            cur.execute("""
                CREATE TABLE IF NOT EXISTS keyword (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    topic_id     INT          NULL,
                    word         VARCHAR(100) NOT NULL,
                    language     VARCHAR(10)  DEFAULT '',
                    match_mode   VARCHAR(20)  NOT NULL DEFAULT 'fuzzy' COMMENT 'exact|fuzzy|regex',
                    weight       INT          NOT NULL DEFAULT 1,
                    enabled      TINYINT(1)   NOT NULL DEFAULT 1,
                    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (topic_id) REFERENCES topic(id) ON DELETE CASCADE,
                    INDEX idx_kw_topic (topic_id),
                    UNIQUE KEY uk_topic_word (topic_id, word, language)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # grab_keyword_hit 表：文章-关键词命中关联
            cur.execute("""
                CREATE TABLE IF NOT EXISTS grab_keyword_hit (
                    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
                    grab_id      INT          NOT NULL,
                    keyword_id   INT          NOT NULL,
                    topic_id     INT          NULL,
                    hit_count    INT          NOT NULL DEFAULT 1,
                    score        INT          NOT NULL DEFAULT 0,
                    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (grab_id) REFERENCES grab(id) ON DELETE CASCADE,
                    FOREIGN KEY (keyword_id) REFERENCES keyword(id) ON DELETE CASCADE,
                    UNIQUE KEY uk_grab_kw (grab_id, keyword_id),
                    INDEX idx_hit_kw (keyword_id),
                    INDEX idx_hit_topic (topic_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # keyword_trend 表：关键词词频趋势快照
            cur.execute("""
                CREATE TABLE IF NOT EXISTS keyword_trend (
                    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
                    keyword_id   INT          NOT NULL,
                    topic_id     INT          NULL,
                    time_bucket  DATETIME     NOT NULL,
                    grain        VARCHAR(10)  NOT NULL COMMENT 'hour|day',
                    article_cnt  INT          NOT NULL DEFAULT 0,
                    hit_cnt      INT          NOT NULL DEFAULT 0,
                    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (keyword_id) REFERENCES keyword(id) ON DELETE CASCADE,
                    UNIQUE KEY uk_kw_bucket (keyword_id, grain, time_bucket),
                    INDEX idx_trend_topic (topic_id, grain, time_bucket)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # hotspot_event 表：热点事件/告警
            cur.execute("""
                CREATE TABLE IF NOT EXISTS hotspot_event (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    keyword_id   INT          DEFAULT NULL,
                    topic_id     INT          NULL,
                    window_start DATETIME     NOT NULL,
                    window_end   DATETIME     NOT NULL,
                    article_cnt  INT          NOT NULL DEFAULT 0,
                    hit_cnt      INT          NOT NULL DEFAULT 0,
                    baseline     DECIMAL(10,2) DEFAULT 0,
                    ratio        DECIMAL(10,2) DEFAULT 0,
                    level        VARCHAR(10)  NOT NULL DEFAULT 'low' COMMENT 'low|mid|high',
                    is_read      TINYINT(1)   NOT NULL DEFAULT 0,
                    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (keyword_id) REFERENCES keyword(id) ON DELETE SET NULL,
                    INDEX idx_hot_time (window_start DESC),
                    INDEX idx_hot_level (level)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # schedule_config 表：调度配置（source_id=0 表示全局默认，不加 FK）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schedule_config (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    source_id    INT          NOT NULL UNIQUE,
                    cron_expr    VARCHAR(50)  NOT NULL DEFAULT '',
                    limit_count  INT          NOT NULL DEFAULT 10,
                    enabled      TINYINT(1)   NOT NULL DEFAULT 1,
                    updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_sched_source (source_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

            # ==================== 去主题化迁移（topic_id 可空） ====================
            # 关键词不再强制归属主题，用户可直接创建独立热点词
            for _tbl in ("keyword", "grab_keyword_hit", "keyword_trend", "hotspot_event"):
                try:
                    cur.execute(f"ALTER TABLE {_tbl} MODIFY COLUMN topic_id INT NULL")
                except Exception:
                    pass  # 已改过

            # ==================== 「教程第 7 节优化」结构迁移（幂等） ====================
            # 1) keyword.variants — Query Expansion 变体列表（JSON 数组）
            cur.execute("""
                SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA='DataGrab' AND TABLE_NAME='keyword' AND COLUMN_NAME='variants'
            """)
            if cur.fetchone()[0] == 0:
                cur.execute("ALTER TABLE keyword ADD COLUMN variants JSON DEFAULT NULL COMMENT 'Query Expansion 变体列表 [\"v1\",\"v2\"]' AFTER word")
                logger.info("Added keyword.variants column")

            # 2) grab_keyword_hit：match_type（直接提及=word / 变体提及=variant）+ matched_variant 文本
            for col, ddl in [
                ("match_type",
                 "ALTER TABLE grab_keyword_hit ADD COLUMN match_type VARCHAR(10) NOT NULL DEFAULT 'word' COMMENT 'word|variant' AFTER score"),
                ("matched_variant",
                 "ALTER TABLE grab_keyword_hit ADD COLUMN matched_variant VARCHAR(255) DEFAULT NULL COMMENT '具体命中的变体/原词' AFTER match_type"),
                ("direct_mention",
                 "ALTER TABLE grab_keyword_hit ADD COLUMN direct_mention TINYINT(1) NOT NULL DEFAULT 0 COMMENT '1=标题或正文直接提到原始词 word，作为锚点证据'"),
            ]:
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA='DataGrab' AND TABLE_NAME='grab_keyword_hit' AND COLUMN_NAME=%s
                """, (col,))
                if cur.fetchone()[0] == 0:
                    cur.execute(ddl)
                    logger.info(f"Added grab_keyword_hit.{col} column")

            # 3) grab 表：相关性评分、锚点、推理原因
            for col, ddl in [
                ("relevance_score",
                 "ALTER TABLE grab ADD COLUMN relevance_score FLOAT DEFAULT NULL COMMENT 'AI 或规则相关性评分 0-100' AFTER tags"),
                ("keyword_mentioned",
                 "ALTER TABLE grab ADD COLUMN keyword_mentioned TINYINT(1) DEFAULT NULL COMMENT '1=内容直接提到监控关键词或变体'"),
                ("relevance_reason",
                 "ALTER TABLE grab ADD COLUMN relevance_reason VARCHAR(1000) DEFAULT '' COMMENT '相关/不相关的推理过程简述'"),
            ]:
                cur.execute("""
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA='DataGrab' AND TABLE_NAME='grab' AND COLUMN_NAME=%s
                """, (col,))
                if cur.fetchone()[0] == 0:
                    cur.execute(ddl)
                    logger.info(f"Added grab.{col} column")

            # 4) notification_pending：通知聚合（教程扩展：批次推送，避免每条 1 推）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notification_pending (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    bucket_start  DATETIME     NOT NULL COMMENT '聚合窗口起点',
                    bucket_end    DATETIME     NOT NULL COMMENT '聚合窗口终点',
                    topic_id      INT          DEFAULT NULL,
                    keyword_id    INT          DEFAULT NULL,
                    event_level   VARCHAR(10)  NOT NULL DEFAULT 'mid',
                    article_cnt   INT          NOT NULL DEFAULT 0,
                    summary       VARCHAR(500) NOT NULL DEFAULT '',
                    status        VARCHAR(10)  NOT NULL DEFAULT 'pending' COMMENT 'pending|sent|ignored',
                    channel       VARCHAR(20)  NOT NULL DEFAULT 'inapp' COMMENT 'inapp|email|lark|wecom',
                    sent_at       DATETIME     DEFAULT NULL,
                    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_notif_status (status, created_at),
                    INDEX idx_notif_bucket (bucket_start)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)

        conn.commit()

        # ==================== 预置 seed 数据（幂等，INSERT IGNORE） ====================
        _seed_topics_and_keywords(conn)
        _seed_global_config(conn)
        logger.info("Database initialized: DataGrab (source/scrape_job/grab/topic/keyword/trend/hotspot/schedule + variants + relevance config)")
    finally:
        conn.close()


def _seed_topics_and_keywords(conn):
    """预置 3 个默认主题和每类核心关键词（幂等，只插不存在的）。

    跳过策略（防止重启后反复插入被删除的预设词）：
    - keyword 表已有任何记录（用户自建或预设）则跳过整个 seed
    - 查询异常时 fail-safe 跳过（不插入，避免误覆盖用户数据）
    """
    from datetime import datetime
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM keyword")
            total_kw = cur.fetchone()[0]
            if total_kw > 0:
                logger.info(f"Seed skipped: {total_kw} keywords already exist in DB")
                return
    except Exception as e:
        logger.warning(f"Seed skip-check failed ({e}), aborting seed to avoid overwrite")
        return
    # 每个关键词：(word, lang, match_mode, weight, [变体列表])
    # Query Expansion 规则版：同义词/简称/英文变体（教程推荐 50-60 阈值的基础覆盖）
    default_topics = [
        # (name, description, color, sort_order, keywords_list)
        ("军事/战场动态", "军事冲突、战场态势、兵力部署、武器装备、伤亡损失",
         "#F56C6C", 1, [
             ("战线", "zh", "fuzzy", 2, ["战线", "阵线", "防线"]),
             ("反攻", "zh", "fuzzy", 3, ["反攻", "反击", "反推", "counterattack", "counteroffensive"]),
             ("进攻", "zh", "fuzzy", 3, ["进攻", "攻势", "推进", "猛攻", "发起进攻"]),
             ("空袭", "zh", "fuzzy", 3, ["空袭", "轰炸", "空中打击", "airstrike", "air raid"]),
             ("导弹", "zh", "fuzzy", 3, ["导弹", "弹道导弹", "巡航导弹", "missile", "rocket strike"]),
             ("坦克", "zh", "fuzzy", 2, ["坦克", "装甲车", "主战坦克", "tank"]),
             ("伤亡", "zh", "fuzzy", 3, ["伤亡", "死伤", "阵亡", "遇难", "casualty", "killed"]),
             ("士兵", "zh", "fuzzy", 1, ["士兵", "军人", "官兵", "战士", "troops", "soldier"]),
             ("部队", "zh", "fuzzy", 1, ["部队", "兵力", "军队", "武装力量", "troops", "forces"]),
             ("防线", "zh", "fuzzy", 2, ["防线", "防御工事", "阵地", "defense line"]),
             ("炮击", "zh", "fuzzy", 2, ["炮击", "炮火", "炮兵打击", "artillery shelling", "shelling"]),
             ("装备损失", "zh", "fuzzy", 3, ["装备损失", "损毁装备", "击毁装甲", "loss of equipment"]),
             ("counteroffensive", "en", "fuzzy", 3, ["counteroffensive", "counter-attack", "counterattack"]),
             ("airstrike", "en", "fuzzy", 3, ["airstrike", "air strike", "air raid", "bombing run"]),
             ("missile", "en", "fuzzy", 2, ["missile", "ballistic missile", "cruise missile", "rocket strike"]),
             ("casualty", "en", "fuzzy", 3, ["casualty", "casualties", "killed in action", "wounded"]),
             ("frontline", "en", "fuzzy", 2, ["frontline", "front line", "front positions"]),
             ("artillery", "en", "fuzzy", 2, ["artillery", "shelling", "howitzer", "barrage"]),
             ("drone", "en", "fuzzy", 2, ["drone", "UAV", "Shahed", "loitering munition"]),
             ("tank", "en", "fuzzy", 2, ["tank", "armor", "armoured vehicle", "AFV", "IFV"]),
         ]),
        ("政治/外交动向", "外交表态、政策发布、领导人讲话、国际峰会、制裁谈判",
         "#409EFF", 2, [
             ("制裁", "zh", "fuzzy", 3, ["制裁", "封禁", "惩罚性措施", "sanction", "embargo"]),
             ("峰会", "zh", "fuzzy", 2, ["峰会", "峰会召开", "高层会晤", "summit", "high-level meeting"]),
             ("谈判", "zh", "fuzzy", 3, ["谈判", "磋商", "会谈", "negotiation", "talks"]),
             ("停火", "zh", "fuzzy", 3, ["停火", "停战", "休战", "ceasefire", "truce"]),
             ("外交", "zh", "fuzzy", 2, ["外交", "外交往来", "外交关系", "diplomacy", "foreign ministry"]),
             ("总统", "zh", "fuzzy", 1, ["总统", "总理", "首相", "领导人", "president", "PM"]),
             ("表态", "zh", "fuzzy", 2, ["表态", "声明", "发表评论", "statement", "announcement"]),
             ("决议", "zh", "fuzzy", 2, ["决议", "草案", "表决", "resolution", "draft"]),
             ("援助", "zh", "fuzzy", 2, ["援助", "军援", "援助计划", "aid", "assistance", "aid package"]),
             ("联合国", "zh", "fuzzy", 2, ["联合国", "安理会", "UN", "United Nations", "Security Council"]),
             ("北约", "zh", "fuzzy", 2, ["北约", "NATO", "北大西洋公约组织"]),
             ("G7", "zh", "exact", 3, ["G7", "七国集团", "Group of Seven"]),
             ("sanction", "en", "fuzzy", 3, ["sanction", "sanctions", "embargo", "penalty"]),
             ("summit", "en", "fuzzy", 2, ["summit", "summit meeting", "high-level talks"]),
             ("negotiation", "en", "fuzzy", 3, ["negotiation", "talks", "negotiations", "mediation"]),
             ("ceasefire", "en", "fuzzy", 3, ["ceasefire", "cease-fire", "truce", "armistice"]),
             ("diplomacy", "en", "fuzzy", 2, ["diplomacy", "diplomatic", "foreign ministry", "envoy"]),
             ("NATO", "en", "exact", 3, ["NATO", "North Atlantic Treaty Organization"]),
             ("UN", "en", "exact", 2, ["UN", "United Nations", "Security Council"]),
             ("aid package", "en", "fuzzy", 3, ["aid package", "military aid", "assistance plan", "lethal aid"]),
         ]),
        ("舆情/社媒讨论", "舆论情绪、谣言传播、信息战、关键人物言论、社会反应",
         "#67C23A", 3, [
             ("舆论", "zh", "fuzzy", 2, ["舆论", "公众舆论", "民意反响", "public opinion"]),
             ("谣言", "zh", "fuzzy", 3, ["谣言", "传言", "不实信息", "rumour", "fake news"]),
             ("言论", "zh", "fuzzy", 1, ["言论", "发声", "发言", "comments", "remarks"]),
             ("信息战", "zh", "fuzzy", 3, ["信息战", "认知战", "虚假信息", "information warfare", "disinformation"]),
             ("民意", "zh", "fuzzy", 2, ["民意", "民心", "公众支持率", "public sentiment"]),
             ("抗议", "zh", "fuzzy", 2, ["抗议", "示威", "游行", "protest", "demonstration"]),
             ("社交媒体", "zh", "fuzzy", 2, ["社交媒体", "社交平台", "社媒", "social media", "platform"]),
             ("推特", "zh", "fuzzy", 2, ["推特", "Twitter", "X 平台"]),
             ("传播", "zh", "fuzzy", 1, ["传播", "扩散", "疯传", "viral", "spread"]),
             ("fake news", "en", "fuzzy", 3, ["fake news", "disinformation", "misinformation", "hoax"]),
             ("propaganda", "en", "fuzzy", 3, ["propaganda", "state media", "narrative"]),
             ("disinformation", "en", "fuzzy", 3, ["disinformation", "misinformation", "fake news", "info ops"]),
             ("viral", "en", "fuzzy", 2, ["viral", "trending", "widely shared", "spreading"]),
             ("public opinion", "en", "fuzzy", 2, ["public opinion", "sentiment", "polling"]),
             ("protest", "en", "fuzzy", 2, ["protest", "rally", "demonstration", "march"]),
             ("social media", "en", "fuzzy", 1, ["social media", "platform", "X", "Facebook", "Telegram"]),
             ("Twitter", "en", "exact", 2, ["Twitter", "X platform", "X.com"]),
         ]),
    ]
    try:
        with conn.cursor() as cur:
            for topic_name, desc, color, sort_order, keywords in default_topics:
                cur.execute(
                    "INSERT IGNORE INTO topic (name, description, color, sort_order, enabled) "
                    "VALUES (%s, %s, %s, %s, 1)",
                    (topic_name, desc, color, sort_order)
                )
                cur.execute("SELECT id FROM topic WHERE name = %s", (topic_name,))
                row = cur.fetchone()
                topic_id = row[0] if row else None
                if not topic_id:
                    continue
                for kw_tuple in keywords:
                    if len(kw_tuple) == 4:
                        word, lang, mode, weight = kw_tuple
                        variants = None
                    else:
                        word, lang, mode, weight, variants_list = kw_tuple
                        variants = list(variants_list) if variants_list else None
                    cur.execute(
                        "INSERT IGNORE INTO keyword (topic_id, word, language, match_mode, weight, enabled) "
                        "VALUES (%s, %s, %s, %s, %s, 1)",
                        (topic_id, word, lang, mode, weight)
                    )
                    # 无论是否 INSERT IGNORE，都补 variants 字段（已有词首次补时 variants 为 NULL）
                    if variants:
                        cur.execute(
                            "UPDATE keyword SET variants = %s "
                            "WHERE topic_id = %s AND word = %s AND language = %s "
                            "  AND (variants IS NULL OR JSON_LENGTH(variants) = 0)",
                            (json.dumps(variants, ensure_ascii=False), topic_id, word, lang)
                        )
        conn.commit()
        logger.info("Seed topics & keywords + variants inserted (idempotent)")
    except Exception as e:
        logger.warning(f"Seed data insert skipped: {e}")
        conn.rollback()


def _seed_global_config(conn):
    """全局配置 seed（幂等）。

    教程第 7 节要求的阈值、通知聚合参数。
    schedule_config 的 source_id 用负值作为「全局配置」的命名空间，
    避免与真实 source 的 id 正整数冲突。
    """
    # (negative_source_id, cron_expr_meaningful_key, limit_count_as_value, enabled)
    import json
    presets = [
        # -1: relevance_threshold（阈值默认 55，教程推荐 50-60 区间，取中间值）
        (-1, "relevance_threshold", 55, 1),
        # -2: notify_batch_minutes（通知聚合窗口 30min；教程第 7 节扩展 4）
        (-2, "notify_batch_minutes", 30, 1),
        # -3: notify_mode（batch / immediate；默认 batch）
        (-3, "notify_mode_batch", 1, 1),
    ]
    try:
        with conn.cursor() as cur:
            for src_id, _key, limit, enabled in presets:
                cur.execute(
                    "INSERT IGNORE INTO schedule_config "
                    "(source_id, cron_expr, limit_count, enabled) VALUES (%s, %s, %s, %s)",
                    (src_id, _key, limit, enabled)
                )
        conn.commit()
        logger.info("Seed global relevance/notify config inserted (idempotent)")
    except Exception as e:
        logger.warning(f"Seed global config skipped: {e}")
        conn.rollback()


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
    """插入一条抓取结果，返回 id。

    去重：当 source_url 非空且为有效详情页链接（长度>30，排除列表页URL兜底）时，
    先按 (source_name, source_url) 查重；已存在则跳过插入，返回已有记录 id。
    避免定时任务重复抓取同一文章导致 content 重复。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # 去重检查：有效详情页 URL 才查重（列表页兜底 URL 跳过，避免误删同源多文章）
            if source_url and len(source_url) > 30:
                cur.execute(
                    "SELECT id FROM grab WHERE source_name = %s AND source_url = %s LIMIT 1",
                    (source_name, source_url)
                )
                row = cur.fetchone()
                if row:
                    logger.debug(
                        f"grab_insert dedup skip: source={source_name} "
                        f"url={source_url[:60]} already exists as id={row['id']}"
                    )
                    return 0  # 0 表示去重跳过，未实际插入（自增id均>0）
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
              data_type: str = None,
              keyword_id: int = None,
              search: str = None) -> List[dict]:
    """查询抓取结果，可按数据源/任务ID/关键词/搜索词过滤。

    keyword_id: 仅返回命中该关键词的文章（通过 grab_keyword_hit 关联）
    search:     在 title/summary/content 中模糊匹配
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            joins = []
            conditions = []
            params = []
            if source_name:
                conditions.append("g.source_name = %s")
                params.append(source_name)
            if job_id:
                conditions.append("g.job_id = %s")
                params.append(job_id)
            if keyword_id:
                joins.append("JOIN grab_keyword_hit h ON h.grab_id = g.id")
                conditions.append("h.keyword_id = %s")
                params.append(keyword_id)
            if search:
                conditions.append("(g.title LIKE %s OR g.summary LIKE %s OR g.content LIKE %s)")
                kw = f"%{search}%"
                params.extend([kw, kw, kw])
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            join_clause = " ".join(joins)
            sql = (f"SELECT DISTINCT g.* FROM grab g {join_clause} {where} "
                   f"ORDER BY g.grabbed_at DESC LIMIT %s OFFSET %s")
            cur.execute(sql, params + [limit, offset])
            return cur.fetchall()
    finally:
        conn.close()


def grab_count(source_name: str = None, job_id: str = None,
               keyword_id: int = None,
               search: str = None) -> int:
    """统计抓取结果数量，可按数据源/任务ID/关键词/搜索词过滤。"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            joins = []
            conditions = []
            params = []
            if source_name:
                conditions.append("g.source_name = %s")
                params.append(source_name)
            if job_id:
                conditions.append("g.job_id = %s")
                params.append(job_id)
            if keyword_id:
                joins.append("JOIN grab_keyword_hit h ON h.grab_id = g.id")
                conditions.append("h.keyword_id = %s")
                params.append(keyword_id)
            if search:
                conditions.append("(g.title LIKE %s OR g.summary LIKE %s OR g.content LIKE %s)")
                kw = f"%{search}%"
                params.extend([kw, kw, kw])
            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            join_clause = " ".join(joins)
            sql = f"SELECT COUNT(DISTINCT g.id) as cnt FROM grab g {join_clause} {where}"
            cur.execute(sql, params)
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
