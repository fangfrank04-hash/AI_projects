package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.KnowledgeRule;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface KnowledgeRepository extends JpaRepository<KnowledgeRule, Long> {
    List<KnowledgeRule> findByProjectLevelAndRuleTypeAndIsActiveTrue(String projectLevel, String ruleType);
    List<KnowledgeRule> findByProjectLevelAndIsActiveTrue(String projectLevel);
}
