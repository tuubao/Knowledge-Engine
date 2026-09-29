import asyncio
from typing import Union

import uvicorn
from fastapi import FastAPI, Depends, BackgroundTasks,Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from core.deps import get_query_service
from core.paths import get_front_page_dir
from starlette.staticfiles import StaticFiles

from schema.query_schema import QueryRequest, QueryResponse, StreamSubmitResponse, HistoryResponse
from service.query_service import QueryService
from utils.sse_util import create_sse_queue, sse_generator
from utils.task_util import get_done_task_list


def register_router(app: FastAPI):

    @app.post("/query")
    async def query(query_request: QueryRequest,
              background_tasks: BackgroundTasks,
              query_service:QueryService = Depends(get_query_service)) -> Union[QueryResponse, StreamSubmitResponse]:
        #1. 获取session_id、task_id、query、is_stream
        session_id = query_request.session_id or query_service.generate_session_id()
        task_id = query_service.generate_task_id()
        query = query_request.query
        is_stream = query_request.is_stream

        #2. 调用service执行整个查询流程
        #2.1 流式调用
        if is_stream:
            #创建流式队列(sse队列)
            create_sse_queue(task_id)
            #必须在另一个线程中异步执行
            background_tasks.add_task(query_service.run_query_graph,query,session_id,task_id,is_stream)
            #将task_id、session_id返回给前端
            return StreamSubmitResponse(message="查询请求已经提交", session_id=session_id, task_id=task_id)
        else:
            #2.2 非流式调用
            #直接执行检索流程,但是也可以放到异步线程中:使用事件循环器的方式让我们的方法在异步线程中执行
            event_loop = asyncio.get_running_loop()
            await event_loop.run_in_executor(
                None,query_service.run_query_graph,query,session_id,task_id,is_stream
            )
            #获取答案
            answer =  query_service.get_query_result(task_id=task_id)
            #获取已完成的节点列表
            done_list = get_done_task_list(task_id=task_id)
            return QueryResponse(message="查询请求已处理完成", session_id=session_id,answer=answer,done_list=done_list)
    @app.get("/stream/{task_id}")
    async def stream(task_id:str,request: Request):
        # 获取流式调用时候的结果
        return StreamingResponse(content=sse_generator(task_id=task_id,request=request),media_type="text/event-stream")

    @app.delete("/history/{session_id}")
    def clean_history(session_id:str,query_service:QueryService = Depends(get_query_service)):
        #清空历史会话
        query_service.clean_history(session_id)
        return {"message": f"会话 {session_id} 的历史记录已清空"}

    @app.get("/history/{session_id}")
    def get_history(session_id:str,query_service:QueryService = Depends(get_query_service)):
        history_list = query_service.get_history(session_id)

        return HistoryResponse(session_id=session_id,items=history_list)


def create_app():
    #1. 创建FastAPI
    app = FastAPI(
        description="掌柜智库检索流程API",
        version="1.0"
    )

    #2. 处理跨域问题: 其实我们这个项目不需要考虑跨域问题
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # ← 和 credentials=True 冲突
        allow_credentials=False,
        allow_methods=["*"],  # ← 和 credentials=True 冲突
        allow_headers=["*"],  # ← 和 credentials=True 冲突
    )

    #3. 挂载静态文件,也就是指定静态文件的访问路径: 其实就是写静态资源的匹配路径
    # 如果前端的请求路径是 /front/import.html 那么后端就 "挂载的目录" 找import.html
    front_dir = get_front_page_dir()
    app.mount("/front", StaticFiles(directory=front_dir))

    #4. 注册路由
    register_router(app)

    return app

if __name__ == '__main__':
    # 运行FastAPI 服务
    app = create_app()

    uvicorn.run(app, host="0.0.0.0", port=8001)