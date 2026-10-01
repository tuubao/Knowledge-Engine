"""Mock Python import worker for STEP07 (stdlib + optional redis)."""
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


def _simulate_graph(task_id: str):
    r = _redis()
    nodes = ["检查文件", "文档切分", "向量生成", "导入向量数据库"]
    if r:
        r.set(f"kb:task:{task_id}:status", "processing", ex=86400)
    for i, name in enumerate(nodes):
        if r:
            r.lrem(f"kb:task:{task_id}:running", 0, name)
            r.rpush(f"kb:task:{task_id}:running", name)
        time.sleep(0.05)
        if r:
            r.lrem(f"kb:task:{task_id}:running", 0, name)
            done = r.lrange(f"kb:task:{task_id}:done", 0, -1) or []
            if name not in done:
                r.rpush(f"kb:task:{task_id}:done", name)
            r.hset(f"kb:task:{task_id}:durations", name, str(0.05 * (i + 1)))
    if r:
        r.set(f"kb:task:{task_id}:status", "completed", ex=86400)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[mock-import]", fmt % args)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        text = raw.decode("utf-8") or "{}"
        print(f"[mock-import] raw body={text!r}", flush=True)
        return json.loads(text)

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/internal/import/run":
            data = self._read_json()
            if not isinstance(data, dict):
                print(f"[mock-import] unexpected body type={type(data)}", flush=True)
                self._json(400, {"detail": "body must be object"})
                return
            task_id = data.get("task_id") or data.get("taskId") or ""
            path = data.get("import_file_path") or data.get("importFilePath") or ""
            print(f"[mock-import] run task={task_id} file={path}", flush=True)
            threading.Thread(target=_simulate_graph, args=(task_id,), daemon=True).start()
            self._json(200, {"message": "导入任务已受理", "task_id": task_id})
            return
        # Legacy public routes intentionally closed (STEP09 — use Java :8080)
        if self.path == "/upload":
            self._json(404, {"detail": "public /upload disabled; use Java :8080"})
            return
        self._json(404, {"detail": "not found"})

    def do_GET(self):
        if self.path == "/health" or self.path == "/hello":
            self._json(200, {"status": "ok", "service": "import-worker"})
            return
        self._json(404, {"detail": "use Java /status"})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("mock import worker on http://127.0.0.1:8000", flush=True)
    server.serve_forever()
