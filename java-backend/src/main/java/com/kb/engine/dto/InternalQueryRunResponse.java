package com.kb.engine.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.ArrayList;
import java.util.List;

/**
 * Response from POST /internal/query/run (STEP08).
 */
public class InternalQueryRunResponse {

    private String message;
    private String taskId;
    private String sessionId;
    private String answer = "";
    private List<String> doneList = new ArrayList<>();
    private String rewrittenQuery = "";
    private List<String> itemNames = new ArrayList<>();

    @JsonProperty("message")
    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    @JsonProperty("task_id")
    public String getTaskId() {
        return taskId;
    }

    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    @JsonProperty("session_id")
    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    @JsonProperty("answer")
    public String getAnswer() {
        return answer;
    }

    public void setAnswer(String answer) {
        this.answer = answer != null ? answer : "";
    }

    @JsonProperty("done_list")
    public List<String> getDoneList() {
        return doneList;
    }

    public void setDoneList(List<String> doneList) {
        this.doneList = doneList != null ? doneList : new ArrayList<>();
    }

    @JsonProperty("rewritten_query")
    public String getRewrittenQuery() {
        return rewrittenQuery;
    }

    public void setRewrittenQuery(String rewrittenQuery) {
        this.rewrittenQuery = rewrittenQuery != null ? rewrittenQuery : "";
    }

    @JsonProperty("item_names")
    public List<String> getItemNames() {
        return itemNames;
    }

    public void setItemNames(List<String> itemNames) {
        this.itemNames = itemNames != null ? itemNames : new ArrayList<>();
    }
}
