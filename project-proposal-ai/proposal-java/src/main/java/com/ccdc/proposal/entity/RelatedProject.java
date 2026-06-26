package com.ccdc.proposal.entity;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.Data;
import org.springframework.data.annotation.CreatedDate;

import java.time.LocalDateTime;

@Entity
@Table(name = "related_projects")
@Data
@JsonIgnoreProperties({"hibernateLazyInitializer", "handler"})
public class RelatedProject {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "project_id", nullable = false, length = 50)
    private String projectId;

    @Column(name = "rel_project_id", nullable = false, length = 50)
    private String relProjectId;

    @Column(name = "rel_type", length = 50)
    private String relType;

    @CreatedDate
    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
