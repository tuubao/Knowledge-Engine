# 智库引擎 (knowledge-engine)

基于 RAG 的企业级知识检索与问答系统，面向产品手册、维修指南等垂直文档。文档经解析、切分、向量化后写入 Milvus；用户提问时做多路召回、融合与重排序，再由大模型生成答案，支持流式输出与会话历史。

## 一句话说明

**浏览器只访问 Java `:8080`**。Python `:8000`（导入）与 `:8001`（查询）是内网 AI Worker，负责跑 LangGraph / 向量模型，默认不对外提供页面与公开 API。

| 页面 | 地址 |
|------|------|
| 文献入库 | http://localhost:8080/front/import.html |
| 知识问答 | http://localhost:8080/front/chat.html |
| 健康检查 | http://localhost:8080/actuator/health |

![问答界面](docs/images/ui-chat.png)

![入库界面](docs/images/ui-import.png)

改造设计过程（STEP01–10 已完成）见 [`docs/design/`](docs/design/)。

---

## 架构

### 职责划分

| 角色 | 端口 | 职责 |
|------|------|------|
| Java 网关 | **8080** | 唯一对外入口：上传落盘、任务状态、查询编排、SSE、会话历史、静态前端 |
| Python 导入 Worker | 8000 | 内网：`POST /internal/import/run`，执行导入 LangGraph |
| Python 查询 Worker | 8001 | 内网：`POST /internal/query/run`，执行查询 LangGraph，并向 Redis 推送进度/token |
| Redis | 6379 | 任务进度真相源 + SSE 事件通道（`kb:task:{id}:*`） |
| MySQL | 3306 | 任务元数据、会话历史（`kb_chat_message`） |
| Milvus | 19530 | 切片向量与商品名集合 |
| MinIO | 9000 | 上传文件 / 图片备份（失败不阻断主流程） |

### 调用关系

```
浏览器
  └─ Java :8080
        ├─ 静态页 /front/**
        ├─ POST /upload  → 落盘 temp_data → Redis「上传文件」→ Python /internal/import/run
        ├─ GET  /status  → 读 Redis
        ├─ POST /query   → 建 task → Python /internal/query/run
        ├─ GET  /stream  → 订阅 Redis events → 转浏览器 SSE
        └─ GET/DELETE /history → MySQL
```

### 技术选型

| 类别 | 选型 |
|------|------|
| 对外 HTTP | Spring Boot 3 + MyBatis |
| AI Worker | FastAPI（内网）+ LangGraph |
| 大模型 | OpenAI 兼容接口（默认通义千问 / DashScope） |
| 向量 | BGE-M3（稠密 1024 维 + 稀疏） |
| 重排序 | BGE-Reranker-Large（本地） |
| 向量库 | Milvus |
| 会话 | MySQL（Mongo 仅遗留可选） |
| 文件 | 本地 `temp_data/` + MinIO |
| PDF 解析 | MinerU HTTP API |
| 前端 | `front/` 原生 HTML（由 Java 挂载） |

---

## 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows / Linux / macOS（下文命令以 PowerShell 为例） |
| Python | 3.12+（仓库可用 `.venv`） |
| JDK | 17+ |
| Maven | 3.9+ |
| 内存 | 建议 16GB+ |
| 显存 | 本地跑 BGE-M3 / Reranker 时建议 8GB+；也可改 `BGE_DEVICE=cpu`（更慢） |
| 基础设施 | MySQL、Redis、Milvus、MinIO（Mongo 可选） |

---

## 安装与启动

以下步骤均在**仓库根目录**执行。Python 的 `api` / `processor` 导入路径依赖根目录，请勿在子目录里直接 `python -m api.xxx`（除非已正确设置 `PYTHONPATH`）。

### 1. 启动 Docker 依赖

```powershell
docker compose up -d
```

会拉起：

| 服务 | 说明 |
|------|------|
| etcd | Milvus 元数据 |
| MinIO | 对象存储（API `9000`，控制台 `9001`） |
| Milvus | 向量库 `19530` |
| Attu | Milvus UI，http://localhost:7000 |
| MongoDB | 遗留可选；默认账号 `admin` / `123456` |

MinIO 默认：`minioadmin` / `minioadmin`。

### 2. 准备 MySQL 与 Redis

**MySQL**（须自行安装或另起容器）：

- 库名：`knowledge_engine`
- 默认账号：`kb` / `kb123`（可在 `java-backend/src/main/resources/application-dev.yml` 修改）
- 表结构：Java 启动时自动执行 `classpath:schema.sql`（`spring.sql.init.mode=always`）

示例：

```sql
CREATE DATABASE IF NOT EXISTS knowledge_engine DEFAULT CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'kb'@'%' IDENTIFIED BY 'kb123';
GRANT ALL ON knowledge_engine.* TO 'kb'@'%';
FLUSH PRIVILEGES;
```

**Redis**：监听 `127.0.0.1:6379`。  
若本机没有 Redis，开发 profile 下 Java 会自动启动 **embedded Redis**（`kb.redis.embedded=true`）。Python Worker 通过 `REDIS_URL` 连接**同一实例**，否则进度与 SSE 会断。

### 3. Python 虚拟环境与依赖

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. 配置文件

```powershell
copy .env.example .env
```

用编辑器打开 `.env`，至少填好真实 RAG 所需项（见下文「配置说明」）。

Java 侧一般不用改即可本地跑；需要时编辑：

- `java-backend/src/main/resources/application.yml` — 端口、Worker URL、temp_data、MinIO、embedded Redis
- `java-backend/src/main/resources/application-dev.yml` — 数据源与 Redis 主机

确保 Java 的 `kb.temp-data-dir` 与 Python 看到的 `temp_data` 是**同一目录**（默认相对路径 `../temp_data`，相对于 `java-backend` 即仓库根下的 `temp_data/`）。

### 5. 启动三个进程

开三个终端：

```powershell
# ---------- 终端 1：导入 Worker ----------
cd <仓库根目录>
.\.venv\Scripts\activate
python -m api.import_api
# 监听 8000，默认仅 /health 与 /internal/import/run

# ---------- 终端 2：查询 Worker ----------
cd <仓库根目录>
.\.venv\Scripts\activate
python -m api.query_api
# 监听 8001，默认仅 /health 与 /internal/query/run

# ---------- 终端 3：Java 网关 ----------
cd <仓库根目录>\java-backend
mvn spring-boot:run
# 监听 8080
```

生产建议：在 `.env` 中设置 `WORKER_BIND_HOST=127.0.0.1`，并保持 `EXPOSE_PUBLIC_API=false`。

### 6. 确认健康

```powershell
curl http://localhost:8080/actuator/health
```

期望整体 `"status":"UP"`，且组件大致为：

| 组件 | 含义 |
|------|------|
| `db` | MySQL 连通 |
| `redisPing` | Redis PING 成功 |
| `importWorker` | `http://127.0.0.1:8000/health` |
| `queryWorker` | `http://127.0.0.1:8001/health` |

然后打开：

- http://localhost:8080/front/import.html
- http://localhost:8080/front/chat.html

### 7. 命令行冒烟（可选）

```powershell
# 上传 Markdown
curl -F "file=@processor/import_processor/input_dir/test_spilt.md" http://localhost:8080/upload
# 返回 {"message":"上传成功","task_id":"xxxxxxxx"}

# 轮询进度（替换 task_id）
curl http://localhost:8080/status/xxxxxxxx

# 非流式问答
curl -H "Content-Type: application/json" ^
  -d "{\"query\":\"RS-12 如何测量电压？\",\"session_id\":\"demo1\",\"is_stream\":false}" ^
  http://localhost:8080/query

# 读历史
curl http://localhost:8080/history/demo1

# 清空历史
curl -X DELETE http://localhost:8080/history/demo1
```

流式：先 `is_stream=true` 拿到 `task_id`，再：

```powershell
curl -N http://localhost:8080/stream/{task_id}
```

会看到 `event: progress` / `delta` / `final`。

### 仅联调 Java 网关（Mock Worker）

不装模型、不跑真实 LangGraph 时，可用自带 mock（stdlib）：

```powershell
cd java-backend
python scripts/mock_import_worker.py   # :8000，模拟导入进度写 Redis
python scripts/mock_query_worker.py    # :8001，模拟答案与 SSE 事件
mvn spring-boot:run                    # :8080
```

Mock **不会**写入真实 Milvus，只用于验证网关编排、进度、SSE、历史落库。

---

## 核心能力

| 模块 | 说明 |
|------|------|
| 文档导入 | 支持 PDF / Markdown；Java 落盘并可选备份 MinIO；Python 跑完整导入图 |
| 混合检索 | BGE-M3 稠密向量 + 稀疏向量，在 Milvus 中混合检索 |
| 多路召回 | 向量检索、HyDE、Web 搜索并行，RRF 融合 |
| 重排序 | BGE-Reranker 打分，按得分断崖截断 |
| 流式问答 | Java 创建任务；Python 推 Redis；Java SSE 转发给浏览器 |
| 会话历史 | MySQL；公开 `/history` 只走 Java；支持连续追问上下文 |

---

## 导入流水线

上传由 **Java** 完成：生成 `task_id` → 保存到 `temp_data/yyyyMMdd/` → Redis 标记「上传文件」→ 调用 Python `/internal/import/run`。  
之后 Python 按后缀分流：

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
|------|------|
| entry_node | 校验本地路径，区分 PDF / Markdown |
| pdf_to_md_node | 调用 MinerU，得到 Markdown |
| md_image_node | 图片摘要，并上传 MinIO |
| document_split_node | 按标题切分；过长再切、过短合并 |
| item_name_recognition_node | 识别商品名，写入商品名集合 |
| bge_embedding_chunks_node | 生成稠密与稀疏向量 |
| milvus_import_node | 写入切片集合 |

前端可通过 `GET /status/{task_id}` 看到中文节点名进度（如「文档切分」「向量生成」）。

---

## 查询流水线

查询任务由 **Java** 创建 `session_id` / `task_id`，再调 Python 跑图。商品名确认后，三路检索并行：

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

| 节点 | 作用 |
|------|------|
| item_name_confirmed_node | 对齐问题中的产品名；高置信继续，否则直接应答 |
| vector_search_node | Milvus 混合检索 |
| hyde_search_node | 假设性文档检索 |
| web_search_node | Web / MCP 搜索（可配置） |
| rrf_merge_node | RRF 融合多路结果 |
| rerank_node | 重排序与截断 |
| answer_output_node | 调用 LLM；流式推 delta；结果写入 Redis |

流式时浏览器走 `EventSource(/stream/{task_id})`，事件名与前端约定为：`progress`、`delta`、`final`。

---

## 对外 API（Java `:8080`）

### 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload` | multipart，字段名 `file`；返回 `task_id` |
| GET | `/status/{task_id}` | `status` / `done_list` / `running_list` / `durations` |
| POST | `/query` | JSON：`query`、`session_id?`、`is_stream` |
| GET | `/stream/{task_id}` | `text/event-stream` |
| GET | `/history/{session_id}` | 会话消息列表 |
| DELETE | `/history/{session_id}` | 清空该会话 |
| GET | `/actuator/health` | 组件健康 |
| GET | `/hello` | 网关探活 |

### 请求 / 响应示例

**上传**

```http
POST /upload
Content-Type: multipart/form-data

file=<二进制>
```

```json
{ "message": "上传成功", "task_id": "a1b2c3d4" }
```

**非流式查询**

```json
{ "query": "如何测量直流电压？", "session_id": "demo1", "is_stream": false }
```

```json
{
  "message": "查询请求已处理完成",
  "session_id": "demo1",
  "answer": "...",
  "done_list": ["确认问题产品", "切片搜索", "生成答案"]
}
```

**流式提交**

```json
{ "query": "如何测量直流电压？", "session_id": "demo1", "is_stream": true }
```

```json
{
  "message": "查询请求已经提交",
  "session_id": "demo1",
  "task_id": "e0423810af24"
}
```

### Python 内网接口（不要给浏览器用）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | Worker 存活 |
| POST | `/internal/import/run` | Body：`task_id`、`import_file_path`、`file_dir` |
| POST | `/internal/query/run` | Body：`task_id`、`session_id`、`query`、`is_stream` |

默认 `EXPOSE_PUBLIC_API=false` 时，Python **不注册** `/upload`、`/query`、`/stream`、`/history`、`/front`。

### 统一错误体

```json
{
  "code": "AI_WORKER_UNAVAILABLE",
  "message": "AI Worker 暂时不可用",
  "detail": "Failed to call query worker: ..."
}
```

| code | 典型场景 |
|------|----------|
| `AI_WORKER_UNAVAILABLE` | Worker 连不上 / 超时（HTTP 502） |
| `AI_WORKER_ERROR` | Worker 返回 4xx/5xx |
| `BAD_REQUEST` | 参数缺失或非法 |
| `INVALID_UPLOAD` | 文件过大或 multipart 异常 |
| `INTERNAL_ERROR` | 未分类服务端错误 |

---

## 配置说明

### `.env`（Python Worker）

复制自 `.env.example`。

**真实跑通 RAG 建议配置**

| 变量 | 用途 |
|------|------|
| `OPEN_API_KEY` | 大模型 / 视觉 / Web 搜索鉴权 |
| `OPEN_API_BASE` | 兼容 OpenAI 的 Base URL |
| `LLM_DEFAULT_MODEL` | 默认对话模型 |
| `VL_MODEL` | 图片摘要模型 |
| `MINERU_API_TOKEN` / `MINERU_BASE_URL` | PDF → Markdown |
| `BGE_M3_PATH` | 本地 BGE-M3 目录 |
| `BGE_RERANKER_LARGE` | 本地重排模型目录 |
| `BGE_DEVICE` / `BGE_FP16` | 如 `cuda:0` / `True` |
| `EMBEDDING_DIM` | 默认 `1024` |
| `MILVUS_URL` | 如 `http://127.0.0.1:19530` |
| `CHUNKS_COLLECTION` / `ITEM_NAME_COLLECTION` | 切片集、商品名集 |
| `MINIO_ENDPOINT` / `ACCESS_KEY` / `SECRET_KEY` / `BUCKET_NAME` | 对象存储 |
| `REDIS_URL` | 如 `redis://127.0.0.1:6379/0` |
| `JAVA_GATEWAY_URL` | 如 `http://127.0.0.1:8080`（读历史等） |

**行为开关**

| 变量 | 默认 | 说明 |
|------|------|------|
| `EXPOSE_PUBLIC_API` | `false` | `true` 时临时恢复 Python 旧公开 API（回滚用） |
| `WORKER_BIND_HOST` | `0.0.0.0` | 生产建议 `127.0.0.1` |
| `KB_HISTORY_OWNER` | `java` | `mongo` 时恢复 Mongo 双写 |

**可选**：`MONGO_URL` / `MONGO_DB_NAME`、`MCP_DASHSCOPE_BASE_URL`；检索超参见 `processor/query_processor/config.py`；切分长度等见 `processor/import_processor/config.py`。

### `application.yml`（Java）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server.port` | `8080` | 对外端口 |
| `ai.import-base-url` | `http://127.0.0.1:8000` | 导入 Worker |
| `ai.query-base-url` | `http://127.0.0.1:8001` | 查询 Worker |
| `kb.front-dir` | `../front` | 静态资源目录 |
| `kb.temp-data-dir` | `../temp_data` | 与 Python 共享落盘目录 |
| `kb.redis.embedded` | `true` | 无外部 Redis 时自动启动 |
| `kb.minio.*` | 见 yml | 上传备份；`enabled=true` 时尝试连接 |

开发数据源见 `application-dev.yml`（MySQL URL、用户名密码、Redis host/port）。

---

## 目录结构

```
knowledge-engine/
├── api/                      # FastAPI Workers
│   ├── import_api.py         # :8000
│   └── query_api.py          # :8001
├── java-backend/             # Spring Boot 网关 :8080
│   ├── src/main/java/...     # 编排、SSE 桥、健康检查、MyBatis
│   ├── src/main/resources/   # application*.yml、schema.sql、mapper
│   └── scripts/              # mock_import_worker / mock_query_worker
├── front/                    # import.html / chat.html
├── processor/
│   ├── import_processor/     # 导入 LangGraph 与节点
│   └── query_processor/      # 查询 LangGraph 与节点
├── service/                  # Python 业务服务
├── utils/                    # Redis 任务、SSE、客户端等
├── schema/                   # Pydantic 请求响应
├── prompts/                  # 提示词
├── docs/
│   ├── design/               # 混合架构 STEP 文档
│   └── images/               # README 截图
├── temp_data/                # 运行时上传目录（勿提交大文件）
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md                 # 本文件（项目唯一使用说明）
```

---

## 常见问题

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 浏览器连不上页面 | 访问了 8000/8001 | 改用 **http://localhost:8080/front/...** |
| `/upload` 或 `/query` 返回 `AI_WORKER_UNAVAILABLE` | Worker 未起或端口不对 | 查进程；看 `/actuator/health` 里 import/queryWorker |
| 上传成功但进度一直只有「上传文件」 | Python 未跑图，或 Redis 不是同一实例 | 确认 import Worker 日志；对齐 `REDIS_URL` 与 Java Redis |
| 导入报找不到文件 | Java 落盘路径 Python 看不见 | 统一 `kb.temp-data-dir` 与仓库 `temp_data` |
| 健康检查 Redis DOWN | 旧版 INFO 探针或端口占用 | 当前用 `redisPing`；检查 6379 / embedded 冲突 |
| 问答无历史上下文 | 历史未写入或 session_id 不一致 | 同一 `session_id`；查 MySQL / `GET /history` |
| 想临时用旧 Python 公网 API | 回滚调试 | `.env` 设 `EXPOSE_PUBLIC_API=true` 并重启 Worker |
| PDF 导入失败 | MinerU 未配置或网络不通 | 检查 `MINERU_*`；可先用 `.md` 验证链路 |

---

## 开发约定

| 改什么 | 改哪里 |
|--------|--------|
| 对外 API、鉴权、运维、历史、SSE 桥 | `java-backend/` |
| 导入 / 查询算法与 LangGraph 节点 | `processor/` |
| Worker 路由与暴露策略 | `api/` |
| 前端交互 | `front/` |

- 鉴权：`SecurityConfig` 已预留空实现，后续可引入 Spring Security。
- 扩展功能优先在 Java 网关增加；RAG 效果迭代继续在 Python `processor/` 完成。
- 提交前不要把真实 `.env`、模型权重、`temp_data` 大文件推进仓库。
