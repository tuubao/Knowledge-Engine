package com.kb.engine.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kb.engine.client.QueryWorkerClient;
import com.kb.engine.dto.QueryDtos.HistoryItem;
import com.kb.engine.dto.QueryDtos.HistoryResponse;
import com.kb.engine.dto.QueryDtos.MessageResponse;
import com.kb.engine.entity.KbChatMessage;
import com.kb.engine.mapper.KbChatMessageMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Chat history backed by MySQL (STEP06).
 * Python may still write Mongo during the dual-write transition; this service is the
 * source of truth for public GET/DELETE /history APIs.
 */
@Service
public class ChatHistoryService {

    private static final Logger log = LoggerFactory.getLogger(ChatHistoryService.class);

    private final KbChatMessageMapper chatMessageMapper;
    private final ObjectMapper objectMapper;
    private final QueryWorkerClient queryWorkerClient;

    public ChatHistoryService(KbChatMessageMapper chatMessageMapper,
                              ObjectMapper objectMapper,
                              QueryWorkerClient queryWorkerClient) {
        this.chatMessageMapper = chatMessageMapper;
        this.objectMapper = objectMapper;
        this.queryWorkerClient = queryWorkerClient;
    }

    public HistoryResponse getHistory(String sessionId) {
        List<KbChatMessage> rows = chatMessageMapper.listBySessionId(sessionId);
        List<HistoryItem> items = new ArrayList<>();
        for (KbChatMessage row : rows) {
            items.add(toHistoryItem(row));
        }
        HistoryResponse response = new HistoryResponse();
        response.setSessionId(sessionId);
        response.setItems(items);
        return response;
    }

    /**
     * Clear MySQL history; also best-effort clear Python/Mongo during dual-write period.
     */
    public MessageResponse clearHistory(String sessionId) {
        int deleted = chatMessageMapper.deleteBySessionId(sessionId);
        try {
            queryWorkerClient.clearHistory(sessionId);
        } catch (Exception e) {
            log.warn("Failed to clear Mongo history via Python for session {}: {}", sessionId, e.getMessage());
        }
        return new MessageResponse("会话 " + sessionId + " 的历史记录已清空 (" + deleted + " rows)");
    }

    /**
     * Internal write used by Python dual-write (STEP06 plan A).
     */
    public HistoryItem appendMessage(String sessionId,
                                     String role,
                                     String text,
                                     String rewrittenQuery,
                                     List<String> itemNames,
                                     Double ts) {
        KbChatMessage message = new KbChatMessage();
        message.setSessionId(sessionId);
        message.setRole(role != null ? role : "");
        message.setText(text != null ? text : "");
        message.setRewrittenQuery(rewrittenQuery != null ? rewrittenQuery : "");
        message.setItemNames(toJsonArray(itemNames));
        message.setTs(ts != null ? ts : (System.currentTimeMillis() / 1000.0));
        chatMessageMapper.insert(message);
        return toHistoryItem(message);
    }

    private HistoryItem toHistoryItem(KbChatMessage row) {
        HistoryItem item = new HistoryItem();
        item.setId(row.getId() != null ? String.valueOf(row.getId()) : "");
        item.setSessionId(row.getSessionId());
        item.setRole(row.getRole());
        item.setText(row.getText());
        item.setRewrittenQuery(row.getRewrittenQuery());
        item.setItemNames(parseJsonArray(row.getItemNames()));
        item.setTs(row.getTs());
        return item;
    }

    private String toJsonArray(List<String> itemNames) {
        try {
            List<String> safe = itemNames != null ? itemNames : Collections.emptyList();
            return objectMapper.writeValueAsString(safe);
        } catch (Exception e) {
            return "[]";
        }
    }

    private List<String> parseJsonArray(String json) {
        if (json == null || json.isBlank()) {
            return new ArrayList<>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<List<String>>() {
            });
        } catch (Exception e) {
            return new ArrayList<>();
        }
    }
}
