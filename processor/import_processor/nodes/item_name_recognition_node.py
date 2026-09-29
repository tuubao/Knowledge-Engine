import json
from pathlib import Path
from typing import Tuple, Any, Dict, List

from dns.message import IndexType
from langchain_core.messages import SystemMessage, HumanMessage
from pymilvus import DataType

from processor.import_processor.base import BaseNode
from processor.import_processor.exceptions import StateFieldError, ConfigurationError
from processor.import_processor.state import ImportGraphState
from prompts.import_prompt import ITEM_NAME_SYSTEM_PROMPT, ITEM_NAME_USER_PROMPT_TEMPLATE
from utils.clients.ai_clients import AIClients
from utils.clients.storage_clients import StorageClients
from utils.embedding_util import generate_bge_m3_hybrid_vectors


class ItemNameRecognitionNode(BaseNode):
    name = "item_name_recognition_node"
    def process(self, state: ImportGraphState) -> ImportGraphState:
        #1. 参数的校验
        file_title, chunks, item_name_chunk_k, item_name_chunk_size = self._validate_state(state)
        #2. 调用LLM 提取文档的商品名
        #2.1 准备输入给LLM的上下文
        context = self._prepare_item_name_recognition_context(chunks,item_name_chunk_k,item_name_chunk_size)
        #2.2 调用LLM识别商品名
        item_name = self._recognition_item_name(context,file_title)

        #3. 将商品名进行向量化
        hybrid_vectors = self._embedding_item_name(item_name)

        #4. 存入向量数据库。嵌入失败时跳过写入，避免把 None 当成向量结果
        if hybrid_vectors:
            self._insert_to_milvus(item_name,hybrid_vectors)
        else:
            self.logger.warning("商品名向量为空，跳过写入 Milvus，后续切片仍会带上商品名")

        #5. 为了下游节点方便拿到商品名,我们可以将商品名回写到chunks里面
        for chunk in chunks:
            if not isinstance(chunk,dict):
                continue
            chunk["item_name"] = item_name

        state["item_name"] = item_name
        state["chunks"] = chunks

        #6. 为了方便后续测试，再次备份chunks
        self._backup_chunks(chunks,state)

        return state


    def _validate_state(self, state:ImportGraphState) -> Tuple[str,list,int,int]:
        """
        参数校验
        :param state:
        :return:
        """
        #1. 获取file_title，作为兜底使用，当没有提取到商品名的时候，使用file_title作为商品名
        file_title = state.get("file_title")
        #2. 校验file_title是否为空,如果为空,则表示前面出现了问题,应该抛出异常
        if not file_title:
            raise StateFieldError(node_name=self.name,field_name="file_title",expected_type=str)
        #3. 获取chunks,也就是上一步拆分之后的结果,这个内容可以提供作为LLM的上下文信息,让LLM进行商品名的提取
        chunks = state.get("chunks")
        #4. 判断chunks是否为空，且其类型是否是list，如果不满足则抛出异常
        if not chunks or not isinstance(chunks,list):
            raise StateFieldError(node_name=self.name,field_name="chunks",expected_type=list)
        #5. 从config中获取item_name_chunk_k和item_name_chunk_size，分别表示商品名提取能使用的最大chunk数量，以及最大的长度
        item_name_chunk_k = self.config.item_name_chunk_k
        item_name_chunk_size = self.config.item_name_chunk_size

        #6. 判断item_name_chunk_k和item_name_chunk_size是否为空，并且是否大于0，如果不满足则抛出异常
        if not item_name_chunk_size or item_name_chunk_size <= 0:
            raise ConfigurationError(node_name=self.name,message="item_name_chunk_size must be greater than 0")

        if not item_name_chunk_k or item_name_chunk_k <= 0:
            raise ConfigurationError(node_name=self.name,message="item_name_chunk_k must be greater than 0")
        #7. 返回file_title、chunks、item_name_chunk_k、item_name_chunk_size
        return file_title, chunks, item_name_chunk_k, item_name_chunk_size

    def _prepare_item_name_recognition_context(self, chunks:List[Dict[str,Any]], item_name_chunk_k:int, item_name_chunk_size:int) -> str:
        """
        目标: 将每一个切片(chunk)的content拼接成字符串,但是有item_name_chunk_k、item_name_chunk_size的限制
        :param chunks:
        :param item_name_chunk_k:
        :param item_name_chunk_size:
        :return:
        """
        #1. 遍历chunks
        #定义容器存储每个chunk的内容
        final_context = []
        #定义一个统计最终上下文长度的变量
        total_length = 0
        for index,chunk in enumerate(chunks[:item_name_chunk_k]):
            #1.1 判断chunk的类型是不是dict，如果不是则跳过这个chunk
            if not isinstance(chunk,dict):
                continue
            #1.2 如果是dict类型，则获取器content
            content = chunk.get("content")
            context = f"【切片】-{index+1}-{content}"
            final_context.append(context)
            total_length += len(context)
            #1.3 判断final_context中内容的长度，是否超过了item_name_chunk_size,如果超过了后续就不添加了
            if total_length >= item_name_chunk_size:
                break

        return "\n".join(final_context)

    def _recognition_item_name(self, context:str, file_title:str):
        #1. 创建LLM客户端对象
        try:
            llm_client = AIClients.get_llm_client(False)
        except Exception as e:
            self.logger.warning(f"获取llm对象失败,{e}")
            return file_title
        #2. 组装LLM的SystemMessage、HumanMessage
        system_prompt = ITEM_NAME_SYSTEM_PROMPT
        system_message = SystemMessage(content=system_prompt)

        user_prompt = ITEM_NAME_USER_PROMPT_TEMPLATE.format(
            file_title = file_title,
            context = context
        )
        human_message = HumanMessage(content=user_prompt)
        #3. 调用LLM的invoke方法进行商品名的提取
        try:
            llm_res = llm_client.invoke([
                system_message,
                human_message
            ])
        except Exception as e:
            self.logger.warning(f"调用llm失败,失败信息为{e}")
            return file_title
        #4. 解析LLM输出结果，将提取到的商品名解析出来
        item_name = llm_res.content.strip()

        #兜底
        if item_name == "UNKNOWN":
            return file_title

        return item_name

    def _embedding_item_name(self, item_name:str) -> Dict[list,list]:
        #1. 创建embedding_client
        try:
            embedding_client = AIClients.get_bge_m3_client()
        except Exception as e:
            self.logger.warning(f"获取嵌入模型失败,{e}")
            return None
        #2. 调用嵌入模型进行向量嵌入
        try:
            hybrid_vectors = generate_bge_m3_hybrid_vectors(embedding_client,[item_name])
        except Exception as e:
            self.logger.warning(f"商品名向量化失败,{e}")
            return None
        return hybrid_vectors

    def _insert_to_milvus(self, item_name:str, hybrid_vectors:dict):
        if not hybrid_vectors:
            self.logger.warning("商品名向量为空，跳过写入 Milvus")
            return
        #1. 创建Milvus客户端
        try:
            milvus_client = StorageClients.get_milvus_client()
        except Exception as e:
            self.logger.warning(f"获取Milvus客户端失败,{e}")
            return
        #2. 取出向量，维度跟当前模型一致（bge-base-zh 是 768，不是写死的 1024）
        dense_vector = hybrid_vectors.get("dense")[0]
        sparse_vector = hybrid_vectors.get("sparse")[0]
        if not dense_vector or not sparse_vector:
            self.logger.warning("稠密向量或者稀疏向量为空")
            return
        vector_dim = len(dense_vector)

        #3. 判断存储item_name的Collection是否存在，如果不存在则创建Collection
        collection_name = self.config.item_name_collection
        if not milvus_client.has_collection(collection_name):
            #2.1 创建表
            #2.1.1 创建Schema
            schema = milvus_client.create_schema()
            schema.add_field(
                field_name="pk",
                datatype=DataType.INT64,
                auto_id=True,
                is_primary=True
            )
            schema.add_field(
                field_name="item_name",
                datatype=DataType.VARCHAR,
                max_length=2048,
            )
            schema.add_field(
                field_name="dense_vector",
                datatype=DataType.FLOAT_VECTOR,
                dim=vector_dim
            )
            schema.add_field(
                field_name="sparse_vector",
                datatype=DataType.SPARSE_FLOAT_VECTOR
            )
            #2.1.2 添加索引
            index_params = milvus_client.prepare_index_params()
            index_params.add_index(
                field_name="dense_vector",
                index_name="dense_vector_index",
                index_type="AUTOINDEX",
                metric_type="COSINE"
            )
            index_params.add_index(
                field_name="sparse_vector",
                index_name="sparse_vector_index",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="IP"
            )

            #2.1.3 创建Collection
            milvus_client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params
            )
        #4. 插入数据
        insert_data = {
            "item_name":item_name,
            "dense_vector":dense_vector,
            "sparse_vector":sparse_vector
        }
        #3.2 调用Milvus客户端的方法插入数据
        milvus_client.insert(
            collection_name=collection_name,
            data=insert_data,
            timeout=30
        )

    def _backup_chunks(self, chunks:List[Dict[str,Any]],state:ImportGraphState):
        # 1. 指定备份文件的路径
        # 1.1 获取文件输出的目录
        md_path = state.get("md_path")
        md_path_obj = Path(md_path)
        file_dir = state.get("file_dir")
        file_dir_obj = Path(file_dir)
        backup_dir = file_dir_obj / md_path_obj.stem
        # 1.2 判断该目录是否真实存在，如果不存在则创建目录
        backup_dir.mkdir(parents=True, exist_ok=True)
        # 1.3 指定备份文件的路径
        backup_file_path = backup_dir / "chunks_item_name.json"

        # 2. 将chunks写入到备份文件中
        try:
            with open(backup_file_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.warning(f"{md_path_obj.stem}文件备份成chunks_item_name.json失败,但是不影响主流程")


if __name__ == '__main__':
    node = ItemNameRecognitionNode()

    #从chunks.json中读取chunks
    json_path = r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir\万用表RS-12的使用\chunks.json"

    with open(json_path,"r",encoding="utf-8") as f:
        chunks = json.loads(f.read())

    state = {
        "md_path":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir\万用表RS-12的使用\万用表RS-12的使用.md",
        "file_dir":r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir",
        "file_title":"万用表RS-12的使用",
        "chunks":chunks
    }

    node(state)