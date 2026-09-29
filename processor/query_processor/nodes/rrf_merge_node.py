from typing import List, Any, Dict, Tuple

from processor.query_processor.base import BaseNode, T
from processor.query_processor.state import QueryGraphState


class RrfMergeNode(BaseNode):
    name = "rrf_merge_node"
    def process(self, state: QueryGraphState) -> QueryGraphState:
        #1. 获取并校验混合检索、以及hyde检索的结果
        vector_search_chunks = state.get("embedding_chunks") or []
        hyde_search_chunks = state.get("hyde_embedding_chunks") or []

        #2. 对两路检索的结果进行格式规整化
        embedding_chunks = self._format_doc(vector_search_chunks)
        hyde_embedding_chunks = self._format_doc(hyde_search_chunks)

        #3. 将两路结果组装成列表，并且给每路设置权重
        rrf_inputs = [(embedding_chunks,1.0),(hyde_embedding_chunks,1.0)]

        #4. 进行rrf融合
        rrf_merged_result = self._rrf_merge(rrf_inputs,self.config.rrf_k,self.config.rrf_max_results)

        #5. 将融合后的结果存储到state中
        state['rrf_chunks'] = rrf_merged_result
        return state

    def _format_doc(self, chunks:List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        输入:
        [{"id":1,"distance":0.02,"entity":{"title":"标题","content":"内容"}}]

        输出:
        [{"chunk_id":1,"title":"标题","content":"内容"}]
        :param chunks:
        :return:
        """
        #1. 声明一个容器formated_chunks,用来存储格式化规整之后的数据
        formated_chunks = []
        #1. 遍历输入的chunks
        for chunk in chunks:
            if not chunk or not isinstance(chunk, dict):
                continue
            #1. 获取chunk_id
            chunk_id = chunk.get("id")
            #2. 获取entity
            entity = chunk.get("entity")
            if not entity or not isinstance(entity, dict):
                continue
            #2.1 获取title
            title = entity.get("title","")
            #2.2 获取content
            content = entity.get("content","")

            if not content:
                continue

            formated_chunks.append({"chunk_id": chunk_id, "title": title, "content": content})
        return formated_chunks

    def _rrf_merge(self, rrf_inputs:List[Tuple[List[Dict[str,Any]],float]],k:int,rrf_max_results:int) -> List[Dict[str,Any]]:

        #声明一个容器，用于存储每个文档的总得分。它是dict类型，key就是文档的chunk_id，value就是文档使用rrf算法得到的的得分
        chunk_score = {}

        #声明一个容器，存储每个文档的内容 {"chunk_id":1,{"chunk_id":1,"title":"标题","content":"内容","score":0.12}}
        chunk_data = {}
        #1. 遍历rrf_inputs
        for rrf_input in rrf_inputs:
            #1.1 获取当前路的权重和chunks
            chunks,weight = rrf_input
            #2. 遍历每一路中的每一条数据
            for rank,chunk in enumerate(chunks,1):
                #2.1 获取文档id
                chunk_id = chunk.get("chunk_id")
                #2.2 通过公式计算当前chunk在当前路中的得分
                chunk_score[chunk_id] = chunk_score.get(chunk_id,0) + weight/(k + rank)

                #2.3 将当前文档的内容设置到chunk_data中
                chunk_data[chunk_id] = {**chunk,"score":chunk_score[chunk_id]}

        #3. 将chunk_data收集到列表中,按照分数进行排序,排序完之后最后的结果不要分数 []
        result_chunks = chunk_data.values()
        #4. 按照分数进行排序，将分数高的排在前面
        sorted_chunks = sorted(result_chunks,key=lambda x:x["score"],reverse=True)
        return sorted_chunks[:rrf_max_results] if rrf_max_results else sorted_chunks


if __name__ == '__main__':
    print("=" * 60)
    print("开始测试: RRF 融合节点")
    print("=" * 60)

    # 模拟两路检索结果
    # chunk_1 命中 2 路（预期最高分）
    # chunk_2 命中 2 路
    # chunk_3, chunk_4 各命中 1 路
    mock_state = {
        "embedding_chunks": [
            {"id":"chunk_1","entity": {"chunk_id": "chunk_1", "content": "向量搜索结果#1"}},
            {"id":"chunk_2","entity": {"chunk_id": "chunk_2", "content": "向量搜索结果#2"}},
            {"id":"chunk_3","entity": {"chunk_id": "chunk_3", "content": "向量搜索结果#3"}},
        ],
        "hyde_embedding_chunks": [
            {"id":"chunk_2","entity": {"chunk_id": "chunk_2", "content": "HyDE搜索结果#1"}},
            {"id":"chunk_1","entity": {"chunk_id": "chunk_1", "content": "HyDE搜索结果#2"}},
            {"id":"chunk_4","entity": {"chunk_id": "chunk_4", "content": "HyDE搜索结果#3"}},
        ],
    }
    """
        chunk_1的总得分: 1/(60+1) + 1/(60+2) = 0.03252247488101534
        chunk_2的总得分: 1/(60+2) + 1/(60+1) = 0.03252247488101534
    """

    print("【输入状态】:")
    print(f"  embedding_chunks: {len(mock_state['embedding_chunks'])} 条")
    print(f"  hyde_embedding_chunks: {len(mock_state['hyde_embedding_chunks'])} 条")
    print("-" * 60)

    rrf_node = RrfMergeNode()
    result = rrf_node.process(mock_state)
    print(result)