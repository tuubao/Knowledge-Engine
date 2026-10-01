import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
from pymongo.collection import Collection
from pymongo import DESCENDING
import os

import requests

from utils.clients.storage_clients import StorageClients

logger = logging.getLogger(__name__)

# STEP08: Java owns chat history writes. Default = java (Mongo write no-op).
# Set KB_HISTORY_OWNER=mongo to restore legacy Mongo dual-write.
_HISTORY_OWNER = os.getenv("KB_HISTORY_OWNER", "java").strip().lower()


def _get_collection() -> Collection:
    """获取 chat_message 集合"""
    return StorageClients.get_mongo_db()["chat_message"]  # "chat_message"表名


def _java_gateway_base() -> str:
    return os.getenv("JAVA_GATEWAY_URL", "http://127.0.0.1:8080").rstrip("/")


def _mirror_to_java(
        session_id: str,
        role: str,
        text: str,
        rewritten_query: str,
        item_names: List[str],
        ts: float,
) -> None:
    """
    STEP06 方案 A：Mongo 写入后双写到 Java/MySQL。
    失败只打日志，不阻断主流程。
    """
    url = f"{_java_gateway_base()}/internal/history"
    payload = {
        "session_id": session_id,
        "role": role,
        "text": text or "",
        "rewritten_query": rewritten_query or "",
        "item_names": item_names or [],
        "ts": ts,
    }
    try:
        resp = requests.post(url, json=payload, timeout=3.0)
        if resp.status_code >= 400:
            logger.warning(
                "mirror history to Java failed: status=%s body=%s",
                resp.status_code,
                resp.text[:300],
            )
    except Exception as e:
        logger.warning("mirror history to Java failed: %s", e)


def save_chat_message(
        session_id: str,
        role: str,
        text: str,
        rewritten_query: str = "",
        item_names: List[str] = None,
        message_id: str = None,
) -> str:
    """
    STEP08：默认不再写 Mongo（历史由 Java 落 MySQL）。
    KB_HISTORY_OWNER=mongo 时恢复 STEP06 双写行为。
    """
    if _HISTORY_OWNER != "mongo":
        logger.debug(
            "skip Mongo history write (KB_HISTORY_OWNER=%s) session=%s role=%s",
            _HISTORY_OWNER,
            session_id,
            role,
        )
        return message_id or ""

    ts = datetime.now().timestamp()
    names = item_names or []

    document = {
        "session_id": session_id,
        "role": role,
        "text": text,
        "rewritten_query": rewritten_query or "",
        "item_names": names,
        "ts": ts,
    }

    collection = _get_collection()
    if message_id:
        collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": document},
        )
        return message_id

    result = collection.insert_one(document)
    inserted_id = str(result.inserted_id)
    # 双写 MySQL（公开 /history 以 Java 为准）
    _mirror_to_java(session_id, role, text or "", rewritten_query or "", names, ts)
    return inserted_id


def _fetch_history_from_java(session_id: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    """Prefer MySQL history via Java gateway (STEP08)."""
    url = f"{_java_gateway_base()}/history/{session_id}"
    try:
        resp = requests.get(url, timeout=3.0)
        if resp.status_code >= 400:
            logger.warning("fetch history from Java failed: status=%s", resp.status_code)
            return None
        data = resp.json() or {}
        items = data.get("items") or []
        # Newest-first to match Mongo get_recent_messages ordering
        sorted_items = sorted(
            items,
            key=lambda x: x.get("ts") or 0,
            reverse=True,
        )[:limit]
        out = []
        for it in sorted_items:
            out.append({
                "_id": it.get("_id") or it.get("id") or "",
                "session_id": it.get("session_id") or session_id,
                "role": it.get("role") or "",
                "text": it.get("text") or "",
                "rewritten_query": it.get("rewritten_query") or "",
                "item_names": it.get("item_names") or [],
                "ts": it.get("ts"),
            })
        return out
    except Exception as e:
        logger.warning("fetch history from Java failed: %s", e)
        return None


def get_recent_messages(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    # STEP08: read from Java/MySQL first
    from_java = _fetch_history_from_java(session_id, limit=limit)
    if from_java is not None:
        return from_java

    try:
        cursor = (
            _get_collection()
            .find({"session_id": session_id})
            .sort("ts", DESCENDING)
            .limit(limit)
        )
        return list(cursor)
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return []


def clear_history(session_id: str) -> int:
    try:
        result = _get_collection().delete_many({"session_id": session_id})
        logger.info(f"Deleted {result.deleted_count} messages for session {session_id}")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error clearing history for session {session_id}: {e}")
        return 0
