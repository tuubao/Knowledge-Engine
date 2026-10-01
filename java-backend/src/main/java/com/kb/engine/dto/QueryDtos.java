package com.kb.engine.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.ArrayList;
import java.util.List;

/**
 * Aligns with Python schema.query_schema (snake_case JSON via Jackson naming).
 */
public final class QueryDtos {

    private QueryDtos() {
    }

    public static class QueryRequest {
        private String query;

        @JsonProperty("session_id")
        private String sessionId;

        @JsonProperty("is_stream")
        private boolean isStream;

        public String getQuery() {
            return query;
        }

        public void setQuery(String query) {
            this.query = query;
        }

        @JsonProperty("session_id")
        public String getSessionId() {
            return sessionId;
        }

        @JsonProperty("session_id")
        public void setSessionId(String sessionId) {
            this.sessionId = sessionId;
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

    public static class QueryResponse {
        private String message;
        private String sessionId;
        private String answer = "";
        private List<String> doneList = new ArrayList<>();

        public String getMessage() {
            return message;
        }

        public void setMessage(String message) {
            this.message = message;
        }

        public String getSessionId() {
            return sessionId;
        }

        public void setSessionId(String sessionId) {
            this.sessionId = sessionId;
        }

        public String getAnswer() {
            return answer;
        }

        public void setAnswer(String answer) {
            this.answer = answer;
        }

        public List<String> getDoneList() {
            return doneList;
        }

        public void setDoneList(List<String> doneList) {
            this.doneList = doneList != null ? doneList : new ArrayList<>();
        }
    }

    public static class StreamSubmitResponse {
        private String message;
        private String sessionId;
        private String taskId;

        public String getMessage() {
            return message;
        }

        public void setMessage(String message) {
            this.message = message;
        }

        public String getSessionId() {
            return sessionId;
        }

        public void setSessionId(String sessionId) {
            this.sessionId = sessionId;
        }

        public String getTaskId() {
            return taskId;
        }

        public void setTaskId(String taskId) {
            this.taskId = taskId;
        }
    }

    public static class HistoryItem {
        @JsonProperty("_id")
        private String id = "";
        private String sessionId = "";
        private String role = "";
        private String text = "";
        private String rewrittenQuery = "";
        private List<String> itemNames = new ArrayList<>();
        private Double ts;

        public String getId() {
            return id;
        }

        public void setId(String id) {
            this.id = id != null ? id : "";
        }

        public String getSessionId() {
            return sessionId;
        }

        public void setSessionId(String sessionId) {
            this.sessionId = sessionId != null ? sessionId : "";
        }

        public String getRole() {
            return role;
        }

        public void setRole(String role) {
            this.role = role != null ? role : "";
        }

        public String getText() {
            return text;
        }

        public void setText(String text) {
            this.text = text != null ? text : "";
        }

        public String getRewrittenQuery() {
            return rewrittenQuery;
        }

        public void setRewrittenQuery(String rewrittenQuery) {
            this.rewrittenQuery = rewrittenQuery != null ? rewrittenQuery : "";
        }

        public List<String> getItemNames() {
            return itemNames;
        }

        public void setItemNames(List<String> itemNames) {
            this.itemNames = itemNames != null ? itemNames : new ArrayList<>();
        }

        public Double getTs() {
            return ts;
        }

        public void setTs(Double ts) {
            this.ts = ts;
        }
    }

    public static class HistoryResponse {
        private String sessionId;
        private List<HistoryItem> items = new ArrayList<>();

        public String getSessionId() {
            return sessionId;
        }

        public void setSessionId(String sessionId) {
            this.sessionId = sessionId;
        }

        public List<HistoryItem> getItems() {
            return items;
        }

        public void setItems(List<HistoryItem> items) {
            this.items = items != null ? items : new ArrayList<>();
        }
    }

    public static class MessageResponse {
        private String message;

        public MessageResponse() {
        }

        public MessageResponse(String message) {
            this.message = message;
        }

        public String getMessage() {
            return message;
        }

        public void setMessage(String message) {
            this.message = message;
        }
    }
}
