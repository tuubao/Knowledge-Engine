import os

import uvicorn
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends

from core.deps import get_file_process_service
from schema.upload_schema import UploadResponse, TaskStatusResponse, InternalImportRunRequest, InternalImportRunResponse
from service.file_process_service import FileProcessService
from utils.task_util import get_task_info

# STEP09: default false — Python is an internal AI worker, not a browser entry.
EXPOSE_PUBLIC_API = os.getenv("EXPOSE_PUBLIC_API", "false").strip().lower() in ("1", "true", "yes")


def register_internal_routes(app: FastAPI):
    @app.get("/health")
    def health():
        return {"status": "ok", "service": "import-worker"}

    @app.get("/hello")
    def hello_world():
        return "Hello world"

    @app.post("/internal/import/run", response_model=InternalImportRunResponse)
    def internal_import_run(
            body: InternalImportRunRequest,
            background_tasks: BackgroundTasks,
            file_process_service: FileProcessService = Depends(get_file_process_service),
    ):
        """
        STEP07：由 Java 完成上传/落盘后，仅触发 LangGraph 导入流水线。
        后台执行，进度写入 Redis（task_util 双写）。
        """
        background_tasks.add_task(
            file_process_service.run_main_graph,
            body.import_file_path,
            body.file_dir,
            body.task_id,
        )
        return InternalImportRunResponse(message="导入任务已受理", task_id=body.task_id)


def register_public_routes(app: FastAPI):
    """Legacy browser-facing routes. Only registered when EXPOSE_PUBLIC_API=true."""

    @app.post("/upload", response_model=UploadResponse)
    def upload_file(file: UploadFile,
                    background_tasks: BackgroundTasks,
                    file_process_service: FileProcessService = Depends(get_file_process_service)):
        import_file_path, file_dir, task_id = file_process_service.process_upload_file(file)
        background_tasks.add_task(file_process_service.run_main_graph, import_file_path, file_dir, task_id)
        return UploadResponse(message="上传成功", task_id=task_id)

    @app.get("/status/{task_id}", response_model=TaskStatusResponse)
    def get_task_status(task_id: str):
        task_info = get_task_info(task_id)
        return TaskStatusResponse(**task_info)


def create_app():
    app = FastAPI(
        description="掌柜智库导入 Worker（内网）",
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
    uvicorn.run(app, host=host, port=8000)
