"""FastAPI 响应模型（Pydantic）"""

from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel


class SourceInfo(BaseModel):
    """数据源信息"""
    name: str
    description: str
    enabled: bool = True
    type: str = "builtin"  # "builtin" | "redroom"


class ConnectionTestResult(BaseModel):
    """redroom 连接测试结果"""
    success: bool
    message: str
    latency_ms: Optional[float] = None


class ScrapeJobResponse(BaseModel):
    """爬取任务状态"""
    job_id: str
    status: str  # pending | running | completed | failed
    sources: List[str] = []
    source_name: str = ""
    total: int = 0
    limit_count: int = 20
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[List[Any]] = None


class ScrapeJobListResponse(BaseModel):
    """任务历史列表"""
    total: int
    limit: int
    offset: int
    items: List[ScrapeJobResponse]


class DataResponse(BaseModel):
    """数据查询响应"""
    total: int
    limit: int
    offset: int
    items: List[Any]


class ExportResponse(BaseModel):
    """导出响应"""
    success: bool
    format: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    message: Optional[str] = None
