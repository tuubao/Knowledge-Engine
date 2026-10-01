package com.kb.engine.service;

import com.kb.engine.config.KbProperties;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;

/**
 * Saves uploaded files under shared {@code temp_data/yyyyMMdd/} (same layout as Python).
 */
@Service
public class FileUploadService {

    private static final DateTimeFormatter DAY = DateTimeFormatter.ofPattern("yyyyMMdd");

    private final KbProperties kbProperties;

    public FileUploadService(KbProperties kbProperties) {
        this.kbProperties = kbProperties;
    }

    public record SavedFile(Path importFilePath, Path fileDir, String filename) {
    }

    public SavedFile saveToLocal(MultipartFile file) throws IOException {
        String original = file.getOriginalFilename();
        if (original == null || original.isBlank()) {
            original = "upload.bin";
        }
        // Prevent path traversal
        String filename = Paths.get(original).getFileName().toString();

        Path baseDir = Paths.get(kbProperties.getTempDataDir())
                .toAbsolutePath()
                .normalize()
                .resolve(LocalDate.now().format(DAY));
        Files.createDirectories(baseDir);

        Path target = baseDir.resolve(filename);
        file.transferTo(target);
        return new SavedFile(target, baseDir, filename);
    }
}
