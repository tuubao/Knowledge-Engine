package com.kb.engine.controller;

import com.kb.engine.dto.QueryDtos.QueryRequest;
import com.kb.engine.service.QueryOrchestrationService;
import com.kb.engine.service.SseBridgeService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@RestController
public class QueryController {

    private final QueryOrchestrationService queryOrchestrationService;
    private final SseBridgeService sseBridgeService;

    public QueryController(QueryOrchestrationService queryOrchestrationService,
                           SseBridgeService sseBridgeService) {
        this.queryOrchestrationService = queryOrchestrationService;
        this.sseBridgeService = sseBridgeService;
    }

    /**
     * STEP08: Java owns query orchestration (no Python /query proxy).
     */
    @PostMapping(value = "/query", consumes = MediaType.APPLICATION_JSON_VALUE)
    public Object query(@RequestBody QueryRequest request) {
        return queryOrchestrationService.handleQuery(request);
    }

    /**
     * STEP08: SSE from Redis events (no Python /stream proxy).
     */
    @GetMapping(value = "/stream/{taskId}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public ResponseEntity<StreamingResponseBody> stream(@PathVariable String taskId) {
        StreamingResponseBody body = sseBridgeService.stream(taskId);
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_EVENT_STREAM)
                .header("Cache-Control", "no-cache")
                .header("Connection", "keep-alive")
                .header("X-Accel-Buffering", "no")
                .body(body);
    }
}
