#!/usr/bin/env python3
"""DataGrab - 俄乌冲突数据爬虫工具

用法:
    python main.py run [--sources bbc,xinhua] [--max 20] [--parallel]
    python main.py list-sources
    python main.py export [--format docx] [--output ./output/report.docx]

示例:
    # 运行所有启用的爬虫
    python main.py run

    # 只运行 BBC 和 ISW
    python main.py run --sources bbc,isw --max 10

    # 并行运行所有爬虫
    python main.py run --parallel

    # 列出可用数据源
    python main.py list-sources

    # 导出为 Word 文档（默认）
    python main.py export

    # 导出为 CSV
    python main.py export --format csv
"""

import sys
import argparse
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent))


def setup_environment():
    """初始化运行环境"""
    from utils.logger import setup_logger
    setup_logger(log_level="INFO", log_dir="./logs")


def cmd_list_sources(args):
    """列出所有可用数据源"""
    from scrapers import list_scrapers

    print("\n📋 可用数据源 / Available Sources:\n")
    print(f"{'名称':<15} {'描述':<50}")
    print("-" * 65)
    for name, desc in list_scrapers().items():
        print(f"  {name:<13} {desc:<50}")
    print()


def cmd_run(args):
    """执行爬取任务"""
    from loguru import logger

    from core.engine import ScraperEngine
    from scrapers import get_scraper_class, SCRAPER_REGISTRY

    # 创建引擎（支持代理配置）
    engine = ScraperEngine(
        max_concurrent=3,
        proxy=getattr(args, "proxy", None),
    )

    # 注册爬虫
    sources = args.sources.split(",") if args.sources else list(SCRAPER_REGISTRY.keys())

    logger.info(f"准备运行 {len(sources)} 个数据源: {sources}")

    for name in sources:
        name = name.strip()
        try:
            cls = get_scraper_class(name)
            if cls:
                engine.register_scraper(name, cls)
                logger.info(f"  已注册: {name}")
        except ImportError as e:
            logger.warning(f"  跳过 {name}: {e}")

    if not engine.list_sources():
        logger.error("没有可用的数据源！")
        return

    # 执行爬取
    results = engine.run(
        sources=sources,
        max_per_source=args.max,
        parallel=args.parallel,
    )

    # 自动导出
    if results and args.export:
        _do_export(engine, args)

    # 清理
    engine.cleanup()

    # 打印摘要
    print(f"\n✅ 爬取完成: 共获取 {len(results)} 条数据")
    print(engine.get_repository().summary())


def cmd_export(args):
    """独立导出命令"""
    from loguru import logger
    from storage.repository import Repository

    logger.warning("Export command requires previously scraped data.")
    logger.info(
        "Use 'python main.py run --export' to scrape and export in one step."
    )
    print("\n💡 提示: 使用 'python main.py run --export' 在一次操作中爬取并导出")


def cmd_serve(args):
    """启动 FastAPI 服务"""
    import uvicorn
    from loguru import logger

    logger.info(f"Starting DataGrab API server on {args.host}:{args.port}")
    uvicorn.run(
        "server.app:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


def _do_export(engine, args):
    """执行导出操作"""
    from loguru import logger
    from exporters.word_exporter import export_to_word
    from exporters.csv_exporter import CSVExporter

    repo = engine.get_repository()
    if repo.count() == 0:
        logger.warning("No data to export")
        return

    fmt = args.format or "docx"

    if fmt == "docx":
        output_path = args.output or "./output/report.docx"
        path = export_to_word(
            repo,
            output_path,
            report_title="俄乌冲突数据报告",
        )
        print(f"\n📄 Word 报告已导出: {path}")

    elif fmt == "csv":
        exporter = CSVExporter()
        output_dir = args.output or "./output"
        files = exporter.export(repo, output_dir)
        print(f"\n📊 CSV 文件已导出 ({len(files)} 个):")
        for f in files:
            print(f"   {f}")

    elif fmt == "json":
        import json
        from dataclasses import asdict
        output_path = args.output or "./output/data.json"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        # 简单序列化（dataclass 不支持直接 json.dumps）
        data = []
        for item in repo.get_all():
            try:
                data.append(asdict(item))
            except TypeError:
                data.append(str(item))
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n📄 JSON 数据已导出: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="DataGrab - 俄乌冲突数据爬虫工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py run                     # 运行所有可用爬虫
  python main.py run --sources bbc,isw   # 只运行指定数据源
  python main.py run --parallel --export  # 并行爬取并导出
  python main.py list-sources             # 列出可用数据源
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run 命令
    run_parser = subparsers.add_parser("run", help="执行爬取任务")
    run_parser.add_argument(
        "--sources", "-s",
        type=str,
        help="数据源名称，逗号分隔 (如: bbc,xinhua,isw)"
    )
    run_parser.add_argument(
        "--max", "-m",
        type=int,
        default=20,
        help="每个数据源最大爬取条数 (默认: 20)"
    )
    run_parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="并行运行多个爬虫"
    )
    run_parser.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="代理地址 (如: http://127.0.0.1:7890)"
    )
    run_parser.add_argument(
        "--export", "-e",
        action="store_true",
        default=True,
        help="爬取后自动导出 (默认: 开启)"
    )
    run_parser.add_argument(
        "--format", "-f",
        choices=["docx", "csv", "json"],
        default="docx",
        help="导出格式 (默认: docx)"
    )
    run_parser.add_argument(
        "--output", "-o",
        type=str,
        help="导出文件路径"
    )

    # list-sources 命令
    list_parser = subparsers.add_parser("list-sources", help="列出所有可用数据源")

    # export 命令
    export_parser = subparsers.add_parser("export", help="导出已有数据")
    export_parser.add_argument("--format", "-f", choices=["docx", "csv", "json"], default="docx")
    export_parser.add_argument("--output", "-o", type=str)

    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="启动 FastAPI 服务")
    serve_parser.add_argument(
        "--host", type=str, default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", type=int, default=8000, help="监听端口 (默认: 8000)"
    )
    serve_parser.add_argument(
        "--reload", action="store_true", help="开启热重载（开发模式）"
    )

    args = parser.parse_args()

    # 初始化环境
    setup_environment()

    # 分发命令
    if args.command == "run":
        cmd_run(args)
    elif args.command == "list-sources":
        cmd_list_sources(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "serve":
        cmd_serve(args)
    else:
        parser.print_help()
        print("\n💡 使用 'python main.py run' 开始爬取数据")


if __name__ == "__main__":
    main()
