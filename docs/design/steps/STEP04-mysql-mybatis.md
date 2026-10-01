# STEP04 — MySQL 建表与 MyBatis

**状态**: 已完成  
**依赖**: STEP03  
**预估**: 1–2 天  
**完成日期**: 2026-10-01  

## 目标

落地业务库表结构与 MyBatis 访问层。本步可先写通单测/简单 CRUD，**暂不切换线上读写路径**（切换在 STEP05/06）。

## 任务清单

### 4.1 依赖

`pom.xml` 增加：

- `mybatis-spring-boot-starter` 3.0.3
- `mysql-connector-j`

### 4.2 schema.sql

已创建 `java-backend/src/main/resources/schema.sql`（`IF NOT EXISTS`）。

表：`kb_task` / `kb_task_node` / `kb_chat_message`。

### 4.3 实体与 Mapper

- Entity: `KbTask`, `KbTaskNode`, `KbChatMessage`
- Mapper 接口 + XML：`insert` / `update` / `selectByTaskId` / `listBySessionId` / `deleteBySessionId` 等

### 4.4 配置

`application-dev.yml` 已配置 datasource（`kb` / `kb123`）与 MyBatis。

### 4.5 冒烟

`GET /dev/db-smoke`（仅 `dev` profile）：插入 task/node/message 后查回并清理。

## 涉及路径

| 操作 | 路径 |
|------|------|
| 新建 | `schema.sql`、`mapper/*.xml`、`entity/*`、`mapper/*Mapper.java` |
| 新建 | `DbSmokeController`、`scripts/init_db_user.sql` |
| 配置 | `application-dev.yml`、`@MapperScan` |
| 不动 | Python 侧 |

## 验收标准

- [x] 表创建成功（`kb_task` / `kb_task_node` / `kb_chat_message`）
- [x] MyBatis 冒烟 `ok=true`
- [x] `/hello`、`/front/chat.html` 仍可用（代理链路未改）

## 完成定义

数据访问层就绪，业务流量仍走原 Python 存储。

## 本步交付物

| 项 | 说明 |
|----|------|
| 库 | `knowledge_engine`，用户 `kb` / `kb123` |
| 冒烟 | `GET http://localhost:8080/dev/db-smoke` |
| 初始化 | `scripts/init_db_user.sql` + `schema.sql` |

## 本地 MySQL 说明

本机曾通过手动启动 mysqld（服务 `MySQL` 需管理员权限时可用）：

```text
E:\Server\mysql-8.0.29-winx64\bin\mysqld.exe --datadir=...\data --port=3306
```

或管理员：`Start-Service MySQL`。然后：

```powershell
mysql -uroot -proot < java-backend\scripts\init_db_user.sql
mysql -ukb -pkb123 knowledge_engine < java-backend\src\main\resources\schema.sql
```
