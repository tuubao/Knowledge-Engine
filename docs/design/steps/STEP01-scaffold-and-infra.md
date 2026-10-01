# STEP01 — 工程骨架与基础设施

**状态**: 已完成  
**依赖**: 无  
**预估**: 1–2 天  
**完成日期**: 2026-10-01  

## 目标

搭好 Java 工程与基础设施，不改变现有 Python 行为。为后续代理与数据迁移打底。

## 任务清单

### 1.1 创建 Java 工程

在仓库根目录创建 `java-backend/`：

```
java-backend/
  pom.xml
  src/main/java/com/kb/engine/
    KnowledgeEngineApplication.java
  src/main/resources/
    application.yml
    application-dev.yml
```

技术选型锁定：

- Spring Boot 3.x
- Java 17+
- spring-boot-starter-web
- 暂可先不引入 MyBatis / Redis（STEP04/05 再加），或在本步就加入依赖但先不写业务

### 1.2 基础配置

`application.yml` 至少包含：

```yaml
server:
  port: 8080
ai:
  import-base-url: http://127.0.0.1:8000
  query-base-url: http://127.0.0.1:8001
```

提供一个健康检查：`GET /actuator/health` 或简单 `GET /hello`。

### 1.3 基础设施就绪

确保本机能启动（可 Docker 或本地安装）：

| 服务 | 用途 | 本步要求 |
|------|------|----------|
| MySQL 8 | 业务库 | 建空库 `knowledge_engine`，账号可连 |
| Redis | 任务/SSE | 可 `PING` |
| Milvus / MinIO / Mongo | 现有 Python | 保持能跑通现有流程 |

本步**不要求**建业务表（见 STEP04）。

> **落地说明**：已在根目录 `docker-compose.yml` 增加 `mysql` / `redis` 服务。若本机未安装 Docker，需自行安装 Docker Desktop 后执行 `docker compose up -d mysql redis`，或改用本机已有的 MySQL 8 / Redis 实例（库名 `knowledge_engine`）。

### 1.4 文档占位

- 在根目录 `README.md` 写清：如何启动 Java 网关（`mvn spring-boot:run`）
- 不修改根 `README.md` 的启动方式（留给 STEP10）

## 涉及路径

| 操作 | 路径 |
|------|------|
| 新建 | `java-backend/**` |
| 修改 | `docker-compose.yml`（增加 mysql/redis）、`.gitignore` |
| 不动 | `api/`、`processor/`、`front/` |

## 验收标准

- [x] `mvn -f java-backend spring-boot:run` 可在 `:8080` 启动
- [x] `GET http://localhost:8080/hello`（或 health）返回成功
- [ ] MySQL、Redis 本机可连接（compose 已就绪；依赖本机 Docker/实例，见上方说明）
- [x] 原有 `python -m api.import_api` / `query_api` 仍可独立运行，行为不变（本步未改 Python）

## 完成定义

仅有可运行的空壳 Java 服务 + 基础设施定义可用，**无业务接口迁移**。

## 本步交付物

| 项 | 说明 |
|----|------|
| `java-backend/` | Spring Boot 3.3.5 + Java 17 |
| `GET /hello` | 探活 JSON |
| `GET /actuator/health` | Actuator 健康检查 |
| `ai.*` 配置 | 预留给 STEP02 Worker 地址 |
| compose `mysql`/`redis` | 库 `knowledge_engine`，用户 `kb` / `kb123`，root `root123` |
