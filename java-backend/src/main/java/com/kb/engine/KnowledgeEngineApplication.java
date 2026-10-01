package com.kb.engine;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.kb.engine.mapper")
public class KnowledgeEngineApplication {

    public static void main(String[] args) {
        SpringApplication.run(KnowledgeEngineApplication.class, args);
    }
}
