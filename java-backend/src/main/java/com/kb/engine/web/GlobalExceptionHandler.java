package com.kb.engine.web;

import com.kb.engine.client.WorkerProxyException;
import com.kb.engine.dto.ApiErrorResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.MultipartException;

/**
 * STEP10: unified error envelope for public APIs.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(WorkerProxyException.class)
    public ResponseEntity<ApiErrorResponse> handleWorkerProxy(WorkerProxyException ex) {
        log.warn("AI worker HTTP error: status={} body={}", ex.getStatusCode(), truncate(ex.getResponseBody()));
        return ResponseEntity.status(ex.getStatusCode())
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiErrorResponse.of("AI_WORKER_ERROR", "AI 服务返回错误")
                        .withDetail(truncate(ex.getResponseBody())));
    }

    @ExceptionHandler(ResourceAccessException.class)
    public ResponseEntity<ApiErrorResponse> handleWorkerUnreachable(ResourceAccessException ex) {
        log.warn("AI worker unreachable: {}", ex.getMostSpecificCause().getMessage());
        return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiErrorResponse.of("AI_WORKER_UNAVAILABLE", "查询或导入服务暂时不可用")
                        .withDetail(ex.getMostSpecificCause().getMessage()));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ApiErrorResponse> handleIllegalState(IllegalStateException ex) {
        String msg = ex.getMessage() != null ? ex.getMessage() : "illegal state";
        if (msg.contains("worker") || msg.contains("Worker") || msg.contains("import") || msg.contains("query")) {
            log.warn("Worker call failed: {}", msg);
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(ApiErrorResponse.of("AI_WORKER_UNAVAILABLE", "AI Worker 暂时不可用")
                            .withDetail(msg));
        }
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiErrorResponse.of("INTERNAL_ERROR", msg));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiErrorResponse> handleBadRequest(IllegalArgumentException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiErrorResponse.of("BAD_REQUEST",
                        ex.getMessage() != null ? ex.getMessage() : "bad request"));
    }

    @ExceptionHandler({MaxUploadSizeExceededException.class, MultipartException.class})
    public ResponseEntity<ApiErrorResponse> handleUpload(Exception ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiErrorResponse.of("INVALID_UPLOAD", "上传文件非法或超出大小限制")
                        .withDetail(ex.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiErrorResponse> handleOther(Exception ex) {
        log.error("Unhandled error", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .contentType(MediaType.APPLICATION_JSON)
                .body(ApiErrorResponse.of("INTERNAL_ERROR", "服务器内部错误")
                        .withDetail(ex.getMessage()));
    }

    private static String truncate(String s) {
        if (s == null) {
            return null;
        }
        return s.length() > 500 ? s.substring(0, 500) + "..." : s;
    }
}
