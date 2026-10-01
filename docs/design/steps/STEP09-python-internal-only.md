# STEP09 — Python 降级为内网 Worker

**状态**: 已完成  
**依赖**: STEP08  
**预估**: 1 天  

## 目标

Python 服务不再作为浏览器入口：去掉对外静态页、可删除或禁用已无调用的公开 API，仅保留 internal 接口与健康检查。

## 任务清单

### 9.1 移除 / 禁用对外面

在 `api/import_api.py`、`api/query_api.py`：

- 移除 `StaticFiles` 挂载 `/front`（改由 Java 提供）
- 对旧公开接口二选一：
  - **推荐**：保留但加环境变量 `EXPOSE_PUBLIC_API=false` 时不注册
  - 或直接删除 `/upload`、`/query`、`/stream`、`/history`（确认 Java 已无调用）

必须保留：

- `/internal/import/run`
- `/internal/query/run`
- 简单 `/health` 或 `/hello`

### 9.2 绑定地址（文档约定）

开发可仍 `0.0.0.0`；文档注明生产应绑定 `127.0.0.1` 或内网网卡，并由防火墙限制。

### 9.3 前端确认

前端仅通过 `:8080` 访问；文档中删除「导入 8000 / 问答 8001」作为用户入口的说明（正式改 README 在 STEP10）。

### 9.4 Mongo 依赖清理（可选本步）

若历史已全走 MySQL，可从查询路径移除 Mongo 客户端初始化；MinIO/Milvus 仍由 Python 使用。

## 涉及路径

| 操作 | 路径 |
|------|------|
| 修改 | `api/import_api.py`、`api/query_api.py` |
| 检查 | Java 调用是否仅 internal |
| 检查 | `front/*` 无硬编码 8000/8001 |

## 验收标准

- [x] 浏览器访问 `:8000/front/...` 不可用或不提供页面
- [x] 浏览器访问 `:8080/front/...` 正常
- [x] Java 全流程导入+问答仍通过
- [x] 直接调 Python 公开旧 API（若已关闭）应 404

## 完成定义

Python = 内网 AI Worker；Java = 唯一对外入口。
