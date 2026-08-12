"""文本清洗工具

提供 HTML 清洗、空白规范化、特殊字符处理等功能。
"""

import re
import html as html_module


def clean_html(raw_html: str) -> str:
    """清洗 HTML 标签，提取纯文本

    Args:
        raw_html: 包含 HTML 标签的原始文本

    Returns:
        清洗后的纯文本
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw_html, "lxml")
    # 移除 script/style 标签
    for tag in soup(["script", "style", "nav", "footer", "aside"]):
        tag.decompose()
    return soup.get_text()


def normalize_whitespace(text: str) -> str:
    """规范化空白字符

    - 合并多个空格/换行
    - 去除首尾空白
    - 保留单个换行作为段落分隔

    Args:
        text: 原始文本

    Returns:
        规范化后的文本
    """
    # 将多个换行合并为两个换行（段落分隔）
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 将多个空格合并为一个
    text = re.sub(r"[ \t]+", " ", text)
    # 去除行首行尾空格
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    # 去除首尾空白
    text = text.strip()
    return text


def clean_text(text: str) -> str:
    """综合文本清洗

    Args:
        text: 原始文本

    Returns:
        清洗后的文本
    """
    # HTML 实体解码
    text = html_module.unescape(text)
    # 移除零宽字符
    text = re.sub(r"[​‌‍‎‏﻿]", "", text)
    # 规范化空白
    text = normalize_whitespace(text)
    return text


def extract_date_from_text(text: str) -> str | None:
    """从文本中提取日期

    支持常见日期格式：
    - 2024-06-08
    - 2024年6月8日
    - June 8, 2024
    - 08/06/2024

    Args:
        text: 包含日期信息的文本

    Returns:
        ISO 格式日期字符串 (YYYY-MM-DD)，未找到返回 None
    """
    # ISO 格式: 2024-06-08
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"

    # 中文格式: 2024年6月8日
    match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if match:
        return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"

    # 英文格式: June 8, 2024
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    match = re.search(
        r"(" + "|".join(months.keys()) + r")\s+(\d{1,2}),?\s+(\d{4})",
        text, re.IGNORECASE
    )
    if match:
        month = months[match.group(1).lower()]
        day = match.group(2).zfill(2)
        year = match.group(3)
        return f"{year}-{month}-{day}"

    # 数字格式: 06/08/2024 或 08/06/2024 (优先 MM/DD/YYYY)
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if match:
        return f"{match.group(3)}-{match.group(1).zfill(2)}-{match.group(2).zfill(2)}"

    return None


def extract_numbers(text: str) -> list[int]:
    """从文本中提取所有数字

    Args:
        text: 原始文本

    Returns:
        数字列表
    """
    numbers = re.findall(r"(\d{1,3}(?:,\d{3})*|\d+)", text)
    return [int(n.replace(",", "")) for n in numbers if n]


def truncate_text(text: str, max_length: int = 500) -> str:
    """截断文本到指定长度（保持单词完整）

    Args:
        text: 原始文本
        max_length: 最大长度

    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    # 尝试在空格处截断
    truncated = text[:max_length]
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.8:
        return truncated[:last_space] + "..."
    return truncated + "..."
