package com.kb.engine.service;

import com.kb.engine.client.ImportWorkerClient;
import com.kb.engine.dto.ImportDtos.UploadResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

/**
 * STEP07: Java owns upload / local save / MinIO / task init; Python only runs the graph.
 */
@Service
public class ImportOrchestrationService {

    private static final Logger log = LoggerFactory.getLogger(ImportOrchestrationService.class);

    private final FileUploadService fileUploadService;
    private final MinioStorageService minioStorageService;
    private final TaskStatusService taskStatusService;
    private final ImportWorkerClient importWorkerClient;

    public ImportOrchestrationService(FileUploadService fileUploadService,
                                      MinioStorageService minioStorageService,
                                      TaskStatusService taskStatusService,
                                      ImportWorkerClient importWorkerClient) {
        this.fileUploadService = fileUploadService;
        this.minioStorageService = minioStorageService;
        this.taskStatusService = taskStatusService;
        this.importWorkerClient = importWorkerClient;
    }

    public UploadResponse uploadAndRun(MultipartFile file) {
        String taskId = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        taskStatusService.startImportTask(taskId);

        long start = System.nanoTime();
        FileUploadService.SavedFile saved;
        try {
            saved = fileUploadService.saveToLocal(file);
        } catch (Exception e) {
            log.error("Save upload failed for task {}: {}", taskId, e.getMessage());
            taskStatusService.markTaskFailed(taskId);
            throw new IllegalStateException("Failed to save uploaded file: " + e.getMessage(), e);
        }

        double uploadSec = (System.nanoTime() - start) / 1_000_000_000.0;
        minioStorageService.backupOriginFile(saved.importFilePath(), saved.filename());
        taskStatusService.completeUploadNode(taskId, uploadSec);

        String importPath = saved.importFilePath().toAbsolutePath().toString();
        String fileDir = saved.fileDir().toAbsolutePath().toString();
        try {
            importWorkerClient.runImport(taskId, importPath, fileDir);
        } catch (Exception e) {
            log.error("Trigger Python import run failed for task {}: {}", taskId, e.getMessage());
            taskStatusService.markTaskFailed(taskId);
            throw e;
        }

        return new UploadResponse("上传成功", taskId);
    }
}
