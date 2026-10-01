package com.kb.engine.client;

import org.springframework.http.HttpStatusCode;

/**
 * Raised when the Python import/query worker returns a non-2xx response.
 * Carries status and raw body so the gateway can pass them through.
 */
public class WorkerProxyException extends RuntimeException {

    private final HttpStatusCode statusCode;
    private final String responseBody;

    public WorkerProxyException(HttpStatusCode statusCode, String responseBody) {
        super("AI worker error: " + statusCode.value());
        this.statusCode = statusCode;
        this.responseBody = responseBody != null ? responseBody : "";
    }

    public HttpStatusCode getStatusCode() {
        return statusCode;
    }

    public String getResponseBody() {
        return responseBody;
    }
}
