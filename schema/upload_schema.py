from typing import List, Dict
from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """文件上传响应 —— POST /upload 返回"""
    message: str = Field(..., description="响应消息")
    task_id: str = Field(..., description="任务ID")


class TaskStatusResponse(BaseModel):
    """任务状态响应 —— GET /status/{task_id} 返回"""
    status: str = Field(..., description="任务状态")
    done_list: List[str] = Field(..., description="已完成节点列表")
    running_list: List[str] = Field(..., description="正在运行节点列表")
    durations: Dict[str, float] = Field(default=dict, description="各节点耗时(秒)")


class InternalImportRunRequest(BaseModel):
    """内部导入跑图 —— POST /internal/import/run（由 Java 编排后调用）"""
    task_id: str = Field(..., description="任务ID")
    import_file_path: str = Field(..., description="本地文件绝对路径（与 Java 共享磁盘）")
    file_dir: str = Field(..., description="工作目录（通常为文件所在目录）")


class InternalImportRunResponse(BaseModel):
    message: str = Field(..., description="响应消息")
    task_id: str = Field(..., description="任务ID")
