"""Mock Python query worker for STEP08 (internal/query/run + Redis events)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time


def _redis():
    try:
        import redis
        c = redis.Redis.from_url(
            os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
            decode_responses=True,
            protocol=2,
            socket_connect_timeout=1.0,
        )
        c.ping()
        return c
    except Exception:
        return None


def _publish(task_id: str, event: str, data: dict, msg_type: str):
    r = _redis()
    if not r:
        return
    envelope = {
        "event": event,
        "type": msg_type,
        "task_id": task_id,
        "data": data,
        **data,
    }
    raw = json.dumps(envelope, ensure_ascii=False)
    buf = f"kb:task:{task_id}:event_buf"
    ch = f"kb:task:{task_id}:events"
    r.rpush(buf, raw)
    r.expire(buf, 86400)
    r.publish(ch, raw)


def _simulate_query(task_id: str, query: str, is_stream: bool):
    r = _redis()
    if r:
        r.set(f"kb:task:{task_id}:status", "processing", ex=86400)
    nodes = ["确认问题产品", "切片搜索", "生成答案"]
    for name in nodes:
        if r:
            r.lrem(f"kb:task:{task_id}:running", 0, name)
            r.rpush(f"kb:task:{task_id}:running", name)
        _publish(
            task_id,
            "progress",
            {"status": "processing", "done_list": [], "running_list": [name]},
            "progress",
        )
        time.sleep(0.05)
        if r:
            r.lrem(f"kb:task:{task_id}:running", 0, name)
            done = r.lrange(f"kb:task:{task_id}:done", 0, -1) or []
            if name not in done:
                r.rpush(f"kb:task:{task_id}:done", name)
        _publish(
            task_id,
            "progress",
            {"status": "processing", "done_list": [name], "running_list": []},
            "progress",
        )

    answer = f"mock 答案：{query}"
    if is_stream:
        for chunk in ["流式", "片段", "完整"]:
            _publish(task_id, "delta", {"delta": chunk}, "token")
            time.sleep(0.02)

    result = {
        "answer": answer,
        "rewritten_query": query,
        "item_names": ["RS-12"],
        "status": "completed",
        "done_list": nodes,
        "running_list": [],
    }
    if r:
        r.hset(f"kb:task:{task_id}:result", mapping={
            "answer": answer,
            "rewritten_query": query,
            "item_names": json.dumps(["RS-12"], ensure_ascii=False),
        })
        r.set(f"kb:task:{task_id}:status", "completed", ex=86400)
    _publish(task_id, "final", result, "done")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[mock-query]", fmt % args)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        text = raw.decode("utf-8") or "{}"
        print(f"[mock-query] raw body={text!r}", flush=True)
        return json.loads(text)

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/internal/query/run":
            data = self._read_json()
            task_id = data.get("task_id") or data.get("taskId") or ""
            session_id = data.get("session_id") or data.get("sessionId") or ""
            query = data.get("query") or ""
            is_stream = bool(data.get("is_stream") if "is_stream" in data else data.get("isStream"))
            print(f"[mock-query] run task={task_id} stream={is_stream} q={query}", flush=True)
            if is_stream:
                threading.Thread(
                    target=_simulate_query, args=(task_id, query, True), daemon=True
                ).start()
                self._json(200, {
                    "message": "查询任务已受理",
                    "task_id": task_id,
                    "session_id": session_id,
                    "answer": "",
                    "done_list": [],
                    "rewritten_query": "",
                    "item_names": [],
                })
            else:
                _simulate_query(task_id, query, False)
                self._json(200, {
                    "message": "查询请求已处理完成",
                    "task_id": task_id,
                    "session_id": session_id,
                    "answer": f"mock 答案：{query}",
                    "done_list": ["确认问题产品", "切片搜索", "生成答案"],
                    "rewritten_query": query,
                    "item_names": ["RS-12"],
                })
            return

        # Legacy public /query closed (STEP09)
        if self.path == "/query":
            length = int(self.headers.get("Content-Length", "0"))
            if length:
                self.rfile.read(length)
            self._json(404, {"detail": "public /query disabled; use Java :8080"})
            return

        self._json(404, {"detail": "not found"})

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "service": "query-worker"})
            return
        if self.path.startswith("/history/"):
            # Legacy public history — STEP09 mocks return 404 unless EXPOSE path kept for clearHistory best-effort
            self._json(404, {"detail": "history is served by Java :8080"})
            return
        self._json(404, {"detail": "use Java /stream"})

    def do_DELETE(self):
        if self.path.startswith("/history/"):
            session_id = self.path.split("/", 2)[-1]
            self._json(200, {"message": f"会话 {session_id} 的历史记录已清空"})
            return
        self._json(404, {"detail": "not found"})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8001), Handler)
    print("mock query worker on http://127.0.0.1:8001", flush=True)
    server.serve_forever()
