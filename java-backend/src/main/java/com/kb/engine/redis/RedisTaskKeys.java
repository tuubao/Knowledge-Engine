package com.kb.engine.redis;

/**
 * Frozen Redis key / channel conventions for task progress (STEP05).
 */
public final class RedisTaskKeys {

    public static final long TTL_SECONDS = 24 * 60 * 60;

    private RedisTaskKeys() {
    }

    public static String status(String taskId) {
        return "kb:task:" + taskId + ":status";
    }

    public static String running(String taskId) {
        return "kb:task:" + taskId + ":running";
    }

    public static String done(String taskId) {
        return "kb:task:" + taskId + ":done";
    }

    public static String durations(String taskId) {
        return "kb:task:" + taskId + ":durations";
    }

    public static String result(String taskId) {
        return "kb:task:" + taskId + ":result";
    }

    public static String eventsChannel(String taskId) {
        return "kb:task:" + taskId + ":events";
    }

    public static String eventBuf(String taskId) {
        return "kb:task:" + taskId + ":event_buf";
    }
}
