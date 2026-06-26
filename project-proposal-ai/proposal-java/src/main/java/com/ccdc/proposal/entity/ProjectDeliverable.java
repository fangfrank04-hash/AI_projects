package com.ccdc.proposal.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.Data;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;

import java.time.LocalDateTime;

@Entity
@Table(name = "project_deliverables")
@Data
@JsonIgnoreProperties({"hibernateLazyInitializer", "handler"})
public class ProjectDeliverable {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "project_id", nullable = false, length = 50)
    private String projectId;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "plan_id", nullable = false)
    private ProjectProgramPlan plan;

    @Column(name = "asset_name", nullable = false, length = 200)
    private String assetName;

    @Column(name = "asset_type", length = 50)
    private String assetType;

    @Column(name = "required")
    private Boolean required = true;

    @Column(name = "cut_result", length = 20)
    private String cutResult;

    @Column(name = "cut_result_explain", columnDefinition = "TEXT")
    private String cutResultExplain;

    @CreatedDate
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
