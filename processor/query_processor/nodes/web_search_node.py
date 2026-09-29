import asyncio
import json

from agents.mcp import MCPServerStreamableHttp

from processor.query_processor.base import BaseNode, T
from processor.query_processor.exceptions import StateFieldError
from processor.query_processor.state import QueryGraphState


class WebSearchNode(BaseNode):
    name = "web_search_node"
    def process(self, state: QueryGraphState) -> QueryGraphState:
        #1. 参数校验
        rewritten_query, item_names = self._validate_state(state)
        #2. 网页搜索失败时返回空结果，避免中断向量检索和 HyDE
        try:
            execute_tool_result = asyncio.run(self.mcp_web_search(rewritten_query))
            web_search_docs = self._parse_pages(execute_tool_result)
        except Exception as e:
            self.logger.warning(f"网页搜索不可用，跳过该路召回: {e}")
            web_search_docs = []

        return {"web_search_docs":web_search_docs}

    def _parse_pages(self, execute_tool_result):
        # 获取查询结果中的 text，这其实就是一个 json 字符串
        result_text = execute_tool_result.content[0].text
        json_object = json.loads(result_text)
        pages = json_object.get("pages") or []

        web_search_docs = []
        for page in pages:
            if not isinstance(page, dict):
                continue
            web_search_docs.append({
                "snippet": page.get("snippet") or "",
                "title": page.get("title") or "",
                "url": page.get("url") or ""
            })
        return web_search_docs

    async def mcp_web_search(self,rewritten_query:str):
        # 1. 创建MCP客户端
        async with MCPServerStreamableHttp(
                name="search_mcp",
                params={
                    "url": self.config.mcp_dashscope_base_url,  # MCP 服务端点
                    "headers": {"Authorization": self.config.openai_api_key},  # 认证头
                    "timeout": 300,  # 请求超时时间（秒）
                    "terminate_on_close": True,  # 关闭时终止连接
                },
                max_retry_attempts=2,  # 最大重试次数
                cache_tools_list=True,  # 缓存工具列表，避免重复请求
        ) as client:
            #2. 调用mcp中的网络搜索的工具
            execute_tool_result = await client.call_tool(
                tool_name="bailian_web_search",
                arguments={"query": rewritten_query, "count": 3}
            )

            return execute_tool_result

    def _validate_state(self, state: QueryGraphState):
        # 1. 获取rewritten_query,item_names
        rewritten_query = state.get("rewritten_query")
        item_names = state.get("item_names")
        # 2. 校验rewritten_query,item_names
        if not rewritten_query or not isinstance(rewritten_query, str):
            self.logger.error(f"rewritten_query不能为空以及类型必须是str")
            raise StateFieldError(node_name=self.name, field_name="rewritten_query", expected_type=str)

        if not item_names or not isinstance(item_names, list):
            self.logger.error("item_names不能为空以及类型必须是list")
            raise StateFieldError(node_name=self.name, field_name="item_names", expected_type=list)

        return rewritten_query, item_names

if __name__ == '__main__':
    # 1. 创建state
    state = {
        "rewritten_query": "RS PRO RS-12 数字万用表的使用方法是什么?",
        "item_names": ["RS PRO RS-12 数字万用表"]
    }
    node = WebSearchNode()
    final_state = node.process(state)
    print(final_state)