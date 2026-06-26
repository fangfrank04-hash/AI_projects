package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.TeamMember;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface TeamMemberRepository extends JpaRepository<TeamMember, Long> {
    List<TeamMember> findByProjectId(String projectId);
    void deleteByProjectId(String projectId);
}
