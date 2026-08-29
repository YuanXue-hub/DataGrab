"""热点监控分析引擎（教程第 7 节升级版）

职责：
1. Query Expansion 变体匹配（word + variants）
2. 命中记录写入 grab_keyword_hit：match_type / matched_variant / direct_mention 三字段
3. 规则启发式相关性打分 0-100（无 LLM 兜底；有 LLM 时可替换）
4. keyword_mentioned 锚点（教程第 7 节：直接提到原始词 vs 仅变体）
5. 写回 grab 表：relevance_score / keyword_mentioned / relevance_reason
6. 趋势聚合并写入 keyword_trend（hour + day 双粒度）
7. 突发检测：对比基线，触发热点事件 hotspot_event
8. 通知聚合（tutorial 扩展思路 4）：批量写 notification_pending，避免 1 条 1 推
"""

import json
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from loguru import logger

import storage.topics as st
from storage.database import get_connection


# ============================
#  阈值 & 常量
# ============================

BASELINE_MULTIPLIER = 2.0   # 阈值 = mean + multiplier * std
BURST_MIN_RATIO = 3.0       # MVP：倍率 ≥ 3× 才算突发
BURST_MIN_ARTICLES = 3      # 窗口内至少 3 篇文章才告警

# schedule_config 负值 id 的语义（与 _seed_global_config 保持一致）
CFGID_RELEVANCE_THRESHOLD = -1   # limit_count 存阈值，教程推荐 50-60
CFGID_NOTIFY_BATCH_MINUTES = -2  # limit_count 存窗口分钟
CFGID_NOTIFY_MODE_BATCH = -3     # limit_count=1=batch 启用


def _relevance_threshold() -> int:
    """读取相关性阈值（schedule_config.source_id=-1），默认 40。"""
    try:
        row = st.schedule_get(CFGID_RELEVANCE_THRESHOLD)
        if row and row.get("limit_count"):
            return int(row["limit_count"])
    except Exception:
        pass
    return 40


def _notify_batch_minutes() -> int:
    try:
        row = st.schedule_get(CFGID_NOTIFY_BATCH_MINUTES)
        if row and row.get("limit_count"):
            return max(5, int(row["limit_count"]))
    except Exception:
        pass
    return 30


def _notify_mode_batch() -> bool:
    try:
        row = st.schedule_get(CFGID_NOTIFY_MODE_BATCH)
        if row:
            return bool(row.get("enabled", 1)) and int(row.get("limit_count", 0) or 0) == 1
    except Exception:
        pass
    return True


# ============================
#  关键词匹配器（升级：含 Query Expansion 变体）
# ============================

class KeywordMatcher:
    """从 DB 加载所有启用关键词（含 variants），提供单文本批量匹配。

    返回结构升级：
      Dict[keyword_id, {"cnt": int, "direct": int, "variants_hit": list[str]}]
    """

    CONTENT_TRUNCATE = 4000   # 教程扩展：前 4000 字，便于打分逻辑
    REGEX_TIMEOUT_S = 2.0

    def __init__(self):
        self.keywords: List[dict] = []
        self._re_cache: Dict[int, re.Pattern] = {}
        self.reload()

    def reload(self):
        self.keywords = st.keyword_list_enabled() or []
        self._re_cache.clear()
        for kw in self.keywords:
            if kw["match_mode"] == "regex":
                try:
                    self._re_cache[kw["id"]] = re.compile(kw["word"], re.IGNORECASE)
                except re.error as e:
                    logger.warning(f"Invalid regex keyword id={kw['id']} {kw['word']!r}: {e}")
        logger.debug(f"KeywordMatcher loaded {len(self.keywords)} enabled keywords")

    # --------- 单个变体的子串计数（规则版 Query Expansion）---------
    @staticmethod
    def _count_variant(variant: str, text: str) -> int:
        """对一个 variant 子串计数，支持中英文混合、大小写不敏感。"""
        if not variant:
            return 0
        s = variant.strip()
        if not s:
            return 0
        if s.isascii():
            pattern = re.compile(r"\b" + re.escape(s) + r"\b", re.IGNORECASE)
            return len(pattern.findall(text))
        return text.count(s)

    def match_text(self, text: str, language: str = ""):
        """对一段文本返回命中详情。

        返回: Dict[keyword_id -> {cnt, direct_cnt, variants_hit: [matched_str,...], top_match: str}]

        language 过滤策略：只对原始 word 做语言过滤，变体不受限。
        这样中文关键词的英文变体（如"俄乌战争"→"Russia-Ukraine war"）也能匹配英文文章。
        """
        if not text:
            return {}
        out: Dict[int, dict] = {}
        for kw in self.keywords:
            kid = kw["id"]
            word = kw["word"]
            mode = kw["match_mode"]
            kw_lang = kw["language"]
            # language 过滤：只对原始 word 生效，变体不受限
            # （中文关键词的英文变体也应能匹配英文文章）
            skip_direct = bool(kw_lang and language and kw_lang != language)
            variants = kw.get("variants") or []
            if isinstance(variants, (str, bytes)):
                try:
                    variants = json.loads(variants)
                except Exception:
                    variants = []
            if not isinstance(variants, list):
                variants = []
            # 确保原始 word 自身也在匹配集合里（第 1 位）
            all_variants = [word] + [v for v in variants if v and v != word]

            direct_cnt = 0
            total_cnt = 0
            hit_variants: List[str] = []
            top_variant: Optional[str] = None
            for idx, v in enumerate(all_variants):
                # 语言不匹配时跳过原始 word（idx==0），但变体照常匹配
                if idx == 0 and skip_direct:
                    continue
                cnt = 0
                try:
                    if mode == "regex":
                        pat = self._re_cache.get(kid)
                        if pat is None:
                            continue
                        start = time.time()
                        matches = pat.findall(text)
                        if time.time() - start > self.REGEX_TIMEOUT_S:
                            logger.warning(f"Regex timeout on keyword id={kid}")
                            continue
                        cnt = len(matches)
                    else:
                        cnt = self._count_variant(v, text)
                except Exception as e:
                    logger.debug(f"Match error on keyword id={kid}: {e}")
                    continue
                if cnt > 0:
                    total_cnt += cnt
                    if idx == 0:
                        direct_cnt += cnt
                    hit_variants.append(v)
                    if top_variant is None:
                        top_variant = v
            if total_cnt > 0:
                out[kid] = {
                    "cnt": total_cnt,
                    "direct_cnt": direct_cnt,
                    "variants_hit": hit_variants,
                    "top_match": hit_variants[0],
                }
        return out

    def match_grab(self, title: str, summary: str, content: str,
                   language: str = ""):
        """对单篇文章三字段分别匹配，再汇总 + 记录是否标题命中（强锚点）。

        返回:
          (hits_map, title_hit_kids_set)
          hits_map: kid -> {"cnt","direct_cnt","variants_hit","top_match","title_hit"}
        """
        title = title or ""
        summary = summary or ""
        body = (content or "")[: self.CONTENT_TRUNCATE]
        combined = title + "\n" + summary + "\n" + body

        # 先整体匹配
        hits = self.match_text(combined, language)
        if not hits:
            return {}, set()

        # 标题命中的关键词（强证据）
        title_hits = self.match_text(title, language)
        title_hit_ids = set(title_hits.keys()) & set(hits.keys())
        for kid in hits:
            hits[kid]["title_hit"] = kid in title_hit_ids
        return hits, title_hit_ids


# ============================
#  全局单例
# ============================

_global_matcher: Optional[KeywordMatcher] = None


def get_matcher() -> KeywordMatcher:
    global _global_matcher
    if _global_matcher is None:
        _global_matcher = KeywordMatcher()
    return _global_matcher


def reload_matcher():
    global _global_matcher
    _global_matcher = None


# ============================
#  时间桶 & 突发检测
# ============================

def _hour_bucket(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _day_bucket(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _classify_level(ratio: float) -> str:
    if ratio >= 10.0:
        return "high"
    if ratio >= 5.0:
        return "mid"
    return "low"


def _detect_hotspot(hour_hits: List[Tuple[int, int, int, datetime]],
                    keyword_id_to_topic: Dict[int, int]):
    """对最近一小时每个关键词，计算基线并判断是否触发热点。
    hour_hits: [(keyword_id, article_cnt, hit_cnt, hour_bucket)]
    """
    created_events = 0
    for kid, art_cnt, hit_cnt, hb in hour_hits:
        topic_id = keyword_id_to_topic.get(kid)
        if art_cnt < BURST_MIN_ARTICLES:
            continue
        mean, std = st.trend_get_baseline(kid, "hour", hb, days_back=7)
        threshold = mean + BASELINE_MULTIPLIER * std
        if threshold <= 0:
            if art_cnt < 10:
                continue
            baseline = 1.0
        else:
            baseline = threshold
        ratio = art_cnt / baseline
        if ratio < BURST_MIN_RATIO and threshold > 0:
            continue
        level = _classify_level(ratio)
        ev_id = st.event_create(
            keyword_id=kid,
            topic_id=topic_id,
            window_start=hb,
            window_end=hb + timedelta(hours=1),
            article_cnt=art_cnt,
            hit_cnt=hit_cnt,
            baseline=baseline,
            ratio=ratio,
            level=level,
        )
        created_events += 1
        logger.info(
            f"[HOTSPOT {level}] keyword_id={kid} art={art_cnt} ratio={ratio:.1f}x event_id={ev_id}"
        )
        # 通知聚合（教程扩展 4）：按 notify_batch_minutes 写一条 pending 通知
        try:
            _queue_notification_pending(kid, topic_id, level, art_cnt, hb)
        except Exception as e:
            logger.warning(f"Queue notify failed (non-fatal): {e}")
    return created_events


def _queue_notification_pending(keyword_id: int, topic_id: Optional[int], level: str,
                                 article_cnt: int, hb: datetime):
    """按聚合窗口写入 notification_pending（ON DUPLICATE KEY +1）。

    幂等：(bucket_start, topic_id, keyword_id, event_level, channel) 唯一键通过自然去重实现，
    先查询再决定 INSERT 或 UPDATE。
    """
    batch_min = _notify_batch_minutes()
    if not _notify_mode_batch():
        return
    minutes_slot = (hb.minute // batch_min) * batch_min
    bucket_start = hb.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minutes_slot)
    bucket_end = bucket_start + timedelta(minutes=batch_min)

    word = ""
    try:
        kw = st.keyword_get(keyword_id)
        if kw:
            word = kw.get("word", "")
    except Exception:
        pass
    summary = f"[{level.upper()}] 关键词「{word}」在 {hb:%m-%d %H:00} 窗口文章 {article_cnt} 篇触发告警"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, article_cnt FROM notification_pending "
                "WHERE bucket_start=%s AND bucket_end=%s AND topic_id<=>%s "
                "  AND keyword_id<=>%s AND event_level=%s AND channel='inapp' "
                "  AND status='pending' LIMIT 1",
                (bucket_start, bucket_end, topic_id or None, keyword_id or None, level)
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE notification_pending SET article_cnt = article_cnt + %s, "
                    "summary = %s WHERE id = %s",
                    (article_cnt, summary[:500], row["id"])
                )
            else:
                cur.execute(
                    "INSERT INTO notification_pending "
                    "(bucket_start, bucket_end, topic_id, keyword_id, event_level, "
                    " article_cnt, summary, status, channel) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,'pending','inapp')",
                    (bucket_start, bucket_end, topic_id or None, keyword_id or None,
                     level, article_cnt, summary[:500])
                )
        conn.commit()
    finally:
        conn.close()


# ============================
#  规则启发式相关性评分（教程第 7 节无 LLM 兜底版）
# ============================

def _score_and_reason(title: str, summary: str, content: str,
                      hits_map: dict, title_hit_ids: set,
                      kw_map: Dict[int, dict]) -> Tuple[float, bool, str]:
    """规则启发式打分 0-100，同时输出 keyword_mentioned 锚点 + reason。

    v4 评分体系（区分用户核心关键词与预设主题词的差异化策略）：
      基础分：
      - 标题命中：原词 +50/词，变体 +35/词，最高 60
      - 正文有效密度：原词1.0/变体0.4折算（用户关键词变体0.7），密度×12/千字，最高 25
      - 多关键词交叉：≥2 个不同关键词 +15
      - direct 权重加成：最高 +10
      - 用户关键词命中基础分：直接+15/词，变体+8/词（确保核心监控词命中有合理底分）
      降权系数（乘法，用户关键词放宽、预设词严格）：
      - 无标题命中：用户 ×0.85 / 预设 ×0.7
      - 仅单一变体浅层命中：用户不降权 / 预设 ×0.6
      - 无 direct（仅变体）：用户 ×0.9 / 预设 ×0.85
    """
    title = title or ""
    body = (content or "")[:4000]
    full = (title + "\n" + (summary or "") + "\n" + body)
    text_len_chars = max(100, len(full.replace("\n", "")))

    raw_score = 0.0
    reasons: List[str] = []
    any_direct = False
    unique_keywords = len(hits_map)
    effective_hits = 0.0
    weight_total_score = 0.0
    weight_sum_denom = 0.0
    title_hits_count = 0
    title_direct_count = 0
    distinct_variant_types = set()
    has_user_kw = False        # 是否含用户自建关键词（topic_id IS NULL）命中
    user_kw_base = 0.0         # 用户关键词命中基础分累加

    for kid, detail in hits_map.items():
        kw = kw_map.get(kid, {})
        w = int(kw.get("weight", 1) or 1)
        weight_sum_denom += w
        cnt = int(detail.get("cnt") or 0)
        direct_cnt = int(detail.get("direct_cnt") or 0)
        variant_cnt = cnt - direct_cnt

        # 区分用户核心关键词 vs 预设主题词
        is_user_kw = kw.get("topic_id") is None
        if is_user_kw:
            has_user_kw = True
            # 用户关键词命中基础分：确保核心监控词命中有合理底分
            user_kw_base += (15.0 if direct_cnt > 0 else 8.0)

        if detail.get("title_hit"):
            title_hits_count += 1
            if direct_cnt > 0:
                title_direct_count += 1
                reasons.append(f"标题直接提到「{kw.get('word','?')}」(强锚点)")
            else:
                reasons.append(f"标题变体命中「{kw.get('word','?')}」")

        # 用户关键词变体有效折算0.7（变体也是用户精心定义的相关词），预设词0.4
        eff_ratio = 0.7 if is_user_kw else 0.4
        effective_hits += direct_cnt * 1.0 + variant_cnt * eff_ratio

        if direct_cnt > 0:
            any_direct = True
            distinct_variant_types.add("__direct__")
        for vh in detail.get("variants_hit", []):
            distinct_variant_types.add(vh)

        if direct_cnt > 0:
            weight_total_score += min(1.0, direct_cnt / 5.0) * w

    # 标题分
    title_direct_score = min(60.0, title_direct_count * 50.0)
    title_variant_score = min(60.0 - title_direct_score,
                               (title_hits_count - title_direct_count) * 35.0)
    title_score = min(60.0, title_direct_score + title_variant_score)
    raw_score += title_score

    # 正文有效密度
    density_per_kchar = (effective_hits / text_len_chars) * 1000
    density_score = min(25.0, density_per_kchar * 12.0)
    raw_score += density_score

    # 多关键词交叉
    cross_score = 15.0 if unique_keywords >= 2 else 0.0
    raw_score += cross_score

    # direct × 权重
    if weight_sum_denom > 0:
        direct_weighted = min(1.0, weight_total_score / weight_sum_denom)
        raw_score += direct_weighted * 10.0
    else:
        direct_weighted = 0.0

    # 用户关键词命中基础分（确保核心监控词命中有合理底分，不被密度/标题缺失归零）
    raw_score += user_kw_base

    # 乘法降权（用户关键词放宽、预设词严格）
    penalty_mult = 1.0
    no_title_pen = 0.85 if has_user_kw else 0.7
    no_direct_pen = 0.9 if has_user_kw else 0.85
    if title_hits_count == 0:
        penalty_mult *= no_title_pen
        reasons.append(f"无标题命中 ×{no_title_pen}")
    # 仅预设词应用"仅单一变体浅层命中"降权（用户关键词变体也是精心定义的相关词，不降权）
    if title_hits_count == 0 and len(distinct_variant_types) <= 1 and not has_user_kw:
        penalty_mult *= 0.6
        reasons.append("仅单一变体浅层命中 ×0.6")
    if not any_direct:
        penalty_mult *= no_direct_pen
        reasons.append(f"仅变体命中无原词 ×{no_direct_pen}")

    score = raw_score * penalty_mult

    # 阈值参考
    threshold = _relevance_threshold()

    # 推理原因
    if reasons:
        head = "；".join(reasons[:3])
    else:
        head = "命中仅来自文本浅层片段"
    reason = (
        f"规则打分：标题{title_score:.0f} + 密度{density_score:.0f} + "
        f"交叉{cross_score:.0f} + 直接权重{direct_weighted*10:.0f} + "
        f"用户词底分{user_kw_base:.0f} "
        f"= {raw_score:.0f} × {penalty_mult:.2f} = {score:.0f}/100；"
        f"阈值={threshold}。原因：{head}；"
        f"关键词覆盖 {unique_keywords} 个，有效命中 {effective_hits:.1f} 次；"
        f"keyword_mentioned={'是' if any_direct else '否'}"
    )[:1000]

    return max(0.0, min(100.0, round(score, 2))), any_direct, reason


# ============================
#  主分析流程
# ============================

def _load_grab_batch(grab_ids: List[int]) -> List[dict]:
    if not grab_ids:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(grab_ids))
            cur.execute(
                f"SELECT id, title, summary, content, language, "
                f"published_at, grabbed_at FROM grab WHERE id IN ({placeholders})",
                grab_ids
            )
            return cur.fetchall()
    finally:
        conn.close()


def _update_grab_relevance_batch(rows: List[Tuple[float, int, str, int]]):
    """批量 UPDATE grab 表：(score, mentioned, reason, grab_id)。"""
    if not rows:
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE grab SET relevance_score = %s, keyword_mentioned = %s, "
                "relevance_reason = %s WHERE id = %s",
                rows
            )
        conn.commit()
    finally:
        conn.close()


def analyze_grab_batch(grab_ids: List[int]) -> Dict[str, int]:
    """增量分析一批 grab_id（教程升级版：变体匹配 + 打分 + 锚点 + 通知聚合）。"""
    if not grab_ids:
        return {"hits_written": 0, "trend_buckets": 0, "hotspot_events": 0,
                "scored_grabs": 0, "high_relevance_grabs": 0, "notifications": 0}

    start_time = time.time()
    threshold = _relevance_threshold()
    matcher = get_matcher()
    if not matcher.keywords:
        return {"hits_written": 0, "trend_buckets": 0, "hotspot_events": 0,
                "scored_grabs": 0, "high_relevance_grabs": 0, "notifications": 0}

    grabs = _load_grab_batch(grab_ids)
    if not grabs:
        return {"hits_written": 0, "trend_buckets": 0, "hotspot_events": 0,
                "scored_grabs": 0, "high_relevance_grabs": 0, "notifications": 0}

    kw_map: Dict[int, dict] = {kw["id"]: kw for kw in matcher.keywords}
    kw_topic_map: Dict[int, int] = {kw["id"]: kw["topic_id"] for kw in matcher.keywords}

    # (gid, kid, topic_id, hit_count, score, match_type, matched_variant, direct_mention)
    hit_rows: List[tuple] = []
    trend_accum: Dict[Tuple[int, datetime, str], Tuple[int, int]] = defaultdict(lambda: (0, 0))
    hour_window: Dict[int, Tuple[int, int, datetime]] = {}
    now_hour = _hour_bucket(datetime.now())

    relevance_updates: List[Tuple[float, int, str, int]] = []
    scored = 0
    high_relevance = 0

    for g in grabs:
        gid = g["id"]
        lang = g.get("language") or ""
        title = g.get("title") or ""
        summary = g.get("summary") or ""
        content = g.get("content") or ""
        hits_map, title_hit_ids = matcher.match_grab(title, summary, content, lang)

        # 打分（无论有没有命中都打 0 分，这样未命中的也有 score=0 可筛）
        if hits_map:
            score, mentioned, reason = _score_and_reason(title, summary, content,
                                                         hits_map, title_hit_ids, kw_map)
        else:
            score, mentioned, reason = 0.0, False, "未命中任何监控关键词或其变体，score=0"
        scored += 1
        if score >= threshold:
            high_relevance += 1
        relevance_updates.append((float(score), 1 if mentioned else 0, reason, gid))

        if not hits_map:
            continue

        # 质量门槛：文章级 score < 8 的极低相关命中不写 hit 记录
        if score < 8:
            logger.debug(f"[FILTER] grab={gid} score={score:.1f} < 8, 跳过 hit 写入")
            continue

        ts = g.get("published_at") or g.get("grabbed_at") or datetime.now()
        hb = _hour_bucket(ts)
        db = _day_bucket(ts)

        for kid, detail in hits_map.items():
            topic_id = kw_topic_map.get(kid)
            kw = kw_map.get(kid, {})
            weight = int(kw.get("weight", 1) or 1)
            total_cnt = int(detail.get("cnt") or 0)
            direct_cnt = int(detail.get("direct_cnt") or 0)
            variant_cnt = total_cnt - direct_cnt
            is_title_hit = kid in title_hit_ids
            direct_mention = 1 if direct_cnt > 0 else 0
            top_match = detail.get("top_match") or kw.get("word", "")
            # 判定 match_type：只要有 direct 就视作 word，否则是 variant
            match_type = "word" if direct_cnt > 0 else "variant"
            hit_score = total_cnt * weight

            # 质量过滤：低相关命中不写 hit 记录
            # 用户自建关键词（topic_id IS NULL）不受浅层过滤，保留所有命中交由打分判断
            # （避免用户核心关键词的有效变体命中被误杀，如"俄乌战争"→"Ukraine conflict"）
            # 预设主题词（topic_id 非空）应用严格浅层过滤：
            # 条件1: 仅变体命中(direct=0) + 无标题命中 + 命中次数<=2 → 浅层误命中
            # 条件2: 仅变体命中 + 命中次数<=1 → 极低相关
            is_user_kw = topic_id is None
            if not is_user_kw:
                if direct_cnt == 0 and not is_title_hit and total_cnt <= 2:
                    logger.debug(f"[FILTER] grab={gid} kw={kw.get('word','?')} "
                                 f"浅层变体命中 variant={top_match} cnt={total_cnt} 跳过")
                    continue
                if direct_cnt == 0 and total_cnt <= 1:
                    continue

            hit_rows.append((
                gid, kid, topic_id, total_cnt, hit_score,
                match_type, top_match, direct_mention
            ))

            key = (kid, hb, "hour")
            prev = trend_accum[key]
            trend_accum[key] = (prev[0] + 1, prev[1] + total_cnt)
            key = (kid, db, "day")
            prev = trend_accum[key]
            trend_accum[key] = (prev[0] + 1, prev[1] + total_cnt)

            if abs((hb - now_hour).total_seconds()) <= 3600 * 2:
                if kid not in hour_window:
                    hour_window[kid] = (0, 0, hb)
                a, h, _ = hour_window[kid]
                hour_window[kid] = (a + 1, h + total_cnt, hb)

    # 1) 写命中（含 match_type / matched_variant / direct_mention）
    if hit_rows:
        st.hit_insert_batch_v2(hit_rows)

    # 2) 写趋势
    trend_rows: List[Tuple[int, int, datetime, str, int, int]] = []
    for (kid, bucket, grain), (art, hit) in trend_accum.items():
        topic_id = kw_topic_map.get(kid)
        trend_rows.append((kid, topic_id, bucket, grain, art, hit))
    if trend_rows:
        st.trend_upsert_batch(trend_rows)

    # 3) 突发检测 + 通知聚合
    event_n = 0
    if hour_window:
        hour_hits_list = [(kid, a, h, hb) for kid, (a, h, hb) in hour_window.items()]
        event_n = _detect_hotspot(hour_hits_list, kw_topic_map)

    # 4) 写回 grab 相关性字段
    if relevance_updates:
        _update_grab_relevance_batch(relevance_updates)

    elapsed = time.time() - start_time
    stats = {
        "hits_written": len(hit_rows),
        "trend_buckets": len(trend_rows),
        "hotspot_events": event_n,
        "scored_grabs": scored,
        "high_relevance_grabs": high_relevance,
    }
    logger.info(
        f"Analyzed {len(grabs)} grabs in {elapsed*1000:.0f}ms: "
        f"{stats['hits_written']} hits, {stats['trend_buckets']} trends, "
        f"{stats['hotspot_events']} events, {stats['scored_grabs']} scored, "
        f"{stats['high_relevance_grabs']} ≥threshold {threshold}"
    )
    return stats


def analyze_for_job(job_id: str) -> Dict[str, int]:
    if not job_id:
        return {"hits_written": 0, "trend_buckets": 0, "hotspot_events": 0,
                "scored_grabs": 0, "high_relevance_grabs": 0, "notifications": 0}
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM grab WHERE job_id = %s ORDER BY id", (job_id,))
            ids = [r["id"] for r in cur.fetchall()]
    finally:
        conn.close()
    if not ids:
        return {"hits_written": 0, "trend_buckets": 0, "hotspot_events": 0,
                "scored_grabs": 0, "high_relevance_grabs": 0, "notifications": 0}
    logger.info(f"Analyzing job {job_id}: {len(ids)} grabs")
    stats = analyze_grab_batch(ids)
    stats["grabs_processed"] = len(ids)
    return stats


# ============================
#  历史重算
# ============================

def analyze_history(start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    batch_size: int = 1000) -> Dict[str, int]:
    if start_time:
        hour_start = _hour_bucket(start_time)
        day_start = _day_bucket(start_time)
    else:
        hour_start = datetime(2020, 1, 1)
        day_start = datetime(2020, 1, 1)

    all_kw_ids = [kw["id"] for kw in (st.keyword_list_enabled() or [])]
    if all_kw_ids:
        st.trend_clear_range(all_kw_ids, "hour", hour_start,
                             _hour_bucket((end_time or datetime.now()) + timedelta(hours=1)))
        st.trend_clear_range(all_kw_ids, "day", day_start,
                             _day_bucket((end_time or datetime.now()) + timedelta(days=1)))

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            where = []
            params: list = []
            if start_time:
                where.append("grabbed_at >= %s")
                params.append(start_time)
            if end_time:
                where.append("grabbed_at <= %s")
                params.append(end_time)
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            cur.execute(
                f"SELECT MIN(id) AS mn, MAX(id) AS mx, COUNT(*) AS cn FROM grab {where_sql}",
                params
            )
            rng = cur.fetchone()
            mn, mx, cnt = (rng["mn"] or 0), (rng["mx"] or 0), (rng["cn"] or 0)
    finally:
        conn.close()

    total = {"hits_written": 0, "trend_buckets": 0, "hotspot_events": 0,
             "scored_grabs": 0, "high_relevance_grabs": 0, "notifications": 0,
             "grabs_processed": cnt}
    if cnt == 0:
        return total

    logger.info(f"Recalc grab history: id range {mn}-{mx}, total ~{cnt} rows")
    lo = mn
    while lo <= mx:
        hi = min(lo + batch_size - 1, mx)
        conn2 = get_connection()
        try:
            with conn2.cursor() as cur2:
                cur2.execute(
                    "SELECT id FROM grab WHERE id BETWEEN %s AND %s ORDER BY id",
                    (lo, hi)
                )
                ids = [r["id"] for r in cur2.fetchall()]
        finally:
            conn2.close()
        if ids:
            s = analyze_grab_batch(ids)
            for k, v in s.items():
                if isinstance(v, int) and k in total:
                    total[k] += v
        lo = hi + 1

    logger.info(f"Recalc complete: {total}")
    return total


# ============================
#  评估报告接口（教程 P/R/F1 量化）
# ============================

def evaluate_relevance(hours: int = 24) -> dict:
    """统计相关性评估指标（教程第 7 节 Precision / Recall / F1 近似估算）。

    Precision = 高相关且有关键词命中的 / 全部被打为高相关的
    Recall    = 有关键词命中且达到阈值的 / 全部有关键词命中的
    F1        = 2PR/(P+R)  （P+R=0 → 0）
    """
    threshold = _relevance_threshold()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COUNT(*)                                              AS total_grabs,
                  SUM(CASE WHEN relevance_score >= %s THEN 1 ELSE 0 END)  AS above_thr,
                  SUM(CASE WHEN keyword_mentioned = 1 THEN 1 ELSE 0 END) AS mentioned_true,
                  SUM(CASE WHEN relevance_score >= %s AND keyword_mentioned = 1
                           THEN 1 ELSE 0 END)                          AS tp,
                  SUM(CASE WHEN relevance_score <  %s AND keyword_mentioned = 1
                           THEN 1 ELSE 0 END)                          AS fn,
                  SUM(CASE WHEN relevance_score >= %s AND (keyword_mentioned = 0 OR keyword_mentioned IS NULL)
                           THEN 1 ELSE 0 END)                          AS fp
                FROM grab
                WHERE grabbed_at >= NOW() - INTERVAL %s HOUR
                  AND relevance_score IS NOT NULL
                """,
                (threshold, threshold, threshold, threshold, hours)
            )
            row = cur.fetchone()
    finally:
        conn.close()

    total = int(row["total_grabs"] or 0)
    above = int(row["above_thr"] or 0)
    mention_true = int(row["mentioned_true"] or 0)
    tp = int(row["tp"] or 0)
    fp = int(row["fp"] or 0)
    fn = int(row["fn"] or 0)

    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "threshold": threshold,
        "hours": hours,
        "scored_grabs": total,
        "above_threshold": above,
        "keyword_mentioned_true": mention_true,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "adjustment_tip": (
            "当前 Precision/Recall 偏低时：若 P 低 → 提高阈值（如 60-65）；"
            "若 R 低 → 降低阈值（如 45-50）。教程推荐平衡点 50-60。"
        ),
    }
