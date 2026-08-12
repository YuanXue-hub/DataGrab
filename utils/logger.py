"""日志配置模块"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(log_level: str = "INFO", log_dir: str = "./logs") -> None:
    """初始化日志配置

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_dir: 日志文件目录
    """
    # 移除默认 handler
    logger.remove()

    # 控制台输出（彩色）
    logger.add(
        sys.stdout,
        level=log_level,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
    )

    # 文件输出（所有级别）
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path / "datagrab_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
    )

    # 错误文件单独输出
    logger.add(
        log_path / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
               "{name}:{function}:{line} | {message}",
    )

    logger.debug("日志系统初始化完成")
