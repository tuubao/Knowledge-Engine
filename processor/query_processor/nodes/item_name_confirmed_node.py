import json
import re
from logging import Logger
from typing import Dict, Any, List, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from processor.query_processor.base import BaseNode
from processor.query_processor.config import QueryConfig
from processor.query_processor.state import QueryGraphState
from prompts.query_prompt import ITEM_NAME_SYSTEM_EXTRACT_TEMPLATE, ITEM_NAME_USER_EXTRACT_TEMPLATE
from utils.clients.ai_clients import AIClients
from utils.clients.storage_clients import StorageClients
from utils.embedding_util import generate_bge_m3_hybrid_vectors
from utils.milvus_util import create_hybrid_search_requests, execute_hybrid_search_query, milvus_client
from utils.mongo_history_util import get_recent_messages


class _ItemNameAligner:
    def __init__(self, logger: Logger,config: QueryConfig):
        self._logger = logger
        self._config = config

    def search_and_align(self,item_names: List[str]) -> Tuple[List[str], List[str]]:
        # 1. 混合检索向量数据库
        search_result = self._search_vector(item_names)
        # 2. 判断检索到的结果，如果为空，则表示confirmed和options都没有
        if not search_result:
            return [],[]
        # 2. 根据混合向量检索到结果做对齐【confirmed/options】
        confirmed,options = self._align(search_result)

        # 3. 分数差异化过滤
        #3.1 如果confirmed的长度大于1，则进行分数差异化过滤
        if len(confirmed) > 1:
            final_confirmed = self._item_name_score_filter()

        # 4. 返回确定的confirmed容器和options容器
        return confirmed,options

    def _search_vector(self, item_names:List[str]):
        """
        [{
            "extracted_name":"大模型提取的item_name",
            "matches":[{"item_name":"从向量数据库匹配到的item_name","score":分数}]
        }]
        :param item_names:
        :return:
        """
        #1. 创建嵌入模型对象
        #初始化检索结果
        final_search_result = []
        try:
            embedding_client = AIClients.get_bge_m3_client()
        except Exception as e:
            self._logger.error(f"获取嵌入模型失败,{e}")
            return final_search_result

        #2. 对item_names进行向量化
        try:
            embedding_result = generate_bge_m3_hybrid_vectors(embedding_client,item_names)
            dense_vector_list = embedding_result.get("dense")
            sparse_vector_list = embedding_result.get("sparse")
        except Exception as e:
            self._logger.error(f"向量嵌入失败,{e}")
            return final_search_result

        #创建milvus_client对象
        try:
            milvus_client = StorageClients.get_milvus_client()
        except Exception as e:
            self._logger.error(f"获取milvus客户端失败,{e}")
            return final_search_result

        #3. 创建混合检索请求
        #3.1 对item_names进行遍历
        for index,item_name in enumerate(item_names):
            # 创建混合检索请求
            search_requests = create_hybrid_search_requests(
                dense_vector=dense_vector_list[index],
                sparse_vector=sparse_vector_list[index],
                limit=self._config.embedding_search_limit
            )

            # 执行混合检索请求
            milvus_search_results = execute_hybrid_search_query(
                milvus_client=milvus_client,
                collection_name=self._config.item_name_collection,
                search_requests=search_requests,
                limit=self._config.embedding_search_limit,
                output_fields=["item_name"]
            )
            #组装匹配结果
            matches = []
            for m in milvus_search_results[0]:
                matches.append({
                    "item_name":m["entity"]["item_name"],
                    "score":m["distance"]
                })

            final_search_result.append({
                "extracted_name": item_name,
                "matches":matches
            })


        return final_search_result

    def _align(self, search_result:List[Dict[str,Any]]):
        """
        2. 如果检索到的结果不为空，则对结果进行对齐
           1.
           2. 遍历检索结果:
              1. 获取每个检索结果的extracted_name、matches
              2. 对matches按照score从大到小进行排序
              3. 收集score>item_name_high_confidence的匹配结果，也就是高可置信的结果
              4. 如果有高可置信的结果
                 1. 判断结果中的item_name与LLM提取的item_name是否一模一样，如果有，则将其添加到confirmed容器中（需要去重，要排除它已经在confirmed的情况）
                 2. 如果没有一模一样的，但是只有一个高可置信的结果，则将这个结果的item_name添加到confirmed容器中（需要去重，要排除它已经在confirmed的情况）
                 3. 如果没有一模一样的，并且有多个高可置信的结果
                    1. 判断最高分是不是比第二名高的分数超过阈值item_name_score_gap，如果超过，则将最高分的结果的item_name添加到confirmed容器中（需要去重）
                    2. 如果最高分比第二名高的分数没有超过阈值，则遍历高可置信结果集，有阈值设置了最大个数item_name_max_options，将这几个结果的item_name添加到options容器中（需要去重: 要排除它已经在confirmed、options中的情况）
              5. 如果没有高可置信的结果:
                 1. 收集中等可置信的结果
                 2. 如果有中等可置信的结果集，则将其item_name添加到options中，最多不能超过item_name_max_options个
           3. 返回confirmed和options
        :param search_result:
        :return:
        """
        #1. 定义两个容器: confirmed、options，分别存放确定好的商品名、以及待确认的商品名
        confirmed = []
        options = []
        #2. 遍历检索结果
        for result in search_result:
            #2.1 获取extracted_name和matches
            extracted_name = result.get("extracted_name")
            matches = result.get("matches")
            #2.2 对matches按照score从大到小进行排序
            matches = sorted(matches, key=lambda x: x["score"], reverse=True)
            #2.3 收集score>item_name_high_confidence的匹配结果，也就是高可置信的结果
            high_result = [m.get("item_name") for m in matches if m.get("score") >= self._config.item_name_high_confidence]
            #2.4 如果有高可置信的结果
            if high_result:
                # 2.4.1. 判断结果中的item_name与LLM提取的item_name是否一模一样，如果有，则将其添加到confirmed容器中（需要去重，要排除它已经在confirmed的情况）
                same_item_name = [h for h in high_result if h == extracted_name and h not in confirmed]
                if same_item_name:
                    confirmed.extend(same_item_name)
                elif len(high_result) == 1:
                    #2.4.1 如果没有一模一样的，但是只有一个高可置信的结果，则将这个结果的item_name添加到confirmed容器中（需要去重，要排除它已经在confirmed的情况）
                    high = high_result[0]
                    if high not in confirmed:
                        confirmed.append(high)
                else:
                    #2.4.2 如果没有一模一样的，并且有多个高可置信的结果
                    #2.4.2.1 判断最高分是不是比第二名高的分数超过阈值item_name_score_gap，如果超过，则将最高分的结果的item_name添加到confirmed容器中（需要去重）
                    max_score = matches[0]["score"]
                    if max_score - matches[1]["score"] > self._config.item_name_score_gap:
                        max_item_name = matches[0]["item_name"]
                        if max_item_name not in confirmed:
                                    confirmed.append(max_item_name)
                    else:
                        #2.4.2.2 2. 如果最高分比第二名高的分数没有超过阈值，则遍历高可置信结果集，有阈值设置了最大个数item_name_max_options，将这几个结果的item_name添加到options容器中（需要去重: 要排除它已经在confirmed、options中的情况）
                        for high in high_result[:self._config.item_name_max_options]:
                            if high not in confirmed and high not in options:
                                options.append(high)


            else:
                #2.5 没有高可置信的结果
                #2.5.1 收集中等可置信结果
                middle_matches = [m for m in matches if m.get("score", 0) >= self._config.item_name_mid_confidence]
                # 当前嵌入模型的稀疏向量未训练，混合分经常落在 0.45~0.75。
                # 名字互相包含时直接确认，避免对唯一命中反复追问。
                overlapped = [
                    m for m in middle_matches
                    if self._names_overlap(extracted_name, m.get("item_name"))
                ]
                if len(overlapped) == 1:
                    overlapped_name = overlapped[0].get("item_name")
                    if overlapped_name and overlapped_name not in confirmed:
                        confirmed.append(overlapped_name)
                    continue
                middle_result = [m.get("item_name") for m in middle_matches]
                #2.5.2 如果有中等可置信的结果集，则将其item_name添加到options中，最多不能超过item_name_max_options个
                if middle_result:
                    for mid in middle_result[:self._config.item_name_max_options]:
                        if mid not in confirmed and mid not in options:
                            options.append(mid)

        return confirmed,options[:self._config.item_name_max_options]

    @staticmethod
    def _names_overlap(left: str, right: str) -> bool:
        """忽略空白后，一方包含另一方即视为同一商品。过短的词不参与，避免「笔记本」误命中。"""
        normalized_left = re.sub(r"\s+", "", left or "").lower()
        normalized_right = re.sub(r"\s+", "", right or "").lower()
        if len(normalized_left) < 4 or len(normalized_right) < 4:
            return False
        return normalized_left in normalized_right or normalized_right in normalized_left

    #分数差异化过滤
    def _item_name_score_filter(self, confirmed: List[str], search_result: List[Dict[str, Any]]):
        """
        1. 找到confirmed中所有item_name的最大得分
        2. 判断每一个item_name的得分，相较于最大得分的差距是否超过阈值，超过阈值则丢弃
        :param confirmed:
        :param search_result:
        :return:
        """
        #1. 找到confirmed中所有item_name的最大得分
        #1.1 建立商品名与分数的dict
        #构建 商品名 → 最高分数 的映射
        item_name_score = {}
        for result in search_result:
            matches = result.get("matches")
            for m in matches:
                item_name = m.get("item_name")
                score = m.get("score")
                item_name_score[item_name] = max(item_name_score[item_name],score)


        #1.2 获取confirmed中所有item_name的最大得分
        max_score = 0
        for item_name in confirmed:
            max_score = max(max_score,item_name_score[item_name])

        #2. 判断每一个item_name的得分，相较于最大得分的差距是否超过阈值，超过阈值则丢弃
        final_confirmed = []
        for item_name in confirmed:
            if max_score - item_name_score[item_name] <= self._config.item_name_score_gap:
                final_confirmed.append(item_name)

        return final_confirmed


class _ItemNameExtractor:
    def __init__(self,logger:Logger,name:str):
        self._logger = logger
        self._name = name
    def extract_item_name(self, original_query: str, formatted_history_str: str) -> Dict[str, Any]:
        # 定义大模型调用后返回的结构
        llm_result = {
            "item_names": [],
            "rewritten_query": original_query
        }

        #1. 创建LLM对象
        try:
            llm_client = AIClients.get_llm_client(response_format=True)
        except Exception as e:
            self._logger.error(f"创建大模型对象失败,{e}")
            return llm_result
        #2. 组装prompt消息
        system_message = SystemMessage(content=ITEM_NAME_SYSTEM_EXTRACT_TEMPLATE)

        user_prompt = ITEM_NAME_USER_EXTRACT_TEMPLATE.format(
                history_text=formatted_history_str,
                query=original_query
        )
        human_message = HumanMessage(content=user_prompt)
        #3. 调用大模型拿到结果
        try:
            llm_result = llm_client.invoke([system_message,human_message])
        except Exception as e:
            self._logger.error(f"调用大模型对象失败,{e}")
            return llm_result
        #4. 清洗结果
        llm_content = llm_result.content


        if not llm_content:
            return llm_result


        #5. 返回清洗后的结果
        return self._clean_and_parse(llm_content)

    def _clean_and_parse(self, llm_content: str) -> Dict[str, Any]:
        # 1. 去掉代码块
        # 1.1 去掉前面的 ```
        content = re.sub(r"^```(?:json)?\s*", "", llm_content)
        # 1.2 去掉后面的```
        content = re.sub(r"\s*```$", "", content)

        # 2. 将llm_content进行反序列化
        llm_content_obj: Dict[str, Any] = json.loads(content)
        # 2.1 获取item_names
        original_item_names = llm_content_obj.get("item_names")
        # 2.2 判断original_item_names的类型
        if not isinstance(original_item_names, list):
            item_names = []
        else:
            # 将original_item_names中的每一个字符串去空格之后，收集到item_names中
            item_names = [item_name.strip() for item_name in original_item_names if
                          isinstance(item_name, str) and item_name.strip()]

        # 2.3 获取rewritten_query
        original_rewritten_query = llm_content_obj.get("rewritten_query")
        # 2.4 判断original_rewritten_query的类型
        if not isinstance(original_rewritten_query, str):
            rewritten_query = ""
        else:
            rewritten_query = original_rewritten_query.strip()

        # 3. 返回Dict
        return {"item_names": item_names, "rewritten_query": rewritten_query}

class ItemNameConfirmedNode(BaseNode):
    name = "item_name_confirmed_node"
    def __init__(self):
        super().__init__()
        self._extractor = _ItemNameExtractor(self.logger,self.name)
        self._item_name_aligner = _ItemNameAligner(self.logger,self.config)

    def process(self, state: QueryGraphState) -> QueryGraphState:
        """
            主要职责：
            1. 利用LLM从用户原始查询中提取商品名以及改写原始问查询（我喜欢你）
            1.1 如果LLM提取到了商品名，才进行第2步 去milvus对齐
            1.2 如果LLM没有提取到商品名，直接返回
            2. 根据Milvus中存储的商品名进行对齐（目的：检索更加的准确：三路检索都会利用该节点提取到的商品名，因此直接用LLM提取到商品名的话 下游三路检索在过滤的时候，过滤条件极其不准确。导致检索到的噪音很多 LLM最终输出的幻觉很高）
            最终不是要LLM的商品名 而是要Milvus中存储的商品名：因为milvus中没一个chunK都会关联milvus自己的商品名
            3. 决策（该走下去，还是回头）

            利用两个容器，产生三个分支：第一个分支去检索  第二个分支：给用户确认  第三个分支：抱歉
            1. confirmed:如果是精确的商品名--->给confirmed添加精确的商品名
            2. options:商品名不是精确，可是找到多个相似的---->给options中添加找到的多个不精确的商品名。

            state['answer']不要给，进行三路检索
            获取到三路检索结果
            把三路检索到的结果(RRF  RERANKER)给LLM
            LLM生成答案,在state['answer']
            state['answer']:就返回：
            1. 返回候选商品名【不精确】，给用户下一步确认使用
            2. 没有任何商品名，返回抱歉，没有找到您询问的关于任何商品的名字
            Args:
                state:
            Returns:
        """
        # 1. 获取用户原始问题
        original_query = state["original_query"]
        #2. 获取历史对话(mongodb)
        # 获取session_id
        session_id = state.get("session_id","")
        # 获取历史会话结果
        history_messages = get_recent_messages(
            session_id=session_id
        )

        #将历史会话信息存入state
        state["history"] = history_messages

        formatted_history_str = ""
        for msg in history_messages:
            role = msg.get("role")
            content = msg.get("text", "")
            formatted_history_str += f"{role}: {content}\n"

        # 3. 获取LLM结果
        llm_result: Dict[str, Any] = self._extractor.extract_item_name(original_query, formatted_history_str)
        self.logger.info(f"大模型提取商品名的结果:{llm_result}")
        # 4. 根据item_names做判断,进行商品名的对齐
        extracted_item_names = llm_result.get("item_names")
        confirmed,options = self._item_name_aligner.search_and_align(extracted_item_names)
        # 5. 决策
        rewritten_query = llm_result.get("rewritten_query")
        self._dicide(confirmed,options,state,rewritten_query)
        return state

    def _dicide(self, confirmed: List[str], options: List[str], state: QueryGraphState, rewritten_query: str):
        #1. 判断confirmed中是否有数据
        if confirmed:
            state["item_names"] = confirmed
            state["rewritten_query"] = rewritten_query
        elif options:
            state["answer"] =(
                f"我不能确认你指的是哪款产品,您是在询问以下产品:{'、'.join(options)}吗"
            )
        else:
            state["answer"] ="抱歉，我无法识别您询问的具体产品名称，请提供更准确的产品名称或型号。"

if __name__ == '__main__':
    node = ItemNameConfirmedNode()
    state = {
        "original_query": "你好呀",
        "session_id": "2",
    }
    result_state = node.process(state)
    print(result_state)