CREATE DATABASE IF NOT EXISTS knowledge_engine
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'kb'@'%' IDENTIFIED BY 'kb123';
CREATE USER IF NOT EXISTS 'kb'@'localhost' IDENTIFIED BY 'kb123';
GRANT ALL PRIVILEGES ON knowledge_engine.* TO 'kb'@'%';
GRANT ALL PRIVILEGES ON knowledge_engine.* TO 'kb'@'localhost';
FLUSH PRIVILEGES;
