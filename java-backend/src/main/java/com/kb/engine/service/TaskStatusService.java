package com.kb.engine.service;

import com.kb.engine.dto.ImportDtos.TaskStatusResponse;
import com.kb.engine.entity.KbTask;
import com.kb.engine.mapper.KbTaskMapper;
import com.kb.engine.redis.RedisTaskRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
public class TaskStatusService {

    private static final Logger log = LoggerFactory.getLogger(TaskStatusService.class);
    public static final String NODE_UPLOAD_CN = "上传文件";

    private final RedisTaskRepository redisTaskRepository;
    private final KbTaskMapper kbTaskMapper;

    public TaskStatusService(RedisTaskRepository redisTaskRepository, KbTaskMapper kbTaskMapper) {
        this.redisTaskRepository = redisTaskRepository;
        this.kbTaskMapper = kbTaskMapper;
    }

    public TaskStatusResponse getStatus(String taskId) {
        return redisTaskRepository.getTaskStatus(taskId);
    }

    public void startImportTask(String taskId) {
        redisTaskRepository.initTask(taskId, "processing");
        redisTaskRepository.addRunning(taskId, NODE_UPLOAD_CN);
        upsertMysqlTask(taskId, "import", "processing");
    }

    public void completeUploadNode(String taskId, double durationSec) {
        redisTaskRepository.markDone(taskId, NODE_UPLOAD_CN);
        redisTaskRepository.setDuration(taskId, NODE_UPLOAD_CN, Math.round(durationSec * 100.0) / 100.0);
    }

    public void markTaskFailed(String taskId) {
        redisTaskRepository.setStatus(taskId, "failed");
        upsertMysqlTask(taskId, null, "failed");
    }

    public void startQueryTask(String taskId, String sessionId, String queryText) {
        redisTaskRepository.initTask(taskId, "processing");
        upsertMysqlQueryTask(taskId, sessionId, queryText, "processing");
    }

    public void completeQueryTask(String taskId, String answer) {
        redisTaskRepository.setStatus(taskId, "completed");
        try {
            KbTask existing = kbTaskMapper.selectByTaskId(taskId);
            if (existing != null) {
                existing.setStatus("completed");
                existing.setAnswer(answer);
                existing.setUpdatedAt(LocalDateTime.now());
                kbTaskMapper.update(existing);
            }
        } catch (Exception e) {
            log.warn("Failed to mark query task {} completed in MySQL: {}", taskId, e.getMessage());
        }
    }

    /**
     * Idempotent init used by older proxy path; prefer {@link #startImportTask(String)}.
     */
    public void ensureImportTask(String taskId) {
        if (taskId == null || taskId.isBlank()) {
            return;
        }
        if (!redisTaskRepository.hasStatus(taskId)) {
            redisTaskRepository.initTask(taskId, "processing");
        }
        upsertMysqlTask(taskId, "import", "processing");
    }

    private void upsertMysqlQueryTask(String taskId, String sessionId, String queryText, String status) {
        try {
            KbTask existing = kbTaskMapper.selectByTaskId(taskId);
            LocalDateTime now = LocalDateTime.now();
            if (existing == null) {
                KbTask task = new KbTask();
                task.setTaskId(taskId);
                task.setType("query");
                task.setStatus(status);
                task.setSessionId(sessionId);
                task.setQueryText(queryText);
                task.setCreatedAt(now);
                task.setUpdatedAt(now);
                kbTaskMapper.insert(task);
            } else {
                existing.setStatus(status);
                existing.setSessionId(sessionId);
                existing.setQueryText(queryText);
                existing.setUpdatedAt(now);
                kbTaskMapper.update(existing);
            }
        } catch (Exception e) {
            log.warn("Failed to sync query task {} to MySQL: {}", taskId, e.getMessage());
        }
    }

    private void upsertMysqlTask(String taskId, String type, String status) {
        try {
            KbTask existing = kbTaskMapper.selectByTaskId(taskId);
            LocalDateTime now = LocalDateTime.now();
            if (existing == null) {
                KbTask task = new KbTask();
                task.setTaskId(taskId);
                task.setType(type != null ? type : "import");
                task.setStatus(status);
                task.setCreatedAt(now);
                task.setUpdatedAt(now);
                kbTaskMapper.insert(task);
            } else {
                existing.setStatus(status);
                existing.setUpdatedAt(now);
                kbTaskMapper.update(existing);
            }
        } catch (Exception e) {
            log.warn("Failed to sync task {} to MySQL: {}", taskId, e.getMessage());
        }
    }
}
