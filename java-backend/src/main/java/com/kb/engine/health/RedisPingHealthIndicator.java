package com.kb.engine.health;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.stereotype.Component;

/**
 * STEP10: lightweight Redis probe (PING). Default RedisHealthIndicator uses INFO,
 * which embedded Redis often does not support.
 */
@Component("redisPing")
public class RedisPingHealthIndicator implements HealthIndicator {

    private final RedisConnectionFactory connectionFactory;

    public RedisPingHealthIndicator(RedisConnectionFactory connectionFactory) {
        this.connectionFactory = connectionFactory;
    }

    @Override
    public Health health() {
        try (var connection = connectionFactory.getConnection()) {
            String pong = connection.ping();
            return Health.up().withDetail("ping", pong != null ? pong : "PONG").build();
        } catch (Exception e) {
            return Health.down(e).build();
        }
    }
}
