# 开发改造步骤总表

按序号执行。每步有独立详情文档；**未完成验收标准不得进入下一步**。

```mermaid
flowchart LR
  S1[STEP01 骨架] --> S2[STEP02 导入代理]
  S2 --> S3[STEP03 查询代理]
  S3 --> S4[STEP04 MySQL]
  S4 --> S5[STEP05 Redis任务]
  S5 --> S6[STEP06 历史迁移]
  S6 --> S7[STEP07 导入编排]
  S7 --> S8[STEP08 查询SSE]
  S8 --> S9[STEP09 Worker内网化]
  S9 --> S10[STEP10 收尾]
```

## 步骤一览

| Step | 名称 | 目标 | 预估 | 详情 |
|------|------|------|------|------|
| 01 | 工程骨架与基础设施 | 建 `java-backend`，就绪 MySQL/Redis | 1–2 天 | [STEP01](steps/STEP01-scaffold-and-infra.md) |
| 02 | 导入 API 反向代理 | Java 转发 `/upload`、`/status` | 1–2 天 | [STEP02](steps/STEP02-proxy-import-api.md) |
| 03 | 查询代理与前端切流 | Java 转发查询/历史/SSE；前端改 `:8080` | 2–3 天 | [STEP03](steps/STEP03-proxy-query-and-frontend.md) |
| 04 | MySQL + MyBatis | 建表、实体、Mapper | 1–2 天 | [STEP04](steps/STEP04-mysql-mybatis.md) |
| 05 | Redis 任务状态 | 跨语言进度真相源 | 2–3 天 | [STEP05](steps/STEP05-redis-task-status.md) |
| 06 | 会话历史迁 MySQL | 替换 Mongo 历史读写 | 2–3 天 | [STEP06](steps/STEP06-chat-history-mysql.md) |
| 07 | Java 主导导入 | 上传/MinIO 在 Java；Python 只跑图 | 2–3 天 | [STEP07](steps/STEP07-java-owns-import.md) |
| 08 | Java 主导查询与 SSE | 编排查询；Redis→SSE | 3–4 天 | [STEP08](steps/STEP08-java-owns-query-sse.md) |
| 09 | Python 内网化 | 去掉对外静态页与公网暴露 | 1 天 | [STEP09](steps/STEP09-python-internal-only.md) |
| 10 | 工程化收尾 | 健康检查、异常码、文档 | 2–3 天 | [STEP10](steps/STEP10-hardening.md) |

## 每步工作流（固定）

1. 阅读该 Step 详情文档  
2. 按「任务清单」改代码  
3. 按「验收标准」自测  
4. 在本页或 Issue 中勾选完成  
5. 再开下一 Step  

## 整体完成标准

- [x] 浏览器只访问 `http://localhost:8080` 即可导入与问答  
- [x] Python `:8000` / `:8001` 仅内网被 Java 调用  
- [x] 任务进度与会话历史可跨进程重启恢复（Redis + MySQL）  
- [x] 前端 API 路径与主要 JSON 字段保持兼容  
- [x] README 启动说明已更新为四进程模型  

## 进度勾选

- [x] STEP01
- [x] STEP02
- [x] STEP03
- [x] STEP04
- [x] STEP05
- [x] STEP06
- [x] STEP07
- [x] STEP08
- [x] STEP09
- [x] STEP10
