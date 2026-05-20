package com.ccdc.proposal.service;

import com.ccdc.proposal.dto.ProposalDTO;
import com.ccdc.proposal.dto.ResourceInput;
import com.ccdc.proposal.dto.request.ChatRequest;
import com.ccdc.proposal.dto.request.CheckRequest;
import com.ccdc.proposal.dto.response.ChatResponse;
import com.ccdc.proposal.dto.response.CheckResponse;
import com.ccdc.proposal.dto.response.StepConfirmResult;
import com.ccdc.proposal.dto.response.StepDataResponse;
import com.ccdc.proposal.entity.*;
import com.ccdc.proposal.exception.BusinessException;
import com.ccdc.proposal.repository.*;
import com.ccdc.proposal.service.ai.AIClientService;
import com.ccdc.proposal.service.ai.PromptBuilder;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

@Service
@Slf4j
public class ProposalService {

    @Resource
    private ProposalRepository proposalRepository;

    @Resource
    private ProposalStepRepository stepRepository;

    @Resource
    private ProjectRepository projectRepository;

    @Resource
    private AIClientService aiClientService;

    @Resource
    private PromptBuilder promptBuilder;

    @Resource
    private HistoryService historyService;

    @Resource
    private OperationLogService operationLogService;

    @Resource
    private ObjectMapper objectMapper;

    public ProposalDTO getProposal(String projectId) {
        Proposal proposal = proposalRepository.findByProjectId(projectId)
                .orElseThrow(() -> new BusinessException("方案书不存在"));

        List<ProposalStep> steps = stepRepository.findByProposalId(proposal.getId());
        return convertToDTO(proposal, steps);
    }

    /**
     * AI生成指定步骤
     */
    public StepDataResponse generateStep(String projectId, int step, Map<String, Object> params) {
        log.info("开始AI生成步骤{}，项目: {}", step, projectId);

        return switch (step) {
            case 1 -> generateTeamStep(projectId);
            case 2 -> generateControlStep(projectId);
            case 3 -> generateScheduleStep(projectId, params);
            case 4 -> generateResourceStep(projectId, params);
            case 5 -> generateQualityStep(projectId);
            default -> throw new BusinessException("无效步骤: " + step);
        };
    }

    private StepDataResponse generateTeamStep(String projectId) {
        Map<String, Object> request = promptBuilder.buildTeamRequest(projectId);
        Map response = aiClientService.generateTeamResponsibilities(request).block();
        saveStepDraft(projectId, 1, "项目团队职责", response.get("content"));
        String sessionId = response.get("session_id") != null
                ? response.get("session_id").toString() : null;
        return new StepDataResponse(1, response.get("content"), sessionId);
    }

    private StepDataResponse generateControlStep(String projectId) {
        Map<String, Object> request = promptBuilder.buildControlRequest(projectId);
        Map response = aiClientService.generateControlPlan(request).block();
        saveStepDraft(projectId, 2, "管控方案", response.get("content"));
        String sessionId = response.get("session_id") != null
                ? response.get("session_id").toString() : null;
        return new StepDataResponse(2, response.get("content"), sessionId);
    }

    private StepDataResponse generateScheduleStep(String projectId, Map<String, Object> params) {
        String approveDate = params.getOrDefault("approveDate", "2026-06-01").toString();
        String projectCycle = params.getOrDefault("projectCycle", "90天").toString();
        Map<String, Object> request = promptBuilder.buildScheduleRequest(projectId, approveDate, projectCycle);
        Map response = aiClientService.generateSchedule(request).block();
        saveStepDraft(projectId, 3, "项目进度计划", response.get("content"));
        String sessionId = response.get("session_id") != null
                ? response.get("session_id").toString() : null;
        return new StepDataResponse(3, response.get("content"), sessionId);
    }

    private StepDataResponse generateResourceStep(String projectId, Map<String, Object> params) {
        ResourceInput input = objectMapper.convertValue(params, ResourceInput.class);
        Map<String, Object> request = promptBuilder.buildResourceRequest(projectId, input);
        Map response = aiClientService.generateResourcePlan(request).block();
        saveStepDraft(projectId, 4, "项目资源计划", response.get("content"));
        String sessionId = response.get("session_id") != null
                ? response.get("session_id").toString() : null;
        return new StepDataResponse(4, response.get("content"), sessionId);
    }

    private StepDataResponse generateQualityStep(String projectId) {
        Map<String, Object> request = promptBuilder.buildQualityRequest(projectId);
        Map response = aiClientService.generateQualityPlan(request).block();
        saveStepDraft(projectId, 5, "质量保证计划", response.get("content"));
        String sessionId = response.get("session_id") != null
                ? response.get("session_id").toString() : null;
        return new StepDataResponse(5, response.get("content"), sessionId);
    }

    /**
     * [MVP] AI对话（修复 P0-6 之一）
     */
    public ChatResponse chat(String projectId, ChatRequest request) {
        log.info("AI对话，项目: {}, 步骤: {}", projectId, request.getCurrentStep());
        return aiClientService.chat(request).block();
    }

    /**
     * [MVP] 方案书检查（修复 P0-6 之一）
     * Python MVP 暂未实现 /ai/check，此方法组装数据后调用
     */
    public CheckResponse checkProposal(String projectId) {
        log.info("方案书检查，项目: {}", projectId);
        Proposal proposal = proposalRepository.findByProjectId(projectId)
                .orElseThrow(() -> new BusinessException("方案书不存在"));

        List<ProposalStep> steps = stepRepository.findByProposalId(proposal.getId());
        Map<String, Object> proposalData = new HashMap<>();
        proposalData.put("projectId", projectId);
        proposalData.put("currentStep", proposal.getCurrentStep());
        proposalData.put("completedSteps", proposal.getCompletedSteps());
        proposalData.put("steps", steps.stream().map(s -> {
            Map<String, Object> stepMap = new HashMap<>();
            stepMap.put("stepNumber", s.getStepNumber());
            stepMap.put("stepName", s.getStepName());
            stepMap.put("status", s.getStatus());
            stepMap.put("data", s.getData());
            return stepMap;
        }).toList());

        return aiClientService.checkProposal(proposalData)
                .onErrorReturn(new CheckResponse(false,
                        List.of(new CheckResponse.CheckItem("AI服务", "fail", "检查服务暂时不可用，请稍后重试"))))
                .block();
    }

    private void saveStepDraft(String projectId, int stepNumber, String stepName, Object data) {
        try {
            Proposal proposal = proposalRepository.findByProjectId(projectId)
                    .orElseGet(() -> createNewProposal(projectId));

            ProposalStep step = stepRepository
                    .findByProposalIdAndStepNumber(proposal.getId(), stepNumber)
                    .orElse(new ProposalStep());

            step.setProposal(proposal);
            step.setStepNumber(stepNumber);
            step.setStepName(stepName);
            if (data instanceof Map) {
                @SuppressWarnings("unchecked")
                Map<String, Object> dataMap = (Map<String, Object>) data;
                step.setData(dataMap);
            }
            step.setStatus("草稿");

            stepRepository.save(step);

            proposal.setCurrentStep(stepNumber);
            proposalRepository.save(proposal);

        } catch (Exception e) {
            log.error("保存步骤草稿失败", e);
            throw new BusinessException("保存草稿失败");
        }
    }

    private Proposal createNewProposal(String projectId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        Proposal proposal = new Proposal();
        proposal.setProject(project);
        proposal.setCurrentStep(1);
        proposal.setCompletedSteps("[]");
        return proposalRepository.save(proposal);
    }

    /**
     * 确认步骤并回填
     */
    @Transactional
    public StepConfirmResult confirmStep(String projectId, int step, Object data, String userId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException("项目不存在"));
        if (!project.getPmName().equals(userId)) {
            throw new BusinessException("只有项目经理可以确认方案书");
        }

        Proposal proposal = proposalRepository.findByProjectId(projectId)
                .orElseThrow(() -> new BusinessException("方案书不存在"));

        ProposalStep stepEntity = stepRepository
                .findByProposalIdAndStepNumber(proposal.getId(), step)
                .orElseThrow(() -> new BusinessException("步骤数据不存在"));

        if (data instanceof Map) {
            @SuppressWarnings("unchecked")
            Map<String, Object> dataMap = (Map<String, Object>) data;
            stepEntity.setData(dataMap);
        }
        stepEntity.setStatus("已确认");
        stepRepository.save(stepEntity);

        List<Integer> completed = parseCompletedSteps(proposal.getCompletedSteps());
        if (!completed.contains(step)) {
            completed.add(step);
        }
        proposal.setCompletedSteps(completed.toString());
        proposal.setCurrentStep(step + 1 > 5 ? 5 : step + 1);
        proposalRepository.save(proposal);

        operationLogService.log(projectId, userId, "确认步骤" + step, null);

        return new StepConfirmResult(true, "步骤" + step + "已确认", proposal.getCurrentStep(), step < 5);
    }

    @Transactional
    public void confirmProposal(String projectId, String userId) {
        Proposal proposal = proposalRepository.findByProjectId(projectId)
                .orElseThrow(() -> new BusinessException("方案书不存在"));

        List<Integer> completed = parseCompletedSteps(proposal.getCompletedSteps());
        if (completed.size() < 5) {
            throw new BusinessException("还有未完成的步骤");
        }

        proposal.setStatus("已确认");
        proposal.setConfirmedBy(userId);
        proposal.setConfirmedAt(LocalDateTime.now());
        proposalRepository.save(proposal);

        historyService.saveSnapshot(projectId, userId);
        operationLogService.log(projectId, userId, "确认方案书", null);
    }

    private List<Integer> parseCompletedSteps(String completedSteps) {
        try {
            if (completedSteps == null || completedSteps.isEmpty()) return new ArrayList<>();
            String cleaned = completedSteps.replace("[", "").replace("]", "").replace(" ", "");
            if (cleaned.isEmpty()) return new ArrayList<>();
            return Arrays.stream(cleaned.split(","))
                    .map(Integer::parseInt)
                    .collect(ArrayList::new, ArrayList::add, ArrayList::addAll);
        } catch (Exception e) {
            return new ArrayList<>();
        }
    }

    private ProposalDTO convertToDTO(Proposal proposal, List<ProposalStep> steps) {
        ProposalDTO dto = new ProposalDTO();
        dto.setId(proposal.getId());
        dto.setProjectId(proposal.getProject().getId());
        dto.setCurrentStep(proposal.getCurrentStep());
        dto.setCompletedSteps(proposal.getCompletedSteps());
        dto.setStatus(proposal.getStatus());
        dto.setConfirmedBy(proposal.getConfirmedBy());
        dto.setSteps(steps);
        return dto;
    }
}
