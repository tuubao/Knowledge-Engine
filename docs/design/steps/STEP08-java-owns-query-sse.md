# STEP08 — Java 主导查询编排与 SSE 桥接

**状态**: 已完成  
**依赖**: STEP07  
**预估**: 3–4 天  

## 目标

查询任务由 Java 创建与对外推流；Python 执行查询图，经 Redis 推送进度与 token；会话历史仅由 Java 写入 MySQL。

## 任务清单

### 8.1 Python 内部查询接口

在 [`api/query_api.py`](../../../api/query_api.py) 新增：

- `POST /internal/query/run`
- Body: `{ "task_id", "session_id", "query", "is_stream" }`
- 行为：等价 `QueryService.run_query_graph`

### 8.2 Python SSE → Redis

改造 [`utils/sse_util.py`](../../../utils/sse_util.py) 与查询节点基类中的 `_push_progress`：

- 事件写入 Redis channel `kb:task:{taskId}:events`
- 事件类型至少：`progress` / `token`（或 `answer_chunk`）/ `done` / `error`
- 最终 `answer` 写入 `kb:task:{id}:result`

停止依赖进程内 SSE queue 对外服务（可短暂保留 `/stream` 作回滚）。

### 8.3 历史写入收口到 Java

- Python **不再**调用 `mongo_history_util.save_chat_message`（或改为 no-op 开关）
- 查询完成后：
  - Python 将最终 state 关键字段放入 Redis result，或
  - internal 接口同步返回 `{ answer, rewritten_query, item_names }`
- Java 写入 user + assistant 两条 `kb_chat_message`

### 8.4 Java 查询编排

`POST /query`：

1. 生成 `session_id`（若未传）、`task_id`
2. 写 MySQL/Redis 任务行
3. 若 `is_stream=true`：异步调 Python internal，立即返回 `StreamSubmitResponse`
4. 若 `is_stream=false`：调 Python，等结果，写历史，返回 `QueryResponse`

`GET /stream/{taskId}`：

- 订阅 Redis `kb:task:{taskId}:events`
- 转成浏览器 SSE
- `done`/`error` 后结束并落库历史（若尚未写）

### 8.5 去掉查询反向代理

Java 不再把 `/query`、`/stream` 透传给 Python 公网式接口。

## 事件协议（冻结示例）

```json
{"type":"progress","status":"processing","done_list":[],"running_list":["确认问题产品"]}
{"type":"token","text":"根据"}
{"type":"done","answer":"...","rewritten_query":"...","item_names":["RS-12"]}
{"type":"error","message":"..."}
```

前端若只消费部分字段，保持与现有 SSE 字段兼容；必要时同步微调 [`front/chat.html`](../../../front/chat.html)。

## 涉及路径

| 操作 | 路径 |
|------|------|
| 修改 | `api/query_api.py`、`utils/sse_util.py`、`processor/query_processor/base.py` |
| 修改 | `answer_output_node`（历史写入剥离） |
| 新建 | Java `QueryOrchestrationService`、`SseBridgeService`、`RedisEventSubscriber` |
| 修改 | `QueryController`、`History` 写入调用 |

## 验收标准

- [x] 非流式问答：答案正确，MySQL 有历史，无新 Mongo 写入
- [x] 流式问答：进度 + token 经 Java SSE 到达浏览器
- [x] 客户端断开 SSE 不导致 Java 进程异常
- [x] `/history` 仅读 MySQL 且与刚聊内容一致

## 完成定义

查询链路完整「Java 编排 + Python 推理 + Redis 事件 + MySQL 历史」。
