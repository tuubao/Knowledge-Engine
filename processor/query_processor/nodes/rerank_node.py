import math
from typing import Any, Dict, List
from processor.query_processor.base import BaseNode, T
from processor.query_processor.state import QueryGraphState
from utils.clients.ai_clients import AIClients


class RerankNode(BaseNode):
    name = "rerank_node"
    def process(self, state: QueryGraphState) -> QueryGraphState:
        #1. 获取用户的问题
        user_query = state.get("rewritten_query")
        #2. 对rrf合并的结果、以及web检索的结果进行规整化
        #2.1 获取rrf合并的结果
        rrf_docs = state.get("rrf_chunks")
        #2.2 获取web检索的结果
        web_search_docs = state.get("web_search_docs")
        #2.3 进行检索结果的格式规整化,并且将rrf的结果与web检索的结果，合成一个列表
        final_docs = self._format_rrf_docs(rrf_docs)
        final_docs.extend(self._format_web_docs(web_search_docs))
        #2.4 调用Rerank模型进行计算文档得分
        doc_score = self._refine_rerank(user_query,final_docs)
        #2.5 按照分数从高到低进行排序
        sorted_doc_score = sorted(doc_score,key=lambda x:x["score"],reverse=True)

        #3. 动态截断,断崖检测
        reranked_docs = self._cliff_cutoff(sorted_doc_score,self.config.rerank_min_top_k,self.config.rerank_max_top_k,self.config.rerank_gap_abs)

        state["reranked_docs"] = reranked_docs
        return state





    def _format_rrf_docs(self, docs:List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        """
        最终规整化后的内容是一个dict的列表,dict的结构:
        {
            "chunk_id":1,
            "title":标题,
            "content":内容,
            "url":网络检索的链接,
        }
        :param docs:
        :return:
        """
        formated_docs = []
        for doc in docs:
            chunk_id = doc.get("chunk_id")
            title = doc.get("title")
            content = doc.get("content")
            formated_docs.append({
                "chunk_id": chunk_id,
                "title": title,
                "content": content,
                "source":"local" #来源,你到底是本地检索的结果还是网络检索的结果
            })
        return formated_docs


    def _format_web_docs(self, docs:List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        """
        最终规整化后的内容是一个dict的列表,dict的结构:
        {
            "chunk_id":1,
            "title":标题,
            "content":内容,
            "url":网络检索的链接,
            "source":来源,你到底是本地检索的结果还是网络检索的结果
        }
        :param docs:
        :return:
        """
        formated_docs = []
        for doc in docs:
            title = doc.get("title")
            content = doc.get("snippet")
            url = doc.get("url")
            formated_docs.append({
                "title": title,
                "content": content,
                "url": url,
                "source":"web"
            })
        return formated_docs

    @staticmethod
    def _sigmoid(score: float) -> float:
        """sigmoid归一化，将 (-∞, +∞) 映射到 (0, 1)"""
        return 1.0 / (1.0 + math.exp(-score))

    def _refine_rerank(self, user_query:str, final_docs:List[Dict[str,Any]]) -> List[Dict[str,Any]]:
        #1.构建Q-D对
        question_document_pairs = [(user_query, doc.get("content")) for doc in final_docs]
        #2. 创建Rerank模型对象
        try:
            rerank_client = AIClients.get_bge_m3_rerank_client()
        except Exception as e:
            self.logger.warn(f"获取Rerank模型对象失败,{e}")
            return [{**doc,"score":None} for doc in final_docs]
        #3. 调用模型进行得分计算
        try:
            scores = rerank_client.compute_score(question_document_pairs)

            return [{**doc,"score":self._sigmoid(score)} for doc,score in zip(final_docs,scores)]
        except Exception as e:
            self.logger.warn(f"调用Rerank模型计算相关性得分失败,{e}")
            return [{**doc, "score": None} for doc in final_docs]

    def _cliff_cutoff(self, sorted_doc_score:List[Dict[str,Any]], rerank_min_top_k:int, rerank_max_top_k:int, rerank_gap_abs:float) -> List[Dict[str,Any]]:
        #1. 定义截取的上边界
        upper_bound = min(rerank_max_top_k,len(sorted_doc_score))

        #2. 定义截取的下边界
        lower_bound = min(rerank_min_top_k,upper_bound)

        #3. 遍历sorted_doc_score列表，计算最大断崖点的下标
        #3.1 指定最大分差
        max_score_gap = 0
        #3.2 指定进行截取的位置的下标
        cut_index = upper_bound
        for i in range(0,upper_bound - 1):
            #3.3 获取当前位置的文档得分
            current_score = sorted_doc_score[i].get("score")
            #3.4 获取下一个位置的文档得分
            next_score = sorted_doc_score[i+1].get("score")

            if current_score is None or next_score is None:
                continue
            #3.5 计算当前位置的得分与下一个位置的得分的差值
            score_gap = current_score - next_score
            #3.6 判断score_gap是否达到阈值、以及是否超过最大差值
            if score_gap >= rerank_gap_abs and score_gap > max_score_gap:
                #3.6.1 更换最大差值
                max_score_gap = score_gap
                #3.6.2 记录断崖点
                cut_index = i

        #3.7 对sorted_doc_score进行截取，截取点cut_index
        cut_index = max(lower_bound,cut_index)
        return sorted_doc_score[:cut_index]


if __name__ == "__main__":
    print("=" * 60)
    print("开始测试: 重排序节点 (RerankNode)")
    print("=" * 60)

    mock_state = {
        "rewritten_query": "怎么测这块主板的短路问题？",
        "rrf_chunks": [
            {"chunk_id": "local_1", "title": "主板维修手册",
             "content": "主板短路通常表现为通电后风扇转一下就停，可以使用万用表的蜂鸣档测量。"},
            {"chunk_id": "local_2", "title": "闲聊",
             "content": "今天中午去吃猪脚饭吧，这块主板外观很漂亮。"},
        ],
        "web_search_docs": [
            {"url": "https://example.com/repair", "title": "短路查修指南",
             "snippet": "主板通电前先打各主供电电感的对地阻值，阻值偏低就是短路。"},
            {"url": "https://example.com/news", "title": "科技新闻",
             "snippet": "苹果发布新款手机，A系列芯片性能提升20%。"},
        ],
    }

    print("【输入状态】:")
    print(f"  查询: {mock_state['rewritten_query']}")
    print(f"  本地文档: {len(mock_state['rrf_chunks'])} 篇")
    print(f"  网络文档: {len(mock_state['web_search_docs'])} 篇")
    print("-" * 60)

    node = RerankNode()
    result = node.process(mock_state)

    print(result.get("reranked_docs"))