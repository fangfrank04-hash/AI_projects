package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.RelatedProject;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface RelatedProjectRepository extends JpaRepository<RelatedProject, Long> {
    List<RelatedProject> findByProjectId(String projectId);
}
