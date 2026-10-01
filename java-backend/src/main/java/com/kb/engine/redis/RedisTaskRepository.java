package com.kb.engine.redis;

import com.kb.engine.dto.ImportDtos.TaskStatusResponse;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Repository
public class RedisTaskRepository {

    private static final Duration TTL = Duration.ofSeconds(RedisTaskKeys.TTL_SECONDS);

    private final StringRedisTemplate redis;

    public RedisTaskRepository(StringRedisTemplate redis) {
        this.redis = redis;
    }

    public void initTask(String taskId, String status) {
        redis.opsForValue().set(RedisTaskKeys.status(taskId), status, TTL);
        // Ensure list keys exist with TTL even if empty
        touch(taskId);
    }

    public void setStatus(String taskId, String status) {
        redis.opsForValue().set(RedisTaskKeys.status(taskId), status, TTL);
        touch(taskId);
    }

    public TaskStatusResponse getTaskStatus(String taskId) {
        TaskStatusResponse resp = new TaskStatusResponse();
        String status = redis.opsForValue().get(RedisTaskKeys.status(taskId));
        resp.setStatus(status != null ? status : "");

        List<String> running = redis.opsForList().range(RedisTaskKeys.running(taskId), 0, -1);
        resp.setRunningList(running != null ? running : new ArrayList<>());

        List<String> done = redis.opsForList().range(RedisTaskKeys.done(taskId), 0, -1);
        resp.setDoneList(done != null ? done : new ArrayList<>());

        Map<Object, Object> rawDurations = redis.opsForHash().entries(RedisTaskKeys.durations(taskId));
        Map<String, Double> durations = new HashMap<>();
        if (rawDurations != null) {
            for (Map.Entry<Object, Object> e : rawDurations.entrySet()) {
                try {
                    durations.put(String.valueOf(e.getKey()), Double.parseDouble(String.valueOf(e.getValue())));
                } catch (NumberFormatException ignored) {
                    // skip bad entries
                }
            }
        }
        resp.setDurations(durations);
        return resp;
    }

    private void touch(String taskId) {
        redis.expire(RedisTaskKeys.status(taskId), TTL);
        redis.expire(RedisTaskKeys.running(taskId), TTL);
        redis.expire(RedisTaskKeys.done(taskId), TTL);
        redis.expire(RedisTaskKeys.durations(taskId), TTL);
        redis.expire(RedisTaskKeys.result(taskId), TTL);
    }

    public boolean hasStatus(String taskId) {
        Boolean exists = redis.hasKey(RedisTaskKeys.status(taskId));
        return Boolean.TRUE.equals(exists);
    }

    public void addRunning(String taskId, String nodeCnName) {
        List<String> running = redis.opsForList().range(RedisTaskKeys.running(taskId), 0, -1);
        if (running == null || !running.contains(nodeCnName)) {
            redis.opsForList().rightPush(RedisTaskKeys.running(taskId), nodeCnName);
        }
        touch(taskId);
    }

    public void markDone(String taskId, String nodeCnName) {
        redis.opsForList().remove(RedisTaskKeys.running(taskId), 0, nodeCnName);
        List<String> done = redis.opsForList().range(RedisTaskKeys.done(taskId), 0, -1);
        if (done == null || !done.contains(nodeCnName)) {
            redis.opsForList().rightPush(RedisTaskKeys.done(taskId), nodeCnName);
        }
        touch(taskId);
    }

    public void setDuration(String taskId, String nodeCnName, double seconds) {
        redis.opsForHash().put(RedisTaskKeys.durations(taskId), nodeCnName, String.valueOf(seconds));
        touch(taskId);
    }

    public Map<String, String> getResult(String taskId) {
        Map<Object, Object> raw = redis.opsForHash().entries(RedisTaskKeys.result(taskId));
        Map<String, String> out = new HashMap<>();
        if (raw != null) {
            for (Map.Entry<Object, Object> e : raw.entrySet()) {
                out.put(String.valueOf(e.getKey()), e.getValue() != null ? String.valueOf(e.getValue()) : "");
            }
        }
        return out;
    }

    public List<String> getEventBuffer(String taskId) {
        List<String> buf = redis.opsForList().range(RedisTaskKeys.eventBuf(taskId), 0, -1);
        return buf != null ? buf : new ArrayList<>();
    }
}
