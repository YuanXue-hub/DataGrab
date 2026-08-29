"""热点监控相关 Pydantic 请求/响应模型"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================
#  Topic
# ============================

class TopicOut(BaseModel):
    id: int
    name: str
    description: str = ""
    color: str = "#409EFF"
    enabled: int = 1
    sort_order: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class TopicCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: str = ""
    color: str = "#409EFF"
    sort_order: int = 0
    enabled: int = 1


class TopicUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None
    enabled: Optional[int] = None


# ============================
#  Keyword
# ============================

class KeywordOut(BaseModel):
    id: int
    topic_id: Optional[int] = None
    word: str
    language: str = ""
    match_mode: str = "fuzzy"
    weight: int = 1
    enabled: int = 1
    # Query Expansion：变体列表，非空表示启用
    variants: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # joined fields
    topic_name: Optional[str] = None
    topic_color: Optional[str] = None

    @field_validator("variants", mode="before")
    @classmethod
    def _parse_variants(cls, v):
        if v is None:
            return None
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v]
        if isinstance(v, (str, bytes)):
            try:
                data = json.loads(v)
                if isinstance(data, list):
                    return [str(x) for x in data]
            except (json.JSONDecodeError, TypeError):
                return [s.strip() for s in str(v).split(",") if s.strip()]
        return None


class KeywordCreate(BaseModel):
    topic_id: Optional[int] = None
    word: str = Field(..., min_length=1, max_length=100)
    language: str = ""
    match_mode: str = "fuzzy"  # exact | fuzzy | regex
    weight: int = Field(default=1, ge=1, le=10)
    enabled: int = 1
    variants: Optional[List[str]] = None


class KeywordUpdate(BaseModel):
    topic_id: Optional[int] = None
    word: Optional[str] = Field(default=None, max_length=100)
    language: Optional[str] = None
    match_mode: Optional[str] = None
    weight: Optional[int] = Field(default=None, ge=1, le=10)
    enabled: Optional[int] = None
    variants: Optional[List[str]] = None


class KeywordBatchImport(BaseModel):
    topic_id: Optional[int] = None
    """纯文本，每行一个关键词。语法：
    词           → 默认 fuzzy 模式, weight=1, language=''
    词,en        → 指定语言
    词,zh,fuzzy,3 → 指定语言/模式/权重
    """
    words_text: str
    default_language: str = ""
    default_match_mode: str = "fuzzy"
    default_weight: int = 1


class KeywordBatchImportResult(BaseModel):
    inserted: int
    skipped: int = 0


# ============================
#  Trend / Analytics
# ============================

class TrendPoint(BaseModel):
    time_bucket: datetime
    article_cnt: int
    hit_cnt: int


class KeywordTrendSeries(BaseModel):
    keyword_id: int
    word: Optional[str] = None
    topic_id: Optional[int] = None
    color: Optional[str] = None
    points: List[TrendPoint]


class TopicTrendSeries(BaseModel):
    topic_id: Optional[int] = None
    name: Optional[str] = None
    color: Optional[str] = None
    points: List[TrendPoint]


class DashboardSummary(BaseModel):
    today_events: int = 0              # 今日热点事件数
    unread_events: int = 0             # 未读事件数
    articles_24h: int = 0              # 近 24h 新增文章数
    active_topics: int = 0             # 活跃主题数（至少有 1 篇命中的）
    keywords_total: int = 0            # 监控关键词总数
    high_level_events: int = 0         # 高级别事件数
    top_keywords: List[Dict[str, Any]] = []  # Top 关键词 [{keyword_id, word, article_cnt, topic_name, topic_color}]
    topic_distribution: List[Dict[str, Any]] = []  # 主题分布 [{topic_id, name, color, article_cnt}]
    # 教程第 7 节：相关性评估指标
    relevance_threshold: Optional[int] = None
    scored_grabs: Optional[int] = None
    high_relevance_grabs: Optional[int] = None
    high_relevance_rate: Optional[float] = None
    keyword_mentioned_true: Optional[int] = None
    keyword_mentioned_rate: Optional[float] = None
    avg_relevance_score_scored: Optional[float] = None


class HotspotEventOut(BaseModel):
    id: int
    keyword_id: Optional[int] = None
    topic_id: Optional[int] = None
    window_start: datetime
    window_end: datetime
    article_cnt: int
    hit_cnt: int
    baseline: float
    ratio: float
    level: str  # low | mid | high
    is_read: int
    created_at: datetime
    # joined
    topic_name: Optional[str] = None
    topic_color: Optional[str] = None
    keyword_word: Optional[str] = None


class HotspotEventListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[HotspotEventOut]


class EventMarkReadRequest(BaseModel):
    ids: List[int]
    all: bool = False  # True → 全部标记已读，忽略 ids


class RecalcRequest(BaseModel):
    """全量/部分历史重算请求。"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class RecalcResponse(BaseModel):
    ok: bool = True
    grabs_processed: int = 0
    hits_written: int = 0
    trend_buckets: int = 0
    hotspot_events: int = 0


# ============================
#  Schedule
# ============================

class ScheduleConfigOut(BaseModel):
    id: Optional[int] = None
    source_id: int
    cron_expr: str = ""
    limit_count: int = 10
    enabled: int = 1
    updated_at: Optional[datetime] = None
    # joined
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    source_enabled: Optional[int] = None


class ScheduleConfigCreate(BaseModel):
    source_id: int
    cron_expr: str = Field(default="", description="标准 unix 5 段 cron，例: 0 */6 * * *")
    limit_count: int = Field(default=10, ge=1, le=500)
    enabled: int = 1


class ScheduleConfigUpdate(BaseModel):
    cron_expr: Optional[str] = None
    limit_count: Optional[int] = Field(default=None, ge=1, le=500)
    enabled: Optional[int] = None


class ScheduleStatus(BaseModel):
    running: bool
    disabled_env: bool
    aps_available: bool
    jobs: List[Dict[str, Any]] = []


class ScheduleTriggerNowResponse(BaseModel):
    ok: bool
    job_id: Optional[str] = None
    message: Optional[str] = None
