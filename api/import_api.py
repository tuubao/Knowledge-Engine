import uvicorn
from fastapi import FastAPI, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends
from starlette.staticfiles import StaticFiles

from core.deps import get_file_process_service
from core.paths import get_front_page_dir
from schema.upload_schema import UploadResponse, TaskStatusResponse
from service.file_process_service import FileProcessService
from utils.task_util import get_task_info


def register_router(app: FastAPI):
    @app.get("/hello")
    def hello_world():
        return "Hello world"

    @app.post("/upload",response_model=UploadResponse)
    def upload_file(file:UploadFile,
                    background_tasks: BackgroundTasks,
                    file_process_service:FileProcessService = Depends(get_file_process_service)):
        #1. 将上传的文件进行处理(保存)
        import_file_path,file_dir,task_id = file_process_service.process_upload_file(file)
        #2. 执行导入的主流程
        background_tasks.add_task(file_process_service.run_main_graph,import_file_path,file_dir,task_id)

        return UploadResponse(message="上传成功",task_id=task_id)

    @app.get("/status/{task_id}",response_model=TaskStatusResponse)
    def get_task_status(task_id: str):
        #1. 获取当前任务的信息
        task_info = get_task_info(task_id)

        return TaskStatusResponse(**task_info)


def create_app():
    #1. 创建FastAPI
    app = FastAPI(
        description="掌柜智库导入流程API",
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

    uvicorn.run(app, host="0.0.0.0", port=8000)