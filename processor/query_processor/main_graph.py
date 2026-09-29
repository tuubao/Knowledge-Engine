"""查询流程主图

使用 LangGraph 构建知识库查询工作流。
"""
import logging

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from dotenv import load_dotenv
from processor.query_processor.nodes.answer_output_node import AnswerOutputNode
from processor.query_processor.nodes.hyde_search_node import HydeSearchNode
from processor.query_processor.nodes.item_name_confirmed_node import ItemNameConfirmedNode
from processor.query_processor.nodes.rerank_node import RerankNode
from processor.query_processor.nodes.rrf_merge_node import RrfMergeNode
from processor.query_processor.nodes.vector_search_node import VectorSearchNode
from processor.query_processor.nodes.web_search_node import WebSearchNode
from processor.query_processor.state import QueryGraphState

# 加载环境变量
load_dotenv()


def route_after_item_confirm(state: QueryGraphState) -> bool:
    """商品名称确认后的路由逻辑。

    根据是否已有答案决定是否跳过搜索直接输出。

    Args:
        state: 查询图状态。

    Returns:
        True 表示已有答案需要跳过搜索，False 表示继续搜索流程。
    """
    if state.get("answer"):
        return True
    return False


def create_query_graph() -> CompiledStateGraph:
    """创建查询流程图。

    Returns:
        编译后的 StateGraph 实例。

    流程结构::

        item_name_confirm
              │
              ├── (有答案) ──────────────────────────> answer_output
              │                                            │
              └── (无答案)                                  │
                   │                                       │
                   v                                       │
              multi_search                                 │
                   │                                       │
             ┌─────┼──────────┐                            │
             │     │          │                            │
             v     v          v                            │
        embedding  hyde    web_mcp                         │
             │     │          │                            │
             └─────┼──────────┘                            │
                   │                                       │
                   v                                       │
                 join                                      │
                   │                                       │
                   v                                       │
                  rrf                                      │
                   │                                       │
                   v                                       │
                rerank                                     │
                   │                                       │
                   v                                       │
             answer_output <───────────────────────────────┘
                   │
                   v
                  END
    """

    # 1. 定义LangGraph工作流
    workflow = StateGraph(QueryGraphState)  # type:ignore

    # 2. 实例化节点
    nodes = {
        "item_name_confirmed_node":ItemNameConfirmedNode(),
        "multi_search":lambda x:x,  # 虚拟节点
        "vector_search_node":VectorSearchNode(),
        "hyde_search_node": HydeSearchNode(),
        "web_search_node":WebSearchNode(),
        "join":lambda x:{}, # 虚拟节点
        "rrf_merge_node":RrfMergeNode(),
        "rerank_node":RerankNode(),
        "answer_output_node":AnswerOutputNode()
    }
    # 3. 添加节点
    for node_name,node in nodes.items():
        workflow.add_node(node_name, node)

    # 4. 定义入口节点
    workflow.set_entry_point("item_name_confirmed_node")

    # 5. 添加条件边
    workflow.add_conditional_edges(
        source="item_name_confirmed_node",
        path=route_after_item_confirm,
        path_map={
            True:"answer_output_node",
            False:"multi_search"
        }
    )

    # 6. 添加业务边
    workflow.add_edge("multi_search","vector_search_node")
    workflow.add_edge("multi_search","hyde_search_node")
    workflow.add_edge("multi_search","web_search_node")

    workflow.add_edge("vector_search_node", "join")
    workflow.add_edge("hyde_search_node", "join")
    workflow.add_edge("web_search_node", "join")

    workflow.add_edge("join", "rrf_merge_node")
    workflow.add_edge("rrf_merge_node", "rerank_node")
    workflow.add_edge("rerank_node", "answer_output_node")
    workflow.add_edge("answer_output_node", END)

    return workflow.compile()


# 创建全局图实例
query_app = create_query_graph()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("开始测试: 查询流程主图 (main_graph)")
    print("=" * 60)

    # ---- 测试场景 1：商品名明确，走完整 pipeline ----
    print("\n【场景 1】: 商品名明确，走完整 pipeline")
    print("-" * 60)

    mock_state_1 = {
        "original_query": "RS-12 数字万用表如何测量直流电压？",
        "session_id": "test_session_main_graph",
        "task_id": "test_task_001",
        "is_stream": False,
    }

    #执行主流程
    result_1 = query_app.invoke(mock_state_1)

    print(f"\n  【结果】:")
    print(f"  商品名: {result_1.get('item_names')}")
    print(f"  重写查询: {result_1.get('rewritten_query')}")
    answer_1 = result_1.get("answer", "")
    print(f"  答案: {answer_1[:200]}..." if len(answer_1) > 200 else f"  答案: {answer_1}")




