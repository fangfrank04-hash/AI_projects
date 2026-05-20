package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.ProjectProgramPlan;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface ProjectProgramPlanRepository extends JpaRepository<ProjectProgramPlan, Long> {
    List<ProjectProgramPlan> findByProjectIdOrderByParentIdAscSortOrderAsc(String projectId);
    List<ProjectProgramPlan> findByProjectIdAndParentIdIsNullOrderBySortOrder(String projectId);
    List<ProjectProgramPlan> findByProjectIdAndParentIdOrderBySortOrder(String projectId, Long parentId);
}
