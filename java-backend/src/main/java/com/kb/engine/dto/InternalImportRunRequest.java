package com.kb.engine.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Body for POST /internal/import/run (STEP07).
 */
public class InternalImportRunRequest {

    private String taskId;
    private String importFilePath;
    private String fileDir;

    public InternalImportRunRequest() {
    }

    public InternalImportRunRequest(String taskId, String importFilePath, String fileDir) {
        this.taskId = taskId;
        this.importFilePath = importFilePath;
        this.fileDir = fileDir;
    }

    @JsonProperty("task_id")
    public String getTaskId() {
        return taskId;
    }

    @JsonProperty("task_id")
    public void setTaskId(String taskId) {
        this.taskId = taskId;
    }

    @JsonProperty("import_file_path")
    public String getImportFilePath() {
        return importFilePath;
    }

    @JsonProperty("import_file_path")
    public void setImportFilePath(String importFilePath) {
        this.importFilePath = importFilePath;
    }

    @JsonProperty("file_dir")
    public String getFileDir() {
        return fileDir;
    }

    @JsonProperty("file_dir")
    public void setFileDir(String fileDir) {
        this.fileDir = fileDir;
    }
}
