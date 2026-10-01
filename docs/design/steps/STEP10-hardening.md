# STEP10 — 工程化收尾

**状态**: 已完成  
**依赖**: STEP09  
**预估**: 2–3 天  

## 目标

补齐可运维性、错误约定与文档，使混合架构可交接、可日常开发。

## 任务清单

### 10.1 健康检查

Java：

- `GET /actuator/health` 或 `/health`
- 组合检查：MySQL、Redis、Python import worker、Python query worker（HTTP 探活）

Python：

- `GET /health` 返回 `{ "status": "ok" }`

### 10.2 统一错误响应

约定 Java 对外错误体，例如：

```json
{
  "code": "AI_WORKER_UNAVAILABLE",
  "message": "查询服务暂时不可用",
  "task_id": "可选"
}
```

覆盖：Python 超时、连接失败、任务不存在、上传格式非法。

### 10.3 配置清单冻结

更新：

- `java-backend/src/main/resources/application.yml` 示例
- 根目录 [`.env.example`](../../../.env.example)（增加 `REDIS_URL` 等）
- 根 [`README.md`](../../../README.md) 启动方式改为：

```text
1. MySQL / Redis / Milvus / MinIO
2. python -m api.import_api     # 内网 8000
3. python -m api.query_api      # 内网 8001
4. java -jar / mvn spring-boot:run   # 对外 8080
```

页面入口改为：

- http://localhost:8080/front/import.html
- http://localhost:8080/front/chat.html

### 10.4 鉴权预留（不做完整登录）

- 预留 `SecurityConfig` 或 filter 空实现
- 注释说明后续可加 Spring Security

### 10.5 可选增强（有余力再做）

- 任务列表管理接口 `GET /admin/tasks`
- 失败任务重试（仅导入）
- 简单请求日志 / traceId

### 10.6 勾选总验收

回到 [dev-steps.md](../dev-steps.md) 勾选「整体完成标准」。

## 涉及路径

| 操作 | 路径 |
|------|------|
| 修改 | `README.md`、`.env.example`、`docs/design/*` 状态 |
| 新建 | Java health、异常处理 `@ControllerAdvice` |
| 可选 | admin API |

## 验收标准

- [x] 按新 README 可从零启动全套服务
- [x] 关掉 Python query worker 时，Java 返回明确错误而非挂死
- [x] 设计文档步骤勾选已更新
- [x] 无必须依赖浏览器访问 8000/8001

## 完成定义

混合架构改造闭环；后续功能优先在 `java-backend` 扩展，RAG 算法继续在 `processor/` 迭代。
