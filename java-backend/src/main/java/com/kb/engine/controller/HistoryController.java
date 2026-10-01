package com.kb.engine.controller;

import com.kb.engine.dto.InternalHistoryRequest;
import com.kb.engine.dto.QueryDtos.HistoryItem;
import com.kb.engine.dto.QueryDtos.HistoryResponse;
import com.kb.engine.dto.QueryDtos.MessageResponse;
import com.kb.engine.service.ChatHistoryService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HistoryController {

    private final ChatHistoryService chatHistoryService;

    public HistoryController(ChatHistoryService chatHistoryService) {
        this.chatHistoryService = chatHistoryService;
    }

    @GetMapping("/history/{sessionId}")
    public HistoryResponse getHistory(@PathVariable String sessionId) {
        return chatHistoryService.getHistory(sessionId);
    }

    @DeleteMapping("/history/{sessionId}")
    public MessageResponse clearHistory(@PathVariable String sessionId) {
        return chatHistoryService.clearHistory(sessionId);
    }

    /**
     * Internal dual-write endpoint for Python (STEP06 plan A).
     * Not for browser use.
     */
    @PostMapping("/internal/history")
    public HistoryItem appendHistory(@RequestBody InternalHistoryRequest request) {
        if (request.getSessionId() == null || request.getSessionId().isBlank()) {
            throw new IllegalArgumentException("session_id is required");
        }
        if (request.getRole() == null || request.getRole().isBlank()) {
            throw new IllegalArgumentException("role is required");
        }
        return chatHistoryService.appendMessage(
                request.getSessionId(),
                request.getRole(),
                request.getText(),
                request.getRewrittenQuery(),
                request.getItemNames(),
                request.getTs()
        );
    }
}
