package com.ccdc.proposal.repository;

import com.ccdc.proposal.entity.HistoryRecord;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface HistoryRepository extends JpaRepository<HistoryRecord, Long> {
    List<HistoryRecord> findByUserIdOrderByCreatedAtDesc(String userId, Pageable pageable);
}
