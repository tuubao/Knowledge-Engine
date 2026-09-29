from typing import Tuple, List

from processor.query_processor.base import BaseNode
from processor.query_processor.exceptions import StateFieldError, MilvusError, EmbeddingError
from processor.query_processor.state import QueryGraphState
from utils.clients.ai_clients import AIClients
from utils.clients.storage_clients import StorageClients
from utils.embedding_util import generate_bge_m3_hybrid_vectors
from utils.milvus_util import _item_names_filter, create_hybrid_search_requests, execute_hybrid_search_query

"""
最终经过混合检索后,state中多了一个embedding_chunks属性,它的值是:
[{
    "id":""
    "distance":分数,
    "entity":{"item_name":"","title":"","content":""}
}]
"""
class VectorSearchNode(BaseNode):
    name = "vector_search_node"
    def process(self, state: QueryGraphState) -> QueryGraphState:
        #1. 参数校验
        rewritten_query,item_names = self._validate_state(state)
        #2. 获取嵌入模型对象、milvus客户端对象
        try:
            embedding_client = AIClients.get_bge_m3_client()
        except Exception as e:
            self.logger.error(f"获取嵌入模型对象失败,{e}")
            raise EmbeddingError(node_name=self.name,message=f"获取嵌入模型对象失败,{e}")

        try:
            milvus_client = StorageClients.get_milvus_client()
        except Exception as e:
            self.logger.error(f"获取milvus客户端对象失败,{e}")
            raise MilvusError(node_name=self.name, message=f"获取milvus客户端对象失败,{e}")
        #3. 将用户的查询进行向量化
        embedding_result = generate_bge_m3_hybrid_vectors(embedding_client,[rewritten_query])
        #4. 构建过滤条件
        expr, expr_params = _item_names_filter(item_names)
        #5. 构建混合检索的请求
        hybrid_search_requests = create_hybrid_search_requests(
            dense_vector=embedding_result.get("dense")[0],
            sparse_vector=embedding_result.get("sparse")[0],
            expr=expr,
            expr_params=expr_params,
            limit=self.config.embedding_search_limit
        )
        #6. 执行混合检索的请求
        hybrid_search_results = execute_hybrid_search_query(
            milvus_client=milvus_client,
            collection_name=self.config.chunks_collection,
            search_requests=hybrid_search_requests,
            limit=self.config.embedding_search_limit,
            output_fields=["item_name","title","content"]
        )
        #7. 返回结果
        return {"embedding_chunks":hybrid_search_results[0]}

    def _validate_state(self, state:QueryGraphState) -> Tuple[str, List[str]]:
        #1. 获取rewritten_query,item_names
        rewritten_query = state.get("rewritten_query")
        item_names = state.get("item_names")
        #2. 校验rewritten_query,item_names
        if not rewritten_query or not isinstance(rewritten_query, str):
            self.logger.error(f"rewritten_query不能为空以及类型必须是str")
            raise StateFieldError(node_name=self.name,field_name="rewritten_query",expected_type=str)

        if not item_names or not isinstance(item_names, list):
            self.logger.error("item_names不能为空以及类型必须是list")
            raise StateFieldError(node_name=self.name,field_name="item_names",expected_type=list)

        return rewritten_query,item_names

if __name__ == '__main__':
    #1. 创建state
    state = {
        "rewritten_query":"RS PRO RS-12 数字万用表的使用方法是什么?",
        "item_names":["RS PRO RS-12 数字万用表"]
    }
    node = VectorSearchNode()
    final_state = node.process(state)
    print(final_state)