# 智库引擎 (knowledge-engine)

基于 RAG 的企业级知识检索与问答系统，面向产品手册、维修指南等垂直文档。文档经解析、切分、向量化后写入 Milvus；提问时做多路召回、融合和重排序，再由大模型生成答案。

## 界面预览

**智库引擎知识库**（问答）

![智库引擎知识库](docs/images/ui-chat.png)

**文献入库**（上传）

![文献入库](docs/images/ui-import.png)

## 环境

| 项目     | 要求                                                         |
| -------- | ------------------------------------------------------------ |
| Python   | 3.12 及以上（当前虚拟环境为 3.13）                           |
| 内存     | 建议 16GB 及以上                                             |
| 显存     | 本地跑 BGE-M3 与 Reranker 时建议 8GB 及以上                  |
| 外部服务 | Milvus、MongoDB、MinIO。可用根目录 `docker-compose.yml` 一键启动 |

## 安装与启动

在仓库根目录执行。导入路径是 `api`、`core`、`processor`，工作目录必须是仓库根目录。

### 1. 启动依赖服务

```powershell
docker compose up -d
```

会拉起 etcd、MinIO、Milvus、Attu（http://localhost:7000）、MongoDB。  
MongoDB 默认账号：`admin` / `123456`，对应连接串示例：`mongodb://admin:123456@127.0.0.1:27017`。  
MinIO 默认：`minioadmin` / `minioadmin`（API `9000`，控制台 `9001`）。

### 2. 安装并启动应用

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# 编辑 .env，填入密钥、模型目录和服务地址
```

```powershell
# 导入服务，端口 8000
python -m api.import_api

# 查询服务，端口 8001
python -m api.query_api
```

`app` 创建在各文件的 `if __name__ == "__main__"` 中，因此用上面的模块方式启动。

- 导入页：http://localhost:8000/front/import.html
- 问答页：http://localhost:8001/front/chat.html

## 核心能力

| 模块 | 说明 |
| --- | --- |
| 文档导入 | 上传 PDF 或 Markdown，解析、切分、向量化后入库 |
| 混合检索 | BGE-M3 稠密向量 + 稀疏向量，在 Milvus 中混合检索 |
| 多路召回 | 向量检索、HyDE、Web 搜索并行，再用 RRF 融合 |
| 重排序 | BGE-Reranker 打分，按得分断崖截断 |
| 流式问答 | 先提交任务，再通过 SSE 推送答案 |
| 会话历史 | MongoDB 保存对话，支持连续提问 |

## 架构

```
front/import.html、front/chat.html
        │  HTTP / SSE
        ▼
api/import_api.py :8000          api/query_api.py :8001
        │                              │
        ▼                              ▼
service/file_process_service.py   service/query_service.py
        │                              │
        ▼                              ▼
processor/import_processor        processor/query_processor
（LangGraph）                     （LangGraph）
        │                              │
        ▼                              ▼
Milvus / MongoDB / MinIO / 大模型 / MinerU
```

| 类别 | 选型 |
| --- | --- |
| HTTP | FastAPI + Uvicorn |
| 流程编排 | LangGraph |
| 大模型 | 兼容 OpenAI 接口的服务（默认按通义千问配置） |
| 向量 | BGE-M3（稠密 1024 维 + 稀疏） |
| 重排序 | BGE-Reranker-Large，本地加载 |
| 向量库 | Milvus |
| 会话 | MongoDB |
| 文件 | MinIO |
| PDF | MinerU HTTP API |
| 前端 | `front/` 下的原生 HTML |

## 目录

```
api/                          # FastAPI
  import_api.py               # 导入，8000
  query_api.py                # 查询，8001
core/
  deps.py                     # Service 单例
  paths.py                    # 根目录、temp_data、front
processor/
  import_processor/           # 导入图
    main_graph.py
    state.py
    nodes/
  query_processor/            # 查询图
    main_graph.py
    state.py
    nodes/
prompts/
schema/
service/
  file_process_service.py
  query_service.py
utils/
  clients/                    # 模型与存储客户端
front/
  import.html
  chat.html
test/
temp_data/                    # 运行时上传目录，不提交
.env.example
docker-compose.yml            # Milvus / MinIO / MongoDB / Attu
requirements.txt
```

## 导入流程

`entry_node` 按后缀分流，之后是一条直线：

```
entry_node
  ├─ .pdf → pdf_to_md_node → md_image_node
  └─ .md  → md_image_node
        → document_split_node
        → item_name_recognition_node
        → bge_embedding_chunks_node
        → milvus_import_node
```

| 节点 | 作用 |
| --- | --- |
| entry_node | 校验路径，区分 PDF 与 Markdown |
| pdf_to_md_node | 调用 MinerU，得到 Markdown |
| md_image_node | 图片摘要，并上传 MinIO |
| document_split_node | 按标题切分，过长再切、过短合并 |
| item_name_recognition_node | 识别商品名，写入商品名集合 |
| bge_embedding_chunks_node | 生成稠密与稀疏向量 |
| milvus_import_node | 写入切片集合 |

上传文件会先保存到 `temp_data/日期/`，并尝试备份到 MinIO。备份失败不会中断导入。

## 查询流程

商品名确认之后，三条检索并行，汇合后再融合、重排、生成答案。`multi_search` 和 `join` 只负责分叉与汇合。

```
item_name_confirmed_node
  ├─ 已有 answer → answer_output_node
  └─ 继续检索
        → vector_search_node
        → hyde_search_node
        → web_search_node
        → rrf_merge_node
        → rerank_node
        → answer_output_node
```

商品名对得上标准名时继续检索；只找到相近候选时直接把候选返回给用户；找不到时直接说明未命中。这两种情况下 `state["answer"]` 已有内容，不会进入三路检索。

## API

导入服务（8000）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/upload` | 上传一个文件，返回 `task_id` |
| GET | `/status/{task_id}` | 任务状态、已完成节点、耗时 |

查询服务（8001）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/query` | `is_stream=false` 时直接返回答案；为 `true` 时返回 `task_id` |
| GET | `/stream/{task_id}` | SSE。连接的是任务 ID，不是会话 ID |
| GET | `/history/{session_id}` | 会话历史 |
| DELETE | `/history/{session_id}` | 清空该会话历史 |

## 配置

复制 `.env.example` 为 `.env`。下面只列出代码会读取的变量。

必填：

| 变量 | 用途 |
| --- | --- |
| `OPEN_API_KEY` | 大模型、视觉模型，以及 Web 搜索请求头 |
| `OPEN_API_BASE` | 大模型接口地址 |
| `LLM_DEFAULT_MODEL` | 默认对话模型 |
| `VL_MODEL` | 图片摘要模型 |
| `MINERU_API_TOKEN` / `MINERU_BASE_URL` | PDF 转 Markdown |
| `BGE_M3_PATH` | 本地 BGE-M3 目录 |
| `BGE_DEVICE` / `BGE_FP16` | 嵌入和重排序的设备与半精度 |
| `BGE_RERANKER_LARGE` | 本地重排序模型目录 |
| `MILVUS_URL` | Milvus 地址 |
| `CHUNKS_COLLECTION` / `ITEM_NAME_COLLECTION` | 切片集合、商品名集合 |
| `MONGO_URL` / `MONGO_DB_NAME` | 对话历史 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` / `MINIO_BUCKET_NAME` | 对象存储 |
| `MCP_DASHSCOPE_BASE_URL` | Web 搜索 MCP 地址 |

`EMBEDDING_DIM` 默认 `1024`，与 BGE-M3 一致。重排序没有单独的设备变量，使用 `BGE_DEVICE` 和 `BGE_FP16`。

查询侧还有可选覆盖项，不写则用代码里的默认值：`MAX_CONTEXT_CHARS`、`RERANK_MAX_TOP_K`、`RERANK_MIN_TOP_K`、`RERANK_GAP_RATIO`、`RERANK_GAP_ABS`、`RRF_K`、`RRF_MAX_RESULTS`、`EMBEDDING_SEARCH_LIMIT`、`HYDE_SEARCH_LIMIT`，以及 `ITEM_NAME_HIGH_CONFIDENCE` 等商品名对齐阈值。定义见 `processor/query_processor/config.py`。

切片长度等导入参数定义在 `processor/import_processor/config.py`（例如单段最大 2000、最小 500）。
