package com.kb.engine.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * Body for POST /internal/history — Python dual-write mirror (STEP06).
 */
public class InternalHistoryRequest {

    private String sessionId;
    private String role;
    private String text;
    private String rewrittenQuery = "";
    private List<String> itemNames = new ArrayList<>();
    private Double ts;

    public String getSessionId() {
        return sessionId;
    }

    public void setSessionId(String sessionId) {
        this.sessionId = sessionId;
    }

    public String getRole() {
        return role;
    }

    public void setRole(String role) {
        this.role = role;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    public String getRewrittenQuery() {
        return rewrittenQuery;
    }

    public void setRewrittenQuery(String rewrittenQuery) {
        this.rewrittenQuery = rewrittenQuery;
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
