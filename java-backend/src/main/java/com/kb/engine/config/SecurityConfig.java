package com.kb.engine.config;

import org.springframework.context.annotation.Configuration;

/**
 * STEP10 — auth placeholder.
 * <p>
 * Intentionally empty. When adding login later:
 * <ol>
 *   <li>Add {@code spring-boot-starter-security}</li>
 *   <li>Define a {@code SecurityFilterChain} bean here</li>
 *   <li>Permit {@code /actuator/health}, {@code /front/**}, and keep
 *       {@code /internal/**} network-restricted</li>
 * </ol>
 * Do not enable full authentication in this hybrid phase.
 */
@Configuration
public class SecurityConfig {
    // Reserved for Spring Security integration.
}
