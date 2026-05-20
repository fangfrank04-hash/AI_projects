package com.ccdc.proposal.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * [MVP] 操作日志实体（修复 P1-5：补充缺失的 OperationLog 实体）
 */
@Entity
@Table(name = "operation_logs")
@Data
public class OperationLog {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "project_id", length = 50)
    private String projectId;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @Column(name = "operation", nullable = false, length = 100)
    private String operation;

    @Column(name = "details", columnDefinition = "TEXT")
    private String details;

    @Column(name = "ip_address", length = 50)
    private String ipAddress;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
