package com.kb.engine.dto;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Aligns with Python schema.upload_schema.UploadResponse / TaskStatusResponse (snake_case JSON).
 */
public final class ImportDtos {

    private ImportDtos() {
    }

    public static class UploadResponse {
        private String message;
        private String taskId;

        public UploadResponse() {
        }

        public UploadResponse(String message, String taskId) {
            this.message = message;
            this.taskId = taskId;
        }

        public String getMessage() {
            return message;
        }

        public void setMessage(String message) {
            this.message = message;
        }

        public String getTaskId() {
            return taskId;
        }

        public void setTaskId(String taskId) {
            this.taskId = taskId;
        }
    }

    public static class TaskStatusResponse {
        private String status = "";
        private List<String> doneList = new ArrayList<>();
        private List<String> runningList = new ArrayList<>();
        private Map<String, Double> durations = new HashMap<>();

        public String getStatus() {
            return status;
        }

        public void setStatus(String status) {
            this.status = status;
        }

        public List<String> getDoneList() {
            return doneList;
        }

        public void setDoneList(List<String> doneList) {
            this.doneList = doneList != null ? doneList : new ArrayList<>();
        }

        public List<String> getRunningList() {
            return runningList;
        }

        public void setRunningList(List<String> runningList) {
            this.runningList = runningList != null ? runningList : new ArrayList<>();
        }

        public Map<String, Double> getDurations() {
            return durations;
        }

        public void setDurations(Map<String, Double> durations) {
            this.durations = durations != null ? durations : new HashMap<>();
        }
    }
}
