package com.kb.engine.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.kb.engine.redis.RedisTaskKeys;
import com.kb.engine.redis.RedisTaskRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Bridges Redis pub/sub (+ event buffer) to browser SSE (STEP08).
 * Emits legacy event names: progress / delta / final for chat.html compatibility.
 */
@Service
public class SseBridgeService {

    private static final Logger log = LoggerFactory.getLogger(SseBridgeService.class);

    private final RedisConnectionFactory connectionFactory;
    private final RedisTaskRepository redisTaskRepository;
    private final ObjectMapper objectMapper;
    private final ChatHistoryService chatHistoryService;
    private final TaskStatusService taskStatusService;

    public SseBridgeService(RedisConnectionFactory connectionFactory,
                            RedisTaskRepository redisTaskRepository,
                            ObjectMapper objectMapper,
                            ChatHistoryService chatHistoryService,
                            TaskStatusService taskStatusService) {
        this.connectionFactory = connectionFactory;
        this.redisTaskRepository = redisTaskRepository;
        this.objectMapper = objectMapper;
        this.chatHistoryService = chatHistoryService;
        this.taskStatusService = taskStatusService;
    }

    public StreamingResponseBody stream(String taskId) {
        return outputStream -> {
            BlockingQueue<String> queue = new LinkedBlockingQueue<>();
            AtomicBoolean terminal = new AtomicBoolean(false);

            RedisMessageListenerContainer container = new RedisMessageListenerContainer();
            container.setConnectionFactory(connectionFactory);
            MessageListener listener = (Message message, byte[] pattern) -> {
                queue.offer(new String(message.getBody(), StandardCharsets.UTF_8));
            };
            container.addMessageListener(listener, new ChannelTopic(RedisTaskKeys.eventsChannel(taskId)));
            try {
                container.afterPropertiesSet();
                container.start();

                // Replay buffered events that may have arrived before subscribe
                for (String buffered : redisTaskRepository.getEventBuffer(taskId)) {
                    if (writeSseEvent(outputStream, buffered, taskId, terminal)) {
                        return;
                    }
                }

                // Already completed? emit final from result hash
                Map<String, String> result = redisTaskRepository.getResult(taskId);
                String status = redisTaskRepository.getTaskStatus(taskId).getStatus();
                if ("completed".equals(status) && result.containsKey("answer") && !terminal.get()) {
                    String finalJson = buildFinalEnvelope(result);
                    writeSseEvent(outputStream, finalJson, taskId, terminal);
                    return;
                }

                while (!terminal.get()) {
                    String raw = queue.poll(15, TimeUnit.SECONDS);
                    if (raw == null) {
                        // heartbeat comment keeps proxies from buffering forever
                        outputStream.write(": ping\n\n".getBytes(StandardCharsets.UTF_8));
                        outputStream.flush();
                        // re-check completion
                        Map<String, String> r2 = redisTaskRepository.getResult(taskId);
                        String st = redisTaskRepository.getTaskStatus(taskId).getStatus();
                        if (("completed".equals(st) || "failed".equals(st)) && r2.containsKey("answer")) {
                            writeSseEvent(outputStream, buildFinalEnvelope(r2), taskId, terminal);
                            break;
                        }
                        continue;
                    }
                    if (writeSseEvent(outputStream, raw, taskId, terminal)) {
                        break;
                    }
                }
            } catch (IOException e) {
                log.info("SSE client disconnected for task {}: {}", taskId, e.getMessage());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            } finally {
                try {
                    container.stop();
                } catch (Exception ignored) {
                }
                try {
                    container.destroy();
                } catch (Exception ignored) {
                }
            }
        };
    }

    /**
     * @return true if terminal event was written
     */
    private boolean writeSseEvent(OutputStream out, String raw, String taskId, AtomicBoolean terminal)
            throws IOException {
        JsonNode root;
        try {
            root = objectMapper.readTree(raw);
        } catch (Exception e) {
            log.debug("skip bad redis event: {}", e.getMessage());
            return false;
        }

        String event = resolveEventName(root);
        JsonNode dataNode = root.has("data") && root.get("data").isObject() ? root.get("data") : root;
        // Build browser payload (strip envelope keys)
        Map<String, Object> payload = objectMapper.convertValue(dataNode, new TypeReference<Map<String, Object>>() {
        });
        payload.remove("event");
        payload.remove("type");
        payload.remove("task_id");
        payload.remove("data");

        // Map token → delta for chat.html
        if ("delta".equals(event) && payload.containsKey("text") && !payload.containsKey("delta")) {
            payload.put("delta", payload.get("text"));
        }
        if ("token".equals(root.path("type").asText()) && !payload.containsKey("delta")) {
            event = "delta";
            Object text = payload.get("text");
            if (text != null) {
                payload.put("delta", text);
            }
        }

        String dataJson = objectMapper.writeValueAsString(payload);
        String chunk = "event: " + event + "\ndata: " + dataJson + "\n\n";
        out.write(chunk.getBytes(StandardCharsets.UTF_8));
        out.flush();

        if ("final".equals(event) || "final_answer".equals(event) || "done".equals(root.path("type").asText())) {
            terminal.set(true);
            persistHistoryFromFinal(taskId, payload);
            return true;
        }
        if ("error".equals(event) || "error".equals(root.path("type").asText())) {
            terminal.set(true);
            return true;
        }
        return false;
    }

    private String resolveEventName(JsonNode root) {
        if (root.hasNonNull("event")) {
            String e = root.get("event").asText();
            if ("done".equals(e)) {
                return "final";
            }
            if ("token".equals(e)) {
                return "delta";
            }
            return e;
        }
        String type = root.path("type").asText("");
        return switch (type) {
            case "token" -> "delta";
            case "done" -> "final";
            case "error" -> "error";
            default -> "progress";
        };
    }

    private String buildFinalEnvelope(Map<String, String> result) throws IOException {
        Map<String, Object> data = new java.util.HashMap<>();
        data.put("answer", result.getOrDefault("answer", ""));
        data.put("rewritten_query", result.getOrDefault("rewritten_query", ""));
        data.put("status", "completed");
        try {
            List<String> names = objectMapper.readValue(
                    result.getOrDefault("item_names", "[]"),
                    new TypeReference<List<String>>() {
                    });
            data.put("item_names", names);
        } catch (Exception e) {
            data.put("item_names", new ArrayList<String>());
        }
        Map<String, Object> envelope = new java.util.HashMap<>();
        envelope.put("event", "final");
        envelope.put("type", "done");
        envelope.put("data", data);
        envelope.putAll(data);
        return objectMapper.writeValueAsString(envelope);
    }

    private void persistHistoryFromFinal(String taskId, Map<String, Object> payload) {
        PendingQueryContext ctx = PendingQueryContext.get(taskId);
        if (ctx == null || ctx.isHistoryWritten()) {
            return;
        }
        synchronized (ctx) {
            if (ctx.isHistoryWritten()) {
                return;
            }
            String answer = stringVal(payload.get("answer"));
            String rewritten = stringVal(payload.get("rewritten_query"));
            List<String> itemNames = toStringList(payload.get("item_names"));
            double now = System.currentTimeMillis() / 1000.0;
            chatHistoryService.appendMessage(ctx.getSessionId(), "user", ctx.getQuery(), rewritten, itemNames, now);
            chatHistoryService.appendMessage(ctx.getSessionId(), "assistant", answer, rewritten, itemNames, now + 0.001);
            taskStatusService.completeQueryTask(taskId, answer);
            ctx.markHistoryWritten();
            PendingQueryContext.remove(taskId);
        }
    }

    private static String stringVal(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    @SuppressWarnings("unchecked")
    private List<String> toStringList(Object o) {
        if (o instanceof List<?> list) {
            List<String> out = new ArrayList<>();
            for (Object item : list) {
                if (item != null) {
                    out.add(String.valueOf(item));
                }
            }
            return out;
        }
        if (o instanceof String s && !s.isBlank()) {
            try {
                return objectMapper.readValue(s, new TypeReference<List<String>>() {
                });
            } catch (Exception ignored) {
            }
        }
        return new ArrayList<>();
    }
}
