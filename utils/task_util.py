"""
任务进度追踪：进程内 dict + Redis 双写（STEP05）。

Redis 为跨语言真相源；内存 dict 保留以便 Python 侧 get_* 与回滚。
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_tasks_running_list: Dict[str, List[str]] = defaultdict(list)
_tasks_done_list: Dict[str, List[str]] = defaultdict(list)
_tasks_duration: Dict[str, Dict[str, float]] = defaultdict(dict)
_tasks_result: Dict[str, Dict[str, str]] = defaultdict(dict)
_tasks_status: Dict[str, str] = {}

TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"

TASK_TTL_SECONDS = 24 * 60 * 60

_NODE_NAME_TO_CN: Dict[str, str] = {
    "upload_file": "上传文件",
    "entry_node": "检查文件",
    "pdf_to_md_node": "PDF转Markdown",
    "md_image_node": "Markdown图片处理",
    "document_split_node": "文档切分",
    "item_name_recognition_node": "主体名称识别",
    "bge_embedding_chunks_node": "向量生成",
    "milvus_import_node": "导入向量数据库",
    "__end__": "处理完成",
    "item_name_confirmed_node": "确认问题产品",
    "answer_output_node": "生成答案",
    "rerank_node": "重排序",
    "rrf_merge_node": "倒排融合",
    "web_search_node": "网络搜索",
    "vector_search_node": "切片搜索",
    "hyde_search_node": "切片搜索(假设性文档)",
}

_redis_client = None
_redis_init_attempted = False


def _to_cn(node_name: str) -> str:
    return _NODE_NAME_TO_CN.get(node_name, node_name)


def _redis():
    """Lazy Redis client; returns None if unavailable."""
    global _redis_client, _redis_init_attempted
    if _redis_client is not None:
        return _redis_client
    if _redis_init_attempted:
        return None
    _redis_init_attempted = True
    url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.0,
            protocol=2,  # RESP2 — compatible with embedded Redis / Redis 5.x
        )
        client.ping()
        _redis_client = client
        logger.info("task_util Redis connected: %s", url)
        return _redis_client
    except Exception as e:
        logger.warning("task_util Redis unavailable (%s); memory-only mode", e)
        return None


def _k_status(task_id: str) -> str:
    return f"kb:task:{task_id}:status"


def _k_running(task_id: str) -> str:
    return f"kb:task:{task_id}:running"


def _k_done(task_id: str) -> str:
    return f"kb:task:{task_id}:done"


def _k_durations(task_id: str) -> str:
    return f"kb:task:{task_id}:durations"


def _k_result(task_id: str) -> str:
    return f"kb:task:{task_id}:result"


def _k_events(task_id: str) -> str:
    return f"kb:task:{task_id}:events"


def _k_event_buf(task_id: str) -> str:
    return f"kb:task:{task_id}:event_buf"


# SSE event name aliases (avoid importing sse_util)
SSE_EVENT_PROGRESS = "progress"
SSE_EVENT_DELTA = "delta"
SSE_EVENT_FINAL = "final"


def _touch_ttl(r, task_id: str) -> None:
    for key in (
        _k_status(task_id),
        _k_running(task_id),
        _k_done(task_id),
        _k_durations(task_id),
        _k_result(task_id),
        _k_event_buf(task_id),
    ):
        try:
            r.expire(key, TASK_TTL_SECONDS)
        except Exception:
            pass


def _event_type_for_sse(event: str) -> str:
    """Map legacy SSE event names to STEP08 protocol types."""
    if event == SSE_EVENT_DELTA or event == "delta":
        return "token"
    if event == SSE_EVENT_FINAL or event == "final" or event == "final_answer":
        return "done"
    if event == "error":
        return "error"
    return "progress"


def publish_sse_event(task_id: str, event: str, data: Optional[Dict[str, Any]] = None) -> None:
    """
    STEP08: publish SSE-compatible event to Redis channel + append to event buffer.
    Payload shape (frozen):
      {"event":"progress|delta|final","type":"progress|token|done|error","data":{...}, ...flat fields}
    """
    r = _redis()
    if not r or not task_id:
        return
    payload_data = dict(data or {})
    msg_type = _event_type_for_sse(event)
    envelope = {
        "event": event,
        "type": msg_type,
        "task_id": task_id,
        "data": payload_data,
    }
    # Flatten common fields for Java consumers that read top-level keys
    envelope.update(payload_data)
    raw = json.dumps(envelope, ensure_ascii=False)
    try:
        r.rpush(_k_event_buf(task_id), raw)
        r.expire(_k_event_buf(task_id), TASK_TTL_SECONDS)
        r.publish(_k_events(task_id), raw)
    except Exception as e:
        logger.debug("publish_sse_event failed: %s", e)


def _publish_progress(task_id: str) -> None:
    r = _redis()
    if not r or not task_id:
        return
    try:
        payload = {
            "event": "progress",
            "type": "progress",
            "task_id": task_id,
            "status": get_task_status(task_id),
            "running_list": get_running_task_list(task_id),
            "done_list": get_done_task_list(task_id),
            "durations": get_node_durations(task_id),
            "data": {
                "status": get_task_status(task_id),
                "running_list": get_running_task_list(task_id),
                "done_list": get_done_task_list(task_id),
                "durations": get_node_durations(task_id),
            },
        }
        raw = json.dumps(payload, ensure_ascii=False)
        r.rpush(_k_event_buf(task_id), raw)
        r.expire(_k_event_buf(task_id), TASK_TTL_SECONDS)
        r.publish(_k_events(task_id), raw)
    except Exception as e:
        logger.debug("publish progress failed: %s", e)


def _redis_add_running(task_id: str, node_name: str) -> None:
    r = _redis()
    if not r or not task_id:
        return
    try:
        cn = _to_cn(node_name)
        current = r.lrange(_k_running(task_id), 0, -1) or []
        if cn not in current:
            r.rpush(_k_running(task_id), cn)
        _touch_ttl(r, task_id)
    except Exception as e:
        logger.warning("redis add running failed: %s", e)


def _redis_add_done(task_id: str, node_name: str) -> None:
    r = _redis()
    if not r or not task_id:
        return
    try:
        cn = _to_cn(node_name)
        r.lrem(_k_running(task_id), 0, cn)
        done = r.lrange(_k_done(task_id), 0, -1) or []
        if cn not in done:
            r.rpush(_k_done(task_id), cn)
        _touch_ttl(r, task_id)
    except Exception as e:
        logger.warning("redis add done failed: %s", e)


def add_running_task(task_id: str, node_name: str) -> None:
    if not task_id:
        return
    running = _tasks_running_list[task_id]
    if node_name not in running:
        running.append(node_name)
    _redis_add_running(task_id, node_name)
    _publish_progress(task_id)


def add_done_task(task_id: str, node_name: str) -> None:
    if not task_id:
        return
    if node_name in _tasks_running_list[task_id]:
        _tasks_running_list[task_id].remove(node_name)
    done = _tasks_done_list[task_id]
    if node_name not in done:
        done.append(node_name)
    _redis_add_done(task_id, node_name)
    _publish_progress(task_id)


def get_running_task_list(task_id: str) -> List[str]:
    return [_to_cn(n) for n in _tasks_running_list.get(task_id, [])]


def get_done_task_list(task_id: str) -> List[str]:
    return [_to_cn(n) for n in _tasks_done_list.get(task_id, [])]


def get_task_status(task_id: str) -> str:
    return _tasks_status.get(task_id, "")


def update_task_status(task_id: str, status_name: str) -> None:
    if not task_id:
        return
    _tasks_status[task_id] = status_name
    r = _redis()
    if r:
        try:
            r.set(_k_status(task_id), status_name, ex=TASK_TTL_SECONDS)
            _touch_ttl(r, task_id)
        except Exception as e:
            logger.warning("redis set status failed: %s", e)
    _publish_progress(task_id)


def set_task_result(task_id: str, key: str, value: str) -> None:
    _tasks_result[task_id][key] = value
    r = _redis()
    if r and task_id:
        try:
            r.hset(_k_result(task_id), key, value if value is not None else "")
            _touch_ttl(r, task_id)
        except Exception as e:
            logger.warning("redis set result failed: %s", e)


def get_task_result(task_id: str, key: str, default: str = "") -> str:
    return _tasks_result.get(task_id, {}).get(key, default)


def add_node_duration(task_id: str, node_name: str, duration: float) -> None:
    cn_name = _to_cn(node_name)
    rounded = round(duration, 2)
    _tasks_duration[task_id][cn_name] = rounded
    r = _redis()
    if r and task_id:
        try:
            r.hset(_k_durations(task_id), cn_name, str(rounded))
            _touch_ttl(r, task_id)
        except Exception as e:
            logger.warning("redis set duration failed: %s", e)
    _publish_progress(task_id)


def get_node_durations(task_id: str) -> Dict[str, float]:
    return dict(_tasks_duration.get(task_id, {}))


def get_task_info(task_id: str) -> Dict[str, Any]:
    return {
        "status": get_task_status(task_id),
        "running_list": get_running_task_list(task_id),
        "done_list": get_done_task_list(task_id),
        "durations": get_node_durations(task_id),
    }
