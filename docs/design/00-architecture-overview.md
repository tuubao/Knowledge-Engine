# 架构总览（设计依据）

## 结论

不全量用 Java 重写 RAG。BGE-M3、Reranker、LangGraph 仍在 Python；用 **Spring Boot + Spring MVC + MyBatis** 承接对外 API、任务、会话等企业侧能力。前端统一访问 Java `:8080`，Python 作为内网 AI Worker（默认不注册公开 `/upload` `/query` `/stream` `/history`，见 `EXPOSE_PUBLIC_API`）。

## 职责划分

| 能力 | 归属 |
|------|------|
| 对外 HTTP / 静态前端 | Java `:8080` |
| 上传落盘 / MinIO 备份 | Java（STEP07 起） |
| 任务状态 / 进度 | Redis + MySQL；Python 推事件 |
| 会话历史 | Java + MySQL + MyBatis |
| 导入 / 查询 LangGraph | Python Worker |
| Milvus / Embedding / Rerank | Python |
| 对外 SSE | Java 订阅 Redis 再转发 |

## 目标结构

```
knowledge-engine/
  front/
  api/                 # FastAPI → 内网 Worker
  processor/           # 保留
  java-backend/        # Spring Boot 对外入口
  docs/design/         # 本设计与步骤文档
```

## 对外 API（契约尽量不变）

| 方法 | 路径 | 最终归属 |
|------|------|----------|
| POST | `/upload` | Java |
| GET | `/status/{taskId}` | Java |
| POST | `/query` | Java |
| GET | `/stream/{taskId}` | Java |
| GET/DELETE | `/history/{sessionId}` | Java |

## Python 内部接口（STEP07/08 新增）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/internal/import/run` | 执行导入图 |
| POST | `/internal/query/run` | 执行查询图 |

## 边界（明确不做）

- 不用 Java 重写 `processor/**`
- 不引入老式 SSM XML 全家桶（用 Spring Boot 集成）
- 改造期内不加复杂权限 / 多租户（STEP10 仅预留）
