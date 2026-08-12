"""数据模型定义

使用 dataclass 定义所有数据结构：
- NewsArticle: 新闻文章
- MilitaryData: 军事/战场数据
- EconomicData: 经济/制裁数据
- SocialPost: 社交媒体帖子
- RawData: 爬取原始数据
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class NewsArticle:
    """新闻文章数据模型"""
    title: str
    content: str
    summary: str = ""
    source_name: str = ""
    source_url: str = ""
    language: str = "en"          # 'zh' | 'en' | 'ru' | 'uk'
    published_at: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    tags: list[str] = field(default_factory=list)
    category: str = ""            # 'war' | 'politics' | 'economy' | 'humanitarian'

    def __repr__(self):
        return f"NewsArticle(title={self.title[:50]!r}, source={self.source_name})"


@dataclass
class MilitaryData:
    """军事/战场数据模型"""
    data_type: str                # 'casualty' | 'equipment_loss' | 'territory' | 'battle_event'
    metric_name: str              # 指标名称
    value: Any                    # 数值
    unit: str = ""                # 单位 (人、辆、架、km²)
    side: str = ""                # 'russia' | 'ukraine' | 'both'
    language: str = "en"          # 'zh' | 'en' | 'ru' | 'uk'
    location: Optional[str] = None
    source_name: str = ""
    source_url: str = ""
    reported_at: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    confidence: str = "claimed"   # 'confirmed' | 'claimed' | 'estimated'
    notes: str = ""

    def __repr__(self):
        return f"MilitaryData({self.metric_name}={self.value}{self.unit}, side={self.side})"


@dataclass
class EconomicData:
    """经济/制裁数据模型"""
    indicator: str                # 'sanction' | 'energy_price' | 'trade' | 'aid'
    description: str
    value: Any = None
    unit: str = ""
    country: str = ""             # 受制裁/影响国家
    language: str = "en"          # 'zh' | 'en' | 'ru' | 'uk'
    source_name: str = ""
    source_url: str = ""
    reported_at: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)

    def __repr__(self):
        return f"EconomicData({self.indicator}: {self.value}, country={self.country})"


@dataclass
class SocialPost:
    """社交媒体帖子数据模型"""
    platform: str                 # 'twitter' | 'reddit' | 'telegram' | 'weibo'
    author: str = ""
    content: str = ""
    language: str = "en"
    engagement: dict = field(default_factory=dict)  # likes, shares, comments
    posted_at: Optional[datetime] = None
    scraped_at: datetime = field(default_factory=datetime.now)
    url: str = ""
    hashtags: list[str] = field(default_factory=list)
    is_verified: bool = False     # 作者是否认证

    def __repr__(self):
        return f"SocialPost(platform={self.platform}, author={self.author})"


@dataclass
class RawData:
    """爬取原始数据（未解析）"""
    source_name: str
    source_url: str
    raw_html: str = ""
    raw_json: dict = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=datetime.now)
    status_code: int = 0
    headers: dict = field(default_factory=dict)

    def __repr__(self):
        return f"RawData(source={self.source_name}, url={self.source_url[:60]})"


# 类型别名
DataItem = NewsArticle | MilitaryData | EconomicData | SocialPost
