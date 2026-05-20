package com.ccdc.proposal.entity;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.Data;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;

import java.time.LocalDateTime;
import java.util.List;

@Entity
@Table(name = "project_program_plans")
@Data
@JsonIgnoreProperties({"hibernateLazyInitializer", "handler"})
public class ProjectProgramPlan {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "project_id", nullable = false, length = 50)
    private String projectId;

    @Column(name = "task_no", length = 50)
    private String taskNo;

    @Column(name = "task_name", nullable = false, length = 200)
    private String taskName;

    @Column(name = "phase", length = 50)
    private String phase;

    @Column(name = "required")
    private Boolean required = true;

    @Column(name = "cut_result", length = 20)
    private String cutResult;

    @Column(name = "cut_result_explain", columnDefinition = "TEXT")
    private String cutResultExplain;

    @Column(name = "parent_id")
    private Long parentId;

    @Column(name = "sort_order")
    private Integer sortOrder = 0;

    @OneToMany(mappedBy = "plan", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<ProjectDeliverable> deliverables;

    @CreatedDate
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
