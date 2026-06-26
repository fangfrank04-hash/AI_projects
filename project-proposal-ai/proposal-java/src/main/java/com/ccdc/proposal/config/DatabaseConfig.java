package com.ccdc.proposal.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

@Configuration
@EnableJpaAuditing
public class DatabaseConfig {
    // JPA审计配置：自动填充 createdAt/updatedAt
}
