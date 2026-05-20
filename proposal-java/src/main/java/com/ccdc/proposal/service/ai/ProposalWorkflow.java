package com.ccdc.proposal.service.ai;

import com.ccdc.proposal.exception.BusinessException;
import com.ccdc.proposal.repository.ProposalRepository;
import com.ccdc.proposal.repository.ProposalStepRepository;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * [MVP] AI填写流程控制
 * 负责管理5步确认流程的状态流转
 */
@Component
@Slf4j
public class ProposalWorkflow {

    @Resource
    private ProposalRepository proposalRepository;

    @Resource
    private ProposalStepRepository stepRepository;

    /**
     * 验证步骤是否可以执行
     * 步骤必须按顺序执行：步骤1完成才能开始步骤2，以此类推
     */
    public void validateStepSequence(Long proposalId, int step) {
        if (step < 1 || step > 5) {
            throw new BusinessException("无效步骤: " + step);
        }
        // [MVP] 基本校验：步骤必须在1-5范围内
        // [V2] 严格校验：前序步骤必须已完成
    }

    /**
     * 获取下一步骤
     */
    public int getNextStep(int currentStep) {
        return Math.min(currentStep + 1, 5);
    }

    /**
     * 判断流程是否全部完成
     */
    public boolean isWorkflowComplete(int currentStep) {
        return currentStep >= 5;
    }
}
