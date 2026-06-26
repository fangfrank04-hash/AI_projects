package com.ccdc.proposal.service;

import com.ccdc.proposal.entity.HistoryRecord;
import com.ccdc.proposal.entity.Proposal;
import com.ccdc.proposal.entity.ProposalStep;
import com.ccdc.proposal.repository.HistoryRepository;
import com.ccdc.proposal.repository.ProposalRepository;
import com.ccdc.proposal.repository.ProposalStepRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.*;

@Service
@Slf4j
public class HistoryService {

    @Resource
    private HistoryRepository historyRepository;

    @Resource
    private ProposalRepository proposalRepository;

    @Resource
    private ProposalStepRepository stepRepository;

    @Resource
    private ObjectMapper objectMapper;

    /**
     * 获取用户历史填写数据
     */
    public List<Map<String, Object>> getUserHistory(String userId, int limit) {
        List<HistoryRecord> records = historyRepository
                .findByUserIdOrderByCreatedAtDesc(userId, PageRequest.of(0, limit));

        List<Map<String, Object>> history = new ArrayList<>();
        for (HistoryRecord record : records) {
            try {
                Map<String, Object> snapshot = objectMapper.readValue(
                        record.getSnapshot(), Map.class);
                history.add(snapshot);
            } catch (Exception e) {
                log.warn("解析历史记录失败: {}", record.getId(), e);
            }
        }
        return history;
    }

    /**
     * 保存方案书快照到历史记录
     */
    public void saveSnapshot(String projectId, String userId) {
        Proposal proposal = proposalRepository.findByProjectId(projectId)
                .orElse(null);
        if (proposal == null) return;

        List<ProposalStep> steps = stepRepository.findByProposalId(proposal.getId());

        HistoryRecord record = new HistoryRecord();
        record.setUserId(userId);
        record.setProject(proposal.getProject());
        record.setProjectName(proposal.getProject().getName());
        record.setProjectLevel(proposal.getProject().getLevel());
        try {
            Map<String, Object> snapshot = new HashMap<>();
            snapshot.put("proposal", proposal);
            snapshot.put("steps", steps);
            record.setSnapshot(objectMapper.writeValueAsString(snapshot));
        } catch (Exception e) {
            log.error("序列化历史快照失败", e);
            record.setSnapshot("{}");
        }
        record.setCreatedAt(LocalDateTime.now());
        historyRepository.save(record);
    }
}
