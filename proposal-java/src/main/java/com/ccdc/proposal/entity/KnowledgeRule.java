package com.ccdc.proposal.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Entity
@Table(name = "knowledge_rules")
@Data
public class KnowledgeRule {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "project_level", nullable = false, length = 10)
    private String projectLevel;

    @Column(name = "rule_type", nullable = false, length = 50)
    private String ruleType;

    @Column(name = "rule_content", nullable = false, columnDefinition = "TEXT")
    private String ruleContent;

    @Column(name = "version", length = 20)
    private String version;

    @Column(name = "is_active")
    private Boolean isActive = true;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
