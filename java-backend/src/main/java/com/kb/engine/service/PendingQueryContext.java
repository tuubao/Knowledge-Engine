package com.kb.engine.service;

import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Holds query context until SSE final / non-stream completion writes MySQL history.
 */
public final class PendingQueryContext {

    private static final ConcurrentHashMap<String, PendingQueryContext> STORE = new ConcurrentHashMap<>();

    private final String taskId;
    private final String sessionId;
    private final String query;
    private volatile boolean historyWritten;

    public PendingQueryContext(String taskId, String sessionId, String query) {
        this.taskId = taskId;
        this.sessionId = sessionId;
        this.query = query;
    }

    public String getTaskId() {
        return taskId;
    }

    public String getSessionId() {
        return sessionId;
    }

    public String getQuery() {
        return query;
    }

    public boolean isHistoryWritten() {
        return historyWritten;
    }

    public void markHistoryWritten() {
        this.historyWritten = true;
    }

    public static void put(PendingQueryContext ctx) {
        STORE.put(ctx.taskId, ctx);
    }

    public static PendingQueryContext get(String taskId) {
        return STORE.get(taskId);
    }

    public static PendingQueryContext remove(String taskId) {
        return STORE.remove(taskId);
    }

    public record FinalPayload(String answer, String rewrittenQuery, List<String> itemNames) {
    }
}
