package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.ProposalStep;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface ProposalStepRepository extends JpaRepository<ProposalStep, Long> {
    List<ProposalStep> findByProposalId(Long proposalId);
    Optional<ProposalStep> findByProposalIdAndStepNumber(Long proposalId, Integer stepNumber);
}
