"""军事数据解析器

从军事分析网站提取结构化的战场数据。
侧重于从文本中提取伤亡数字、装备损失、领土变化等信息。
支持多语言关键词匹配。
"""

from typing import List, Optional
from datetime import datetime

from loguru import logger

from core.base_parser import BaseParser
from storage.models import RawData, DataItem, MilitaryData, NewsArticle
from utils.text_cleaner import clean_text, extract_numbers
from utils.language_detector import detect_language


class MilitaryParser(BaseParser):
    """军事数据解析器

    从 ISW、Oryx 等军事分析网站的报告中提取结构化军事数据。
    支持中、英、俄、乌克兰语关键词匹配。
    """

    # 伤亡相关关键词（英文）
    CASUALTY_KEYWORDS_EN = [
        "casualty", "casualties", "killed", "wounded", "dead", "death",
        "fatality", "losses", "troops lost", "personnel losses",
        "soldiers killed", "military dead",
    ]

    # 装备相关关键词
    EQUIPMENT_KEYWORDS_EN = [
        "tank", "tanks", "armored vehicle", "artillery", "aircraft",
        "helicopter", "drone", "UAV", "missile", "air defense",
        "destroyed", "captured", "damaged", "abandoned",
    ]

    # 领土相关关键词
    TERRITORY_KEYWORDS_EN = [
        "captured", "liberated", "occupied", "controlled",
        "advanced", "retreated", "withdrawn",
        "square kilometers", "km²", "territory",
    ]

    # --- 中文关键词 ---
    CASUALTY_KEYWORDS_ZH = [
        "伤亡", "阵亡", "死亡", "受伤", "损失",
        "死伤", "牺牲", "战损", "减员",
    ]
    EQUIPMENT_KEYWORDS_ZH = [
        "坦克", "装甲车", "火炮", "飞机", "直升机",
        "无人机", "导弹", "防空", "摧毁", "缴获", "击毁",
    ]
    TERRITORY_KEYWORDS_ZH = [
        "占领", "解放", "控制", "推进", "撤退", "平方公里",
    ]

    # --- 俄语关键词 ---
    CASUALTY_KEYWORDS_RU = [
        "потер", "убит", "ранен", "погиб", "жертв",
        "уничтожен", "ликвидирован",
    ]
    EQUIPMENT_KEYWORDS_RU = [
        "танк", "танков", "бронемашин", "артиллери",
        "самолет", "вертолет", "беспилотник", "БПЛА",
        "уничтожен", "захвачен", "сбит", "подбит",
    ]
    TERRITORY_KEYWORDS_RU = [
        "освобожден", "занят", "контрол", "продвижен",
        "отступлен", "квадратн километр", "км²",
    ]

    # --- 乌克兰语关键词 ---
    CASUALTY_KEYWORDS_UK = [
        "втрат", "убит", "поранен", "загибл", "жертв",
        "знищен", "ліквідован",
    ]
    EQUIPMENT_KEYWORDS_UK = [
        "танк", "танків", "бронемашин", "артилері",
        "літак", "гелікоптер", "безпілотник", "БПЛА",
        "знищен", "захоплен", "збит", "підбит",
    ]
    TERRITORY_KEYWORDS_UK = [
        "звільнен", "захоплен", "контрол", "просуван",
        "відступ", "квадратн кілометр", "км²",
    ]

    def __init__(self, source_language: str = None):
        """
        Args:
            source_language: 数据源配置的语言代码，作为语言检测提示
        """
        self.source_language = source_language

    def parse(self, raw_data: RawData) -> List[DataItem]:
        """解析军事数据

        从原始 HTML 中提取：
        1. 新闻文章（作为战报记录）
        2. 结构化的军事数据（伤亡、装备、领土）

        Args:
            raw_data: 原始数据

        Returns:
            MilitaryData 和 NewsArticle 列表
        """
        if not raw_data.raw_html:
            return []

        soup = self.make_soup(raw_data)
        results: List[DataItem] = []

        # 提取文章标题
        title = self.get_text(soup, "h1") or self.get_text(soup, "title")

        # 提取正文
        content = self._extract_main_content(soup)

        # 提取日期
        date = self._extract_date(soup)

        if not content:
            return []

        # 检测语言
        cleaned_content = clean_text(content)
        cleaned_title = clean_text(title)
        language = detect_language(
            cleaned_title + " " + cleaned_content,
            hint=self.source_language,
        )

        # 添加新闻文章记录
        article = NewsArticle(
            title=cleaned_title,
            content=cleaned_content,
            source_name=raw_data.source_name,
            source_url=raw_data.source_url,
            language=language,
            published_at=date,
            scraped_at=raw_data.fetched_at,
            tags=["military", "battlefield"],
            category="war",
        )
        results.append(article)

        # 尝试提取结构化军事数据
        military_data = self._extract_military_data(
            cleaned_content, content, raw_data, date, language
        )
        results.extend(military_data)

        return results

    def _extract_main_content(self, soup) -> str:
        """提取主要内容"""
        from parsers.news_parser import NewsParser
        parser = NewsParser()
        return parser._extract_content(soup)

    def _extract_date(self, soup) -> datetime | None:
        """提取发布日期"""
        # ISW 特有日期格式
        date_selectors = [
            ".date-display-single",
            ".submitted-date",
            ".field-name-field-publication-date",
            "time",
        ]
        for selector in date_selectors:
            el = soup.select_one(selector)
            if el:
                date_str = el.get("datetime") or el.get_text(strip=True)
                try:
                    from dateutil.parser import parse as dateutil_parse
                    return dateutil_parse(date_str)
                except Exception:
                    pass
        return None

    def _extract_military_data(
        self, cleaned_content: str, raw_content: str,
        raw_data: RawData, date: datetime | None, language: str,
    ) -> List[MilitaryData]:
        """从文本中提取结构化军事数据

        Args:
            cleaned_content: 清洗后的文本
            raw_content: 原始内容（用于小写匹配）
            raw_data: 原始数据
            date: 发布日期
            language: 检测到的语言代码

        Returns:
            MilitaryData 列表
        """
        results = []
        content_lower = raw_content.lower()

        # 提取伤亡数据
        results.extend(self._extract_casualty_data(
            cleaned_content, content_lower, raw_data, date, language
        ))

        # 提取装备损失数据
        results.extend(self._extract_equipment_data(
            cleaned_content, content_lower, raw_data, date, language
        ))

        # 提取领土变化数据
        results.extend(self._extract_territory_data(
            cleaned_content, content_lower, raw_data, date, language
        ))

        return results

    def _extract_casualty_data(
        self, content: str, content_lower: str, raw_data: RawData,
        date: datetime | None, language: str,
    ) -> List[MilitaryData]:
        """提取伤亡数据"""
        import re
        results = []

        for keyword in self.CASUALTY_KEYWORDS_EN[:5]:
            if keyword in content_lower:
                # 查找关键词附近的数字
                idx = content_lower.find(keyword)
                context = content_lower[max(0, idx - 200):idx + 300]
                numbers = extract_numbers(context)
                if numbers:
                    # 取最大的合理数字（伤亡数通常较大）
                    for n in sorted(numbers, reverse=True):
                        if 10 < n < 1000000:  # 合理范围
                            side = self._determine_side(context)
                            results.append(MilitaryData(
                                data_type="casualty",
                                metric_name=f"{side}_casualties" if side else "total_casualties",
                                value=n,
                                unit="人",
                                side=side,
                                language=language,
                                source_name=raw_data.source_name,
                                source_url=raw_data.source_url,
                                reported_at=date,
                                confidence="claimed",
                            ))
                            break
                break  # 只取第一个主要伤亡数字

        return results

    def _extract_equipment_data(
        self, content: str, content_lower: str, raw_data: RawData,
        date: datetime | None, language: str,
    ) -> List[MilitaryData]:
        """提取装备损失数据"""
        import re
        results = []
        equipment_types = {
            "tank": "tanks_lost",
            "armored vehicle": "armored_vehicles_lost",
            "artillery": "artillery_lost",
            "aircraft": "aircraft_lost",
            "drone": "drones_lost",
            "helicopter": "helicopters_lost",
        }

        for eq_key, metric_name in equipment_types.items():
            if eq_key in content_lower:
                idx = content_lower.find(eq_key)
                context = content_lower[max(0, idx - 100):idx + 100]
                numbers = [n for n in extract_numbers(context) if 0 < n < 50000]
                if numbers:
                    side = self._determine_side(context)
                    results.append(MilitaryData(
                        data_type="equipment_loss",
                        metric_name=metric_name,
                        value=numbers[0],
                        unit="units",
                        side=side,
                        language=language,
                        source_name=raw_data.source_name,
                        source_url=raw_data.source_url,
                        reported_at=date,
                        confidence="claimed",
                    ))

        return results

    def _extract_territory_data(
        self, content: str, content_lower: str, raw_data: RawData,
        date: datetime | None, language: str,
    ) -> List[MilitaryData]:
        """提取领土变化数据"""
        results = []

        if "square kilometer" in content_lower or "km²" in content_lower:
            idx = content_lower.find("square kilometer") if "square kilometer" in content_lower else content_lower.find("km²")
            context = content_lower[max(0, idx - 150):idx + 100]
            numbers = [n for n in extract_numbers(context) if 0 < n < 100000]
            if numbers:
                side = self._determine_side(context)
                results.append(MilitaryData(
                    data_type="territory",
                    metric_name="territory_change",
                    value=numbers[0],
                    unit="km²",
                    side=side,
                    language=language,
                    source_name=raw_data.source_name,
                    source_url=raw_data.source_url,
                    reported_at=date,
                    confidence="estimated",
                ))

        return results

    def _determine_side(self, context: str) -> str:
        """推断数据指代哪一方

        支持中、英、俄、乌克兰语的关键词匹配。
        """
        # 俄方关键词（多语言）
        russia_markers = [
            "russian", "russia", "moscow", "kremlin",
            "российск", "росси", "рф", "москв", "кремл",
            "вс рф", "армия рф",
            "російськ", "росі", "рф", "москв", "кремл",
            "俄军", "俄方", "俄罗斯", "莫斯科", "克里姆林宫",
        ]
        # 乌方关键词（多语言）
        ukraine_markers = [
            "ukrainian", "ukraine", "kyiv",
            "украинск", "украин", "киев", "всу",
            "українськ", "україн", "київ", "зсу",
            "乌军", "乌方", "乌克兰", "基辅",
        ]

        for marker in russia_markers:
            if marker in context.lower():
                return "russia"
        for marker in ukraine_markers:
            if marker in context.lower():
                return "ukraine"
        return ""
