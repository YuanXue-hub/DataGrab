"""FastAPI 应用工厂

创建并配置 FastAPI 应用实例，包含：
- 生命周期管理（启动时初始化引擎，关闭时清理）
- CORS 中间件
- 路由挂载
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.dependencies import init_engine, cleanup_engine
from server.routes import sources, scrape, data, export_
from server.routes import topics as topics_routes
from server.routes import analytics as analytics_routes
from server.routes import schedule as schedule_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时初始化 ScraperEngine，关闭时清理资源。
    """
    from core.scheduler import get_scheduler
    init_engine()
    sched = get_scheduler()
    sched.start()
    try:
        yield
    finally:
        sched.stop()
        cleanup_engine()


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例。

    Returns:
        配置完成的 FastAPI 应用
    """
    app = FastAPI(
        title="DataGrab API",
        description="REST API for data source management, scraping, and data retrieval. "
        "Integrates with redroomcn geopolitical intelligence platform.",
        version="0.2.0",
        docs_url="/docs",
        lifespan=lifespan,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载路由模块
    app.include_router(sources.router, prefix="/api", tags=["Sources"])
    app.include_router(scrape.router, prefix="/api", tags=["Scrape"])
    app.include_router(data.router, prefix="/api", tags=["Data"])
    app.include_router(export_.router, prefix="/api", tags=["Export"])
    app.include_router(topics_routes.router, prefix="/api", tags=["Topics & Keywords"])
    app.include_router(analytics_routes.router, prefix="/api", tags=["Analytics & Hotspot"])
    app.include_router(schedule_routes.router, prefix="/api", tags=["Scheduler"])

    # 健康检查端点
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "version": "0.2.0"}

    return app


# 模块级实例，供 CLI / ASGI 服务器（uvicorn server.app:app）直接引用
app = create_app()
