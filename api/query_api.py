import asyncio
import json
import os
from typing import Union

import uvicorn
from fastapi import FastAPI, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from core.deps import get_query_service
from schema.query_schema import (
    QueryRequest,
    QueryResponse,
    StreamSubmitResponse,
    HistoryResponse,
    InternalQueryRunRequest,
    InternalQueryRunResponse,
)
from service.query_service import QueryService
from utils.sse_util import create_sse_queue, sse_generator
from utils.task_util import get_done_task_list, get_task_result

# STEP09: default false — Python is an internal AI worker, not a browser entry.
EXPOSE_PUBLIC_API = os.getenv("EXPOSE_PUBLIC_API", "false").strip().lower() in ("1", "true", "yes")


def register_internal_routes(app: FastAPI):
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "query-worker"}

    @app.post("/internal/query/run", response_model=InternalQueryRunResponse)
    async def internal_query_run(
            body: InternalQueryRunRequest,
            background_tasks: BackgroundTasks,
            query_service: QueryService = Depends(get_query_service),
    ):
        """
        STEP08：由 Java 创建 task/session 后，仅触发查询 LangGraph。
        流式：后台执行，进度/token 写 Redis events；非流式：同步跑完并返回答案字段。
        """
        if body.is_stream:
            create_sse_queue(body.task_id)  # 保留进程内队列作回滚
            background_tasks.add_task(
                query_service.run_query_graph,
                body.query,
                body.session_id,
                body.task_id,
                True,
            )
            return InternalQueryRunResponse(
                message="查询任务已受理",
                task_id=body.task_id,
                session_id=body.session_id,
            )

        event_loop = asyncio.get_running_loop()
        await event_loop.run_in_executor(
            None,
            query_service.run_query_graph,
            body.query,
            body.session_id,
            body.task_id,
            False,
        )
        answer = query_service.get_query_result(task_id=body.task_id)
        rewritten = get_task_result(body.task_id, "rewritten_query", "")
        item_names_raw = get_task_result(body.task_id, "item_names", "[]")
        try:
            item_names = json.loads(item_names_raw) if item_names_raw else []
            if not isinstance(item_names, list):
                item_names = []
        except Exception:
            item_names = []
        return InternalQueryRunResponse(
            message="查询请求已处理完成",
            task_id=body.task_id,
            session_id=body.session_id,
            answer=answer or "",
            done_list=get_done_task_list(body.task_id),
            rewritten_query=rewritten or "",
            item_names=item_names,
        )


def register_public_routes(app: FastAPI):
    """Legacy browser-facing routes. Only registered when EXPOSE_PUBLIC_API=true."""

    @app.post("/query")
    async def query(query_request: QueryRequest,
              background_tasks: BackgroundTasks,
              query_service: QueryService = Depends(get_query_service)) -> Union[QueryResponse, StreamSubmitResponse]:
        session_id = query_request.session_id or str(query_service.generate_session_id())
        task_id = query_service.generate_task_id()
        q = query_request.query
        is_stream = query_request.is_stream

        if is_stream:
            create_sse_queue(task_id)
            background_tasks.add_task(query_service.run_query_graph, q, session_id, task_id, is_stream)
            return StreamSubmitResponse(message="查询请求已经提交", session_id=session_id, task_id=task_id)

        event_loop = asyncio.get_running_loop()
        await event_loop.run_in_executor(
            None, query_service.run_query_graph, q, session_id, task_id, is_stream
        )
        answer = query_service.get_query_result(task_id=task_id)
        done_list = get_done_task_list(task_id=task_id)
        return QueryResponse(message="查询请求已处理完成", session_id=session_id, answer=answer, done_list=done_list)

    @app.get("/stream/{task_id}")
    async def stream(task_id: str, request: Request):
        return StreamingResponse(content=sse_generator(task_id=task_id, request=request), media_type="text/event-stream")

    @app.delete("/history/{session_id}")
    def clean_history(session_id: str, query_service: QueryService = Depends(get_query_service)):
        query_service.clean_history(session_id)
        return {"message": f"会话 {session_id} 的历史记录已清空"}

    @app.get("/history/{session_id}")
    def get_history(session_id: str, query_service: QueryService = Depends(get_query_service)):
        history_list = query_service.get_history(session_id)
        return HistoryResponse(session_id=session_id, items=history_list)


def create_app():
    app = FastAPI(
        description="掌柜智库检索 Worker（内网）",
        version="1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        )

    register_internal_routes(app)
    if EXPOSE_PUBLIC_API:
        # Static /front is intentionally NOT mounted — Java :8080 serves the UI (STEP09).
        register_public_routes(app)

    return app


if __name__ == '__main__':
    # Dev may use 0.0.0.0; production should bind 127.0.0.1 (or private NIC) + firewall.
    host = os.getenv("WORKER_BIND_HOST", "0.0.0.0")
    app = create_app()
    uvicorn.run(app, host=host, port=8001)
