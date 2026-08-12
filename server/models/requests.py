"""FastAPI 请求模型（Pydantic）"""

from typing import Optional, List
from pydantic import BaseModel, Field


class RedroomConnectionTest(BaseModel):
    """测试 redroom 连接请求"""
    url: str = Field(
        default="http://localhost:3000",
        description="redroomcn 服务基 URL",
    )


class RedroomConfig(BaseModel):
    """redroom 数据源配置"""
    url: str = Field(default="http://localhost:3000")
    region: Optional[str] = Field(default="MENA", description="默认地区过滤")
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)
    rate_limit: float = Field(default=1.0, ge=0.1, le=10.0)


class ScrapeRequest(BaseModel):
    """触发爬取任务请求

    params 中的 region 可选：不传则自动使用 configure 保存的默认地区。
    """
    sources: List[str] = Field(
        default=["redroom"],
        description="要爬取的数据源名称列表",
    )
    params: dict = Field(
        default={"endpoint": "articles.list", "limit": 20},
        description="传递给 scraper.scrape(**params) 的参数。"
                    "region 可选，未传时使用 configure 保存的默认值",
    )


class DataQuery(BaseModel):
    """数据查询参数"""
    source: Optional[str] = Field(default=None, description="按数据源名称过滤")
    data_type: Optional[str] = Field(
        default=None,
        description="数据类型: news, military, economic, social",
    )
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ExportRequest(BaseModel):
    """导出请求"""
    format: str = Field(default="json", description="导出格式: json, csv, docx")
    data_type: Optional[str] = Field(default=None)
    source: Optional[str] = Field(default=None)
