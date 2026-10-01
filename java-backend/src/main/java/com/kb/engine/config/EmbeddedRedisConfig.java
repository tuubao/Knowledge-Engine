package com.kb.engine.config;

import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import redis.embedded.RedisServer;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;

/**
 * Starts an embedded Redis on the configured port when nothing is listening (dev only).
 * Runs early so Lettuce can connect on first use.
 */
@Configuration
@Profile("dev")
@Order(Ordered.HIGHEST_PRECEDENCE)
public class EmbeddedRedisConfig {

    private static final Logger log = LoggerFactory.getLogger(EmbeddedRedisConfig.class);

    @Value("${spring.data.redis.host:127.0.0.1}")
    private String host;

    @Value("${spring.data.redis.port:6379}")
    private int port;

    @Value("${kb.redis.embedded:true}")
    private boolean embeddedEnabled;

    private RedisServer redisServer;

    @PostConstruct
    public void startEmbeddedIfNeeded() throws IOException {
        if (!embeddedEnabled) {
            log.info("kb.redis.embedded=false, skip embedded Redis");
            return;
        }
        if (isPortOpen(host, port)) {
            log.info("Redis already listening on {}:{}, skip embedded", host, port);
            return;
        }
        log.info("Starting embedded Redis on port {}", port);
        redisServer = RedisServer.newRedisServer()
                .port(port)
                .build();
        redisServer.start();
        log.info("Embedded Redis started on port {}", port);
    }

    @PreDestroy
    public void stopEmbedded() throws IOException {
        if (redisServer != null) {
            redisServer.stop();
            log.info("Embedded Redis stopped");
        }
    }

    private static boolean isPortOpen(String host, int port) {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(host, port), 200);
            return true;
        } catch (Exception e) {
            return false;
        }
    }
}
