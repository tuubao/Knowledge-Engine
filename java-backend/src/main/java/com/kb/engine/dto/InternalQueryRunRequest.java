package com.kb.engine.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.ArrayList;
import java.util.List;

/**
 * Body for POST /internal/query/run (STEP08).
 */
public class InternalQueryRunRequest {

    private String taskId;
    private String sessionId;
    private String query;
    private boolean isStream;

    public InternalQueryRunRequest() {
    }

    public InternalQueryRunRequest(String taskId, String sessionId, String query, boolean isStream) {
        this.taskId = taskId;
        this.sessionId = sessionId;
        this.query = query;
        this.isStream = isStream;
    }

    @JsonProperty("task_id")
    public String getTaskId() {
        return taskId;
    }

    @JsonProperty("task_id")
    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    @JsonProperty("session_id")
    public String getSessionId() {
        return sessionId;
    }

    @JsonProperty("session_id")
    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    @JsonProperty("query")
    public String getQuery() {
        return query;
    }

    @JsonProperty("query")
    public void setQuery(String query) {
        this.query = query;
    }

    @JsonProperty("is_stream")
    public boolean getIsStream() {
        return isStream;
    }

    @JsonProperty("is_stream")
    public void setIsStream(boolean isStream) {
        this.isStream = isStream;
    }
}
