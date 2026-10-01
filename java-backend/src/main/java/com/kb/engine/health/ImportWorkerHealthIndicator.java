package com.kb.engine.health;

import com.kb.engine.config.AiProperties;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/**
 * STEP10: probe Python import worker GET /health.
 */
@Component("importWorker")
public class ImportWorkerHealthIndicator implements HealthIndicator {

    private final String baseUrl;
    private final HttpClient httpClient;

    public ImportWorkerHealthIndicator(AiProperties aiProperties) {
        this.baseUrl = trimSlash(aiProperties.getImportBaseUrl());
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .build();
    }

    @Override
    public Health health() {
        return probe(baseUrl + "/health", "import-worker");
    }

    private Health probe(String url, String name) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(2))
                    .GET()
                    .build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() >= 200 && resp.statusCode() < 300) {
                return Health.up().withDetail("url", url).withDetail("service", name).build();
            }
            return Health.down()
                    .withDetail("url", url)
                    .withDetail("status", resp.statusCode())
                    .build();
        } catch (Exception e) {
            return Health.down(e).withDetail("url", url).build();
        }
    }

    private static String trimSlash(String url) {
        if (url == null || url.isBlank()) {
            return "http://127.0.0.1:8000";
        }
        return url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
    }
}
