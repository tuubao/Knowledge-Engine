import logging
import uuid

from processor.query_processor.main_graph import query_app
from processor.query_processor.state import QueryGraphState
from utils.mongo_history_util import clear_history, get_recent_messages
from utils.task_util import get_task_result, update_task_status, TASK_STATUS_PROCESSING, \
    TASK_STATUS_COMPLETED, TASK_STATUS_FAILED

logger = logging.getLogger(__name__)
class QueryService:

    def generate_session_id(self):
        return uuid.uuid4()

    def generate_task_id(self):
        return uuid.uuid4().hex[:12]

    def get_query_result(self,task_id:str) -> str:
        return get_task_result(task_id=task_id,key="answer")

    def run_query_graph(self,query:str,session_id:str,task_id:str,is_stream:bool):
        #执行整个检索流程
        #1. 创建State
        query_graph_state = QueryGraphState()
        """
        {
            "original_query": "RS-12 数字万用表如何测量直流电压？",
            "session_id": "test_session_main_graph",
            "task_id": "test_task_001",
            "is_stream": False,
        }
        """
        query_graph_state['original_query'] = query
        query_graph_state['session_id'] = session_id
        query_graph_state['task_id'] = task_id
        query_graph_state['is_stream'] = is_stream
        try:
            #2. 调用LangGraph执行
            # 设置整个检索流程的状态为正在进行
            update_task_status(task_id=task_id, status_name=TASK_STATUS_PROCESSING)
            query_app.invoke(query_graph_state)
            # 设置整个检索流程的状态为已完成
            update_task_status(task_id=task_id, status_name=TASK_STATUS_COMPLETED)
        except Exception as e:
            logger.error(f"运行查询流程出现异常:{str(e)}")
            # 设置整个检索流程的状态为失败
            update_task_status(task_id=task_id, status_name=TASK_STATUS_FAILED)
            raise e

    def clean_history(self,session_id:str):
        clear_history(session_id)

    def get_history(self,session_id:str):
        history_list = get_recent_messages(session_id)

        # 按照ts从小到大排序
        sorted_history_list = sorted(history_list, key=lambda k: k['ts'], reverse=False)
        return [
            {
                "_id": str(history.get("_id", "")),
                "session_id": history.get("session_id") or "",
                "role": history.get("role") or "",
                "text": history.get("text") or "",
                "rewritten_query": history.get("rewritten_query") or "",
                "item_names": history.get("item_names") or [],
                "ts": history.get("ts"),
            } for history in sorted_history_list
        ]

