import json
from typing import Dict, Any, List

from pymilvus import MilvusClient, DataType

from processor.import_processor.base import BaseNode, T
from processor.import_processor.exceptions import StateFieldError, EmbeddingError, MilvusError
from processor.import_processor.state import ImportGraphState
from utils.clients.storage_clients import StorageClients

class _IndexParamsBuilder:
    @classmethod
    def build_index_params(cls,milvus_client:MilvusClient):
        #1. 创建index_params
        index_params = milvus_client.prepare_index_params()
        #2. 添加索引
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
        return index_params

class _MilvusSchemaBuilder:
    @classmethod
    def build_schema(cls,milvus_client:MilvusClient,dim:int):
        #1. 创建Schema
        schema = milvus_client.create_schema()
        #2. 添加字段
        #主键
        schema.add_field(
            field_name="id",
            datatype=DataType.INT64,
            auto_id=True,
            is_primary=True
        )
        #标量
        schema.add_field(
            field_name="item_name",
            datatype=DataType.VARCHAR,
            max_length=65535
        )
        schema.add_field(
            field_name="title",
            datatype=DataType.VARCHAR,
            max_length=65535
        )
        schema.add_field(
            field_name="parent_title",
            datatype=DataType.VARCHAR,
            max_length=65535
        )
        schema.add_field(
            field_name="file_title",
            datatype=DataType.VARCHAR,
            max_length=65535
        )
        schema.add_field(
            field_name="content",
            datatype=DataType.VARCHAR,
            max_length=65535
        )
        #向量
        schema.add_field(
            field_name="dense_vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=dim
        )
        schema.add_field(
            field_name="sparse_vector",
            datatype=DataType.SPARSE_FLOAT_VECTOR
        )
        return schema

class MilvusImportNode(BaseNode):
    name = "milvus_import_node"
    def process(self, state: ImportGraphState) -> ImportGraphState:
        #1. 参数校验
        final_chunks,dim = self._validate_state(state)

        #2. 向量入库
        self.insert_data(final_chunks,dim)

        state["chunks"] = final_chunks
        return state

    def _validate_state(self, state:ImportGraphState):
        #1. 获取chunks
        chunks = state.get("chunks")
        #2. 校验chunks是否为空、类型是否是list
        if not chunks or not isinstance(chunks, list):
            self.logger.error("chunks 为空，或者类型不是list")
            raise StateFieldError(node_name=self.name,field_name="chunks",expected_type=list)
        #3. 遍历每一个chunk，校验chunk是否是dict，chunk是否有向量，如果没有向量则将这个chunk丢弃
        final_chunks = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            # 获取稠密向量和稀疏向量
            dense_vector = chunk.get("dense_vector")
            sparse_vector = chunk.get("sparse_vector")
            if not dense_vector or not sparse_vector:
                continue

            # 5. 获取dim,后续创建Collection的时候需要指定dim
            # dim就是稠密向量的维度，其实就是数组的长度
            dim = len(dense_vector)
            final_chunks.append(chunk)

        #4. 判断final_chunks是否为空
        if not final_chunks:
            self.logger.error("所有chunk都没有向量,导入失败")
            raise EmbeddingError("所有chunk都没有向量,导入失败")



        return final_chunks,dim

    def insert_data(self, final_chunks:List[Dict[str,Any]], dim):
        #1. 创建MilvusClient
        try:
            milvus_client = StorageClients.get_milvus_client()
        except ConnectionError as e:
            self.logger.error(f"获取milvus客户端失败,{e}")
            raise MilvusError(f"获取milvus客户端失败,{e}")
        #2. 从配置中获取存储chunk的Collection的name
        collection_name = self.config.chunks_collection
        #3. 判断Collection是否存在,如果不存在则创建Collection
        if not milvus_client.has_collection(collection_name):
            #3.1 创建Schema
            schema = _MilvusSchemaBuilder.build_schema(milvus_client,dim)
            #3.2 创建IndexParams
            index_params = _IndexParamsBuilder.build_index_params(milvus_client)
            #3.3 创建Collection
            milvus_client.create_collection(
                collection_name=collection_name,
                schema=schema,
                index_params=index_params,
                timeout=30
            )
        #4. 插入数据,获取自增长的id
        insert_results = milvus_client.insert(
            collection_name=collection_name,
            data=final_chunks
        )
        ids = insert_results.get("ids")
        #5. 将自增长的id回填到final_chunks中
        for i,chunk in enumerate(final_chunks):
            chunk["chunk_id"] = ids[i]


if __name__ == '__main__':
    # 读chunks_vector.json获取chunks
    json_path = r"D:\workspace\pycharm\shopkeeper-brain-BJ0108\knowledge\processor\import_processor\output_dir\万用表RS-12的使用\chunks_vector.json"

    with open(json_path,"r",encoding="utf-8") as f:
        chunks = json.load(f)

    state = {
        "chunks": chunks
    }

    node = MilvusImportNode()
    node.process(state)
