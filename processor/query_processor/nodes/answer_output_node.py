from typing import Dict, Any, List, Tuple
import os

from langchain_openai import ChatOpenAI
from typer.cli import state

from processor.query_processor.base import BaseNode, T
from processor.query_processor.state import QueryGraphState
from prompts.query_prompt import ANSWER_PROMPT
from utils.clients.ai_clients import AIClients
from utils.mongo_history_util import save_chat_message, get_recent_messages
from utils.sse_util import push_sse_event, SSEEvent
from utils.task_util import set_task_result


class AnswerOutputNode(BaseNode):
    name = "answer_output_node"
    def process(self, state: QueryGraphState) -> QueryGraphState:
        #1. 获取用户的问题(重写后的问题)
        user_query = state.get("rewritten_query")
        #获取task_id
        task_id = state.get("task_id")
        #2. 获取answer
        answer = state.get("answer")
        #3. 获取是否要进行流式输出
        is_stream = state.get("is_stream")
        #4. 判断是否有answer
        if answer:
            #4.1 表示在答案输出节点执行之前，就已经生成了答案，那么就应该将已有答案进行输出
            self._push_exist_answer(answer,is_stream,task_id)
        else:
            #4.1 表示在答案输出节点执行之前，没有生成答案，那么就需要在答案输出节点中调用大模型来生成答案
            #4.1.1 组装提示词
            prompt = self._build_answer_prompt(state,self.config.max_context_chars)
            #4.1.2 调用大模型生成答案
            llm_answer = self._generate_answer(prompt,state)
            state["answer"] = llm_answer
            # FINAL 统一在 _persist_result_fields 推送

        #5. 将答案相关字段写入 Redis result（历史由 Java 落库，STEP08）
        self._persist_result_fields(state)
        #6. 不再写 Mongo；保留调用点以便 KB_HISTORY_OWNER=mongo 回滚
        if os.getenv("KB_HISTORY_OWNER", "java").strip().lower() == "mongo":
            self._save_history(state)

        return state

    def _persist_result_fields(self, state: QueryGraphState) -> None:
        task_id = state.get("task_id")
        if not task_id:
            return
        answer = state.get("answer") or ""
        set_task_result(task_id=task_id, key="answer", value=answer)
        set_task_result(task_id=task_id, key="rewritten_query", value=state.get("rewritten_query") or "")
        import json
        set_task_result(
            task_id=task_id,
            key="item_names",
            value=json.dumps(state.get("item_names") or [], ensure_ascii=False),
        )
        # 流式最终包带上完整字段，供 Java SSE / 落库
        if state.get("is_stream"):
            push_sse_event(
                task_id=task_id,
                event=SSEEvent.FINAL,
                data={
                    "answer": answer,
                    "rewritten_query": state.get("rewritten_query") or "",
                    "item_names": state.get("item_names") or [],
                    "status": "completed",
                },
            )

    #输出已有答案
    def _push_exist_answer(self, answer:str, is_stream:bool,task_id:str):
        #1. 判断到底是流式输出还是非流式输出
        if is_stream:
            # FINAL 统一在 _persist_result_fields 推送（含完整字段）
            return
        #1.2 非流式输出
        set_task_result(task_id=task_id,key="answer",value=answer)


    #构建答案生成的上下文prompt
    def _build_answer_prompt(self, state:QueryGraphState, max_context_chars:int) -> str:
        #1. 获取用户的问题
        user_query = state.get("rewritten_query")
        #2. 获取商品名列表
        item_names = state.get("item_names") or []
        #3. 获取rerank重排序之后文档列表
        reranked_docs = state.get("reranked_docs") or []
        #3.1 对reranked_docs进行格式规整化,并且进行截断(保证最终的提示词长度不超过模型的限制)
        formatted_context, usage_chars = self._format_retrieval_context(reranked_docs,max_context_chars)
        #4. 获取历史对话列表
        history = state.get("history") or []
        #4.1 对历史对话进行格式规整化,并且进行截断(保证最终的提示词长度不超过模型的限制)
        formatted_history = self._format_history(history,max_context_chars - usage_chars)

        return ANSWER_PROMPT.format(
            question = user_query,
            context = formatted_context,
            history = formatted_history,
            item_names = ",".join(item_names)
        )

    #对历史对话的内容进行格式规整化
    def _format_history(self, history: List[Dict[str, Any]], char_budget: int) -> Tuple[str, int]:
        """
        格式化历史对话
        Args:
            history: 历史对话
            char_budget:

        Returns:

        """

        formatted_lines = []
        used_chars = 0
        # 1. 遍历格式化后的文档
        role_map = {"user": "用户", "assistant": "助手"}
        for msg in history:
            # 1.1 获取消息角色
            role = msg.get('role', '')

            # 1.2 获取消息内容
            text = msg.get('text', '')

            # 1.3 获取格式化后的行
            if not text or role not in role_map:
                continue

            formatted_line = f"{role_map[role]}: {text}"

            # 1.4 计算分割符长度
            seperator_usage = 1 if formatted_lines else 0

            # 1.5 计算总长度
            total_usage = seperator_usage + len(formatted_line)

            if used_chars + total_usage > char_budget:
                break

            formatted_lines.append(formatted_line)
            used_chars += total_usage

        return "\n".join(formatted_lines), char_budget - used_chars

    #对检索到的内容进行格式规整化
    def _format_retrieval_context(self, reranked_docs:List[Dict[str,Any]], max_context_chars:int) -> Tuple[str, int]:
        """
        最终规整化后的结果的例子:
        [1] [source=local] [chunk_id=chunk_001] [title=操作指导] [score=5.0600]
        测量直流电压时，将旋钮转到DCV档位，红表笔接VΩmA孔，黑表笔接COM孔。

        [2] [source=web] [url=https://example.com] [title=电压测量指南] [score=3.9600]
        注意：测量前请确认档位与量程，避免误接导致损坏或触电。
        :param reranked_docs:
        :param max_context_chars:
        :return:
        """
        #定义存放最终段落的容器
        final_context = []
        #定义已使用的长度
        usage_chars = 0

        #1. 遍历reranked_docs
        for index,reranked_doc in enumerate(reranked_docs,1):
                #1.1 获取文档的来源、标题、内容等信息
                metadata_content = [f"[{index}]"]
                for field_name,template in [("chunk_id","[chunk_id={}]"),
                                            ("title","[title={}]"),
                                            ("source","[source={}]"),
                                            ("url","[url={}]")]:
                    #1.1.1 获取字段值
                    field_value = reranked_doc.get(field_name)
                    #1.1.2 判断字段值是否有
                    if field_value:
                        metadata_content.append(template.format(field_value))

                #拼接当前文档的分数,保留6位小数
                score = float(reranked_doc.get("score"))
                metadata_content.append(f"[score={score:.6f}]")
                # 拼接当前文档的内容
                content = reranked_doc.get("content")
                # 每段的内容
                format_chunk = " ".join(metadata_content) + "\n" + content

                # 段与段之间的拼接符的长度:2
                spec_len = 2 if final_context else 0

                # 判断已使用长度 + 当前段落拼接需要的分隔符长度 + 当前段落的长度  是否大于最大长度
                chunk_length = spec_len + len(format_chunk)
                if usage_chars + chunk_length > max_context_chars:
                    break

                # 将当前段落拼接到final_context
                final_context.append(format_chunk)
                # 更新已使用长度
                usage_chars += chunk_length

        #1.3 将规整化后的结果进行拼接,并且保证最终的提示词长度不超过模型的限制
        return "\n\n".join(final_context),usage_chars

    #调用大模型根据提示词生成答案
    def _generate_answer(self, prompt:str, state:QueryGraphState):
        #1. 创建大模型对象
        try:
            llm_client = AIClients.get_llm_client(response_format=False)
        except Exception as e:
            return "LLM暂无任何内容输出"

        llm_result = ""
        #2. 判断是流式输出还是非流式输出
        if state.get("is_stream"):
             #2.1 如果是流式输出,则需要边生成边推送SSE事件
             llm_result = self._llm_stream(prompt,llm_client,state)
        else:
            #2.2 如果是非流式输出,则直接调用大模型的生成接口,获取完整答案后进行输出
            llm_result = self._llm_invoke(prompt,llm_client)
            #2.3 将生成的答案添加到任务队列中
            set_task_result(task_id=state.get("task_id"),key="answer",value=llm_result)
        return llm_result

    #大模型非流式执行
    def _llm_invoke(self, prompt:str, llm_client:ChatOpenAI):
        #1. 调用大模型
        try:
            llm_res = llm_client.invoke(prompt)
        except Exception as e:
            return "LLM暂无任何内容输出"
        #2. 获取大模型输出的内容
        llm_content = llm_res.content
        if not llm_content:
            return "LLM暂无任何内容输出"
        return llm_content

    #d大模型流式执行
    def _llm_stream(self, prompt:str, llm_client:ChatOpenAI,state:QueryGraphState):
        final_answer = ""
        #1. 流式调用大模型
        for chunk in llm_client.stream(prompt):
            #1.1 每得到一个内容块，就将其推送到SSE队列中
            content = getattr(chunk,"content","")
            if content:
                push_sse_event(task_id=state.get("task_id"),event=SSEEvent.DELTA,data={"delta":content})

            #1.2 将每个chunk的内容拼接到最终的答案返回出来
            final_answer += content
        return final_answer

    def _save_history(self, state:QueryGraphState):
        #1. 保存用户的对话内容
        save_chat_message(
            session_id=state.get("session_id"),
            role="user",
            text=state.get("original_query",""),
            rewritten_query=state.get("rewritten_query") or "",
            item_names=state.get("item_names") or []
        )

        #2. 保存AI的对话内容
        save_chat_message(
            session_id=state.get("session_id"),
            role="assistant",
            text=state.get("answer") or "",
            rewritten_query=state.get("rewritten_query") or "",
            item_names=state.get("item_names",[])
        )


if __name__ == '__main__':
    print("=" * 60)
    print("开始测试: 答案输出节点 (AnswerOutputNode)")
    print("=" * 60)

    mock_state = QueryGraphState()
    mock_state["rewritten_query"] = "怎么测量主板是否通电？"
    mock_state["original_query"] = "怎么测量主板是否通电？"
    mock_state["session_id"] = "2"
    mock_state["item_names"] = ["主板"]
    mock_state["reranked_docs"] = [
        {"chunk_id": "local_1", "title": "主板维修手册","source":"local",
         "content": "主板通电后通常表现为通电后风扇转一下不停，可以使用万用表的蜂鸣档测量。",
         "score": 5.06},
        {"chunk_id": "local_2", "title": "闲聊","url":"https://example.com","source":"web",
         "content": "今天中午去吃鸡腿饭饭吧，这块主板外观很漂亮。",
         "score": 3.96},
    ]
    mock_state["task_id"] = "1"
    mock_state["is_stream"] = True

    histories = get_recent_messages("2")
    mock_state["history"] = histories

    node = AnswerOutputNode()
    final_state = node(mock_state)
    print(final_state)