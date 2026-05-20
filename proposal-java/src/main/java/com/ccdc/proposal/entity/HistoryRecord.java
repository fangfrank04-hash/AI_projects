package com.ccdc.proposal.entity;

import jakarta.persistence.*;
import lombok.Data;

import java.time.LocalDateTime;

@Entity
@Table(name = "history_records")
@Data
public class HistoryRecord {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false, length = 50)
    private String userId;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @Column(name = "project_name", length = 200)
    private String projectName;

    @Column(name = "project_level", length = 10)
    private String projectLevel;

    @Column(name = "snapshot", columnDefinition = "TEXT")
    private String snapshot;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
