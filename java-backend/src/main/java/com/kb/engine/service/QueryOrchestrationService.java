package com.kb.engine.service;

import com.kb.engine.client.QueryWorkerClient;
import com.kb.engine.dto.InternalQueryRunRequest;
import com.kb.engine.dto.InternalQueryRunResponse;
import com.kb.engine.dto.QueryDtos.QueryRequest;
import com.kb.engine.dto.QueryDtos.QueryResponse;
import com.kb.engine.dto.QueryDtos.StreamSubmitResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * STEP08: Java owns query task creation, history writes, and SSE; Python only runs the graph.
 */
@Service
public class QueryOrchestrationService {

    private static final Logger log = LoggerFactory.getLogger(QueryOrchestrationService.class);

    private final QueryWorkerClient queryWorkerClient;
    private final TaskStatusService taskStatusService;
    private final ChatHistoryService chatHistoryService;
    private final ExecutorService asyncRunner = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "query-run-async");
        t.setDaemon(true);
        return t;
    });

    public QueryOrchestrationService(QueryWorkerClient queryWorkerClient,
                                     TaskStatusService taskStatusService,
                                     ChatHistoryService chatHistoryService) {
        this.queryWorkerClient = queryWorkerClient;
        this.taskStatusService = taskStatusService;
        this.chatHistoryService = chatHistoryService;
    }

    public Object handleQuery(QueryRequest request) {
        if (request.getQuery() == null || request.getQuery().isBlank()) {
            throw new IllegalArgumentException("query is required");
        }
        String sessionId = request.getSessionId();
        if (sessionId == null || sessionId.isBlank()) {
            sessionId = UUID.randomUUID().toString();
        }
        String taskId = UUID.randomUUID().toString().replace("-", "").substring(0, 12);
        taskStatusService.startQueryTask(taskId, sessionId, request.getQuery());
        PendingQueryContext.put(new PendingQueryContext(taskId, sessionId, request.getQuery()));

        if (request.getIsStream()) {
            String sid = sessionId;
            asyncRunner.submit(() -> {
                try {
                    queryWorkerClient.runQuery(new InternalQueryRunRequest(taskId, sid, request.getQuery(), true));
                } catch (Exception e) {
                    log.error("Async query run failed for task {}: {}", taskId, e.getMessage());
                    taskStatusService.markTaskFailed(taskId);
                }
            });
            StreamSubmitResponse resp = new StreamSubmitResponse();
            resp.setMessage("查询请求已经提交");
            resp.setSessionId(sessionId);
            resp.setTaskId(taskId);
            return resp;
        }

        try {
            InternalQueryRunResponse workerResp = queryWorkerClient.runQuery(
                    new InternalQueryRunRequest(taskId, sessionId, request.getQuery(), false));
            String answer = workerResp.getAnswer() != null ? workerResp.getAnswer() : "";
            String rewritten = workerResp.getRewrittenQuery() != null ? workerResp.getRewrittenQuery() : "";
            List<String> itemNames = workerResp.getItemNames() != null ? workerResp.getItemNames() : List.of();
            writeHistoryOnce(taskId, sessionId, request.getQuery(), answer, rewritten, itemNames);
            taskStatusService.completeQueryTask(taskId, answer);

            QueryResponse resp = new QueryResponse();
            resp.setMessage("查询请求已处理完成");
            resp.setSessionId(sessionId);
            resp.setAnswer(answer);
            resp.setDoneList(workerResp.getDoneList() != null ? workerResp.getDoneList() : List.of());
            return resp;
        } catch (Exception e) {
            taskStatusService.markTaskFailed(taskId);
            PendingQueryContext.remove(taskId);
            throw e;
        }
    }

    private void writeHistoryOnce(String taskId, String sessionId, String query,
                                  String answer, String rewritten, List<String> itemNames) {
        PendingQueryContext ctx = PendingQueryContext.get(taskId);
        if (ctx != null && ctx.isHistoryWritten()) {
            return;
        }
        double now = System.currentTimeMillis() / 1000.0;
        chatHistoryService.appendMessage(sessionId, "user", query, rewritten, itemNames, now);
        chatHistoryService.appendMessage(sessionId, "assistant", answer, rewritten, itemNames, now + 0.001);
        if (ctx != null) {
            ctx.markHistoryWritten();
            PendingQueryContext.remove(taskId);
        }
    }
}
