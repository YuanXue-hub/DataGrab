"""主题与关键词管理路由

GET    /api/topics                    — 主题列表
POST   /api/topics                    — 新建主题
PATCH  /api/topics/{topic_id}        — 更新主题
DELETE /api/topics/{topic_id}        — 删除主题

GET    /api/keywords                  — 关键词列表（可按 topic_id 过滤）
POST   /api/keywords                  — 新建关键词
PATCH  /api/keywords/{keyword_id}    — 更新关键词
DELETE /api/keywords/{keyword_id}    — 删除关键词
POST   /api/keywords/import          — 批量导入关键词
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

import storage.topics as st
from core.analyzer import reload_matcher
from server.models.analytics_models import (
    KeywordBatchImport, KeywordBatchImportResult,
    KeywordCreate, KeywordOut, KeywordUpdate,
    TopicCreate, TopicOut, TopicUpdate,
)

router = APIRouter()


# ============================
#  Topic
# ============================

@router.get("/topics", response_model=List[TopicOut])
def list_topics(include_disabled: bool = Query(default=False)):
    rows = st.topic_list(include_disabled=include_disabled)
    return [TopicOut(**r) for r in rows]


@router.post("/topics", response_model=TopicOut)
def create_topic(body: TopicCreate):
    try:
        tid = st.topic_create(**body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Create failed: {e}")
    row = st.topic_get(tid)
    if not row:
        raise HTTPException(status_code=500, detail="Created topic not found")
    return TopicOut(**row)


@router.patch("/topics/{topic_id}", response_model=TopicOut)
def update_topic(topic_id: int, body: TopicUpdate):
    existing = st.topic_get(topic_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if payload:
        st.topic_update(topic_id, **payload)
    return TopicOut(**st.topic_get(topic_id))


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int):
    existing = st.topic_get(topic_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Topic {topic_id} not found")
    st.topic_delete(topic_id)
    reload_matcher()
    return {"ok": True}


# ============================
#  Keyword
# ============================

@router.get("/keywords", response_model=List[KeywordOut])
def list_keywords(
    topic_id: Optional[int] = Query(default=None, description="按主题过滤"),
    include_disabled: bool = Query(default=False),
):
    rows = st.keyword_list(topic_id=topic_id, include_disabled=include_disabled)
    return [KeywordOut(**r) for r in rows]


@router.post("/keywords", response_model=KeywordOut)
def create_keyword(body: KeywordCreate):
    try:
        kid = st.keyword_create(**body.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Create failed: {e}")
    row = st.keyword_get(kid)
    if not row:
        raise HTTPException(status_code=500, detail="Created keyword not found")
    reload_matcher()
    return KeywordOut(**row)


@router.patch("/keywords/{keyword_id}", response_model=KeywordOut)
def update_keyword(keyword_id: int, body: KeywordUpdate):
    existing = st.keyword_get(keyword_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword_id} not found")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if payload:
        st.keyword_update(keyword_id, **payload)
    reload_matcher()
    return KeywordOut(**st.keyword_get(keyword_id))


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int):
    existing = st.keyword_get(keyword_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Keyword {keyword_id} not found")
    st.keyword_delete(keyword_id)
    reload_matcher()
    return {"ok": True}


@router.post("/keywords/import", response_model=KeywordBatchImportResult)
def batch_import_keywords(body: KeywordBatchImport):
    """按行解析 keywords_text。支持格式：
    word
    word,lang
    word,lang,mode,weight
    """
    if body.topic_id is not None:
        topic = st.topic_get(body.topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail=f"Topic {body.topic_id} not found")
    items = []
    for raw_line in body.words_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        word = parts[0]
        if not word:
            continue
        lang = parts[1] if len(parts) >= 2 and parts[1] else body.default_language
        mode = parts[2] if len(parts) >= 3 and parts[2] else body.default_match_mode
        try:
            weight = int(parts[3]) if len(parts) >= 4 and parts[3] else body.default_weight
        except ValueError:
            weight = body.default_weight
        if mode not in ("exact", "fuzzy", "regex"):
            mode = body.default_match_mode
        weight = max(1, min(10, weight))
        items.append((word, lang, mode, weight))
    total_lines = len(items)
    inserted = st.keyword_bulk_import(body.topic_id, items)
    reload_matcher()
    return KeywordBatchImportResult(inserted=inserted, skipped=total_lines - inserted)
