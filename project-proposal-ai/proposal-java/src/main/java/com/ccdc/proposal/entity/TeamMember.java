package com.ccdc.proposal.entity;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.*;
import lombok.Data;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;
import java.util.List;

@Entity
@Table(name = "team_members")
@Data
public class TeamMember {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @JsonIgnore
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "project_id", nullable = false)
    private Project project;

    @Column(name = "role", nullable = false, length = 50)
    private String role;

    @Column(name = "name", nullable = false, length = 50)
    private String name;

    @Column(name = "user_id", length = 50)
    private String userId;

    @Column(name = "nickname", length = 50)
    private String nickname;

    @Column(name = "role_ids", columnDefinition = "TEXT")
    @JdbcTypeCode(SqlTypes.JSON)
    private List<String> roleIds;

    @Column(name = "responsibilities", columnDefinition = "TEXT")
    @JdbcTypeCode(SqlTypes.JSON)
    private List<ResponsibilityItem> responsibilities;

    @Column(name = "created_at")
    private LocalDateTime createdAt;
}
