package com.kb.engine.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kb.engine.config.AiProperties;
import com.kb.engine.dto.InternalQueryRunRequest;
import com.kb.engine.dto.InternalQueryRunResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * HTTP client for the Python query worker (:8001). STEP08: only internal run + optional history clear.
 */
@Component
public class QueryWorkerClient {

    private static final Logger log = LoggerFactory.getLogger(QueryWorkerClient.class);

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final String queryBaseUrl;

    public QueryWorkerClient(AiProperties aiProperties, ObjectMapper objectMapper) {
        this.queryBaseUrl = trimTrailingSlash(aiProperties.getQueryBaseUrl());
        this.objectMapper = objectMapper;

        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory();
        // Non-stream query may wait for full RAG pipeline.
        requestFactory.setReadTimeout(Duration.ofMinutes(10));

        this.restClient = RestClient.builder()
                .baseUrl(this.queryBaseUrl)
                .requestFactory(requestFactory)
                .build();
        log.info("QueryWorkerClient baseUrl={}", this.queryBaseUrl);
    }

    /**
     * STEP08: ask Python to run the query LangGraph.
     */
    public InternalQueryRunResponse runQuery(InternalQueryRunRequest body) {
        try {
            byte[] jsonBytes = objectMapper.writeValueAsBytes(body);
            log.info("POST {}/internal/query/run body={}", queryBaseUrl, new String(jsonBytes, StandardCharsets.UTF_8));
            String responseBody = restClient.post()
                    .uri("/internal/query/run")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(jsonBytes)
                    .exchange((request, response) -> {
                        String raw = response.bodyTo(String.class);
                        if (response.getStatusCode().isError()) {
                            throw new WorkerProxyException(response.getStatusCode(), raw);
                        }
                        return raw != null ? raw : "{}";
                    });
            log.info("query run response: {}", responseBody);
            return objectMapper.readValue(responseBody, InternalQueryRunResponse.class);
        } catch (WorkerProxyException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("Failed to call query worker: " + e.getMessage(), e);
        }
    }

    /**
     * Best-effort clear Python/Mongo history during transition.
     */
    public void clearHistory(String sessionId) {
        try {
            restClient.method(org.springframework.http.HttpMethod.DELETE)
                    .uri("/history/{sessionId}", sessionId)
                    .exchange((req, response) -> {
                        if (response.getStatusCode().isError()) {
                            log.warn("clear Mongo history failed: {}", response.getStatusCode());
                        }
                        return null;
                    });
        } catch (Exception e) {
            log.warn("clear Mongo history via Python failed: {}", e.getMessage());
        }
    }

    private static String trimTrailingSlash(String url) {
        if (url == null || url.isEmpty()) {
            return "http://127.0.0.1:8001";
        }
        return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }
}
