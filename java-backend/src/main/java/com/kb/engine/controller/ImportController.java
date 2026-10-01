package com.kb.engine.controller;

import com.kb.engine.dto.ImportDtos.TaskStatusResponse;
import com.kb.engine.dto.ImportDtos.UploadResponse;
import com.kb.engine.service.ImportOrchestrationService;
import com.kb.engine.service.TaskStatusService;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

@RestController
public class ImportController {

    private final ImportOrchestrationService importOrchestrationService;
    private final TaskStatusService taskStatusService;

    public ImportController(ImportOrchestrationService importOrchestrationService,
                            TaskStatusService taskStatusService) {
        this.importOrchestrationService = importOrchestrationService;
        this.taskStatusService = taskStatusService;
    }

    /**
     * STEP07: Java owns upload orchestration; Python only runs LangGraph.
     */
    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public UploadResponse upload(@RequestPart("file") MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new IllegalArgumentException("file is required");
        }
        return importOrchestrationService.uploadAndRun(file);
    }

    @GetMapping("/status/{taskId}")
    public TaskStatusResponse status(@PathVariable String taskId) {
        return taskStatusService.getStatus(taskId);
    }
}
