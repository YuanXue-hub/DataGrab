"""数据管道

实现 Scrape → Parse → Clean → Validate → Store 的处理管道。
"""

from typing import List, Callable, Optional
from dataclasses import dataclass

from loguru import logger

from storage.models import DataItem, RawData


@dataclass
class PipelineStats:
    """管道统计数据"""
    scraped: int = 0        # 原始页面抓取数
    parsed: int = 0         # 成功解析数
    failed: int = 0         # 失败数
    total_items: int = 0    # 最终数据条数

    def __repr__(self):
        return (f"PipelineStats(scraped={self.scraped}, parsed={self.parsed}, "
                f"failed={self.failed}, total={self.total_items})")


class Pipeline:
    """数据处理管道

    依次执行以下步骤：
    1. 爬取 (scrape)    - 从数据源获取原始数据
    2. 解析 (parse)     - 将原始数据解析为结构化数据
    3. 清洗 (clean)     - 清洗文本、去除噪声
    4. 校验 (validate)  - 校验数据完整性和合法性
    5. 存储 (store)     - 暂存到本地
    """

    def __init__(self):
        self.stats = PipelineStats()
        self._cleaners: List[Callable] = []
        self._validators: List[Callable] = []
        self._stored_items: List[DataItem] = []

    def add_cleaner(self, cleaner: Callable[[DataItem], DataItem]):
        """添加数据清洗步骤

        Args:
            cleaner: 清洗函数，接受并返回 DataItem
        """
        self._cleaners.append(cleaner)

    def add_validator(self, validator: Callable[[DataItem], bool]):
        """添加数据校验步骤

        Args:
            validator: 校验函数，返回 True 表示通过
        """
        self._validators.append(validator)

    def run(
        self,
        raw_items: List[RawData],
        parser: Callable[[RawData], List[DataItem]],
        source_name: str = "unknown",
    ) -> List[DataItem]:
        """运行管道处理原始数据

        Args:
            raw_items: 原始数据列表
            parser: 解析函数
            source_name: 数据源名称（用于日志）

        Returns:
            处理后的数据列表
        """
        self.stats = PipelineStats()
        self.stats.scraped = len(raw_items)
        results: List[DataItem] = []

        logger.info(f"[{source_name}] Pipeline start: {len(raw_items)} raw items")

        for i, raw in enumerate(raw_items):
            try:
                # Step 2: Parse
                parsed_items = parser(raw)
                if not parsed_items:
                    self.stats.failed += 1
                    continue

                for item in parsed_items:
                    # Step 3: Clean
                    for cleaner in self._cleaners:
                        try:
                            item = cleaner(item)
                        except Exception as e:
                            logger.debug(f"Cleaner error on {item}: {e}")

                    # Step 4: Validate
                    is_valid = True
                    for validator in self._validators:
                        try:
                            if not validator(item):
                                is_valid = False
                                break
                        except Exception as e:
                            logger.debug(f"Validator error on {item}: {e}")

                    if is_valid:
                        results.append(item)
                        self.stats.parsed += 1
                    else:
                        self.stats.failed += 1

            except Exception as e:
                logger.error(f"[{source_name}] Parse error on item {i}: {e}")
                self.stats.failed += 1

        self.stats.total_items = len(results)
        self._stored_items = results

        logger.info(
            f"[{source_name}] Pipeline done: "
            f"{self.stats.parsed} parsed, {self.stats.failed} failed, "
            f"{self.stats.total_items} total"
        )
        return results

    def get_items(self) -> List[DataItem]:
        """获取最后一次管道运行的结果"""
        return self._stored_items

    def clear(self):
        """清空暂存数据"""
        self._stored_items.clear()
        self.stats = PipelineStats()
