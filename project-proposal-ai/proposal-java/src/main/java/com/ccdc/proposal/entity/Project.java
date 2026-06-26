package com.ccdc.proposal.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import jakarta.persistence.*;
import lombok.Data;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;

import java.time.LocalDateTime;
import java.util.List;

@Entity
@Table(name = "projects")
@Data
@JsonIgnoreProperties({"hibernateLazyInitializer", "handler"})
public class Project {
    @Id
    @Column(name = "id", length = 50)
    private String id;

    @Column(name = "name", nullable = false, length = 200)
    private String name;

    @Column(name = "dept", length = 100)
    private String dept;

    @Column(name = "base_req", length = 50)
    private String baseReq;

    @Column(name = "level", length = 10)
    private String level;

    @Column(name = "product_no", length = 50)
    private String productNo;

    @Column(name = "product_name", length = 200)
    private String productName;

    @Column(name = "req_dept", length = 100)
    private String reqDept;

    @Column(name = "change_req", length = 50)
    private String changeReq;

    @Column(name = "pm_name", nullable = false, length = 50)
    private String pmName;

    @Column(name = "proposal_background", columnDefinition = "TEXT")
    private String proposalBackground;

    @Column(name = "proposal_scope", columnDefinition = "TEXT")
    private String proposalScope;

    @Column(name = "status", length = 20)
    private String status = "待确认";

    @JsonIgnore
    @OneToMany(mappedBy = "project", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<TeamMember> teamMembers;

    @JsonIgnore
    @OneToOne(mappedBy = "project", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private Proposal proposal;

    @CreatedDate
    @Column(name = "created_at")
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;
}
