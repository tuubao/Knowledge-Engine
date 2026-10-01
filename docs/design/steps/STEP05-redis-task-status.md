# STEP05 — Redis 任务状态跨语言同步

**状态**: 已完成  
**依赖**: STEP04  
**预估**: 2–3 天  
**完成日期**: 2026-10-01  

## 目标

用 Redis 替换 Python 进程内 [`utils/task_util.py`](../../../utils/task_util.py) 作为**跨语言任务进度真相源**。Java `/status` 改为读 Redis（可双写 MySQL），不再转发 Python 内存状态。

## 任务清单

### 5.1 Redis Key / Channel 约定（冻结）

| Key / Channel | 类型 | 含义 |
|---------------|------|------|
| `kb:task:{id}:status` | string | processing / completed / failed |
| `kb:task:{id}:running` | list | 运行中节点（中文展示名） |
| `kb:task:{id}:done` | list | 已完成节点（中文） |
| `kb:task:{id}:durations` | hash | node → seconds |
| `kb:task:{id}:result` | hash | 如 answer |
| `kb:task:{id}:events` | pub/sub channel | 进度事件 JSON |

TTL：24 小时（每次写入刷新）。

### 5.2 Python 改造

- `redis>=5`，连接使用 `protocol=2`（兼容嵌入式 / 旧版 Redis）
- `task_util`：内存 + Redis **增量双写**
- `.env.example` 增加 `REDIS_URL`

### 5.3 Java 改造

- `spring-boot-starter-data-redis`
- `RedisTaskRepository` / `TaskStatusService`
- `GET /status/{taskId}` **读 Redis**，不再代理 Python
- 可选 MySQL：`ensureImportTask` 幂等写入 `kb_task`
- dev：`EmbeddedRedisConfig`（无外部 Redis 时进程内启动 6379）

### 5.4 上传时建任务

`POST /upload` 代理成功后调用 `ensureImportTask(taskId)`。

## 验收标准

- [x] Python 写入进度后，Java `/status` 可见中文节点与 durations
- [x] 跨 Python 进程增量写入不覆盖已有 done_list
- [x] 任务 key TTL 24h；Java 重启后（同一 Redis）状态仍可读
- [x] 响应字段兼容前端（status / done_list / running_list / durations）

## 完成定义

任务进度跨 Java/Python 共享；`/status` 不再依赖 Python 进程内存。

## 验证摘录

```json
{"status":"completed","done_list":["检查文件","文档切分"],"running_list":[],"durations":{"检查文件":0.1,"文档切分":0.2}}
```
