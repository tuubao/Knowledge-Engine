# STEP03 — Java 查询/历史/SSE 代理与前端切流

**状态**: 已完成  
**依赖**: STEP02  
**预估**: 2–3 天  
**完成日期**: 2026-10-01  

## 目标

Java 代理全部对外查询相关接口；前端改为只访问 `:8080`。至此进入「Java 网关 + Python 原逻辑」阶段。

## 任务清单

### 3.1 Query / History / Stream Controller

实现并转发：

| 方法 | 路径 | Python 目标 |
|------|------|-------------|
| POST | `/query` | `:8001/query` |
| GET | `/stream/{taskId}` | `:8001/stream/{taskId}` |
| GET | `/history/{sessionId}` | `:8001/history/{sessionId}` |
| DELETE | `/history/{sessionId}` | `:8001/history/{sessionId}` |

DTO 对齐 [`schema/query_schema.py`](../../../schema/query_schema.py)。  
`/query` 采用 **原始 JSON 透传**，避免 `session_id` / `is_stream` 在双向序列化中丢失。

### 3.2 SSE 代理要点

- 使用可流式转发的客户端（避免把整个 SSE 缓冲成一次性响应）
- `Content-Type: text/event-stream`
- 正确处理客户端断开（取消对 Python 的订阅/连接）

本步实现：JDK `HttpClient` + `StreamingResponseBody` 字节流式透传。

### 3.3 挂载前端

Java 挂载仓库 `front/` 到 `/front/**`（STEP02 已做）：

- 导入页：`http://localhost:8080/front/import.html`
- 问答页：`http://localhost:8080/front/chat.html`

### 3.4 前端基址调整

- `import.html` / `chat.html`：`API_BASE` 改为同源空串（`file://` 时回退 `http://127.0.0.1:8080`）
- 页面互链改为相对路径 `/front/...`

### 3.5 CORS

Java 侧已允许 `*`（同 origin 后实际可简化）。

## 涉及路径

| 操作 | 路径 |
|------|------|
| 新建 | `QueryController`、`HistoryController`、`QueryWorkerClient`、`QueryDtos` |
| 新建 | `scripts/mock_query_worker.py`（联调） |
| 修改 | `front/import.html`、`front/chat.html` |
| 修改 | `application.yml`（async timeout）、`GlobalExceptionHandler` |

## 验收标准

- [x] `/query` 非流式 / 流式提交经 Java 代理字段正确（含 `session_id`、`task_id`）
- [x] `/stream/{taskId}` SSE 事件可透传（progress / delta / final）
- [x] `/history` GET/DELETE 可用，`_id` 字段保留
- [x] `/front/import.html`、`/front/chat.html` 返回 200
- [x] 导入 `/upload` 代理仍可用
- [ ] 真实 Python Worker 全链路 UI 联调（需本机启动 `api.import_api` + `api.query_api`）

## 完成定义

用户感知入口已切到 Java；业务状态仍在 Python 内存 / Mongo。

## 本步交付物

| 项 | 说明 |
|----|------|
| `POST /query` | JSON 透传到 `:8001` |
| `GET /stream/{taskId}` | SSE 流式代理 |
| `GET/DELETE /history/{sessionId}` | 历史代理 |
| 前端 | 仅访问 `:8080` |
