package com.kb.engine.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.kb.engine.config.AiProperties;
import com.kb.engine.dto.InternalImportRunRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;

/**
 * HTTP client for the Python import worker (:8000).
 */
@Component
public class ImportWorkerClient {

    private static final Logger log = LoggerFactory.getLogger(ImportWorkerClient.class);

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final String importBaseUrl;

    public ImportWorkerClient(AiProperties aiProperties, ObjectMapper objectMapper) {
        this.importBaseUrl = aiProperties.getImportBaseUrl();
        this.objectMapper = objectMapper;
        JdkClientHttpRequestFactory requestFactory = new JdkClientHttpRequestFactory();
        requestFactory.setReadTimeout(Duration.ofMinutes(2));

        this.restClient = RestClient.builder()
                .baseUrl(this.importBaseUrl)
                .requestFactory(requestFactory)
                .build();
        log.info("ImportWorkerClient baseUrl={}", this.importBaseUrl);
    }

    /**
     * STEP07: ask Python to run the import LangGraph in background.
     */
    public void runImport(String taskId, String importFilePath, String fileDir) {
        try {
            InternalImportRunRequest body = new InternalImportRunRequest(taskId, importFilePath, fileDir);
            // Write bytes ourselves so Jackson does not double-encode a String body.
            byte[] jsonBytes = objectMapper.writeValueAsBytes(body);
            log.info("POST {}/internal/import/run body={}", importBaseUrl, new String(jsonBytes, java.nio.charset.StandardCharsets.UTF_8));
            String responseBody = restClient.post()
                    .uri("/internal/import/run")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(jsonBytes)
                    .exchange((request, response) -> {
                        String raw = response.bodyTo(String.class);
                        if (response.getStatusCode().isError()) {
                            throw new WorkerProxyException(response.getStatusCode(), raw);
                        }
                        return raw;
                    });
            log.info("import run accepted: {}", responseBody);
        } catch (WorkerProxyException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("Failed to call import worker: " + e.getMessage(), e);
        }
    }
}
