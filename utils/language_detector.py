"""语言检测工具

提供通用的文本语言检测功能，支持中/英/俄/乌克兰语。
所有解析器共享此模块以避免重复实现。
"""

# Unicode 字符范围
CJK_RANGE = ("一", "鿿")        # CJK 统一表意文字（中文）
CYRILLIC_RANGE = ("Ѐ", "ӿ")  # 西里尔字母（俄语、乌克兰语等）

# 乌克兰语独有词汇标记（这些词在俄语中不使用或使用形式不同）
UKRAINIAN_MARKERS = {
    "та",        # "和" — 俄语用 "и"
    "це",        # "这" — 俄语用 "это"
    "що",        # "什么" — 俄语用 "что"
    "він",       # "他" — 俄语用 "он"
    "України",   # "乌克兰的"（属格）
    "Києва",     # "基辅的"（属格）— 俄语用 "Киева"
    "але",       # "但是" — 俄语用 "но"
    "чи",        # "或者" — 俄语用 "или"
    "як",        # "如何" — 俄语用 "как"
    "війська",   # "军队" — 俄语用 "войска"
    "збройні",   # "武装的" — 俄语用 "вооружённые"
    "ЗСУ",       # "乌克兰武装部队"缩写
    "оборони",   # "防御的"（属格）— 俄语用 "обороны"
}

# 俄语独有词汇标记
RUSSIAN_MARKERS = {
    "это",       # "这" — 乌克兰语用 "це"
    "что",       # "什么" — 乌克兰语用 "що"
    "как",       # "如何" — 乌克兰语用 "як"
    "он",        # "他" — 乌克兰语用 "він"
    "России",    # "俄罗斯的"（属格）
    "Москвы",    # "莫斯科的"（属格）
    "Кремля",    # "克里姆林宫的"（属格）
    "спецопераци", # "特别行动"（俄罗斯官方术语）
    "СВО",       # "特别军事行动"缩写（俄罗斯官方术语）
    "демилитаризаци",  # "非军事化"（俄罗斯官方术语）
    "денацификаци",    # "去纳粹化"（俄罗斯官方术语）
}


def count_cjk(text: str) -> int:
    """统计文本中的 CJK 字符数"""
    lo, hi = CJK_RANGE
    return sum(1 for c in text if lo <= c <= hi)


def count_cyrillic(text: str) -> int:
    """统计文本中的西里尔字母数量"""
    lo, hi = CYRILLIC_RANGE
    return sum(1 for c in text if lo <= c <= hi)


def detect_language(text: str, hint: str = None) -> str:
    """检测文本语言

    支持的语言代码：'zh'（中文）、'en'（英文）、'ru'（俄语）、'uk'（乌克兰语）

    检测策略：
    1. 如果提供了 hint 且文本中存在对应语言的字符特征，直接返回 hint
    2. 统计 CJK 字符数，超过阈值则判定为中文
    3. 统计西里尔字符数，超过阈值则进一步区分钟/乌克兰语
    4. 默认返回英文

    Args:
        text: 待检测的文本
        hint: 语言提示（如数据源配置的语言），优先级最高

    Returns:
        语言代码字符串
    """
    if not text:
        return hint or "en"

    # 截取前 2000 个字符用于检测
    sample = text[:2000]

    # 如果提供了 hint 且与样本字符特征一致，直接采用
    if hint and hint in ("zh", "en", "ru", "uk"):
        if hint == "zh":
            if count_cjk(sample) > 5:
                return "zh"
        elif hint in ("ru", "uk"):
            if count_cyrillic(sample) > 5:
                # 有西里尔字符，进一步区分钟/乌
                uk_count = sum(1 for marker in UKRAINIAN_MARKERS if marker in sample)
                ru_count = sum(1 for marker in RUSSIAN_MARKERS if marker in sample)
                if uk_count > ru_count:
                    return "uk"
                elif ru_count > uk_count:
                    return "ru"
                # 无法区分时使用 hint
                return hint
        else:
            # hint 是 "en" 但没有西里尔或 CJK 字符，就用 en
            if count_cjk(sample) <= 5 and count_cyrillic(sample) <= 5:
                return "en"

    # 检测中文
    if count_cjk(sample) > 5:
        return "zh"

    # 检测西里尔文字
    cyrillic_count = count_cyrillic(sample)
    if cyrillic_count > 5:
        # 进一步区分乌克兰语和俄语
        uk_score = sum(1 for marker in UKRAINIAN_MARKERS if marker in sample)
        ru_score = sum(1 for marker in RUSSIAN_MARKERS if marker in sample)

        if uk_score > ru_score:
            return "uk"
        elif ru_score > uk_score:
            return "ru"
        else:
            # 无法区分时，如果有 hint 则使用 hint，否则默认为 uk
            # （本项目的西里尔来源主要是乌克兰语）
            return hint if hint in ("ru", "uk") else "uk"

    # 默认为英文
    return "en"


def get_accept_language(lang: str) -> str:
    """根据语言代码返回合适的 Accept-Language 请求头

    Args:
        lang: 语言代码 ('zh', 'en', 'ru', 'uk')

    Returns:
        Accept-Language 头字符串
    """
    lang_map = {
        "zh": "zh-CN,zh;q=0.9,en;q=0.5",
        "en": "en-US,en;q=0.9",
        "ru": "ru-RU,ru;q=0.9,en;q=0.5",
        "uk": "uk-UA,uk;q=0.9,ru;q=0.5,en;q=0.5",
    }
    return lang_map.get(lang, "en-US,en;q=0.9,zh-CN;q=0.8,ru;q=0.5,uk;q=0.3")
