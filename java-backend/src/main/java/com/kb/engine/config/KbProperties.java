package com.kb.engine.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "kb")
public class KbProperties {

    /**
     * Shared temp directory with Python (repo temp_data/).
     */
    private String tempDataDir = "../temp_data";

    private String frontDir = "../front";

    private final Redis redis = new Redis();
    private final Minio minio = new Minio();

    public String getTempDataDir() {
        return tempDataDir;
    }

    public void setTempDataDir(String tempDataDir) {
        this.tempDataDir = tempDataDir;
    }

    public String getFrontDir() {
        return frontDir;
    }

    public void setFrontDir(String frontDir) {
        this.frontDir = frontDir;
    }

    public Redis getRedis() {
        return redis;
    }

    public Minio getMinio() {
        return minio;
    }

    public static class Redis {
        private boolean embedded = true;

        public boolean isEmbedded() {
            return embedded;
        }

        public void setEmbedded(boolean embedded) {
            this.embedded = embedded;
        }
    }

    public static class Minio {
        private boolean enabled = true;
        private String endpoint = "127.0.0.1:9000";
        private String accessKey = "minioadmin";
        private String secretKey = "minioadmin";
        private String bucketName = "knowledge-base-v1";
        private boolean secure = false;

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public String getEndpoint() {
            return endpoint;
        }

        public void setEndpoint(String endpoint) {
            this.endpoint = endpoint;
        }

        public String getAccessKey() {
            return accessKey;
        }

        public void setAccessKey(String accessKey) {
            this.accessKey = accessKey;
        }

        public String getSecretKey() {
            return secretKey;
        }

        public void setSecretKey(String secretKey) {
            this.secretKey = secretKey;
        }

        public String getBucketName() {
            return bucketName;
        }

        public void setBucketName(String bucketName) {
            this.bucketName = bucketName;
        }

        public boolean isSecure() {
            return secure;
        }

        public void setSecure(boolean secure) {
            this.secure = secure;
        }
    }
}
