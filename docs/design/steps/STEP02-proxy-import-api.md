# STEP02 — Java 导入 API 反向代理

**状态**: 已完成  
**依赖**: STEP01  
**预估**: 1–2 天  
**完成日期**: 2026-10-01  

## 目标

Java 对外暴露与现有一致的导入接口，请求原样转发到 Python `:8000`。前端本步可仍直连 Python；本步只验证 Java 代理正确。

## 任务清单

### 2.1 Controller

实现：

- `POST /upload` — multipart 转发到 Python `/upload`
- `GET /status/{taskId}` — 转发到 Python `/status/{taskId}`

响应 JSON 字段对齐现有：

- `UploadResponse`: `message`, `task_id`
- `TaskStatusResponse`: `status`, `done_list`, `running_list`, `durations`

参考：[`schema/upload_schema.py`](../../../schema/upload_schema.py)

### 2.2 AiWorkerClient（导入）

使用 `RestClient` 或 `WebClient`：

- baseUrl = `ai.import-base-url`
- 正确转发 `multipart/form-data`（文件字段名与现有前端一致）

### 2.3 静态资源（可选本步）

可先不挂载 `front/`；若方便可在本步挂载 `/front/**` 指向仓库 `front/`，便于后续切流。

### 2.4 错误透传

Python 4xx/5xx 时，Java 尽量透传状态码与 body，或统一包装但保留可读错误信息。

## 涉及路径

| 操作 | 路径 |
|------|------|
| 新建 | `java-backend/.../controller/ImportController.java` |
| 新建 | `java-backend/.../client/ImportWorkerClient.java` |
| 新建 | `java-backend/.../dto/ImportDtos.java` |
| 新建 | `java-backend/.../client/WorkerProxyException.java` |
| 新建 | `java-backend/.../web/GlobalExceptionHandler.java` |
| 修改 | `AppConfig`（静态资源 `/front/**`、CORS）、`application.yml`（Jackson SNAKE_CASE、multipart） |
| 不动业务逻辑 | `api/import_api.py`、`service/file_process_service.py` |

## 手工验收步骤

1. 启动 Python import `:8000` + Java `:8080`
2. 用 curl 或 Postman：`POST http://localhost:8080/upload` 上传一份 `.md`
3. 用返回的 `task_id` 调 `GET http://localhost:8080/status/{task_id}`
4. 对比直连 `:8000` 的结果，字段一致、任务最终 `completed`

本步已用 `java-backend/scripts/mock_import_worker.py` 验证代理字段透传；接真实 `python -m api.import_api` 时流程相同。

## 验收标准

- [x] 经 Java 上传可转发至 Worker，返回 `message` + `task_id`
- [x] `/status` 返回 `done_list` / `running_list` / `durations`（snake_case）
- [x] Python 侧业务代码无改动
- [x] `/front/import.html` 可通过 Java `:8080` 访问

## 完成定义

导入链路「浏览器/客户端 → Java → Python」打通，Java 尚无自有业务状态。

## 本步交付物

| 项 | 说明 |
|----|------|
| `POST /upload` | multipart 字段 `file` → Python |
| `GET /status/{taskId}` | 状态代理 |
| Worker 不可达 | `502` + JSON message |
| Worker 4xx/5xx | 状态码与 body 透传 |
| 静态页 | `http://localhost:8080/front/import.html` |
