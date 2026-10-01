# STEP06 — 会话历史迁 MySQL

**状态**: 已完成  
**依赖**: STEP05  
**预估**: 2–3 天  
**完成日期**: 2026-10-01  

## 目标

会话历史从 MongoDB 迁到 MySQL（MyBatis）。Java 提供真正的 `/history` 读写；Python 逐步停止写 Mongo。

## 任务清单

### 6.1 Java History 服务落地

- `ChatHistoryService`：基于 `KbChatMessageMapper`
- `GET /history/{sessionId}`：按 `ts` 升序，字段含 `_id`、`role`、`text`、`rewritten_query`、`item_names`、`ts`
- `DELETE /history/{sessionId}`：删 MySQL，并尽力清空 Python/Mongo
- **已停止** 对外 history 反向代理

### 6.2 写入时机（方案 A）

- 公开读/删：Java + MySQL
- Python `save_chat_message`：仍写 Mongo，并 `POST /internal/history` 双写 MySQL
- STEP08 再去掉 Mongo 写

### 6.3 Python 侧

- `utils/mongo_history_util.py` 增加 `_mirror_to_java`
- `.env.example`：`JAVA_GATEWAY_URL=http://127.0.0.1:8080`

### 6.4 兼容字段

- `HistoryItem.id` 使用 `@JsonProperty("_id")`

## 验收标准

- [x] `POST /internal/history` 写入后 `GET /history` 可读
- [x] `DELETE` 后 GET 为空
- [x] 字段含 `_id` / `item_names` 列表
- [x] 前端仍走同源 `/history`（无需改路径）

## 完成定义

History API 以 Java + MySQL 为准；Mongo 仅作过渡双写与查询链路上下文读取。
