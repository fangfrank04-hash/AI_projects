package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.ProjectDeliverable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProjectDeliverableRepository extends JpaRepository<ProjectDeliverable, Long> {
    List<ProjectDeliverable> findByProjectId(String projectId);
    List<ProjectDeliverable> findByPlanId(Long planId);
}
