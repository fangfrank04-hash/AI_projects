package com.ccdc.proposal.service;

import com.ccdc.proposal.entity.OperationLog;
import com.ccdc.proposal.repository.OperationLogRepository;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

@Service
@Slf4j
public class OperationLogService {

    @Resource
    private OperationLogRepository operationLogRepository;

    public void log(String projectId, String userId, String operation, String details) {
        OperationLog logEntry = new OperationLog();
        logEntry.setProjectId(projectId);
        logEntry.setUserId(userId);
        logEntry.setOperation(operation);
        logEntry.setDetails(details);
        logEntry.setCreatedAt(LocalDateTime.now());
        operationLogRepository.save(logEntry);
        log.info("操作日志: 项目={}, 用户={}, 操作={}", projectId, userId, operation);
    }
}
