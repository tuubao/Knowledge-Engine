package com.kb.engine.service;

import com.kb.engine.config.KbProperties;
import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.UploadObjectArgs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.nio.file.Path;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * Best-effort MinIO backup (failures must not block import).
 */
@Service
public class MinioStorageService {

    private static final Logger log = LoggerFactory.getLogger(MinioStorageService.class);
    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final KbProperties kbProperties;
    private volatile MinioClient client;

    public MinioStorageService(KbProperties kbProperties) {
        this.kbProperties = kbProperties;
    }

    public void backupOriginFile(Path localFile, String filename) {
        KbProperties.Minio cfg = kbProperties.getMinio();
        if (!cfg.isEnabled()) {
            return;
        }
        try {
            MinioClient minio = getClient();
            String bucket = cfg.getBucketName();
            ensureBucket(minio, bucket);
            String objectName = "origin_files/" + LocalDate.now().format(DAY) + "/" + filename;
            minio.uploadObject(
                    UploadObjectArgs.builder()
                            .bucket(bucket)
                            .object(objectName)
                            .filename(localFile.toAbsolutePath().toString())
                            .build()
            );
            log.info("MinIO backup ok: {}/{}", bucket, objectName);
        } catch (Exception e) {
            log.warn("MinIO backup failed (ignored): {}", e.getMessage());
        }
    }

    private MinioClient getClient() {
        if (client == null) {
            synchronized (this) {
                if (client == null) {
                    KbProperties.Minio cfg = kbProperties.getMinio();
                    client = MinioClient.builder()
                            .endpoint((cfg.isSecure() ? "https://" : "http://") + cfg.getEndpoint())
                            .credentials(cfg.getAccessKey(), cfg.getSecretKey())
                            .build();
                }
            }
        }
        return client;
    }

    private void ensureBucket(MinioClient minio, String bucket) throws Exception {
        boolean exists = minio.bucketExists(BucketExistsArgs.builder().bucket(bucket).build());
        if (!exists) {
            minio.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
        }
    }
}
