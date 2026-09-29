# LangGraph的具体流程
#1. 创建StateGraph,将state传给StateGraph
#2. 添加节点
#3. 添加边: 业务边和条件边
#4. 编译StateGraph
#5. 执行
from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.import_processor.nodes.bge_embedding_chunks_node import BgeEmbeddingChunksNode
from processor.import_processor.nodes.document_split_node import DocumentSplitNode
from processor.import_processor.nodes.entry_node import EntryNode
from processor.import_processor.nodes.item_name_recognition_node import ItemNameRecognitionNode
from processor.import_processor.nodes.md_image_node import MdImageNode
from processor.import_processor.nodes.milvus_import_node import MilvusImportNode
from processor.import_processor.nodes.pdf_to_md_node import PdfToMdNode
from processor.import_processor.state import ImportGraphState

def import_router(state:ImportGraphState):
    #1. 判断是不是pdf文件
    if state['is_pdf_read_enabled']:
        # 是pdf文件
        return "pdf_router"
    elif state['is_md_read_enabled']:
        # 是md文件
        return "md_router"
    return END

def import_graph():
    #1. 创建StateGraph,将state传给StateGraph
    work_flow = StateGraph(state_schema=ImportGraphState)
    #2. 添加节点
    #2.1 声明节点列表
    node_list = {
        "entry_node":EntryNode(),
        "pdf_to_md_node":PdfToMdNode(),
        "md_image_node":MdImageNode(),
        "document_split_node":DocumentSplitNode(),
        "item_name_recognition_node":ItemNameRecognitionNode(),
        "bge_embedding_chunks_node":BgeEmbeddingChunksNode(),
        "milvus_import_node":MilvusImportNode()
    }
    #2.2 遍历节点列表，进行节点的添加
    for node_name,node in node_list.items():
        work_flow.add_node(node_name,node)

    #2.3 指定入口节点为entry_node
    work_flow.set_entry_point("entry_node")

    #2.3 添加边
    """
    entry_node ----> 条件边: 判断pdf还是md,如果是pdf -----> pdf_to_md_node,如果是md ----> md_image_node
    pdf_to_md_node ----> md_image_node
    md_image_node -----> document_split_node
    document_split_node ----> item_name_recognition_node
    item_name_recognition_node ----> bge_embedding_chunks_node
    bge_embedding_chunks_node ----> milvus_import_node
    milvus_import_node -----> END
    """
    #2.3.1 条件边
    work_flow.add_conditional_edges("entry_node",import_router,
                                    {
                                        "pdf_router":"pdf_to_md_node",
                                        "md_router":"md_image_node"
                                    })
    #2.3.2 业务边
    work_flow.add_edge("pdf_to_md_node","md_image_node")
    work_flow.add_edge("md_image_node","document_split_node")
    work_flow.add_edge("document_split_node","item_name_recognition_node")
    work_flow.add_edge("item_name_recognition_node","bge_embedding_chunks_node")
    work_flow.add_edge("bge_embedding_chunks_node","milvus_import_node")
    work_flow.add_edge("milvus_import_node",END)

    #2.4 编译graph
    compiled_graph = work_flow.compile()
    return compiled_graph

import_app = import_graph()


if __name__ == '__main__':
    #1. 创建graph
    state = {
        "import_file_path":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\input_dir\Aolynk CB304n Cable网桥 用户手册-5W100-整本手册.pdf",
        "file_dir":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir"
    }

    #执行
    final_state = {}
    for event in import_app.stream(state):
        for node_name,state in event.items():
            print(f"{node_name}执行......")
            final_state = state


    print(final_state)


