package com.kb.engine.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "ai")
public class AiProperties {

    /**
     * Python import worker base URL (default port 8000).
     */
    private String importBaseUrl = "http://127.0.0.1:8000";

    /**
     * Python query worker base URL (default port 8001).
     */
    private String queryBaseUrl = "http://127.0.0.1:8001";

    public String getImportBaseUrl() {
        return importBaseUrl;
    }

    public void setImportBaseUrl(String importBaseUrl) {
        this.importBaseUrl = importBaseUrl;
    }

    public String getQueryBaseUrl() {
        return queryBaseUrl;
    }

    public void setQueryBaseUrl(String queryBaseUrl) {
        this.queryBaseUrl = queryBaseUrl;
    }
}
