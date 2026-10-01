"""查询相关 Schema 定义"""

from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(..., description="查询内容")
    session_id: Optional[str] = Field(None, description="会话ID，不传则自动生成")
    is_stream: bool = Field(False, description="是否流式返回")


class QueryResponse(BaseModel):
    message: str = Field(..., description="响应消息")
    session_id: str = Field(..., description="会话ID")
    answer: str = Field("", description="生成的答案")
    done_list: List[str] = Field(default=[],description="已完成的节点列表")

class StreamSubmitResponse(BaseModel):
    message: str = Field(..., description="响应消息")
    session_id: str = Field(..., description="会话ID")
    task_id: str = Field(..., description="任务ID，前端用此 ID 建立 SSE 连接")


class InternalQueryRunRequest(BaseModel):
    """内部查询跑图 —— POST /internal/query/run（由 Java 编排后调用）"""
    task_id: str = Field(..., description="任务ID")
    session_id: str = Field(..., description="会话ID")
    query: str = Field(..., description="查询内容")
    is_stream: bool = Field(False, description="是否流式")


class InternalQueryRunResponse(BaseModel):
    message: str = Field(..., description="响应消息")
    task_id: str = Field(..., description="任务ID")
    session_id: str = Field(..., description="会话ID")
    answer: str = Field("", description="非流式时返回答案；流式后台受理时为空")
    done_list: List[str] = Field(default_factory=list, description="已完成节点")
    rewritten_query: str = Field("", description="重写后的查询")
    item_names: List[str] = Field(default_factory=list, description="识别到的产品名")


class HistoryItem(BaseModel):
    id: str = Field("", alias="_id")
    session_id: str = ""
    role: str = ""
    text: str = ""
    rewritten_query: str = ""
    item_names: List[str] = Field(default=list)
    ts: Optional[float] = None

    @field_validator("session_id", "role", "text", "rewritten_query", mode="before")
    @classmethod
    def coerce_none_to_empty_str(cls, v):
        return v if v is not None else ""


class HistoryResponse(BaseModel):
    session_id: str
    items: List[HistoryItem]
