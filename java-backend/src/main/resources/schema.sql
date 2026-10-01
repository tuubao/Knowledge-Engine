-- STEP04 schema for knowledge-engine Java gateway
-- Safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS kb_task (
  task_id       VARCHAR(64)  NOT NULL PRIMARY KEY,
  type          VARCHAR(16)  NOT NULL COMMENT 'import | query',
  status        VARCHAR(32)  NOT NULL COMMENT 'processing | completed | failed',
  session_id    VARCHAR(64)  NULL,
  query_text    TEXT         NULL,
  answer        MEDIUMTEXT   NULL,
  error_msg     TEXT         NULL,
  created_at    DATETIME(3)  NOT NULL,
  updated_at    DATETIME(3)  NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kb_task_node (
  id            BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
  task_id       VARCHAR(64)  NOT NULL,
  node_name     VARCHAR(128) NOT NULL,
  status        VARCHAR(16)  NOT NULL COMMENT 'running | done',
  duration_sec  DOUBLE       NULL,
  updated_at    DATETIME(3)  NOT NULL,
  INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS kb_chat_message (
  id               BIGINT       NOT NULL PRIMARY KEY AUTO_INCREMENT,
  session_id       VARCHAR(64)  NOT NULL,
  role             VARCHAR(32)  NOT NULL,
  text             MEDIUMTEXT   NOT NULL,
  rewritten_query  TEXT         NULL,
  item_names       JSON         NULL,
  ts               DOUBLE       NOT NULL,
  INDEX idx_session_ts (session_id, ts)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
