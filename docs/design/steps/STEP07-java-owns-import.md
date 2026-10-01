# STEP07 — Java 主导导入编排

**状态**: 已完成  
**依赖**: STEP06  
**预估**: 2–3 天  

## 目标

上传、落盘、MinIO 备份、创建任务由 Java 完成；Python 只负责执行导入 LangGraph。去掉对 Python `POST /upload` 的依赖。

## 任务清单

### 7.1 Python 内部接口

在 [`api/import_api.py`](../../../api/import_api.py) 新增：

- `POST /internal/import/run`
- Body: `{ "task_id", "import_file_path", "file_dir" }`
- 行为：等价 `FileProcessService.run_main_graph(...)`
- 可同步执行或后台任务；若后台，需保证进度仍写 Redis

建议：保留原 `/upload` 一段时间作回滚，但 Java 不再调用。

### 7.2 Java 上传实现

对齐 [`service/file_process_service.py`](../../../service/file_process_service.py)：

1. 生成 `task_id`
2. 保存到 `temp_data/日期/`（路径规则与 Python `core/paths` 一致或可配置共享目录）
3. 可选上传 MinIO（失败不阻断）
4. 写 Redis / MySQL：`status=processing`
5. 调用 Python `/internal/import/run`
6. 立即返回 `{ message, task_id }`

**共享文件注意**：Java 与 Python 必须能看到同一 `import_file_path`（同机共享磁盘，或 Java 先传 MinIO、Python 再下载——本步默认**同机共享 `temp_data`**）。

### 7.3 MinIO Java SDK

配置：`MINIO_ENDPOINT` 等与 `.env` 对齐（可在 `application.yml` 引用同一套值）。

### 7.4 路径配置

`application.yml`：

```yaml
kb:
  temp-data-dir: D:/PythonCode/workspace/knowledge-engine/temp_data
ai:
  import-base-url: http://127.0.0.1:8000
```

## 涉及路径

| 操作 | 路径 |
|------|------|
| 修改 | `api/import_api.py`（internal 路由） |
| 新建 | Java `FileUploadService`、`MinioStorageService`、`ImportOrchestrationService` |
| 修改 | `ImportController`：不再代理 upload |

## 验收标准

- [x] 经 Java 上传的 PDF/MD 能完整跑完导入节点
- [x] Redis `/status` 进度正常
- [x] MinIO 中可见备份对象（若启用）— 未启用时 soft-fail 不阻断
- [x] Java 不再调用 Python `/upload`

## 完成定义

导入业务编排权在 Java；Python 是「跑图 Worker」。
